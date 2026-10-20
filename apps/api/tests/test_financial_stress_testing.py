"""Tests unitarios y de integración para el Simulador de Pruebas de Estrés Financiero (SPEC-10).

Cubre los criterios de aceptación formales TEST-01 a TEST-06.
"""

from typing import Any
import pytest
from httpx import ASGITransport, AsyncClient

from src.domain.metrics import DSCRResult, FinancialHealthMetrics
from src.domain.scoring import (
    CreditScorecardResult,
    RegulatoryScorecardEngine,
    RiskRatingCategory,
    ScorecardBreakdown,
)
from src.domain.stress_testing import (
    FinancialStressTestingEngine,
    StressParameters,
    StressScenarioType,
)
from src.infrastructure.repositories import InMemoryUnderwritingRepository
from src.application.use_cases.stress_test_underwriting import StressTestUnderwritingUseCase
from src.main import app


@pytest.fixture
def sample_base_scorecard() -> CreditScorecardResult:
    """Scorecard base simulada en Categoría A con provisión del 1.0%."""
    return CreditScorecardResult(
        total_score=92.5,
        rating_category=RiskRatingCategory.A,
        category_title="Riesgo Normal",
        provision_percentage=1.0,
        estimated_provision_usd=500.0,
        breakdown=ScorecardBreakdown(
            dscr_score=100.0,
            liquidity_score=100.0,
            concentration_score=85.0,
            ai_alignment_score=80.0,
        ),
        regulatory_justification="Calificación inicial Categoría A.",
    )


def test_01_sales_shock_reduces_ebitda_and_dscr(sample_base_scorecard: CreditScorecardResult) -> None:
    """TEST-01: Caída de ventas del 20% reduce EBITDA y contrae el ratio DSCR."""
    base_rev = 100000.0
    base_costs = 70000.0
    debt_service = 15000.0  # EBITDA inicial 30,000 => DSCR base = 2.0x

    params = StressParameters(sales_shock_pct=0.20, opex_shock_pct=0.0, interest_rate_shock_bps=0)
    result = FinancialStressTestingEngine.simulate_scenario(
        params=params,
        base_revenue=base_rev,
        base_costs=base_costs,
        base_debt_service=debt_service,
        base_current_assets=50000.0,
        base_current_liabilities=25000.0,
        base_cash_balance=20000.0,
        base_runway=12.0,
        anomaly_flags=[],
        top_client_percentage=20.0,
        negative_balance_days=0,
        ai_recommendation="APROBADO",
        requested_amount_usd=50000.0,
        base_scorecard=sample_base_scorecard,
        scenario_type=StressScenarioType.SALES_SHOCK_MODERATE,
        scenario_name="Ventas -20%",
        description="Shock del 20%",
    )

    # 100,000 * 0.8 = 80,000 ventas. EBITDA = 80,000 - 70,000 = 10,000
    assert result.stressed_revenue == 80000.0
    assert result.stressed_costs == 70000.0
    assert result.stressed_ebitda == 10000.0
    # DSCR = 10,000 / 15,000 = 0.67x
    assert result.stressed_dscr == pytest.approx(0.67, abs=0.02)
    assert result.is_solvent is False  # DSCR < 1.0


