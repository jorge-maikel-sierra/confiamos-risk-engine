"""Pruebas unitarias e integrales para el subsistema de Ingesta Documental Inteligente (SPEC-08).

TDD Seams:
1. TEST-01: Validación de archivo (MIME/Magic bytes, límite 10MB, extensiones).
2. TEST-02: Modelo de dominio FinancialExtractionResult y MockDocumentExtractor.
3. TEST-03: ExcelDocumentExtractor con openpyxl en memoria.
4. TEST-04: PDF extractor básico con pypdf.
5. TEST-05: Integración del endpoint POST /api/v1/underwritings/upload-financials.
"""

import io

import pytest
from openpyxl import Workbook
from pypdf import PdfWriter

from src.domain.document_ingestion import (
    CorruptedDocumentError,
    ExcelDocumentExtractor,
    FileValidator,
    FinancialExtractionResult,
    MockDocumentExtractor,
    PayloadTooLargeError,
    UnsupportedFileTypeError,
)


def create_sample_pdf_bytes() -> bytes:
    """Genera en memoria un archivo PDF válido con encabezados reales."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def create_sample_xlsx_bytes() -> bytes:
    """Genera en memoria un archivo Excel (.xlsx) válido con balance general estructurado."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Balance y Flujo"

    # Encabezados y valores contables simulados
    ws.append(["Rubro Contable", "Monto USD"])
    ws.append(["Flujo de Caja Operativo", 85000.0])
    ws.append(["Servicio Anual de Deuda", 52400.0])
    ws.append(["Activo Corriente", 210000.0])
    ws.append(["Pasivo Corriente", 100000.0])
    ws.append(["Caja y Bancos", 45000.0])
    ws.append(["Gasto Operativo Mensual (Burn Rate)", 12000.0])

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


class TestFileValidator:
    """TEST-01: Validación estricta de archivos y magic bytes."""

    def test_validate_valid_pdf(self):
        pdf_bytes = create_sample_pdf_bytes()
        doc_type = FileValidator.validate(filename="balance_2026.pdf", file_bytes=pdf_bytes)
        assert doc_type == "pdf"

    def test_validate_valid_xlsx(self):
        xlsx_bytes = create_sample_xlsx_bytes()
        doc_type = FileValidator.validate(filename="extracto_bancario.xlsx", file_bytes=xlsx_bytes)
        assert doc_type == "xlsx"

    def test_reject_unsupported_extension(self):
        with pytest.raises(UnsupportedFileTypeError) as exc_info:
            FileValidator.validate(filename="malicious.exe", file_bytes=b"MZ\x90\x00\x03\x00")
        assert "no soportada" in str(exc_info.value).lower()

    def test_reject_oversized_file(self):
        large_bytes = b"%PDF-" + b"0" * (10 * 1024 * 1024 + 1)
        with pytest.raises(PayloadTooLargeError) as exc_info:
            FileValidator.validate(filename="huge.pdf", file_bytes=large_bytes)
        assert "10 mb" in str(exc_info.value).lower()

    def test_reject_spoofed_magic_bytes(self):
        # Extensión .pdf pero contenido de texto plano sin header %PDF-
        fake_pdf = b"Esto no es un pdf real, es texto plano"
        with pytest.raises(CorruptedDocumentError) as exc_info:
            FileValidator.validate(filename="fake.pdf", file_bytes=fake_pdf)
        assert "magic bytes" in str(exc_info.value).lower()


