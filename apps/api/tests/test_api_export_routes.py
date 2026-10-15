"""Tests para exportación y verificación de sello (SPEC-07 / TDD Seam 4)."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.routes.underwriting import get_risk_auditor, get_underwriting_repository
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


@pytest.mark.asyncio
async def test_export_pdf_and_excel_and_verify_seal():
    """Valida ciclo completo: radicar -> exportar PDF -> exportar Excel -> verificar sello."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Radicamos una solicitud válida
        payload = {
            "associated_id": "ASOC-EXPORT-1",
            "business_name": "Distribuidora Mayorista del Café",
            "requested_amount_usd": 90000.0,
            "term_months": 24,
            "financial_data": {
                "operating_cash_flow": 72000.0,
                "annual_debt_service": 36000.0,
                "current_assets": 150000.0,
                "current_liabilities": 75000.0,
                "monthly_burn_rate": 8000.0,
                "cash_balance": 48000.0,
            },
        }

        res_post = await client.post("/api/v1/underwritings", json=payload)
        assert res_post.status_code == 201
        created = res_post.json()
        app_id = created["application_id"]

        # 2. Exportar PDF
        res_pdf = await client.get(f"/api/v1/underwritings/{app_id}/export/pdf")
        assert res_pdf.status_code == 200
        assert res_pdf.headers["content-type"] == "application/pdf"
        expected_disp = f'attachment; filename="dictamen-credito-{app_id}.pdf"'
        assert expected_disp in res_pdf.headers.get("content-disposition", "")
        assert res_pdf.content.startswith(b"%PDF-1.")

        # 3. Exportar Excel
        res_excel = await client.get(f"/api/v1/underwritings/{app_id}/export/excel")
        assert res_excel.status_code == 200
        assert "spreadsheetml.sheet" in res_excel.headers["content-type"]
        assert len(res_excel.content) > 500

        # 4. Verificar Sello Criptográfico sin hash proporcionado (obtiene el hash canónico)
        res_seal = await client.get(f"/api/v1/underwritings/{app_id}/verify-seal")
        assert res_seal.status_code == 200
        seal_data = res_seal.json()
        assert seal_data["application_id"] == app_id
        canonical_hash = seal_data["expected_hash"]
        assert len(canonical_hash) == 64

        # 5. Verificar con el hash correcto -> is_authentic == True
        res_verify_true = await client.get(
            f"/api/v1/underwritings/{app_id}/verify-seal",
            params={"hash": canonical_hash},
        )
        assert res_verify_true.status_code == 200
        assert res_verify_true.json()["is_authentic"] is True

        # 6. Verificar con un hash adulterado -> is_authentic == False
        tampered_hash = canonical_hash[:-4] + "0000"
        res_verify_false = await client.get(
            f"/api/v1/underwritings/{app_id}/verify-seal",
            params={"hash": tampered_hash},
        )
        assert res_verify_false.status_code == 200
        assert res_verify_false.json()["is_authentic"] is False


@pytest.mark.asyncio
async def test_export_pdf_not_found():
    """Exportar PDF de una solicitud inexistente debe retornar 404 Not Found."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        dummy_id = "00000000-0000-0000-0000-000000000000"
        res = await client.get(f"/api/v1/underwritings/{dummy_id}/export/pdf")
        assert res.status_code == 404