def test_02_interest_rate_shock_increases_debt_service(
    sample_base_scorecard: CreditScorecardResult,
) -> None:
    """TEST-02: Subida de 300 bps en tasa encarece el servicio de deuda y reduce DSCR."""
    base_rev = 100000.0
    base_costs = 70000.0
    base_debt_service = 10000.0
    requested_amount = 50000.0  # +300 bps (+3%) => +$1,500 de servicio anual

    params = StressParameters(
        sales_shock_pct=0.0, opex_shock_pct=0.0, interest_rate_shock_bps=300
    )
    result = FinancialStressTestingEngine.simulate_scenario(
        params=params,
        base_revenue=base_rev,
        base_costs=base_costs,
        base_debt_service=base_debt_service,
        base_current_assets=50000.0,
        base_current_liabilities=25000.0,
        base_cash_balance=20000.0,
        base_runway=12.0,
        anomaly_flags=[],
        top_client_percentage=20.0,
        negative_balance_days=0,
        ai_recommendation="APROBADO",
        requested_amount_usd=requested_amount,
        base_scorecard=sample_base_scorecard,
        scenario_type=StressScenarioType.RATE_SHOCK,
        scenario_name="Tasa +300 bps",
        description="Shock de tasa",
    )

    expected_debt_service = base_debt_service + (requested_amount * 0.03)  # 11,500.0
    assert result.stressed_debt_service == expected_debt_service
    # EBITDA = 30,000 / 11,500 = 2.61x
    assert result.stressed_dscr == pytest.approx(2.61, abs=0.02)
    assert result.is_solvent is True


def test_03_combined_severe_scenario_downgrades_rating(
    sample_base_scorecard: CreditScorecardResult,
) -> None:
    """TEST-03: Escenario adverso severo degrada rating y genera incremento en provisión USD."""
    base_rev = 100000.0
    base_costs = 75000.0
    base_debt_service = 15000.0
    requested_amount = 50000.0

    # Escenario severo: -20% ventas, +10% costos, +300 bps tasa
    # Ventas = 80,000. Costos = 82,500 => EBITDA = -2,500 (operación a pérdida)
    params = StressParameters(
        sales_shock_pct=0.20, opex_shock_pct=0.10, interest_rate_shock_bps=300
    )
    result = FinancialStressTestingEngine.simulate_scenario(
        params=params,
        base_revenue=base_rev,
        base_costs=base_costs,
        base_debt_service=base_debt_service,
        base_current_assets=40000.0,
        base_current_liabilities=30000.0,
        base_cash_balance=10000.0,
        base_runway=12.0,
        anomaly_flags=[],
        top_client_percentage=25.0,
        negative_balance_days=1,
        ai_recommendation="APROBADO",
        requested_amount_usd=requested_amount,
        base_scorecard=sample_base_scorecard,
        scenario_type=StressScenarioType.COMBINED_SEVERE,
        scenario_name="Adverso Severo",
        description="Shock múltiple",
    )

    assert result.stressed_ebitda < 0.0
    assert result.stressed_dscr == 0.0
    assert result.rating_downgraded is True
    # Migra hacia categoría E o D
    assert result.stressed_rating in [RiskRatingCategory.D, RiskRatingCategory.E]
    assert result.delta_provision_usd > 0.0  # Requiere provisión patrimonial adicional
    assert result.is_solvent is False


def test_04_analytical_breakeven_sales_drop_calculation() -> None:
    """TEST-04: Cálculo exacto del punto de quiebre de ventas (Breakeven Sales Drop)."""
    # 1. Caso estándar: Ingresos 100,000, Costos 60,000, Deuda 20,000.
    # Total necesario = 80,000 => Soporta caída del 20% (Delta* = 1 - 80k/100k = 0.20)
    drop_pct, is_tolerable = FinancialStressTestingEngine.calculate_breakeven_sales_drop(
        revenue=100000.0, costs=60000.0, annual_debt_service=20000.0
    )
    assert drop_pct == pytest.approx(0.20, abs=0.001)
    assert is_tolerable is True

    # 2. Caso ajustado: Requiere 90,000 de 100,000 => Soporta 10% (no tolerable según umbral 15%)
    drop_pct_low, is_tolerable_low = FinancialStressTestingEngine.calculate_breakeven_sales_drop(
        revenue=100000.0, costs=80000.0, annual_debt_service=10000.0
    )
    assert drop_pct_low == pytest.approx(0.10, abs=0.001)
    assert is_tolerable_low is False

    # 3. Caso insolvente preexistente: Costos 90,000 + Deuda 20,000 > Ingresos 100,000
    drop_pct_zero, is_tolerable_zero = FinancialStressTestingEngine.calculate_breakeven_sales_drop(
        revenue=100000.0, costs=90000.0, annual_debt_service=20000.0
    )
    assert drop_pct_zero == 0.0
    assert is_tolerable_zero is False


