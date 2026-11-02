"""Motor de Compuerta de Desembolso, Verificación de Covenants, Liquidación Cooperativa y Pagaré Digital (SPEC-14).

Implementa la lógica determinística de arquitectura hexagonal pura para:
1. Validar el cumplimiento estricto de covenants precedentes antes del desembolso.
2. Calcular la liquidación cooperativa con deducciones estatutarias (Aportes 2%, Fondo $25, Seguro).
3. Generar el título valor Pagaré Desmaterializado con numeración consecutiva.
4. Emitir la Orden de Giro ACH / Abono en cuenta y cambiar el estado del crédito a DISBURSED.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, Field


class CovenantFulfillmentStatus(StrEnum):
    """Estado de verificación y cumplimiento de un covenant o condición precedente."""

    PENDING = "PENDING"  # Pendiente de subsanación o entrega documental
    FULFILLED = "FULFILLED"  # Verificado y aceptado por el oficial de cartera
    WAIVED = "WAIVED"  # Exonerado formalmente por el Consejo de Administración


class CovenantFulfillmentRecord(BaseModel):
    """Registro de trazabilidad y verificación de un covenant precedente."""

    code: str = Field(description="Identificador mnemotécnico del covenant")
    description: str = Field(min_length=5, description="Obligación pactada")
    covenant_type: str = Field(
        default="GARANTIA",
        description="Tipo de condición: GARANTIA, FINANCIERO, DOCUMENTAL",
    )
    due_days: int = Field(default=30, gt=0, description="Días hábiles para entrega")
    status: CovenantFulfillmentStatus = Field(
        default=CovenantFulfillmentStatus.PENDING,
        description="Estado actual del cumplimiento",
    )
    verified_by: str | None = Field(
        default=None, description="Identificador del oficial que verificó"
    )
    verified_at: str | None = Field(
        default=None, description="Timestamp ISO-8601 de la verificación"
    )
    evidence_notes: str | None = Field(
        default=None, description="Notas de auditoría o radicado de soporte"
    )


class DisbursementDeductions(BaseModel):
    """Liquidación estatutaria y deducciones cooperativas al monto aprobado."""

    gross_amount_usd: float = Field(gt=0, description="Monto bruto aprobado en comité")
    social_contributions_pct: float = Field(
        default=2.0, description="Porcentaje de retención estatutaria en aportes (2.0%)"
    )
    social_contributions_usd: float = Field(
        description="Monto deducido para aportes sociales cooperativos"
    )
    solidarity_fund_usd: float = Field(
        default=25.0, description="Cuota fija reglamentaria Fondo de Solidaridad y Auxilio Mutual"
    )
    insurance_first_month_usd: float = Field(
        description="Prima de seguro de cartera del primer mes"
    )
    total_deductions_usd: float = Field(
        description="Suma total de deducciones cooperativas aplicadas"
    )
    net_disbursement_usd: float = Field(
        description="Monto neto final a transferir al asociado"
    )


class PromissoryNote(BaseModel):
    """Pagaré Digital Desmaterializado expedido conforme al régimen cambiario."""

    note_number: str = Field(description="Folio consecutivo único (PAGARE-2026-XXXX)")
    debtor_name: str = Field(description="Nombre o razón social del titular deudor")
    debtor_id: str = Field(description="Cédula o NIT del deudor")
    principal_amount_usd: float = Field(description="Monto capital del pagaré (Bruto)")
    applied_tea: float = Field(description="Tasa Efectiva Anual pactada")
    term_months: int = Field(description="Plazo convenido en meses")
    issued_at: str = Field(description="Fecha y hora de emisión ISO-8601")
    maturity_date: str = Field(description="Fecha límite de vencimiento total del crédito")
    acceleration_clause_accepted: bool = Field(
        default=True,
        description="Aceptación irrevocable de la cláusula de aceleración por mora",
    )


class DisbursementOrder(BaseModel):
    """Orden oficial de giro bancario y formalización del desembolso."""

    order_id: str = Field(description="Consecutivo único de giro (GIRO-2026-XXXX)")
    application_id: str = Field(description="Identificador del expediente crediticio")
    liquidation: DisbursementDeductions = Field(description="Liquidación neta detallada")
    promissory_note: PromissoryNote = Field(description="Pagaré digital suscrito")
    destination_bank: str = Field(description="Entidad financiera receptora")
    destination_account_number: str = Field(description="Número de cuenta de destino")
    account_type: str = Field(default="AHORROS", description="Tipo de cuenta: AHORROS o CORRIENTE")
    covenants: list[CovenantFulfillmentRecord] = Field(
        default_factory=list, description="Covenants verificados asociados al crédito"
    )
    status: str = Field(default="EXECUTED", description="Estado de la orden de giro")
    disbursed_at: str = Field(description="Timestamp ISO-8601 del giro")


class DisbursementGateStatus(BaseModel):
    """Estado y evaluación de la compuerta de desembolso (Disbursement Gate)."""

    application_id: str
    is_eligible: bool = Field(description="True si el desembolso puede ser ejecutado de inmediato")
    resolution_status: str = Field(description="Estado resolutivo del acta de comité")
    pending_covenants_count: int = Field(description="Número de covenants pendientes")
    covenants: list[CovenantFulfillmentRecord] = Field(default_factory=list)
    liquidation_preview: DisbursementDeductions = Field(description="Liquidación proyectada")
    disbursement_order: DisbursementOrder | None = Field(
        default=None, description="Orden de giro si ya fue desembolsado"
    )
    blocking_reasons: list[str] = Field(default_factory=list)


class DisbursementEngine:
    """Motor determinístico de liquidación cooperativa y compuerta de desembolso."""

    DEFAULT_INSURANCE_MONTHLY_RATE: float = 0.0012  # 0.12% mensual (1.44% anual de SPEC-12)
    SOCIAL_CONTRIBUTION_PCT: float = 2.0  # 2.0% del capital
    SOLIDARITY_FUND_FIXED_USD: float = 25.0  # Cuota fija reglamentaria

    @classmethod
    def calculate_liquidation(
        cls,
        gross_amount_usd: float,
        monthly_insurance_rate: float | None = None,
    ) -> DisbursementDeductions:
        """Calcula la liquidación cooperativa descontando aportes, auxilio y seguro."""
        gross = round(float(gross_amount_usd), 2)
        ins_rate = (
            monthly_insurance_rate
            if monthly_insurance_rate is not None and monthly_insurance_rate > 0
            else cls.DEFAULT_INSURANCE_MONTHLY_RATE
        )

        social_contrib = round(gross * (cls.SOCIAL_CONTRIBUTION_PCT / 100.0), 2)
        solidarity = cls.SOLIDARITY_FUND_FIXED_USD
        insurance_m1 = round(gross * ins_rate, 2)
        total_deductions = round(social_contrib + solidarity + insurance_m1, 2)
        net_amount = round(gross - total_deductions, 2)

        return DisbursementDeductions(
            gross_amount_usd=gross,
            social_contributions_pct=cls.SOCIAL_CONTRIBUTION_PCT,
            social_contributions_usd=social_contrib,
            solidarity_fund_usd=solidarity,
            insurance_first_month_usd=insurance_m1,
            total_deductions_usd=total_deductions,
            net_disbursement_usd=net_amount,
        )

    @classmethod
    def create_promissory_note(
        cls,
        debtor_name: str,
        debtor_id: str,
        principal_amount_usd: float,
        applied_tea: float,
        term_months: int,
        note_number: str | None = None,
    ) -> PromissoryNote:
        """Emite el pagaré digital desmaterializado con cláusula aceleratoria."""
        now = datetime.now(UTC)
        folio = note_number or f"PAGARE-2026-{uuid.uuid4().hex[:6].upper()}"
        maturity = now + timedelta(days=term_months * 30)

        return PromissoryNote(
            note_number=folio,
            debtor_name=debtor_name,
            debtor_id=debtor_id,
            principal_amount_usd=round(principal_amount_usd, 2),
            applied_tea=round(applied_tea, 4),
            term_months=term_months,
            issued_at=now.isoformat(),
            maturity_date=maturity.strftime("%Y-%m-%d"),
            acceleration_clause_accepted=True,
        )

    @classmethod
    def evaluate_gate(
        cls,
        resolution_status: str,
        covenants: list[CovenantFulfillmentRecord],
        is_already_disbursed: bool = False,
    ) -> tuple[bool, list[str]]:
        """Determina la elegibilidad para desembolso evaluando estado y condiciones."""
        reasons: list[str] = []

        if is_already_disbursed:
            reasons.append("El crédito ya fue desembolsado formalmente.")
            return False, reasons

        valid_approval_statuses = {
            "APPROVED_BY_COMMITTEE",
            "APPROVED_WITH_CONDITIONS",
            "APPROVED",
        }
        if resolution_status not in valid_approval_statuses:
            reasons.append(
                f"El crédito no cuenta con aprobación formal del comité (Estado actual: {resolution_status})."
            )

        pending_covenants = [c for c in covenants if c.status == CovenantFulfillmentStatus.PENDING]
        if pending_covenants:
            reasons.append(
                f"Existen {len(pending_covenants)} condición(es) precedente(s) pendiente(s) de verificación."
            )

        is_eligible = len(reasons) == 0
        return is_eligible, reasons

    @classmethod
    def create_disbursement_order(
        cls,
        application_id: str,
        liquidation: DisbursementDeductions,
        promissory_note: PromissoryNote,
        destination_bank: str,
        destination_account_number: str,
        account_type: str = "AHORROS",
        covenants: list[CovenantFulfillmentRecord] | None = None,
        order_id: str | None = None,
    ) -> DisbursementOrder:
        """Crea la orden formal de giro ACH / abono en cuenta."""
        now = datetime.now(UTC)
        giro_id = order_id or f"GIRO-2026-{uuid.uuid4().hex[:6].upper()}"

        return DisbursementOrder(
            order_id=giro_id,
            application_id=application_id,
            liquidation=liquidation,
            promissory_note=promissory_note,
            destination_bank=destination_bank.strip(),
            destination_account_number=destination_account_number.strip(),
            account_type=account_type.upper().strip(),
            covenants=covenants or [],
            status="EXECUTED",
            disbursed_at=now.isoformat(),
        )
