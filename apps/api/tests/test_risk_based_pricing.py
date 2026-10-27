"""Tests unitarios y de integración para el Motor de Pricing Ajustado al Riesgo y Amortizaciones (SPEC-12).

Cubre los criterios de aceptación formales TEST-01 a TEST-06:
- TEST-01: Cálculo de Pérdida Esperada (EL = PD * LGD * EAD_net) según matriz de rating y LTV.
- TEST-02: Composición aditiva de TEA y tasa mensual equivalente.
- TEST-03: Control y alerta de techo de usura con tope automático y flag.
- TEST-04: Cronograma de amortización Francés (cuota fija y cuadre contable a 0).
- TEST-05: Cronograma de amortización Alemán (amortización fija, cuota decreciente y cuadre).
- TEST-06: Endpoints HTTP REST POST/GET /pricing, persistencia y RFC 7807 ante 404.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.domain.pricing import (
    AmortizationSystem,
    RiskBasedPricingEngine,
)
from src.main import app


def test_01_expected_loss_calculation() -> None:
    """TEST-01: Pérdida esperada EL = PD * LGD * EAD_net según matrices de riesgo y mitigantes."""
    # Caso 1: Rating B (PD = 4.0%), LTV WARNING (LGD = 35.0%), Monto $50,000, EAD neta $30,000
    proposal_b = RiskBasedPricingEngine.calculate_pricing(
        application_id="APP-TEST-P01",
        requested_amount_usd=50000.0,
        term_months=24,
        rating_category="B",
        ltv_status="WARNING",
        net_exposure_at_default_usd=30000.0,
    )
    # EL = 0.04 * 0.35 * 30,000 = $420.00
    assert proposal_b.expected_loss_usd == 420.00
    # Prima EL = (420 / 50,000) * 100 = 0.84%
    assert proposal_b.expected_loss_rate_ea == 0.84
    assert proposal_b.probability_of_default_pct == 4.0
    assert proposal_b.loss_given_default_pct == 35.0

    # Caso 2: Rating A (PD = 1.5%), LTV HEALTHY (LGD = 20.0%), Monto $100,000, EAD neta $0 (Sobrecolateralizado)
    proposal_a = RiskBasedPricingEngine.calculate_pricing(
        application_id="APP-TEST-P02",
        requested_amount_usd=100000.0,
        term_months=36,
        rating_category="A",
        ltv_status="HEALTHY",
        net_exposure_at_default_usd=0.0,
    )
    assert proposal_a.expected_loss_usd == 0.0
    assert proposal_a.expected_loss_rate_ea == 0.0


def test_02_additive_tea_composition_and_monthly_rate() -> None:
    """TEST-02: Composición aditiva de TEA (COF + OPEX + Prima EL + RAROC) y tasa mensual equivalente."""
    # Monto $50,000, Rating B, LTV WARNING (Prima EL = 0.84%)
    # COF = 8.5%, OPEX = 4.5%, RAROC = 3.0% => TEA = 8.5 + 4.5 + 0.84 + 3.0 = 16.84%
    proposal = RiskBasedPricingEngine.calculate_pricing(
        application_id="APP-TEST-P03",
        requested_amount_usd=50000.0,
        term_months=24,
        rating_category="B",
        ltv_status="WARNING",
        net_exposure_at_default_usd=30000.0,
    )

    assert proposal.cost_of_funds_ea == 8.50
    assert proposal.opex_spread_ea == 4.50
    assert proposal.raroc_target_ea == 3.00
    assert proposal.uncapped_tea == 16.84
    assert proposal.applied_tea == 16.84
    assert proposal.exceeds_usury_cap is False
    assert proposal.usury_adjustment_delta == 0.0

    # Verificar tasa mensual equivalente: (1 + i_mes)^12 - 1 = TEA
    i_monthly = proposal.monthly_effective_rate_pct / 100.0
    annualized = ((1.0 + i_monthly) ** 12) - 1.0
    assert round(annualized * 100.0, 1) == 16.8


def test_03_usury_cap_control_and_automatic_adjustment() -> None:
    """TEST-03: Crédito de alto riesgo supera tope de usura (28.5%), se ajusta automáticamente y activa alerta."""
    # Rating E (PD = 65%), UNSECURED (LGD = 65%), Monto $40,000, EAD neta $40,000
    # EL = 0.65 * 0.65 * 40,000 = $16,900 => Prima EL = (16,900 / 40,000) * 100 = 42.25%
    # TEA no topeada = 8.5 + 4.5 + 42.25 + 3.0 = 58.25% > 28.50%
    proposal = RiskBasedPricingEngine.calculate_pricing(
        application_id="APP-TEST-P04",
        requested_amount_usd=40000.0,
        term_months=12,
        rating_category="E",
        ltv_status="UNSECURED",
        net_exposure_at_default_usd=40000.0,
        usury_cap_ea=28.50,
    )

    assert proposal.uncapped_tea == 58.25
    assert proposal.exceeds_usury_cap is True
    assert proposal.applied_tea == 28.50
    assert proposal.usury_adjustment_delta == 29.75
    assert "ALERTA DE USURA" in proposal.recommendation_notes


def test_04_french_amortization_schedule() -> None:
    """TEST-04: Cronograma Francés genera cuotas fijas y cuadra el capital exacto en 0.00."""
    amount = 24000.0
    term = 12

    proposal = RiskBasedPricingEngine.calculate_pricing(
        application_id="APP-TEST-P05",
        requested_amount_usd=amount,
        term_months=term,
        rating_category="A",
        ltv_status="HEALTHY",
        net_exposure_at_default_usd=0.0,
        amortization_system=AmortizationSystem.FRENCH,
    )

    schedule = proposal.amortization_schedule
    assert len(schedule) == term

    # Verificar abonos de capital y cuadre exacto
    total_principal_paid = sum(q.principal_amortization for q in schedule)
    assert round(total_principal_paid, 2) == round(amount, 2)

    # El saldo del último mes debe ser 0.00
    assert schedule[-1].ending_balance == 0.0

    # Las cuotas puras (capital + interés) deben ser constantes antes de seguros
    base_quotas = [round(q.principal_amortization + q.interest_payment, 2) for q in schedule[:-1]]
    assert len(set(base_quotas)) == 1

    # Intereses son estrictamente decrecientes
    for idx in range(len(schedule) - 1):
        assert schedule[idx].interest_payment >= schedule[idx + 1].interest_payment


def test_05_german_amortization_schedule() -> None:
    """TEST-05: Cronograma Alemán genera amortización constante y cuotas totales decrecientes."""
    amount = 30000.0
    term = 10

    proposal = RiskBasedPricingEngine.calculate_pricing(
        application_id="APP-TEST-P06",
        requested_amount_usd=amount,
        term_months=term,
        rating_category="B",
        ltv_status="WARNING",
        amortization_system=AmortizationSystem.GERMAN,
    )

    schedule = proposal.amortization_schedule
    assert len(schedule) == term

    # Amortización a capital fija (30,000 / 10 = 3,000)
    for q in schedule:
        assert q.principal_amortization == 3000.0

    # Cuota total estrictamente decreciente
    for idx in range(len(schedule) - 1):
        assert schedule[idx].total_quota > schedule[idx + 1].total_quota

    assert schedule[-1].ending_balance == 0.0
    total_principal = sum(q.principal_amortization for q in schedule)
    assert round(total_principal, 2) == round(amount, 2)


@pytest.mark.asyncio
async def test_06_pricing_endpoints_and_persistence() -> None:
    """TEST-06: Endpoints POST y GET /pricing, persistencia en repositorio y RFC 7807 ante 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Crear solicitud de crédito
        init_payload = {
            "associated_id": "SOC-SPEC12-001",
            "business_name": "Distribuciones Químicas Industriales SAS",
            "sector": "Industria y Manufactura",
            "requested_amount_usd": 60000.0,
            "term_months": 24,
            "financial_data": {
                "operating_cash_flow": 45000.0,
                "annual_debt_service": 15000.0,
                "current_assets": 90000.0,
                "current_liabilities": 40000.0,
                "cash_balance": 30000.0,
                "monthly_burn_rate": 0.0,
                "negative_balance_days": 0,
                "top_client_revenue_percentage": 20.0,
            },
        }
        res_init = await client.post("/api/v1/underwritings", json=init_payload)
        assert res_init.status_code == 201
        app_id = res_init.json()["application_id"]

        # 2. Generar pricing inicial (Francés por defecto)
        pricing_payload = {
            "amortization_system": "FRENCH",
            "term_months_override": 24,
        }
        res_pricing = await client.post(
            f"/api/v1/underwritings/{app_id}/pricing", json=pricing_payload
        )
        assert res_pricing.status_code == 200
        data_pricing = res_pricing.json()

        assert data_pricing["application_id"] == app_id
        assert data_pricing["amortization_system"] == "FRENCH"
        assert data_pricing["requested_amount_usd"] == 60000.0
        assert data_pricing["term_months"] == 24
        assert len(data_pricing["amortization_schedule"]) == 24
        assert data_pricing["applied_tea"] > 0.0

        # 3. Recalcular pricing con sistema Alemán
        german_payload = {
            "amortization_system": "GERMAN",
            "term_months_override": 12,
        }
        res_german = await client.post(
            f"/api/v1/underwritings/{app_id}/pricing", json=german_payload
        )
        assert res_german.status_code == 200
        data_german = res_german.json()
        assert data_german["amortization_system"] == "GERMAN"
        assert data_german["term_months"] == 12
        assert len(data_german["amortization_schedule"]) == 12

        # 4. Consultar pricing persistido vía GET
        res_get = await client.get(f"/api/v1/underwritings/{app_id}/pricing")
        assert res_get.status_code == 200
        saved_pricing = res_get.json()
        assert saved_pricing["application_id"] == app_id
        assert saved_pricing["amortization_system"] == "GERMAN"

        # 5. Consultar expediente general y verificar pricing incrustado
        res_full = await client.get(f"/api/v1/underwritings/{app_id}")
        assert res_full.status_code == 200
        full_record = res_full.json()
        assert full_record["pricing_proposal"] is not None
        assert full_record["pricing_proposal"]["amortization_system"] == "GERMAN"

        # 6. ID inexistente retorna 404 Problem Details (RFC 7807)
        res_404 = await client.get("/api/v1/underwritings/non-existent-id/pricing")
        assert res_404.status_code == 404
        problem = res_404.json()
        assert problem["status"] == 404
        assert "title" in problem
