"""Caso de Uso: Ingesta Documental y Extracción Financiera (IngestFinancialDocumentUseCase).

Valida tipos MIME y magic bytes (SPEC-08) y extrae métricas de balances contables
utilizando el extractor especializado según el formato.
"""

from dataclasses import dataclass

from src.domain.document_ingestion import (
    ExcelDocumentExtractor,
    FileValidator,
    FinancialExtractionResult,
    GeminiDocumentExtractor,
)
from src.domain.ports import RiskAuditorProtocol


@dataclass(frozen=True)
class IngestDocumentCommand:
    """Parámetros de entrada para la ingesta de un documento contable."""

    file_bytes: bytes
    filename: str


class IngestFinancialDocumentUseCase:
    """Implementa la validación y extracción financiera de archivos contables."""

    def __init__(self, risk_auditor: RiskAuditorProtocol) -> None:
        self.risk_auditor = risk_auditor

    async def execute(self, command: IngestDocumentCommand) -> FinancialExtractionResult:
        """Valida cabeceras por magic bytes y extrae la información financiera."""
        # Validación de integridad física y tamaño
        doc_type = FileValidator.validate(filename=command.filename, file_bytes=command.file_bytes)

        if doc_type == "xlsx":
            extractor = ExcelDocumentExtractor()
        else:
            extractor = GeminiDocumentExtractor(gemini_adapter=self.risk_auditor)

        return await extractor.extract_financial_data(
            file_bytes=command.file_bytes,
            filename=command.filename,
        )
