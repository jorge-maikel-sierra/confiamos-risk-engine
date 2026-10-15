"""Motor de Scoring Crediticio Regulatorio y Provisiones Contables (SPEC-09).

Implementa la matriz de evaluación multicriterio, la asignación de categorías
regulatorias (A a E) y el cálculo de la provisión patrimonial estimada en USD
según directrices de la supervisión financiera para cooperativas de crédito.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from src.domain.metrics import FinancialHealthMetrics


class RiskRatingCategory(StrEnum):
    """Categorías regulatorias oficiales según estándares de supervisión financiera."""

    A = "A"  # Riesgo Normal (Pérdida esperada mínima)
    B = "B"  # Riesgo Aceptable con Potencial de Deterioro
    C = "C"  # Riesgo Apreciable / Deficiente
    D = "D"  # Riesgo Significativo / Difícil Cobro
    E = "E"  # Riesgo de Pérdida / Irrecuperable


class ScorecardBreakdown(BaseModel):
    """Desglose de puntuación por componente individual (0 a 100 puntos)."""

    dscr_score: float = Field(ge=0.0, le=100.0, description="Puntaje de cobertura de deuda (35%)")
    liquidity_score: float = Field(
        ge=0.0, le=100.0, description="Puntaje de liquidez y runway (30%)"
    )
    concentration_score: float = Field(
        ge=0.0, le=100.0, description="Puntaje de concentración y extractos (20%)"
    )
    ai_alignment_score: float = Field(
        ge=0.0, le=100.0, description="Puntaje de alineación cualitativa IA (15%)"
    )


class CreditScorecardResult(BaseModel):
    """Resultado oficial del scoring crediticio y cálculo de provisión."""

    total_score: float = Field(ge=0.0, le=100.0, description="Puntaje total ponderado (0-100)")
    rating_category: RiskRatingCategory = Field(
        description="Calificación regulatoria oficial (A a E)"
    )
    category_title: str = Field(description="Denominación formal de la categoría")
    provision_percentage: float = Field(description="Tasa de provisión patrimonial requerida (%)")
    estimated_provision_usd: float = Field(
        description="Monto en USD de la reserva patrimonial requerida"
    )
    breakdown: ScorecardBreakdown = Field(description="Desglose numérico por componente")
    regulatory_justification: str = Field(
        description="Sustentación técnica para el comité de crédito"
    )


class RegulatoryScorecardEngine:
    """Motor de cálculo determinístico para scoring y provisiones regulatorias."""

    # Ponderaciones multicriterio oficiales
    WEIGHT_DSCR = 0.35
    WEIGHT_LIQUIDITY = 0.30
    WEIGHT_CONCENTRATION = 0.20
    WEIGHT_AI = 0.15

    # Bandas de corte y porcentajes de provisión normativa
    RATING_MATRIX = [
        (85.0, RiskRatingCategory.A, "Riesgo Normal", 1.0),
        (70.0, RiskRatingCategory.B, "Riesgo Aceptable con Potencial", 3.2),
        (55.0, RiskRatingCategory.C, "Riesgo Apreciable / Deficiente", 10.0),
        (40.0, RiskRatingCategory.D, "Riesgo Significativo / Difícil Cobro", 35.0),
        (0.0, RiskRatingCategory.E, "Riesgo de Pérdida / Irrecuperable", 100.0),
    ]

    @classmethod
    def calculate_dscr_score(cls, dscr: float | None, is_debt_free: bool) -> float:
        """Calcula el puntaje del componente DSCR (0 a 100 puntos)."""
        if is_debt_free or dscr is None:
            return 100.0

        if dscr >= 1.50:
            return 100.0
        elif dscr >= 1.30:
            return 80.0
        elif dscr >= 1.15:
            return 60.0
        elif dscr >= 1.00:
            return 40.0
        return 0.0

    @classmethod
    def calculate_liquidity_score(
        cls, current_ratio: float | None, runway_months: float | None
    ) -> float:
        """Calcula el puntaje del componente Liquidez y Runway (0 a 100 puntos)."""
        ratio = current_ratio if current_ratio is not None else 0.0

        # Si no hay quema de caja (runway infinito o None),
        # se evalúa según fortaleza de activos corrientes
        effective_runway = runway_months if runway_months is not None else 12.0

        if ratio >= 1.50 and effective_runway >= 6.0:
            return 100.0
        elif ratio >= 1.20 and effective_runway >= 3.0:
            return 80.0
        elif ratio >= 1.00:
            return 60.0
        return 20.0

    @classmethod
    def calculate_concentration_score(
        cls,
        top_client_percentage: float | None,
        negative_balance_days: int | None,
        anomaly_flags: list[str] | None,
    ) -> float:
        """Calcula el puntaje de concentración comercial y calidad de extractos bancarios."""
        client_pct = top_client_percentage if top_client_percentage is not None else 20.0
        overdraft_days = negative_balance_days if negative_balance_days is not None else 0
        anomalies = anomaly_flags or []

        # Puntaje base
        if client_pct <= 25.0 and overdraft_days == 0:
            base_score = 100.0
        elif client_pct <= 50.0 and overdraft_days <= 2:
            base_score = 70.0
        else:
            base_score = 30.0

        # Penalización por cada anomalía crítica (-15 pts c/u)
        penalty = len(anomalies) * 15.0
        return max(0.0, base_score - penalty)

    @classmethod
    def calculate_ai_score(cls, ai_recommendation: str | None) -> float:
        """Calcula el puntaje derivado del dictamen cualitativo emitido por Gemini AI."""
        if not ai_recommendation:
            return 50.0

        rec_upper = ai_recommendation.upper()
        if "APROBADO_CONDICIONADO" in rec_upper:
            return 60.0
        elif "APROBADO" in rec_upper:
            return 100.0
        elif "RECHAZADO" in rec_upper:
            return 0.0
        return 50.0

    @classmethod
    def evaluate(
        cls,
        metrics: FinancialHealthMetrics,
        top_client_percentage: float,
        negative_balance_days: int,
        ai_recommendation: str | None,
        requested_amount_usd: float,
    ) -> CreditScorecardResult:
        """Evalúa todas las dimensiones y devuelve el resultado integral de scoring y provisión."""
        dscr_val = metrics.dscr_result.dscr
        is_debt_free = metrics.dscr_result.is_debt_free
        s_dscr = cls.calculate_dscr_score(dscr_val, is_debt_free)
        s_liq = cls.calculate_liquidity_score(metrics.current_ratio, metrics.runway_months)
        s_conc = cls.calculate_concentration_score(
            top_client_percentage, negative_balance_days, metrics.anomaly_flags
        )
        s_ai = cls.calculate_ai_score(ai_recommendation)

        total_score = round(
            (s_dscr * cls.WEIGHT_DSCR)
            + (s_liq * cls.WEIGHT_LIQUIDITY)
            + (s_conc * cls.WEIGHT_CONCENTRATION)
            + (s_ai * cls.WEIGHT_AI),
            2,
        )

        # Determinar categoría y tasa de provisión
        category = RiskRatingCategory.E
        title = "Riesgo de Pérdida / Irrecuperable"
        provision_rate = 100.0

        for cutoff, cat, cat_title, prov_rate in cls.RATING_MATRIX:
            if total_score >= cutoff:
                category = cat
                title = cat_title
                provision_rate = prov_rate
                break

        estimated_provision_usd = round(requested_amount_usd * (provision_rate / 100.0), 2)

        justification = (
            f"Calificación oficial Categoría {category.value} ({title}) "
            f"con puntaje {total_score}/100. Provisión regulatoria asignada del {provision_rate}% ("
            f"${estimated_provision_usd:,.2f} USD sobre capital solicitado de "
            f"${requested_amount_usd:,.2f} USD)."
        )

        return CreditScorecardResult(
            total_score=total_score,
            rating_category=category,
            category_title=title,
            provision_percentage=provision_rate,
            estimated_provision_usd=estimated_provision_usd,
            breakdown=ScorecardBreakdown(
                dscr_score=s_dscr,
                liquidity_score=s_liq,
                concentration_score=s_conc,
                ai_alignment_score=s_ai,
            ),
            regulatory_justification=justification,
        )
