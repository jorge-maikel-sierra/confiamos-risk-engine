"""Capa de Aplicación (Use Cases / Application Services).

Orquesta las operaciones de negocio interactuando únicamente con los puertos
del dominio y desacoplando completamente los adaptadores HTTP de la lógica.
"""

from src.application.exceptions import (
    ApplicationConflictError,
    ApplicationError,
    ApplicationNotFoundError,
    DocumentProcessingError,
)
from src.application.use_cases.export_dossier import (
    ExportDossierPdfUseCase,
    ExportFinancialExcelUseCase,
    SealVerificationResult,
    VerifyIntegritySealUseCase,
)
from src.application.use_cases.get_underwriting import (
    GetUnderwritingByIdUseCase,
    ListUnderwritingsQuery,
    ListUnderwritingsUseCase,
)
from src.application.use_cases.ingest_document import (
    IngestDocumentCommand,
    IngestFinancialDocumentUseCase,
)
from src.application.use_cases.manage_collaterals import (
    GetCollateralAnalysisUseCase,
    RegisterCollateralsUseCase,
)
from src.application.use_cases.manage_committee import (
    CastCommitteeVoteUseCase,
    EvaluateGovernanceLevelUseCase,
    GetCommitteeResolutionUseCase,
)
from src.application.use_cases.manage_pricing import (
    GeneratePricingUseCase,
    GetPricingUseCase,
)
from src.application.use_cases.start_underwriting import (
    StartUnderwritingCommand,
    StartUnderwritingUseCase,
)
from src.application.use_cases.stress_test_underwriting import (
    GetStressTestAnalysisUseCase,
    StressTestUnderwritingUseCase,
)
from src.application.use_cases.submit_human_review import (
    SubmitHumanReviewCommand,
    SubmitHumanReviewUseCase,
)

__all__ = [
    "ApplicationError",
    "ApplicationNotFoundError",
    "ApplicationConflictError",
    "DocumentProcessingError",
    "StartUnderwritingCommand",
    "StartUnderwritingUseCase",
    "SubmitHumanReviewCommand",
    "SubmitHumanReviewUseCase",
    "GetUnderwritingByIdUseCase",
    "ListUnderwritingsQuery",
    "ListUnderwritingsUseCase",
    "ExportDossierPdfUseCase",
    "ExportFinancialExcelUseCase",
    "SealVerificationResult",
    "VerifyIntegritySealUseCase",
    "IngestDocumentCommand",
    "IngestFinancialDocumentUseCase",
    "StressTestUnderwritingUseCase",
    "GetStressTestAnalysisUseCase",
    "RegisterCollateralsUseCase",
    "GetCollateralAnalysisUseCase",
    "GeneratePricingUseCase",
    "GetPricingUseCase",
    "EvaluateGovernanceLevelUseCase",
    "CastCommitteeVoteUseCase",
    "GetCommitteeResolutionUseCase",
]
