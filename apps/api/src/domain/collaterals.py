"""Motor de Valuación de Garantías, Cálculo de LTV y Provisiones Netas (SPEC-11).

Implementa la formulación matemática determinística bajo Arquitectura Hexagonal Pura
para evaluar segundas fuentes de pago, castigos de liquidez normativos (Haircuts),
ratios Loan-to-Value (LTV), Exposición Neta (EAD) y deducción de provisiones contables.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
import uuid

from pydantic import BaseModel, Field


class CollateralType(StrEnum):
    """Tipos de garantías y colaterales reconocidos normativamente."""

    CDAT_DEPOSIT = "CDAT_DEPOSIT"  # Depósito a plazo pignorado en custodia directa
    FNG_GUARANTEE = "FNG_GUARANTEE"  # Garantía institucional soberana (FNG / Fogacoop)
    REAL_ESTATE_URBAN = "REAL_ESTATE_URBAN"  # Hipoteca sobre inmueble urbano comercial/residencial
    REAL_ESTATE_RURAL = "REAL_ESTATE_RURAL"  # Hipoteca sobre inmueble rural, finca o terreno
    VEHICLE_COMMERCIAL = "VEHICLE_COMMERCIAL"  # Prenda sobre flota vehicular o transporte
    INDUSTRIAL_MACHINERY = "INDUSTRIAL_MACHINERY"  # Prenda sobre maquinaria y equipo industrial
    PERSONAL_GUARANTEE = "PERSONAL_GUARANTEE"  # Pagaré con aval solidario o fianza personal


# Matriz oficial de haircuts y admisibilidad regulatoria para deducción de provisión
COLLATERAL_RULES: dict[CollateralType, tuple[float, bool, str]] = {
    CollateralType.CDAT_DEPOSIT: (5.0, True, "Depósito a Plazo / CDAT Pignorado (Líquido)"),
    CollateralType.FNG_GUARANTEE: (10.0, True, "Garantía Institucional FNG (Soberana)"),
    CollateralType.REAL_ESTATE_URBAN: (20.0, True, "Hipoteca Inmueble Urbano (Comercial / Vivienda)"),
    CollateralType.REAL_ESTATE_RURAL: (35.0, True, "Hipoteca Inmueble Rural / Terreno / Bodega"),
    CollateralType.VEHICLE_COMMERCIAL: (30.0, True, "Prenda Vehicular / Flota Comercial"),
    CollateralType.INDUSTRIAL_MACHINERY: (40.0, True, "Prenda Maquinaria y Equipo Industrial"),
    CollateralType.PERSONAL_GUARANTEE: (50.0, False, "Pagaré con Aval Solidario (No Admisible Contable)"),
}


class CollateralItemInput(BaseModel):
    """Payload de entrada para registrar o actualizar un colateral en el expediente."""

    collateral_type: CollateralType
    description: str = Field(min_length=3, description="Descripción pericial y física del bien")
    commercial_appraisal_usd: float = Field(
        gt=0.0, description="Valor del avalúo comercial pericial en USD"
    )


class CollateralItem(BaseModel):
    """Modelo de dominio de un colateral individual con su valuación y haircut."""

    id: str = Field(description="Identificador único del colateral")
    collateral_type: CollateralType
    description: str
    commercial_appraisal_usd: float
    haircut_percentage: float = Field(description="Porcentaje de castigo por liquidez aplicado")
    admissible_value_usd: float = Field(description="Valor computable tras castigo regulatorio")
    is_statutory_admissible: bool = Field(
        description="True si la norma de la Superintendencia permite deducir provisión con este bien"
    )


class UnderwritingCollateralAnalysis(BaseModel):
    """Análisis consolidado de garantías, ratios LTV y provisión neta (SPEC-11)."""

    application_id: str
    evaluated_at: str
    items: list[CollateralItem] = Field(default_factory=list)
    total_appraisal_usd: float = Field(description="Suma total de avalúos comerciales brutos en USD")
    total_admissible_usd: float = Field(description="Suma de colaterales admisibles tras haircut en USD")
    requested_amount_usd: float = Field(description="Capital solicitado del crédito en USD")
    ltv_percentage: float | None = Field(
        description="Ratio Loan-to-Value (Monto / Avalúo) o None si no hay garantías"
    )
    ltv_status: str = Field(
        description="Estado del LTV: HEALTHY (<=70%), WARNING (70-85%), CRITICAL (>85%), UNSECURED"
    )
    collateral_coverage_ratio: float = Field(
        description="CCR (%) = (Total Admisible / Monto Solicitado) * 100"
    )
    net_exposure_at_default_usd: float = Field(
        description="EAD neta residual expuesta a pérdida tras descontar colaterales"
    )
    rating_category: str = Field(description="Calificación oficial obtenida en SPEC-09 (A a E)")
    provision_rate_percentage: float = Field(description="Tasa de provisión patrimonial normativa (%)")
    gross_provision_usd: float = Field(description="Provisión patrimonial bruta sin colaterales (USD)")
    net_provision_usd: float = Field(description="Provisión patrimonial neta requerida tras mitigantes (USD)")
    capital_relief_usd: float = Field(
        description="Alivio patrimonial en USD liberado para la cooperativa (Bruta - Neta)"
    )
    is_fully_secured: bool = Field(
        description="True si el valor admisible cubre el 100% del monto solicitado"
    )
    recommendation_notes: str = Field(
        description="Dictamen de idoneidad de garantías para el oficial de crédito"
    )


class CollateralValuationEngine:
    """Motor determinístico de cálculo de garantías y deducción de provisiones."""

    @classmethod
    def valuate_item(
        cls,
        item_input: CollateralItemInput,
        item_id: str | None = None,
    ) -> CollateralItem:
        """Calcula el valor admisible individual aplicando el haircut normativo."""
        rule = COLLATERAL_RULES.get(
            item_input.collateral_type,
            (40.0, True, "Colateral Estándar"),
        )
        haircut_pct, is_admissible, _ = rule

        if is_admissible:
            admissible_val = round(
                item_input.commercial_appraisal_usd * (1.0 - (haircut_pct / 100.0)),
                2,
            )
        else:
            # Si no es admisible por la Superintendencia (ej. aval personal),
            # no puede deducir exposición contable
            admissible_val = 0.0

        return CollateralItem(
            id=item_id or f"COL-{uuid.uuid4().hex[:8].upper()}",
            collateral_type=item_input.collateral_type,
            description=item_input.description,
            commercial_appraisal_usd=round(item_input.commercial_appraisal_usd, 2),
            haircut_percentage=haircut_pct,
            admissible_value_usd=admissible_val,
            is_statutory_admissible=is_admissible,
        )

    @classmethod
    def evaluate(
        cls,
        application_id: str,
        requested_amount_usd: float,
        rating_category: str,
        provision_rate_percentage: float,
        gross_provision_usd: float,
        items_input: list[CollateralItemInput],
    ) -> UnderwritingCollateralAnalysis:
        """Realiza el balance consolidado de colaterales, LTV y provisión neta."""
        valuated_items = [cls.valuate_item(item) for item in items_input]

        total_appraisal = round(
            sum(item.commercial_appraisal_usd for item in valuated_items),
            2,
        )
        total_admissible = round(
            sum(item.admissible_value_usd for item in valuated_items if item.is_statutory_admissible),
            2,
        )

        # 1. Ratio Loan-to-Value (LTV)
        if total_appraisal > 0:
            ltv_pct = round((requested_amount_usd / total_appraisal) * 100.0, 2)
            if ltv_pct <= 70.0:
                ltv_status = "HEALTHY"
            elif ltv_pct <= 85.0:
                ltv_status = "WARNING"
            else:
                ltv_status = "CRITICAL"
        else:
            ltv_pct = None
            ltv_status = "UNSECURED"

        # 2. Ratio de Cobertura de Garantía Admisible (CCR)
        if requested_amount_usd > 0:
            ccr_pct = round((total_admissible / requested_amount_usd) * 100.0, 2)
        else:
            ccr_pct = 100.0

        # 3. Exposición Neta al Incumplimiento (EAD Neta)
        net_ead = round(max(0.0, requested_amount_usd - total_admissible), 2)
        is_fully_secured = total_admissible >= requested_amount_usd

        # 4. Provisión Neta y Alivio Patrimonial
        net_provision = round(net_ead * (provision_rate_percentage / 100.0), 2)
        capital_relief = round(max(0.0, gross_provision_usd - net_provision), 2)

        # 5. Dictamen cualitativo estructurado
        if ltv_status == "UNSECURED":
            notes = (
                f"Crédito no garantizado (A Sola Firma). Provisión bruta del {provision_rate_percentage}% "
                f"(${gross_provision_usd:,.2f} USD) exigida íntegramente sin deducción de garantías."
            )
        elif is_fully_secured:
            notes = (
                f"Operación Plenamente Garantizada: Valor admisible ponderado (${total_admissible:,.2f} USD) "
                f"cubre el 100% del capital solicitado. Provisión neta reducida a $0.00 USD, liberando "
                f"${capital_relief:,.2f} USD de capital patrimonial."
            )
        else:
            notes = (
                f"Cobertura Parcial (CCR: {ccr_pct:.1f}%, LTV: {ltv_pct:.1f}% [{ltv_status}]). "
                f"Colaterales admisibles por ${total_admissible:,.2f} USD reducen la exposición a ${net_ead:,.2f} USD. "
                f"Provisión neta: ${net_provision:,.2f} USD (Ahorro de Capital: ${capital_relief:,.2f} USD)."
            )

        return UnderwritingCollateralAnalysis(
            application_id=application_id,
            evaluated_at=datetime.now(UTC).isoformat(),
            items=valuated_items,
            total_appraisal_usd=total_appraisal,
            total_admissible_usd=total_admissible,
            requested_amount_usd=requested_amount_usd,
            ltv_percentage=ltv_pct,
            ltv_status=ltv_status,
            collateral_coverage_ratio=ccr_pct,
            net_exposure_at_default_usd=net_ead,
            rating_category=rating_category,
            provision_rate_percentage=provision_rate_percentage,
            gross_provision_usd=gross_provision_usd,
            net_provision_usd=net_provision,
            capital_relief_usd=capital_relief,
            is_fully_secured=is_fully_secured,
            recommendation_notes=notes,
        )
