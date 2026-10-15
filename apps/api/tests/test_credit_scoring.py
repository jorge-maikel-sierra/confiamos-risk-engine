"""Pruebas unitarias para el subsistema de Scoring Regulatorio y Provisiones (SPEC-09).

TDD Seams:
1. TEST-01: Cálculo de puntaje del componente DSCR (35%).
2. TEST-02: Cálculo de puntaje del componente Liquidez y Runway (30%).
3. TEST-03: Cálculo de puntaje de Concentración y Anomalías (20%).
4. TEST-04: Cálculo de puntaje de Alineación IA (15%).
5. TEST-05: Ponderación global, clasificación de categorías (A a E) y provisión en USD.
"""

import pytest

from src.domain.metrics import DSCRResult, FinancialHealthMetrics
from src.domain.scoring import (
    CreditScorecardResult,
    RegulatoryScorecardEngine,
    RiskRatingCategory,
)


class TestScorecardComponents:
    """TEST-01 a TEST-04: Puntuación de componentes individuales."""

    def test_dscr_scoring_tiers(self):
        # DSCR >= 1.50 -> 100 pts
        assert (
            RegulatoryScorecardEngine.calculate_dscr_score(dscr=1.75, is_debt_free=False) == 100.0
        )
        # 1.30 <= DSCR < 1.50 -> 80 pts
        assert RegulatoryScorecardEngine.calculate_dscr_score(dscr=1.35, is_debt_free=False) == 80.0
        # 1.15 <= DSCR < 1.30 -> 60 pts
        assert RegulatoryScorecardEngine.calculate_dscr_score(dscr=1.20, is_debt_free=False) == 60.0
        # 1.00 <= DSCR < 1.15 -> 40 pts
        assert RegulatoryScorecardEngine.calculate_dscr_score(dscr=1.05, is_debt_free=False) == 40.0
        # DSCR < 1.00 -> 0 pts
        assert RegulatoryScorecardEngine.calculate_dscr_score(dscr=0.85, is_debt_free=False) == 0.0
        # Sin deuda previa -> 100 pts
        assert RegulatoryScorecardEngine.calculate_dscr_score(dscr=None, is_debt_free=True) == 100.0

    def test_liquidity_scoring_tiers(self):
        # Current Ratio >= 1.50 y Runway >= 6 -> 100 pts
        assert (
            RegulatoryScorecardEngine.calculate_liquidity_score(
                current_ratio=1.60, runway_months=8.0
            )
            == 100.0
        )
        # Current Ratio >= 1.20 y Runway >= 3 -> 80 pts
        assert (
            RegulatoryScorecardEngine.calculate_liquidity_score(
                current_ratio=1.30, runway_months=4.0
            )
            == 80.0
        )
        # Current Ratio >= 1.00 -> 60 pts
        assert (
            RegulatoryScorecardEngine.calculate_liquidity_score(
                current_ratio=1.05, runway_months=1.5
            )
            == 60.0
        )
        # Current Ratio < 1.00 -> 20 pts
        assert (
            RegulatoryScorecardEngine.calculate_liquidity_score(
                current_ratio=0.80, runway_months=0.5
            )
            == 20.0
        )
        # Runway None (sin quema de caja) pero con ratio corriente fuerte -> 100 pts
        assert (
            RegulatoryScorecardEngine.calculate_liquidity_score(
                current_ratio=2.00, runway_months=None
            )
            == 100.0
        )

    def test_concentration_and_anomalies_scoring(self):
        # Concentración <= 25%, 0 sobregiros, 0 anomalías -> 100 pts
        score_optimal = RegulatoryScorecardEngine.calculate_concentration_score(
            top_client_percentage=20.0, negative_balance_days=0, anomaly_flags=[]
        )
        assert score_optimal == 100.0

        # Concentración <= 50%, 1 sobregiro, 0 anomalías -> 70 pts
        score_moderate = RegulatoryScorecardEngine.calculate_concentration_score(
            top_client_percentage=35.0, negative_balance_days=1, anomaly_flags=[]
        )
        assert score_moderate == 70.0

        # Concentración > 50% -> 30 pts base
        score_high = RegulatoryScorecardEngine.calculate_concentration_score(
            top_client_percentage=60.0, negative_balance_days=0, anomaly_flags=[]
        )
        assert score_high == 30.0

        # Penalización por anomalías críticas (-15 pts c/u)
        score_with_anomalies = RegulatoryScorecardEngine.calculate_concentration_score(
            top_client_percentage=20.0,
            negative_balance_days=0,
            anomaly_flags=["Pérdida acelerada", "Concentración extrema"],
        )
        assert score_with_anomalies == 70.0  # 100 - 30 = 70

    def test_ai_alignment_scoring(self):
        assert RegulatoryScorecardEngine.calculate_ai_score("APROBADO") == 100.0
        assert RegulatoryScorecardEngine.calculate_ai_score("APROBADO_CONDICIONADO") == 60.0
        assert RegulatoryScorecardEngine.calculate_ai_score("RECHAZADO") == 0.0
        assert RegulatoryScorecardEngine.calculate_ai_score(None) == 50.0


