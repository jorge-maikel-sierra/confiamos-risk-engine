"""Tests unitarios y de integración para la capa de observabilidad con Langfuse.

Issue #17 / SPEC-03.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.routes.underwriting import (
    get_observability_tracker,
    get_risk_auditor,
    get_underwriting_repository,
)
from src.domain.metrics import (
    DSCRResult,
    FinancialHealthMetrics,
)
from src.domain.repositories import InMemoryUnderwritingRepository
from src.infrastructure.gemini_adapter import MockGeminiAuditor
from src.infrastructure.observability import (
    LangfuseTracker,
    MockObservabilityTracker,
)
from src.main import app


@pytest.fixture
def clean_mock_tracker() -> MockObservabilityTracker:
    return MockObservabilityTracker()


def test_mock_observability_tracker_lifecycle(
    clean_mock_tracker: MockObservabilityTracker,
) -> None:
    """Verifica el registro en memoria de trazas, generaciones y scores."""
    tracker = clean_mock_tracker

    # 1. Iniciar traza
    tracker.trace_start(
        application_id="APP-TEST-OBS",
        associated_id="CONF-12345",
        business_name="Soluciones Financieras SAS",
        requested_amount_usd=80000.0,
        term_months=24,
    )
    assert len(tracker.traces) == 1
    assert tracker.traces[0]["id"] == "APP-TEST-OBS"
    assert tracker.traces[0]["user_id"] == "CONF-12345"

    # 2. Registrar generación
    tracker.record_generation(
        application_id="APP-TEST-OBS",
        model_name="gemini-1.5-flash",
        prompt="Audit Soluciones Financieras SAS",
        output={"recommendation": "APROBADO"},
        usage={"prompt_tokens": 150, "completion_tokens": 50, "total_tokens": 200},
        latency_ms=120.5,
    )
    assert len(tracker.generations) == 1
    gen = tracker.generations[0]
    assert gen["trace_id"] == "APP-TEST-OBS"
    assert gen["model_name"] == "gemini-1.5-flash"
    assert gen["usage"]["total_tokens"] == 200

    # 3. Registrar score humano
    tracker.record_human_score(
        application_id="APP-TEST-OBS",
        approved=True,
        notes="Aprobado por el comité de crédito.",
    )
    assert len(tracker.scores) == 1
    score = tracker.scores[0]
    assert score["trace_id"] == "APP-TEST-OBS"
    assert score["name"] == "human_approval"
    assert score["value"] == 1.0
    assert "comité de crédito" in score["comment"]


@pytest.mark.asyncio
async def test_mock_gemini_auditor_records_generation_in_tracker(
    clean_mock_tracker: MockObservabilityTracker,
) -> None:
    """Verifica que MockGeminiAuditor registre la generación en el tracker."""
    tracker = clean_mock_tracker
    auditor = MockGeminiAuditor(tracker=tracker)

    dummy_metrics = FinancialHealthMetrics(
        dscr_result=DSCRResult(dscr=2.5, is_solvent=True, is_debt_free=False),
        current_ratio=2.0,
        runway_months=None,
        anomaly_flags=[],
    )

    verdict = await auditor.audit_application(
        business_name="Comercializadora del Norte",
        requested_amount_usd=60000.0,
        term_months=18,
        metrics=dummy_metrics,
        application_id="APP-TEST-GEN",
        associated_id="CONF-9999",
    )

    assert verdict.recommendation.value == "APROBADO"
    assert len(tracker.generations) == 1
    assert tracker.generations[0]["trace_id"] == "APP-TEST-GEN"


def test_langfuse_tracker_graceful_degradation() -> None:
    """Verifica que LangfuseTracker no arroje excepciones ante ausencia de credenciales."""
    tracker = LangfuseTracker(public_key=None, secret_key=None)
    # Ninguna de estas operaciones debe fallar
    tracker.trace_start("APP-1", "CONF-1", "Empresa", 10000.0, 12)
    tracker.record_generation("APP-1", "gemini-1.5-flash", "prompt", {})
    tracker.record_human_score("APP-1", True, "ok")
    tracker.flush()


@pytest.mark.asyncio
async def test_end_to_end_observability_via_api() -> None:
    """Verifica el flujo completo de observabilidad a través de los endpoints de FastAPI."""
    mock_tracker = MockObservabilityTracker()
    in_memory_repo = InMemoryUnderwritingRepository()

    app.dependency_overrides[get_observability_tracker] = lambda: mock_tracker
    app.dependency_overrides[get_underwriting_repository] = lambda: in_memory_repo
    app.dependency_overrides[get_risk_auditor] = lambda: MockGeminiAuditor(tracker=mock_tracker)

    payload = {
        "associated_id": "CONF-TRACE-1",
        "business_name": "Tecnología y Servicios SAS",
        "requested_amount_usd": 45000.0,
        "term_months": 12,
        "financial_data": {
            "operating_cash_flow": 35000.0,
            "annual_debt_service": 15000.0,
            "current_assets": 80000.0,
            "current_liabilities": 40000.0,
            "cash_balance": 25000.0,
            "monthly_burn_rate": 0.0,
            "negative_balance_days": 0,
            "top_client_revenue_percentage": 18.0,
        },
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Iniciar evaluación
        res_create = await client.post("/api/v1/underwritings", json=payload)
        assert res_create.status_code == 201
        app_id = res_create.json()["application_id"]

        # Validar traza y generación registradas en el tracker
        assert len(mock_tracker.traces) == 1
        assert mock_tracker.traces[0]["id"] == app_id
        assert mock_tracker.traces[0]["user_id"] == "CONF-TRACE-1"

        assert len(mock_tracker.generations) == 1
        assert mock_tracker.generations[0]["trace_id"] == app_id

        # 2. Emitir revisión humana
        review_payload = {
            "approved": True,
            "notes": "Aprobación de comité observada y trazada con éxito.",
        }
        res_review = await client.post(
            f"/api/v1/underwritings/{app_id}/reviews", json=review_payload
        )
        assert res_review.status_code == 200

        # Validar score registrado en el tracker
        assert len(mock_tracker.scores) == 1
        score = mock_tracker.scores[0]
        assert score["trace_id"] == app_id
        assert score["value"] == 1.0
        assert "Aprobación de comité" in score["comment"]

    app.dependency_overrides.clear()
