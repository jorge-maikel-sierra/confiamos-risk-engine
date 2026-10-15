"""Tests unitarios para la generación de la planilla financiera en Excel (SPEC-07 / TDD Seam 3)."""

import io

import openpyxl

from src.infrastructure.excel_generator import ExcelFinancialGenerator


def test_excel_financial_generator_produces_valid_workbook_with_live_formulas():
    """Valida generación de .xlsx con hojas estructuradas y fórmulas vivas."""
    sample_data = {
        "id": "7f0b5d90-3a1b-4b8c-8f47-2b734892cfa1",
        "associated_id": "ASOC-4455",
        "business_name": "Cooperativa Textilera del Sur",
        "requested_amount_usd": 120000.0,
        "term_months": 36,
        "created_at": "2026-10-15T10:30:00Z",
        "metrics": {
            "dscr": 1.62,
            "current_ratio": 2.1,
            "runway_months": 11.4,
            "operating_cash_flow": 85000.0,
            "annual_debt_service": 52400.0,
            "is_debt_free": False,
        },
        "raw_financials": {
            "current_assets": 210000.0,
            "current_liabilities": 100000.0,
        },
        "ai_verdict": {
            "recommendation": "APROBADO",
            "confidence_score": 0.94,
            "executive_summary": "Empresa solvente con capacidad de pago comprobada.",
        },
        "crypto_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    }

    generator = ExcelFinancialGenerator()
    excel_bytes = generator.generate(sample_data)

    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 500

    # Cargar el libro desde memoria con openpyxl para verificar estructura y fórmulas
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    sheet_names = wb.sheetnames
    assert "Resumen Ejecutivo" in sheet_names
    assert "Balance y Liquidez" in sheet_names
    assert "Flujo y Cobertura" in sheet_names

    # Verificar fórmulas vivas
    ws_liquidity = wb["Balance y Liquidez"]
    assert ws_liquidity["B6"].value == "=B4/B5"

    ws_cashflow = wb["Flujo y Cobertura"]
    assert ws_cashflow["B6"].value == '=IF(B5=0,"N/A",B4/B5)'

    # Verificar presencia de datos y sello
    ws_summary = wb["Resumen Ejecutivo"]
    assert ws_summary["B5"].value == sample_data["business_name"]
    assert ws_summary["B11"].value == sample_data["crypto_hash"]