class TestFinancialExtractionResult:
    """TEST-02: Esquema Pydantic y MockDocumentExtractor."""

    def test_domain_model_instantiation(self):
        result = FinancialExtractionResult(
            operating_cash_flow=85000.0,
            annual_debt_service=52400.0,
            current_assets=210000.0,
            current_liabilities=100000.0,
            cash_balance=45000.0,
            monthly_burn_rate=12000.0,
            confidence_score=0.95,
            detected_anomalies=["Sobregiro menor en mayo"],
            extracted_source_name="balance_general_2026.pdf",
            summary_notes="Extracción financiera completa",
        )
        assert result.operating_cash_flow == 85000.0
        assert result.confidence_score == 0.95
        assert len(result.detected_anomalies) == 1

    @pytest.mark.asyncio
    async def test_mock_extractor_success(self):
        extractor = MockDocumentExtractor()
        pdf_bytes = create_sample_pdf_bytes()
        result = await extractor.extract_financial_data(
            file_bytes=pdf_bytes, filename="balance.pdf"
        )

        assert isinstance(result, FinancialExtractionResult)
        assert result.operating_cash_flow > 0
        assert result.confidence_score >= 0.9
        assert result.extracted_source_name == "balance.pdf"


class TestExcelDocumentExtractor:
    """TEST-03: Extractor de Excel con openpyxl."""

    @pytest.mark.asyncio
    async def test_extract_from_valid_xlsx(self):
        extractor = ExcelDocumentExtractor()
        xlsx_bytes = create_sample_xlsx_bytes()

        result = await extractor.extract_financial_data(
            file_bytes=xlsx_bytes, filename="extracto_mensual.xlsx"
        )

        assert isinstance(result, FinancialExtractionResult)
        assert result.operating_cash_flow == 85000.0
        assert result.annual_debt_service == 52400.0
        assert result.current_assets == 210000.0
        assert result.current_liabilities == 100000.0
        assert result.cash_balance == 45000.0
        assert result.monthly_burn_rate == 12000.0
        assert result.confidence_score >= 0.85


class TestUploadFinancialsEndpoint:
    """TEST-05: Integración del endpoint POST /api/v1/underwritings/upload-financials."""

    @pytest.mark.asyncio
    async def test_upload_valid_xlsx(self):
        from httpx import ASGITransport, AsyncClient

        from src.main import app

        xlsx_bytes = create_sample_xlsx_bytes()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {
                "file": (
                    "estados_financieros.xlsx",
                    xlsx_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            }
            response = await client.post("/api/v1/underwritings/upload-financials", files=files)
            assert response.status_code == 200
            data = response.json()
            assert data["operating_cash_flow"] == 85000.0
            assert data["annual_debt_service"] == 52400.0
            assert data["current_assets"] == 210000.0
            assert data["current_liabilities"] == 100000.0
            assert data["confidence_score"] >= 0.85
            assert data["extracted_source_name"] == "estados_financieros.xlsx"

    @pytest.mark.asyncio
    async def test_upload_valid_pdf(self):
        from httpx import ASGITransport, AsyncClient

        from src.main import app

        pdf_bytes = create_sample_pdf_bytes()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": ("balance_general.pdf", pdf_bytes, "application/pdf")}
            response = await client.post("/api/v1/underwritings/upload-financials", files=files)
            assert response.status_code == 200
            data = response.json()
            assert data["operating_cash_flow"] > 0
            assert data["confidence_score"] >= 0.50
            assert data["extracted_source_name"] == "balance_general.pdf"

    @pytest.mark.asyncio
    async def test_upload_unsupported_file_type(self):
        from httpx import ASGITransport, AsyncClient

        from src.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": ("script.sh", b"#!/bin/bash\necho hello", "text/plain")}
            response = await client.post("/api/v1/underwritings/upload-financials", files=files)
            assert response.status_code == 415
            assert "no soportada" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_oversized_file(self):
        from httpx import ASGITransport, AsyncClient

        from src.main import app

        huge_file = b"%PDF-" + b"x" * (10 * 1024 * 1024 + 1)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": ("huge.pdf", huge_file, "application/pdf")}
            response = await client.post("/api/v1/underwritings/upload-financials", files=files)
            assert response.status_code == 413
            assert "10 mb" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_spoofed_pdf(self):
        from httpx import ASGITransport, AsyncClient

        from src.main import app

        fake_pdf = b"Plain text claiming to be a pdf"
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": ("fake.pdf", fake_pdf, "application/pdf")}
            response = await client.post("/api/v1/underwritings/upload-financials", files=files)
            assert response.status_code == 422
            assert "magic bytes" in response.json()["detail"].lower()
