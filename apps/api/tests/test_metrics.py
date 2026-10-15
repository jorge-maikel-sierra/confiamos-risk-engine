"""Tests unitarios para el motor determinístico de métricas financieras (SPEC-01).

Cubre:
1. DSCR (Debt Service Coverage Ratio) estándar y edge cases (deuda cero, flujo negativo).
2. Ratio de Liquidez Corriente (Current Ratio).
3. Runway (meses de caja).
4. Detección de anomalías de flujo de caja.
"""

from src.domain.metrics import (
    FinancialInput,
    calculate_current_ratio,
    calculate_dscr,
    calculate_runway,
    evaluate_financial_health,
)


def test_calculate_dscr_standard() -> None:
    """Verifica TEST-01 del SPEC-01: Flujo $48,500 y deuda $24,000 da DSCR ~2.0208."""
    result = calculate_dscr(operating_cash_flow=48500.0, annual_debt_service=24000.0)
    assert result.dscr is not None
    assert round(result.dscr, 4) == 2.0208
    assert result.is_debt_free is False
    assert result.is_solvent is True


def test_calculate_dscr_zero_debt() -> None:
    """Verifica TEST-02 del SPEC-01: Deuda cero no debe lanzar ZeroDivisionError."""
    result = calculate_dscr(operating_cash_flow=50000.0, annual_debt_service=0.0)
    assert result.dscr is None
    assert result.is_debt_free is True
    assert result.is_solvent is True


def test_calculate_dscr_deficit() -> None:
    """Verifica que un DSCR < 1.0 marque a la empresa como no solvente en flujo."""
    result = calculate_dscr(operating_cash_flow=18000.0, annual_debt_service=24000.0)
    assert result.dscr is not None
    assert round(result.dscr, 2) == 0.75
    assert result.is_solvent is False


def test_calculate_current_ratio() -> None:
    """Verifica cálculo de liquidez corriente: Activo Corriente / Pasivo Corriente."""
    ratio = calculate_current_ratio(current_assets=120000.0, current_liabilities=65000.0)
    assert round(ratio, 4) == 1.8462


def test_calculate_current_ratio_zero_liabilities() -> None:
    """Verifica que sin pasivos corrientes el ratio sea None y no lance error."""
    ratio = calculate_current_ratio(current_assets=120000.0, current_liabilities=0.0)
    assert ratio is None


def test_calculate_runway() -> None:
    """Verifica cálculo de runway: Caja / Gasto neto mensual."""
    runway = calculate_runway(cash_balance=60000.0, monthly_burn_rate=12000.0)
    assert runway == 5.0


def test_calculate_runway_profitable() -> None:
    """Verifica que si la empresa no quema caja (burn rate <= 0), el runway sea None (infinito)."""
    runway = calculate_runway(cash_balance=60000.0, monthly_burn_rate=0.0)
    assert runway is None


def test_evaluate_financial_health_end_to_end() -> None:
    """Verifica el cálculo integral de métricas y detección de banderas de riesgo."""
    data = FinancialInput(
        operating_cash_flow=-5000.0,
        annual_debt_service=20000.0,
        current_assets=80000.0,
        current_liabilities=50000.0,
        cash_balance=15000.0,
        monthly_burn_rate=5000.0,
        negative_balance_days=3,
        top_client_revenue_percentage=42.0,
    )
    metrics = evaluate_financial_health(data)
    assert metrics.dscr_result.is_solvent is False
    assert "FLAG_NEGATIVE_OPERATING_CASH_FLOW" in metrics.anomaly_flags
    assert "FLAG_OVERDRAFT_DETECTED" in metrics.anomaly_flags
    assert "FLAG_HIGH_CLIENT_CONCENTRATION" in metrics.anomaly_flags
    assert metrics.runway_months == 3.0
