"""Motor determinístico de métricas financieras y detección de anomalías (SPEC-01).

Implementa las fórmulas requeridas por la Cooperativa Confiamos:
- DSCR (Debt Service Coverage Ratio)
- Ratio de Liquidez Corriente (Current Ratio)
- Runway en meses
- Banderas de anomalías de flujo de caja
"""

from dataclasses import dataclass

from pydantic import BaseModel, Field

# Umbrales bancarios estándar
MIN_SOLVENT_DSCR = 1.25
MIN_HEALTHY_LIQUIDITY = 1.30
MAX_CLIENT_CONCENTRATION_PCT = 30.0


class FinancialInput(BaseModel):
    """Datos financieros de entrada para el cálculo de solvencia."""

    operating_cash_flow: float = Field(description="Flujo de caja operativo anual")
    annual_debt_service: float = Field(
        ge=0.0, description="Servicio anual de la deuda (capital + intereses)"
    )
    current_assets: float = Field(ge=0.0, description="Activo corriente total")
    current_liabilities: float = Field(ge=0.0, description="Pasivo corriente total")
    cash_balance: float = Field(ge=0.0, description="Efectivo y equivalentes disponibles")
    monthly_burn_rate: float = Field(
        default=0.0, ge=0.0, description="Gasto neto de caja mensual (si opera a pérdida)"
    )
    negative_balance_days: int = Field(
        default=0, ge=0, description="Días con saldo negativo o sobregiro en el periodo"
    )
    top_client_revenue_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Porcentaje de ingresos que representa el cliente principal",
    )


@dataclass(frozen=True)
class DSCRResult:
    """Resultado del cálculo de Cobertura de Servicio de Deuda."""

    dscr: float | None
    is_debt_free: bool
    is_solvent: bool


@dataclass(frozen=True)
class FinancialHealthMetrics:
    """Consolidado de métricas determinísticas y alertas de riesgo."""

    dscr_result: DSCRResult
    current_ratio: float | None
    runway_months: float | None
    anomaly_flags: list[str]


def calculate_dscr(operating_cash_flow: float, annual_debt_service: float) -> DSCRResult:
    """Calcula el Debt Service Coverage Ratio (DSCR).

    Fórmula: Flujo Operativo / Servicio de la Deuda.
    Maneja división por cero asignando None y marcando is_debt_free=True.
    """
    if annual_debt_service <= 0:
        return DSCRResult(
            dscr=None,
            is_debt_free=True,
            is_solvent=operating_cash_flow > 0,
        )

    dscr_value = operating_cash_flow / annual_debt_service
    is_solvent = dscr_value >= MIN_SOLVENT_DSCR

    return DSCRResult(
        dscr=dscr_value,
        is_debt_free=False,
        is_solvent=is_solvent,
    )


def calculate_current_ratio(current_assets: float, current_liabilities: float) -> float | None:
    """Calcula la razón corriente de liquidez.

    Fórmula: Activo Corriente / Pasivo Corriente.
    Si pasivos corrientes son cero, retorna None sin error de división por cero.
    """
    if current_liabilities <= 0:
        return None
    return current_assets / current_liabilities


def calculate_runway(cash_balance: float, monthly_burn_rate: float) -> float | None:
    """Calcula la cantidad de meses de caja restante (Runway).

    Fórmula: Efectivo / Gasto Neto Mensual.
    Si el burn rate es <= 0, retorna None (runway infinito / empresa rentable).
    """
    if monthly_burn_rate <= 0:
        return None
    return cash_balance / monthly_burn_rate


def evaluate_financial_health(data: FinancialInput) -> FinancialHealthMetrics:
    """Evalúa la salud financiera completa e inyecta banderas de anomalías."""
    dscr_res = calculate_dscr(data.operating_cash_flow, data.annual_debt_service)
    curr_ratio = calculate_current_ratio(data.current_assets, data.current_liabilities)
    runway = calculate_runway(data.cash_balance, data.monthly_burn_rate)

    flags: list[str] = []

    # 1. Alerta por flujo operativo negativo
    if data.operating_cash_flow < 0:
        flags.append("FLAG_NEGATIVE_OPERATING_CASH_FLOW")

    # 2. Alerta por días en sobregiro / saldo negativo
    if data.negative_balance_days > 0:
        flags.append("FLAG_OVERDRAFT_DETECTED")

    # 3. Alerta por concentración excesiva en un solo cliente
    if data.top_client_revenue_percentage > MAX_CLIENT_CONCENTRATION_PCT:
        flags.append("FLAG_HIGH_CLIENT_CONCENTRATION")

    # 4. Alerta por liquidez insuficiente
    if curr_ratio is not None and curr_ratio < MIN_HEALTHY_LIQUIDITY:
        flags.append("FLAG_LOW_LIQUIDITY")

    return FinancialHealthMetrics(
        dscr_result=dscr_res,
        current_ratio=curr_ratio,
        runway_months=runway,
        anomaly_flags=flags,
    )
