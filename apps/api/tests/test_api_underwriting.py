"""Tests de integración para los endpoints REST de evaluación crediticia (Issue #4 / SPEC-01)."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.routes.underwriting import get_risk_auditor
from src.infrastructure.gemini_adapter import MockGeminiAuditor
from src.main import app


@pytest.fixture(autouse=True)
def override_auditor():
    """Garantiza que todos los tests de API utilicen el MockGeminiAuditor."""
    app.dependency_overrides[get_risk_auditor] = lambda: MockGeminiAuditor()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def sample_payload() -> dict:
    """Payload de prueba para una solicitud crediticia solvente."""
    return {
        "associated_id": "CONF-98214",
        "business_name": "Distribuidora Andina SAS",
        "requested_amount_usd": 75000.0,
        "term_months": 24,
        "financial_data": {
            "operating_cash_flow": 48500.0,
            "annual_debt_service": 24000.0,
            "current_assets": 120000.0,
            "current_liabilities": 65000.0,
            "cash_balance": 35000.0,
            "monthly_burn_rate": 0.0,
            "negative_balance_days": 0,
            "top_client_revenue_percentage": 22.5,
        },
    }


@pytest.mark.asyncio
async def test_underwriting_lifecycle_via_rest_api(sample_payload: dict) -> None:
    """Verifica el ciclo de vida completo: Creación ➔ Consulta ➔ Revisión humana ➔ Finalización."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Iniciar evaluación crediticia
        create_res = await client.post("/api/v1/underwrite", json=sample_payload)
        assert create_res.status_code == 201
        data = create_res.json()

        app_id = data["application_id"]
        assert app_id.startswith("APP-")
        assert data["current_step"] == "PENDING_HUMAN_REVIEW"
        assert data["is_completed"] is False
        assert data["metrics"] is not None
        assert round(data["metrics"]["dscr"], 4) == 2.0208
        assert data["metrics"]["is_solvent"] is True
        assert data["ai_verdict"]["recommendation"] == "APROBADO"

        # 2. Consultar el snapshot de la solicitud
        get_res = await client.get(f"/api/v1/underwrite/{app_id}")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["application_id"] == app_id
        assert get_data["current_step"] == "PENDING_HUMAN_REVIEW"

        # 3. Emitir resolución del oficial de crédito (Human-in-the-loop)
        review_payload = {
            "approved": True,
            "notes": (
                "Aprobado por el comité de crédito de Cooperativa Confiamos con garantía estándar."
            ),
        }
        review_res = await client.post(f"/api/v1/underwrite/{app_id}/review", json=review_payload)
        assert review_res.status_code == 200
        final_data = review_res.json()

        assert final_data["current_step"] == "COMPLETED"
        assert final_data["is_completed"] is True
        assert final_data["human_approved"] is True
        assert "Aprobado por el comité" in final_data["human_notes"]


@pytest.mark.asyncio
async def test_get_nonexistent_application_returns_404() -> None:
    """Verifica que solicitar un ID inexistente retorne 404 Not Found."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/underwrite/APP-INEXISTENTE-999")
        assert res.status_code == 404
        assert "No se encontró la solicitud" in res.json()["detail"]


@pytest.mark.asyncio
async def test_underwrite_invalid_payload_returns_422() -> None:
    """Verifica que montos negativos o plazos inválidos sean rechazados por Pydantic con 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        invalid_payload = {
            "associated_id": "CONF-111",
            "business_name": "Test Fail",
            "requested_amount_usd": -5000.0,  # Inválido: debe ser gt=0
            "term_months": 0,  # Inválido: debe ser gt=0
            "financial_data": {},
        }
        res = await client.post("/api/v1/underwrite", json=invalid_payload)
        assert res.status_code == 422
