"""Motor de Pricing Ajustado al Riesgo (Risk-Based Pricing / RAROC) y Amortizaciones (SPEC-12).

Implementa la formulación matemática determinística bajo Arquitectura Hexagonal Pura
para descomponer la tasa de interés en sus componentes económicos (Fondeo, OPEX, Riesgo, Margen),
validar el tope legal de usura y generar planes de amortización (Francés y Alemán).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
import math

from pydantic import BaseModel, Field


class AmortizationSystem(StrEnum):
    """Sistemas de amortización financiera soportados."""

    FRENCH = "FRENCH"  # Cuota fija constante con interés decreciente y capital creciente
    GERMAN = "GERMAN"  # Amortización constante a capital con cuota decreciente


# Parámetros macroeconómicos y de política institucional por defecto
COST_OF_FUNDS_EA: float = 8.50  # Costo de fondeo CDAT/Ahorros (% E.A.)
OPEX_SPREAD_EA: float = 4.50  # Margen de intermediación y operación (% E.A.)
RAROC_TARGET_EA: float = 3.00  # Retorno objetivo sobre capital patrimonial (% E.A.)
DEFAULT_USURY_CAP_EA: float = 28.50  # Límite máximo legal de usura (% E.A.)
DEFAULT_MONTHLY_INSURANCE_RATE: float = 0.0012  # Seguro de vida / cartera (0.12% mensual s/saldo)

# Matriz de Probabilidad de Incumplimiento (PD) anual por categoría de riesgo (SPEC-09)
PD_BY_RATING: dict[str, float] = {
    "A": 1.5,
    "B": 4.0,
    "C": 12.0,
    "D": 28.0,
    "E": 65.0,
}

# Matriz de Severidad de Pérdida (LGD) según cobertura de garantías / LTV (SPEC-11)
LGD_BY_LTV_STATUS: dict[str, float] = {
    "HEALTHY": 20.0,  # LTV <= 70% o 100% garantizado con colaterales admisibles
    "WARNING": 35.0,  # LTV entre 70% y 85%
    "CRITICAL": 50.0,  # LTV > 85%
    "UNSECURED": 65.0,  # Sin garantías (A sola firma)
}


class PaymentPeriodQuota(BaseModel):
    """Detalle de una cuota mensual en la tabla de amortización."""

    period: int = Field(ge=1, description="Número de mes / periodo")
    beginning_balance: float = Field(ge=0.0, description="Saldo deudor inicial del periodo")
    principal_amortization: float = Field(ge=0.0, description="Abono a capital amortizado")
    interest_payment: float = Field(ge=0.0, description="Intereses remuneratorios del periodo")
    insurance_payment: float = Field(ge=0.0, description="Seguro de vida deudores / cartera")
    total_quota: float = Field(gt=0.0, description="Cuota total a pagar (Capital + Interés + Seguro)")
    ending_balance: float = Field(ge=0.0, description="Saldo insoluto final tras el pago")


class PricingProposal(BaseModel):
    """Propuesta de pricing financiero y cronograma de pagos ajustado al riesgo (SPEC-12)."""

    application_id: str
    calculated_at: str
    requested_amount_usd: float = Field(gt=0.0)
    term_months: int = Field(gt=0)
    amortization_system: AmortizationSystem
    rating_category: str
    ltv_status: str
    probability_of_default_pct: float
    loss_given_default_pct: float
    net_exposure_at_default_usd: float
    expected_loss_usd: float = Field(description="Pérdida esperada EL = PD * LGD * EAD_net")
    expected_loss_rate_ea: float = Field(description="Prima por riesgo en tasa (EL / Monto) * 100")
    cost_of_funds_ea: float
    opex_spread_ea: float
    raroc_target_ea: float
    uncapped_tea: float = Field(description="TEA requerida teórica sin tope de usura")
    applied_tea: float = Field(description="TEA final aprobada / aplicable al crédito")
    monthly_effective_rate_pct: float = Field(description="Tasa mensual equivalente (1+TEA)^(1/12) - 1")
    usury_cap_tea: float
    exceeds_usury_cap: bool = Field(description="True si la TEA teórica superó el límite legal de usura")
    usury_adjustment_delta: float = Field(
        description="Puntos porcentuales recortados por usura (Uncapped - Applied)"
    )
    first_month_quota_usd: float
    total_interest_usd: float
    total_insurance_usd: float
    total_cost_of_credit_usd: float
    recommendation_notes: str
    amortization_schedule: list[PaymentPeriodQuota] = Field(default_factory=list)


class RiskBasedPricingEngine:
    """Motor determinístico de cálculo de tasas ajustadas al riesgo y amortizaciones."""

    @classmethod
    def calculate_pricing(
        cls,
        application_id: str,
        requested_amount_usd: float,
        term_months: int,
        rating_category: str = "C",
        ltv_status: str = "UNSECURED",
        net_exposure_at_default_usd: float | None = None,
        amortization_system: AmortizationSystem = AmortizationSystem.FRENCH,
        cost_of_funds_ea: float = COST_OF_FUNDS_EA,
        opex_spread_ea: float = OPEX_SPREAD_EA,
        raroc_target_ea: float = RAROC_TARGET_EA,
        usury_cap_ea: float = DEFAULT_USURY_CAP_EA,
        insurance_rate_monthly: float = DEFAULT_MONTHLY_INSURANCE_RATE,
    ) -> PricingProposal:
        """Calcula la estructura de tasa, prima de riesgo y plan de amortización."""
        clean_rating = rating_category.upper().strip()
        clean_ltv = ltv_status.upper().strip()

        # 1. Parámetros de Riesgo Crediticio (PD y LGD)
        pd_pct = PD_BY_RATING.get(clean_rating, 12.0)
        lgd_pct = LGD_BY_LTV_STATUS.get(clean_ltv, 65.0)

        # Si no se pasó EAD neta, se asume el monto total solicitado
        ead_net = requested_amount_usd if net_exposure_at_default_usd is None else net_exposure_at_default_usd
        ead_net = max(0.0, ead_net)

        # 2. Pérdida Esperada (Expected Loss - EL)
        # EL = (PD / 100) * (LGD / 100) * EAD_net
        el_usd = round((pd_pct / 100.0) * (lgd_pct / 100.0) * ead_net, 2)
        if requested_amount_usd > 0:
            el_spread_pct = round((el_usd / requested_amount_usd) * 100.0, 2)
        else:
            el_spread_pct = 0.0

        # 3. Composición Aditiva de la Tasa Efectiva Anual (TEA)
        uncapped_tea = round(cost_of_funds_ea + opex_spread_ea + el_spread_pct + raroc_target_ea, 2)

        # 4. Control de Usura (Ajuste automático al tope legal con alerta visual)
        if uncapped_tea > usury_cap_ea:
            exceeds_usury = True
            applied_tea = round(usury_cap_ea, 2)
            usury_delta = round(uncapped_tea - usury_cap_ea, 2)
        else:
            exceeds_usury = False
            applied_tea = uncapped_tea
            usury_delta = 0.0

        # 5. Tasa Efectiva Mensual Equivalente: i_mes = (1 + TEA)^(1/12) - 1
        i_monthly = math.pow(1.0 + (applied_tea / 100.0), 1.0 / 12.0) - 1.0
        monthly_rate_pct = round(i_monthly * 100.0, 4)

        # 6. Generación de Tabla de Amortización Determinística
        schedule = cls.generate_amortization_schedule(
            principal=requested_amount_usd,
            term_months=term_months,
            monthly_rate=i_monthly,
            system=amortization_system,
            insurance_rate_monthly=insurance_rate_monthly,
        )

        total_interest = round(sum(q.interest_payment for q in schedule), 2)
        total_insurance = round(sum(q.insurance_payment for q in schedule), 2)
        total_cost = round(requested_amount_usd + total_interest + total_insurance, 2)
        first_quota = schedule[0].total_quota if schedule else 0.0

        # 7. Dictamen cualitativo y notas de pricing
        if exceeds_usury:
            notes = (
                f"ALERTA DE USURA: La TEA técnica requerida ({uncapped_tea:.2f}%) superó el límite legal "
                f"de usura ({usury_cap_ea:.2f}% E.A.). La tasa fue ajustada automáticamente al tope legal "
                f"(recorte de -{usury_delta:.2f}% E.A.). Se sugiere al oficial de crédito requerir garantías "
                f"admisibles adicionales para reducir la prima por pérdida esperada (EL actual: ${el_usd:,.2f} USD)."
            )
        else:
            notes = (
                f"Pricing Óptimo Aprobado: TEA de {applied_tea:.2f}% E.A. ({monthly_rate_pct:.2f}% mes vencido). "
                f"Cubre Fondeo ({cost_of_funds_ea:.1f}%), Operación ({opex_spread_ea:.1f}%), Pérdida Esperada "
                f"({el_spread_pct:.2f}% s/capital - EL: ${el_usd:,.2f} USD) y Margen RAROC ({raroc_target_ea:.1f}%)."
            )

        return PricingProposal(
            application_id=application_id,
            calculated_at=datetime.now(UTC).isoformat(),
            requested_amount_usd=round(requested_amount_usd, 2),
            term_months=term_months,
            amortization_system=amortization_system,
            rating_category=clean_rating,
            ltv_status=clean_ltv,
            probability_of_default_pct=pd_pct,
            loss_given_default_pct=lgd_pct,
            net_exposure_at_default_usd=round(ead_net, 2),
            expected_loss_usd=el_usd,
            expected_loss_rate_ea=el_spread_pct,
            cost_of_funds_ea=cost_of_funds_ea,
            opex_spread_ea=opex_spread_ea,
            raroc_target_ea=raroc_target_ea,
            uncapped_tea=uncapped_tea,
            applied_tea=applied_tea,
            monthly_effective_rate_pct=monthly_rate_pct,
            usury_cap_tea=usury_cap_ea,
            exceeds_usury_cap=exceeds_usury,
            usury_adjustment_delta=usury_delta,
            first_month_quota_usd=first_quota,
            total_interest_usd=total_interest,
            total_insurance_usd=total_insurance,
            total_cost_of_credit_usd=total_cost,
            recommendation_notes=notes,
            amortization_schedule=schedule,
        )

    @classmethod
    def generate_amortization_schedule(
        cls,
        principal: float,
        term_months: int,
        monthly_rate: float,
        system: AmortizationSystem,
        insurance_rate_monthly: float = DEFAULT_MONTHLY_INSURANCE_RATE,
    ) -> list[PaymentPeriodQuota]:
        """Genera el cronograma de amortización detallado mes a mes."""
        if term_months <= 0 or principal <= 0:
            return []

        schedule: list[PaymentPeriodQuota] = []
        balance = round(principal, 2)
        n = term_months
        i = monthly_rate

        if system == AmortizationSystem.FRENCH:
            # Cuota fija mensual constante (Fórmula de Anualidad Vencida)
            # C = P * [ i * (1 + i)^n ] / [ (1 + i)^n - 1 ]
            if i > 0:
                factor = math.pow(1.0 + i, n)
                base_quota = round(principal * (i * factor) / (factor - 1.0), 2)
            else:
                base_quota = round(principal / n, 2)

            for period in range(1, n + 1):
                interest = round(balance * i, 2)
                insurance = round(balance * insurance_rate_monthly, 2)

                if period == n:
                    # En la última cuota, el abono a capital es exactamente el saldo residual
                    # para garantizar cuadre contable a 0.00
                    principal_payment = balance
                    quota = round(principal_payment + interest, 2)
                    ending_balance = 0.0
                else:
                    principal_payment = round(base_quota - interest, 2)
                    # En caso extremo de que el interés supere la cuota base
                    if principal_payment < 0:
                        principal_payment = 0.0
                    ending_balance = round(max(0.0, balance - principal_payment), 2)
                    quota = base_quota

                total_quota = round(quota + insurance, 2)

                schedule.append(
                    PaymentPeriodQuota(
                        period=period,
                        beginning_balance=balance,
                        principal_amortization=principal_payment,
                        interest_payment=interest,
                        insurance_payment=insurance,
                        total_quota=total_quota,
                        ending_balance=ending_balance,
                    )
                )
                balance = ending_balance

        elif system == AmortizationSystem.GERMAN:
            # Amortización constante a capital con cuota decreciente
            fixed_amort = round(principal / n, 2)

            for period in range(1, n + 1):
                interest = round(balance * i, 2)
                insurance = round(balance * insurance_rate_monthly, 2)

                if period == n:
                    principal_payment = balance
                    ending_balance = 0.0
                else:
                    principal_payment = fixed_amort
                    ending_balance = round(max(0.0, balance - principal_payment), 2)

                quota = round(principal_payment + interest, 2)
                total_quota = round(quota + insurance, 2)

                schedule.append(
                    PaymentPeriodQuota(
                        period=period,
                        beginning_balance=balance,
                        principal_amortization=principal_payment,
                        interest_payment=interest,
                        insurance_payment=insurance,
                        total_quota=total_quota,
                        ending_balance=ending_balance,
                    )
                )
                balance = ending_balance

        return schedule