@pytest.mark.asyncio
async def test_05_rest_endpoints_post_and_get_stress_test() -> None:
    """TEST-05: Integración REST para simulación y consulta de estrés (RFC 9110 / RFC 7807)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Crear solicitud crediticia previa
        init_payload = {
            "associated_id": "ASOC-TEST-STRESS-01",
            "business_name": "Agroindustria del Valle S.A.S.",
            "sector": "Agropecuario",
            "requested_amount_usd": 60000.0,
            "term_months": 24,
            "financial_data": {
                "operating_cash_flow": 35000.0,
                "annual_debt_service": 12000.0,
                "current_assets": 80000.0,
                "current_liabilities": 40000.0,
                "cash_balance": 25000.0,
                "monthly_burn_rate": 0.0,
                "negative_balance_days": 0,
                "top_client_revenue_percentage": 20.0,
            },
        }
        res_create = await client.post("/api/v1/underwritings", json=init_payload)
        assert res_create.status_code == 201
        app_id = res_create.json()["application_id"]

        # 2. Ejecutar simulación de estrés vía POST
        stress_payload = {
            "custom_scenario": {
                "sales_shock_pct": 0.25,
                "opex_shock_pct": 0.10,
                "interest_rate_shock_bps": 250,
            }
        }
        res_stress = await client.post(
            f"/api/v1/underwritings/{app_id}/stress-test", json=stress_payload
        )
        assert res_stress.status_code == 200
        analysis = res_stress.json()

        assert analysis["application_id"] == app_id
        assert len(analysis["scenarios"]) >= 6  # 5 estándar + 1 custom
        assert analysis["breakeven_sales_drop_pct"] > 0.0
        assert "resilience_summary" in analysis

        # 3. Consultar vía GET persistido
        res_get = await client.get(f"/api/v1/underwritings/{app_id}/stress-test")
        assert res_get.status_code == 200
        saved_analysis = res_get.json()
        assert saved_analysis["application_id"] == app_id

        # 4. Solicitud no encontrada responde 404 Problem Details (RFC 7807)
        res_not_found = await client.get("/api/v1/underwritings/non-existent-uuid/stress-test")
        assert res_not_found.status_code == 404
        problem = res_not_found.json()
        assert problem["status"] == 404
        assert "title" in problem


def test_06_custom_scenario_simulation(sample_base_scorecard: CreditScorecardResult) -> None:
    """TEST-06: Simulación con parámetros personalizados a medida del comité."""
    custom = StressParameters(
        sales_shock_pct=0.35, opex_shock_pct=0.20, interest_rate_shock_bps=500
    )
    result = FinancialStressTestingEngine.simulate_scenario(
        params=custom,
        base_revenue=150000.0,
        base_costs=100000.0,
        base_debt_service=20000.0,
        base_current_assets=60000.0,
        base_current_liabilities=30000.0,
        base_cash_balance=15000.0,
        base_runway=6.0,
        anomaly_flags=[],
        top_client_percentage=22.0,
        negative_balance_days=0,
        ai_recommendation="APROBADO",
        requested_amount_usd=40000.0,
        base_scorecard=sample_base_scorecard,
        scenario_type=StressScenarioType.CUSTOM,
        scenario_name="Comité Especial",
        description="Shock muy adverso",
    )

    # 150,000 * (1 - 0.35) = 97,500
    assert result.stressed_revenue == 97500.0
    # 100,000 * 1.20 = 120,000
    assert result.stressed_costs == 120000.0
    # EBITDA = 97,500 - 120,000 = -22,500
    assert result.stressed_ebitda == -22500.0
    assert result.stressed_dscr == 0.0
    assert result.rating_downgraded is True
    assert result.is_solvent is False
