"""Tests de integración para los endpoints REST de evaluación crediticia.

SPEC-01 y SPEC-02 (Fase 3).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.routes.underwriting import (
    get_risk_auditor,
    get_underwriting_repository,
)
from src.domain.repositories import InMemoryUnderwritingRepository
from src.infrastructure.gemini_adapter import MockGeminiAuditor
from src.main import app


@pytest.fixture(autouse=True)
def override_dependencies():
    """Garantiza el uso de MockGeminiAuditor y un repositorio en memoria limpio."""
    fresh_repo = InMemoryUnderwritingRepository()
    app.dependency_overrides[get_risk_auditor] = lambda: MockGeminiAuditor()
    app.dependency_overrides[get_underwriting_repository] = lambda: fresh_repo
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
        # 1. Iniciar evaluación crediticia (usando ruta plural canónica)
        create_res = await client.post("/api/v1/underwritings", json=sample_payload)
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
        get_res = await client.get(f"/api/v1/underwritings/{app_id}")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["application_id"] == app_id
        assert get_data["current_step"] == "PENDING_HUMAN_REVIEW"

        # 3. Emitir resolución del oficial de crédito (Human-in-the-loop en ruta /reviews)
        review_payload = {
            "approved": True,
            "notes": "Aprobado por el comité de crédito de Cooperativa Confiamos con garantía.",
        }
        review_res = await client.post(
            f"/api/v1/underwritings/{app_id}/reviews", json=review_payload
        )
        assert review_res.status_code == 200
        final_data = review_res.json()

        assert final_data["current_step"] == "COMPLETED"
        assert final_data["is_completed"] is True
        assert final_data["human_approved"] is True
        assert "Aprobado por el comité" in final_data["human_notes"]

        # 4. Verificar retrocompatibilidad con la ruta /underwrite/{app_id}
        legacy_get = await client.get(f"/api/v1/underwrite/{app_id}")
        assert legacy_get.status_code == 200
        assert legacy_get.json()["is_completed"] is True


@pytest.mark.asyncio
async def test_paginated_list_underwritings(sample_payload: dict) -> None:
    """Verifica que el endpoint GET /api/v1/underwritings pagine y liste correctamente."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Crear dos solicitudes
        await client.post("/api/v1/underwritings", json=sample_payload)
        payload_2 = sample_payload.copy()
        payload_2["associated_id"] = "CONF-00002"
        await client.post("/api/v1/underwritings", json=payload_2)

        # Listar con paginación
        res = await client.get("/api/v1/underwritings?limit=10&offset=0")
        assert res.status_code == 200
        data = res.json()

        assert "items" in data
        assert len(data["items"]) == 2
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert data["total"] == 2


@pytest.mark.asyncio
async def test_conflict_on_already_completed_review(sample_payload: dict) -> None:
    """Verifica que intentar revisar una solicitud ya finalizada retorne 409 Conflict."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Crear y aprobar
        create_res = await client.post("/api/v1/underwritings", json=sample_payload)
        app_id = create_res.json()["application_id"]

        review_payload = {"approved": True, "notes": "Primera aprobación válida."}
        res1 = await client.post(f"/api/v1/underwritings/{app_id}/reviews", json=review_payload)
        assert res1.status_code == 200

        # Segundo intento de revisión -> 409 Conflict
        res2 = await client.post(f"/api/v1/underwritings/{app_id}/reviews", json=review_payload)
        assert res2.status_code == 409
        assert "ya ha sido finalizada previamente" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_get_nonexistent_application_returns_404() -> None:
    """Verifica que solicitar un ID inexistente retorne 404 Not Found."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/underwritings/APP-INEXISTENTE-999")
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
            "requested_amount_usd": -5000.0,
            "term_months": 0,
            "financial_data": {},
        }
        res = await client.post("/api/v1/underwritings", json=invalid_payload)
        assert res.status_code == 422