class TestScorecardEvaluation:
    """TEST-05: Ponderación total, bandas regulatorias y cálculo de provisión en USD."""

    def test_category_a_perfect_scorecard(self):
        metrics = FinancialHealthMetrics(
            dscr_result=DSCRResult(dscr=1.80, is_debt_free=False, is_solvent=True),
            current_ratio=1.90,
            runway_months=12.0,
            anomaly_flags=[],
        )

        result = RegulatoryScorecardEngine.evaluate(
            metrics=metrics,
            top_client_percentage=20.0,
            negative_balance_days=0,
            ai_recommendation="APROBADO",
            requested_amount_usd=100000.0,
        )

        assert isinstance(result, CreditScorecardResult)
        assert result.total_score >= 85.0
        assert result.rating_category == RiskRatingCategory.A
        assert result.provision_percentage == 1.0
        assert result.estimated_provision_usd == 1000.0  # 1% de 100,000

    def test_category_c_moderate_risk(self):
        metrics = FinancialHealthMetrics(
            dscr_result=DSCRResult(dscr=1.18, is_debt_free=False, is_solvent=True),
            current_ratio=1.05,
            runway_months=2.0,
            anomaly_flags=["FLAG_LOW_LIQUIDITY"],  # -15 pts en concentración
        )

        result = RegulatoryScorecardEngine.evaluate(
            metrics=metrics,
            top_client_percentage=35.0,
            negative_balance_days=1,
            ai_recommendation="APROBADO_CONDICIONADO",
            requested_amount_usd=50000.0,
        )

        assert 55.0 <= result.total_score < 70.0
        assert result.rating_category == RiskRatingCategory.C
        assert result.provision_percentage == 10.0
        assert result.estimated_provision_usd == 5000.0  # 10% de 50,000

    def test_category_e_loss_risk(self):
        metrics = FinancialHealthMetrics(
            dscr_result=DSCRResult(dscr=0.70, is_debt_free=False, is_solvent=False),
            current_ratio=0.75,
            runway_months=0.5,
            anomaly_flags=["FLAG_NEGATIVE_OPERATING_CASH_FLOW", "FLAG_LOW_LIQUIDITY"],
        )

        result = RegulatoryScorecardEngine.evaluate(
            metrics=metrics,
            top_client_percentage=65.0,
            negative_balance_days=8,
            ai_recommendation="RECHAZADO",
            requested_amount_usd=80000.0,
        )

        assert result.total_score < 40.0
        assert result.rating_category == RiskRatingCategory.E
        assert result.provision_percentage == 100.0
        assert result.estimated_provision_usd == 80000.0  # 100% de 80,000


class TestScorecardApiIntegration:
    """TEST-06: Verificación de integración en API REST y persistencia."""

    @pytest.mark.asyncio
    async def test_endpoint_returns_scorecard_and_persists(self):
        from httpx import ASGITransport, AsyncClient

        from src.api.routes.underwriting import (
            get_risk_auditor,
            get_underwriting_repository,
        )
        from src.domain.repositories import InMemoryUnderwritingRepository
        from src.infrastructure.gemini_adapter import MockGeminiAuditor
        from src.main import app

        repo = InMemoryUnderwritingRepository()
        app.dependency_overrides[get_risk_auditor] = lambda: MockGeminiAuditor()
        app.dependency_overrides[get_underwriting_repository] = lambda: repo

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                payload = {
                    "associated_id": "ASOC-SCORE-01",
                    "business_name": "Agroindustrias del Valle",
                    "requested_amount_usd": 120000.0,
                    "term_months": 36,
                    "financial_data": {
                        "operating_cash_flow": 95000.0,
                        "annual_debt_service": 40000.0,
                        "current_assets": 220000.0,
                        "current_liabilities": 90000.0,
                        "cash_balance": 60000.0,
                        "monthly_burn_rate": 0.0,
                        "negative_balance_days": 0,
                        "top_client_revenue_percentage": 18.0,
                    },
                }

                # 1. Crear solicitud
                res_post = await client.post("/api/v1/underwritings", json=payload)
                assert res_post.status_code == 201
                data = res_post.json()
                assert data["scorecard"] is not None
                assert data["scorecard"]["rating_category"] == "A"
                assert data["scorecard"]["total_score"] >= 85.0
                assert data["scorecard"]["estimated_provision_usd"] == 1200.0  # 1% de 120,000

                app_id = data["application_id"]

                # 2. Consultar solicitud
                res_get = await client.get(f"/api/v1/underwritings/{app_id}")
                assert res_get.status_code == 200
                get_data = res_get.json()
                assert get_data["scorecard"] is not None
                assert get_data["scorecard"]["rating_category"] == "A"
                assert get_data["scorecard"]["estimated_provision_usd"] == 1200.0
        finally:
            app.dependency_overrides.clear()
