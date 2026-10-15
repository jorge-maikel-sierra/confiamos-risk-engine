"""Tests unitarios para la generación de legajos oficiales en PDF (SPEC-07 / TDD Seam 2)."""


from src.domain.crypto_seal import CryptoSealService
from src.infrastructure.pdf_generator import PdfDossierGenerator


def test_pdf_dossier_generator_produces_valid_pdf_buffer():
    """PdfDossierGenerator debe generar un buffer binario válido de PDF (%PDF-1.)."""
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
        "ai_verdict": {
            "recommendation": "APROBADO",
            "confidence_score": 0.94,
            "executive_summary": (
                "Empresa con excelente solvencia y márgenes holgados para cubrir el crédito."
            ),
            "key_strengths": ["DSCR robusto de 1.62x", "Flujo operativo positivo consistente"],
            "identified_risks": ["Concentración moderada de inventario en temporada baja"],
            "due_diligence_questions": [
                "¿Cuál es el plan de cobertura ante fluctuaciones de materia prima?",
                "¿Se cuenta con garantías hipotecarias o prendarias adicionales?",
            ],
        },
        "precedents": [
            {
                "business_name": "Textiles Andinos S.A.",
                "loan_amount_usd": 100000.0,
                "outcome": "PAGADO",
                "similarity_score": 0.88,
            }
        ],
    }

    # Calculamos el sello canónico
    crypto_hash = CryptoSealService.compute_canonical_hash(sample_data)
    sample_data["crypto_hash"] = crypto_hash

    generator = PdfDossierGenerator()
    pdf_bytes = generator.generate(sample_data)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-1.")
    # Verificar que el PDF contenga strings clave (en formato binario o texto embebido)
    assert b"COOPERATIVA CONFIAMOS" in pdf_bytes
    assert b"DICTAMEN" in pdf_bytes
    assert sample_data["business_name"].encode("utf-8") in pdf_bytes
