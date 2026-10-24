"""Tests unitarios y de integración para el Motor de Valuación de Garantías y LTV (SPEC-11).

Cubre los criterios de aceptación formales TEST-01 a TEST-06:
- TEST-01: Valuación y haircuts por tipo normativo de bien.
- TEST-02: Cálculo de LTV, CCR y umbrales de semaforización.
- TEST-03: Deducción de provisiones contables y cálculo de alivio de capital.
- TEST-04: Condición de sobrecolateralización (EAD neta = 0).
- TEST-05: Garantía personal no admisible no deduce provisión contable.
- TEST-06: Endpoints HTTP REST y persistencia en repositorio.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.domain.collaterals import (
    CollateralItemInput,
    CollateralType,
    CollateralValuationEngine,
)
from src.main import app


def test_01_haircut_valuation_by_collateral_type() -> None:
    """TEST-01: Valuación individual aplicando la matriz regulatoria de haircuts."""
    # 1. Depósito a plazo / CDAT (5% haircut)
    cdat_in = CollateralItemInput(
        collateral_type=CollateralType.CDAT_DEPOSIT,
        description="CDAT Banco Cooperativo a 360 días",
        commercial_appraisal_usd=10000.0,
    )
    cdat_item = CollateralValuationEngine.valuate_item(cdat_in)
    assert cdat_item.haircut_percentage == 5.0
    assert cdat_item.admissible_value_usd == 9500.0
    assert cdat_item.is_statutory_admissible is True

    # 2. Inmueble Urbano (20% haircut)
    urban_in = CollateralItemInput(
        collateral_type=CollateralType.REAL_ESTATE_URBAN,
        description="Local comercial en Bogotá D.C.",
        commercial_appraisal_usd=100000.0,
    )
    urban_item = CollateralValuationEngine.valuate_item(urban_in)
    assert urban_item.haircut_percentage == 20.0
    assert urban_item.admissible_value_usd == 80000.0
    assert urban_item.is_statutory_admissible is True

    # 3. Flota vehicular comercial (30% haircut)
    veh_in = CollateralItemInput(
        collateral_type=CollateralType.VEHICLE_COMMERCIAL,
        description="Camión Hino 2023 de carga pesada",
        commercial_appraisal_usd=50000.0,
    )
    veh_item = CollateralValuationEngine.valuate_item(veh_in)
    assert veh_item.haircut_percentage == 30.0
    assert veh_item.admissible_value_usd == 35000.0
    assert veh_item.is_statutory_admissible is True

    # 4. FNG Garantía soberana (10% haircut)
    fng_in = CollateralItemInput(
        collateral_type=CollateralType.FNG_GUARANTEE,
        description="Certificado de Garantía FNG 80%",
        commercial_appraisal_usd=20000.0,
    )
    fng_item = CollateralValuationEngine.valuate_item(fng_in)
    assert fng_item.haircut_percentage == 10.0
    assert fng_item.admissible_value_usd == 18000.0
    assert fng_item.is_statutory_admissible is True


def test_02_ltv_and_ccr_calculation_and_status() -> None:
    """TEST-02: Cálculo de LTV y CCR con clasificación semafórica de riesgo."""
    requested = 60000.0

    # Escenario 1: Saludable (LTV = 60% <= 70%)
    item_healthy = CollateralItemInput(
        collateral_type=CollateralType.REAL_ESTATE_URBAN,
        description="Bodega industrial",
        commercial_appraisal_usd=100000.0,
    )
    analysis_healthy = CollateralValuationEngine.evaluate(
        application_id="APP-TEST-01",
        requested_amount_usd=requested,
        rating_category="B",
        provision_rate_percentage=3.0,
        gross_provision_usd=1800.0,
        items_input=[item_healthy],
    )
    assert analysis_healthy.ltv_percentage == 60.0
    assert analysis_healthy.ltv_status == "HEALTHY"
    # CCR: 80,000 / 60,000 = 133.33%
    assert analysis_healthy.collateral_coverage_ratio == 133.33

    # Escenario 2: Alerta / Warning (LTV = 80% entre 70% y 85%)
    item_warning = CollateralItemInput(
        collateral_type=CollateralType.REAL_ESTATE_URBAN,
        description="Oficina",
        commercial_appraisal_usd=75000.0,
    )
    analysis_warning = CollateralValuationEngine.evaluate(
        application_id="APP-TEST-02",
        requested_amount_usd=60000.0,
        rating_category="B",
        provision_rate_percentage=3.0,
        gross_provision_usd=1800.0,
        items_input=[item_warning],
    )
    assert analysis_warning.ltv_percentage == 80.0
    assert analysis_warning.ltv_status == "WARNING"

    # Escenario 3: Crítico (LTV > 85%)
    item_crit = CollateralItemInput(
        collateral_type=CollateralType.REAL_ESTATE_URBAN,
        description="Depósito pequeño",
        commercial_appraisal_usd=60000.0,
    )
    analysis_crit = CollateralValuationEngine.evaluate(
        application_id="APP-TEST-03",
        requested_amount_usd=55000.0,
        rating_category="C",
        provision_rate_percentage=10.0,
        gross_provision_usd=5500.0,
        items_input=[item_crit],
    )
    # 55,000 / 60,000 = 91.67%
    assert analysis_crit.ltv_percentage == 91.67
    assert analysis_crit.ltv_status == "CRITICAL"

    # Escenario 4: Sin garantías (UNSECURED)
    analysis_unsecured = CollateralValuationEngine.evaluate(
        application_id="APP-TEST-04",
        requested_amount_usd=50000.0,
        rating_category="A",
        provision_rate_percentage=1.0,
        gross_provision_usd=500.0,
        items_input=[],
    )
    assert analysis_unsecured.ltv_percentage is None
    assert analysis_unsecured.ltv_status == "UNSECURED"
    assert analysis_unsecured.net_exposure_at_default_usd == 50000.0


def test_03_net_provision_and_capital_relief_deduction() -> None:
    """TEST-03: Deducción de provisiones sobre EAD neta y cálculo del alivio patrimonial."""
    requested = 50000.0
    provision_rate = 10.0  # Categoría C
    gross_provision = 5000.0

    # Inmueble urbano avalúo $40,000 -> Admisible $32,000 (haircut 20%)
    urban = CollateralItemInput(
        collateral_type=CollateralType.REAL_ESTATE_URBAN,
        description="Local comercial",
        commercial_appraisal_usd=40000.0,
    )
    analysis = CollateralValuationEngine.evaluate(
        application_id="APP-TEST-05",
        requested_amount_usd=requested,
        rating_category="C",
        provision_rate_percentage=provision_rate,
        gross_provision_usd=gross_provision,
        items_input=[urban],
    )

    # EAD neta = 50,000 - 32,000 = 18,000
    assert analysis.net_exposure_at_default_usd == 18000.0
    # Provisión neta = 18,000 * 10% = 1,800.0
    assert analysis.net_provision_usd == 1800.0
    # Alivio patrimonial = 5,000 - 1,800 = 3,200.0
    assert analysis.capital_relief_usd == 3200.0
    assert analysis.is_fully_secured is False


def test_04_overcollateralization_boundary() -> None:
    """TEST-04: Sobrecolateralización satura EAD neta en 0 y provisión neta en 0."""
    requested = 30000.0
    gross_prov = 3000.0

    # CDAT de $50,000 (haircut 5% => admisible $47,500 > $30,000)
    cdat = CollateralItemInput(
        collateral_type=CollateralType.CDAT_DEPOSIT,
        description="CDAT pignorado",
        commercial_appraisal_usd=50000.0,
    )
    analysis = CollateralValuationEngine.evaluate(
        application_id="APP-TEST-06",
        requested_amount_usd=requested,
        rating_category="C",
        provision_rate_percentage=10.0,
        gross_provision_usd=gross_prov,
        items_input=[cdat],
    )

    assert analysis.total_admissible_usd == 47500.0
    assert analysis.net_exposure_at_default_usd == 0.0
    assert analysis.net_provision_usd == 0.0
    assert analysis.capital_relief_usd == gross_prov
    assert analysis.is_fully_secured is True


def test_05_non_statutory_collateral_does_not_deduct_provisions() -> None:
    """TEST-05: Garantía personal/aval no es computable como mitigante contable de provisión."""
    requested = 25000.0
    gross_prov = 2500.0  # 10% Categoría C

    personal = CollateralItemInput(
        collateral_type=CollateralType.PERSONAL_GUARANTEE,
        description="Pagaré con codeudor solidario solvente",
        commercial_appraisal_usd=50000.0,
    )
    item_val = CollateralValuationEngine.valuate_item(personal)
    assert item_val.is_statutory_admissible is False
    assert item_val.admissible_value_usd == 0.0

    analysis = CollateralValuationEngine.evaluate(
        application_id="APP-TEST-07",
        requested_amount_usd=requested,
        rating_category="C",
        provision_rate_percentage=10.0,
        gross_provision_usd=gross_prov,
        items_input=[personal],
    )

    assert analysis.total_admissible_usd == 0.0
    assert analysis.net_exposure_at_default_usd == requested
    assert analysis.net_provision_usd == gross_prov
    assert analysis.capital_relief_usd == 0.0
    assert analysis.is_fully_secured is False


@pytest.mark.asyncio
async def test_06_collateral_endpoints_and_persistence() -> None:
    """TEST-06: Endpoints POST y GET /collaterals con persistencia y RFC 7807 en 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Crear solicitud crediticia base
        init_payload = {
            "associated_id": "SOC-SPEC11-001",
            "business_name": "Logística y Envíos Andinos SAS",
            "sector": "Transporte y Logística",
            "requested_amount_usd": 40000.0,
            "term_months": 36,
            "financial_data": {
                "operating_cash_flow": 28000.0,
                "annual_debt_service": 10000.0,
                "current_assets": 60000.0,
                "current_liabilities": 30000.0,
                "cash_balance": 18000.0,
                "monthly_burn_rate": 0.0,
                "negative_balance_days": 0,
                "top_client_revenue_percentage": 25.0,
            },
        }
        res_init = await client.post("/api/v1/underwritings", json=init_payload)
        assert res_init.status_code == 201
        app_id = res_init.json()["application_id"]

        # 2. Registrar colaterales vía POST
        collaterals_payload = {
            "collaterals": [
                {
                    "collateral_type": "REAL_ESTATE_URBAN",
                    "description": "Bodega Principal en Fontibón",
                    "commercial_appraisal_usd": 35000.0,
                },
                {
                    "collateral_type": "CDAT_DEPOSIT",
                    "description": "Pagaré CDAT Custodiado",
                    "commercial_appraisal_usd": 10000.0,
                },
            ]
        }
        res_post = await client.post(
            f"/api/v1/underwritings/{app_id}/collaterals", json=collaterals_payload
        )
        assert res_post.status_code == 200
        analysis_data = res_post.json()

        assert analysis_data["application_id"] == app_id
        assert len(analysis_data["items"]) == 2
        assert analysis_data["total_appraisal_usd"] == 45000.0
        # Bodega (35,000 * 0.80 = 28,000) + CDAT (10,000 * 0.95 = 9,500) = 37,500
        assert analysis_data["total_admissible_usd"] == 37500.0
        # LTV = 40,000 / 45,000 = 88.89% (CRITICAL)
        assert analysis_data["ltv_percentage"] == 88.89
        assert analysis_data["ltv_status"] == "CRITICAL"
        assert analysis_data["capital_relief_usd"] > 0.0

        # 3. Consultar vía GET /collaterals
        res_get = await client.get(f"/api/v1/underwritings/{app_id}/collaterals")
        assert res_get.status_code == 200
        retrieved_analysis = res_get.json()
        assert retrieved_analysis["application_id"] == app_id
        assert retrieved_analysis["total_admissible_usd"] == 37500.0

        # 4. Consultar el expediente completo y verificar que collateral_analysis viene incrustado
        res_full = await client.get(f"/api/v1/underwritings/{app_id}")
        assert res_full.status_code == 200
        full_record = res_full.json()
        assert full_record["collateral_analysis"] is not None
        assert full_record["collateral_analysis"]["total_admissible_usd"] == 37500.0

        # 5. Petición sobre ID inexistente responde 404 Problem Details (RFC 7807)
        res_404 = await client.get("/api/v1/underwritings/non-existent-id/collaterals")
        assert res_404.status_code == 404
        problem = res_404.json()
        assert problem["status"] == 404
        assert "title" in problem
