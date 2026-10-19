"""Casos de Uso para Exportación de Expedientes y Verificación de Sello Criptográfico."""

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.application.exceptions import ApplicationNotFoundError
from src.domain.crypto_seal import CryptoSealService
from src.domain.repositories import IUnderwritingRepository
from src.infrastructure.excel_generator import ExcelFinancialGenerator
from src.infrastructure.pdf_generator import PdfDossierGenerator


def prepare_export_payload(record: dict[str, Any], application_id: str) -> dict[str, Any]:
    """Construye la estructura normalizada para exportación y sellado criptográfico."""
    metrics_obj = record.get("metrics")
    metrics_dict = None
    if metrics_obj:
        if isinstance(metrics_obj, dict):
            metrics_dict = metrics_obj
        else:
            metrics_dict = {
                "dscr": getattr(metrics_obj.dscr_result, "dscr", None),
                "is_solvent": getattr(metrics_obj.dscr_result, "is_solvent", False),
                "is_debt_free": getattr(metrics_obj.dscr_result, "is_debt_free", False),
                "current_ratio": getattr(metrics_obj, "current_ratio", None),
                "runway_months": getattr(metrics_obj, "runway_months", None),
                "anomaly_flags": getattr(metrics_obj, "anomaly_flags", []),
            }

    ai_v = record.get("ai_verdict")
    if hasattr(ai_v, "model_dump"):
        ai_v = ai_v.model_dump()

    precedents = record.get("historical_precedents") or []
    precedents = [p.to_dict() if hasattr(p, "to_dict") else p for p in precedents]

    raw_fin = record.get("raw_financials")
    if hasattr(raw_fin, "model_dump"):
        raw_fin = raw_fin.model_dump()

    export_data = {
        "application_id": application_id,
        "associated_id": record.get("associated_id", ""),
        "business_name": record.get("business_name", ""),
        "requested_amount_usd": record.get("requested_amount_usd", 0.0),
        "term_months": record.get("term_months", 0),
        "current_step": record.get("current_step", ""),
        "is_completed": record.get("is_completed", False),
        "human_approved": record.get("human_approved"),
        "human_notes": record.get("human_notes"),
        "created_at": record.get("created_at"),
        "metrics": metrics_dict,
        "ai_verdict": ai_v,
        "scorecard": record.get("scorecard"),
        "precedents": precedents,
        "raw_financials": raw_fin,
    }

    crypto_hash = CryptoSealService.compute_canonical_hash(export_data)
    export_data["crypto_hash"] = crypto_hash
    return export_data


class ExportDossierPdfUseCase:
    """Caso de uso: Generar dictamen crediticio formal en PDF con sello criptográfico."""

    def __init__(
        self,
        repository: IUnderwritingRepository,
        pdf_generator: PdfDossierGenerator | None = None,
    ) -> None:
        self.repository = repository
        self.pdf_generator = pdf_generator or PdfDossierGenerator()

    async def execute(self, application_id: str) -> tuple[bytes, str]:
        """Retorna la tupla (pdf_bytes, filename)."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        data = prepare_export_payload(record, application_id)
        pdf_bytes = self.pdf_generator.generate(data)
        filename = f"dictamen-credito-{application_id}.pdf"
        return pdf_bytes, filename


class ExportFinancialExcelUseCase:
    """Caso de uso: Generar planilla financiera viva en formato Excel (.xlsx)."""

    def __init__(
        self,
        repository: IUnderwritingRepository,
        excel_generator: ExcelFinancialGenerator | None = None,
    ) -> None:
        self.repository = repository
        self.excel_generator = excel_generator or ExcelFinancialGenerator()

    async def execute(self, application_id: str) -> tuple[bytes, str]:
        """Retorna la tupla (excel_bytes, filename)."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        data = prepare_export_payload(record, application_id)
        excel_bytes = self.excel_generator.generate(data)
        filename = f"modelo-financiero-{application_id}.xlsx"
        return excel_bytes, filename


@dataclass(frozen=True)
class SealVerificationResult:
    """Resultado de la verificación de autenticidad e integridad."""

    application_id: str
    expected_hash: str
    provided_hash: str | None
    is_authentic: bool
    verified_at: str


class VerifyIntegritySealUseCase:
    """Caso de uso: Auditar integridad y no-repudio bancario mediante SHA-256."""

    def __init__(self, repository: IUnderwritingRepository) -> None:
        self.repository = repository

    async def execute(
        self, application_id: str, provided_hash: str | None
    ) -> SealVerificationResult:
        """Compara el hash canónico actual contra el provisto o certifica el actual."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        data = prepare_export_payload(record, application_id)
        canonical_hash = data["crypto_hash"]

        is_authentic = False
        if provided_hash:
            is_authentic = hmac.compare_digest(canonical_hash, provided_hash)
        else:
            is_authentic = True

        return SealVerificationResult(
            application_id=application_id,
            expected_hash=canonical_hash,
            provided_hash=provided_hash,
            is_authentic=is_authentic,
            verified_at=datetime.now(UTC).isoformat(),
        )
