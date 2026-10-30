"""Contenedor de Inyección de Dependencias / Composition Root (Arquitectura Hexagonal).

Ensambla los adaptadores concretos de infraestructura con los casos de uso de aplicación,
permitiendo que los controladores de FastAPI dependan únicamente de los casos de uso (SRP / DIP).
"""

import os
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.use_cases.export_dossier import (
    ExportDossierPdfUseCase,
    ExportFinancialExcelUseCase,
    VerifyIntegritySealUseCase,
)
from src.application.use_cases.get_underwriting import (
    GetUnderwritingByIdUseCase,
    ListUnderwritingsUseCase,
)
from src.application.use_cases.ingest_document import IngestFinancialDocumentUseCase
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
from src.application.use_cases.start_underwriting import StartUnderwritingUseCase
from src.application.use_cases.stress_test_underwriting import (
    GetStressTestAnalysisUseCase,
    StressTestUnderwritingUseCase,
)
from src.application.use_cases.submit_human_review import SubmitHumanReviewUseCase
from src.domain.events import IEventPublisher
from src.domain.ports import IObservabilityTracker, RiskAuditorProtocol
from src.domain.repositories import IUnderwritingRepository
from src.domain.vector_search import (
    IEmbeddingGenerator,
    IVectorSearchRepository,
    MockVectorSearchRepository,
)
from src.domain.workflow import create_underwriting_graph
from src.infrastructure.aws_sns_adapter import get_event_publisher
from src.infrastructure.database import async_session_factory
from src.infrastructure.embedding_adapter import get_embedding_generator
from src.infrastructure.gemini_adapter import GeminiRiskAuditor, MockGeminiAuditor
from src.infrastructure.observability import get_observability_tracker
from src.infrastructure.repositories import (
    InMemoryUnderwritingRepository,
    PostgresUnderwritingRepository,
)
from src.infrastructure.vector_repository import PostgresVectorSearchRepository

# Instancias compartidas para entornos de sesión / fallback
_checkpointer = MemorySaver()
_fallback_repo = InMemoryUnderwritingRepository()
_fallback_vector_repo = MockVectorSearchRepository()


async def get_optional_db_session() -> AsyncGenerator[AsyncSession | None, None]:
    """Generador seguro de sesión de base de datos que no falla en testing offline o sin DB local."""
    if os.getenv("TESTING") == "true":
        yield None
        return

    session = None
    try:
        session = async_session_factory()
        await session.connection()
    except Exception:
        if session is not None:
            await session.close()
        yield None
        return

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()



def get_underwriting_repository(
    session: Annotated[AsyncSession | None, Depends(get_optional_db_session)],
) -> IUnderwritingRepository:
    """Resuelve la implementación de persistencia adecuada."""
    if session is not None and os.getenv("TESTING") != "true":
        return PostgresUnderwritingRepository(session)
    return _fallback_repo


def get_risk_auditor(
    tracker: Annotated[IObservabilityTracker, Depends(get_observability_tracker)],
) -> RiskAuditorProtocol:
    """Resuelve el auditor cualitativo (Gemini en producción o Mock en testing)."""
    if os.getenv("TESTING") == "true":
        return MockGeminiAuditor(tracker=tracker)

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key and api_key != "your_gemini_api_key_here":
        return GeminiRiskAuditor(api_key=api_key, tracker=tracker)
    return MockGeminiAuditor(tracker=tracker)


def get_embedding_generator_dep() -> IEmbeddingGenerator:
    """Resuelve el generador de representaciones vectoriales."""
    return get_embedding_generator()


def get_event_publisher_dep() -> IEventPublisher:
    """Resuelve el bus de publicación de eventos reactivos."""
    return get_event_publisher()


def get_vector_search_repository(
    session: Annotated[AsyncSession | None, Depends(get_optional_db_session)],
    embedder: Annotated[IEmbeddingGenerator, Depends(get_embedding_generator_dep)],
) -> IVectorSearchRepository:
    """Resuelve el repositorio de búsqueda vectorial de precedentes."""
    if session is not None and os.getenv("TESTING") != "true":
        return PostgresVectorSearchRepository(session, embedder=embedder)
    return _fallback_vector_repo


def get_workflow_graph(
    auditor: Annotated[RiskAuditorProtocol, Depends(get_risk_auditor)],
    vector_repo: Annotated[IVectorSearchRepository, Depends(get_vector_search_repository)],
    embedder: Annotated[IEmbeddingGenerator, Depends(get_embedding_generator_dep)],
    tracker: Annotated[IObservabilityTracker, Depends(get_observability_tracker)],
) -> Any:
    """Ensambla el StateGraph determinístico de LangGraph con todos sus puertos."""
    return create_underwriting_graph(
        auditor=auditor,
        checkpointer=_checkpointer,
        vector_repo=vector_repo,
        embedder=embedder,
        tracker=tracker,
    )


# -------------------------------------------------------------------------
# Proveedores de Casos de Uso (Application Layer)
# -------------------------------------------------------------------------


def get_start_underwriting_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
    graph: Annotated[Any, Depends(get_workflow_graph)],
    tracker: Annotated[IObservabilityTracker, Depends(get_observability_tracker)],
    publisher: Annotated[IEventPublisher, Depends(get_event_publisher_dep)],
) -> StartUnderwritingUseCase:
    """Construye StartUnderwritingUseCase."""
    return StartUnderwritingUseCase(
        repository=repo,
        graph=graph,
        tracker=tracker,
        event_publisher=publisher,
    )


def get_submit_human_review_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
    graph: Annotated[Any, Depends(get_workflow_graph)],
    tracker: Annotated[IObservabilityTracker, Depends(get_observability_tracker)],
    publisher: Annotated[IEventPublisher, Depends(get_event_publisher_dep)],
) -> SubmitHumanReviewUseCase:
    """Construye SubmitHumanReviewUseCase."""
    return SubmitHumanReviewUseCase(
        repository=repo,
        graph=graph,
        tracker=tracker,
        event_publisher=publisher,
    )


def get_underwriting_by_id_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
) -> GetUnderwritingByIdUseCase:
    """Construye GetUnderwritingByIdUseCase."""
    return GetUnderwritingByIdUseCase(repository=repo)


def get_list_underwritings_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
) -> ListUnderwritingsUseCase:
    """Construye ListUnderwritingsUseCase."""
    return ListUnderwritingsUseCase(repository=repo)


def get_export_dossier_pdf_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
) -> ExportDossierPdfUseCase:
    """Construye ExportDossierPdfUseCase."""
    return ExportDossierPdfUseCase(repository=repo)


def get_export_financial_excel_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
) -> ExportFinancialExcelUseCase:
    """Construye ExportFinancialExcelUseCase."""
    return ExportFinancialExcelUseCase(repository=repo)


def get_verify_integrity_seal_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
) -> VerifyIntegritySealUseCase:
    """Construye VerifyIntegritySealUseCase."""
    return VerifyIntegritySealUseCase(repository=repo)


def get_ingest_document_use_case(
    auditor: Annotated[RiskAuditorProtocol, Depends(get_risk_auditor)],
) -> IngestFinancialDocumentUseCase:
    """Construye IngestFinancialDocumentUseCase."""
    return IngestFinancialDocumentUseCase(risk_auditor=auditor)


def get_stress_test_underwriting_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
) -> StressTestUnderwritingUseCase:
    """Construye StressTestUnderwritingUseCase (SPEC-10)."""
    return StressTestUnderwritingUseCase(repository=repo)


def get_get_stress_test_analysis_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
    simulator: Annotated[StressTestUnderwritingUseCase, Depends(get_stress_test_underwriting_use_case)],
) -> GetStressTestAnalysisUseCase:
    """Construye GetStressTestAnalysisUseCase (SPEC-10)."""
    return GetStressTestAnalysisUseCase(repository=repo, simulator_use_case=simulator)


def get_register_collaterals_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
) -> RegisterCollateralsUseCase:
    """Construye RegisterCollateralsUseCase (SPEC-11)."""
    return RegisterCollateralsUseCase(repository=repo)


def get_get_collateral_analysis_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
    register_use_case: Annotated[RegisterCollateralsUseCase, Depends(get_register_collaterals_use_case)],
) -> GetCollateralAnalysisUseCase:
    """Construye GetCollateralAnalysisUseCase (SPEC-11)."""
    return GetCollateralAnalysisUseCase(repository=repo, register_use_case=register_use_case)


def get_generate_pricing_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
) -> GeneratePricingUseCase:
    """Construye GeneratePricingUseCase (SPEC-12)."""
    return GeneratePricingUseCase(repository=repo)


def get_get_pricing_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
    generate_use_case: Annotated[GeneratePricingUseCase, Depends(get_generate_pricing_use_case)],
) -> GetPricingUseCase:
    """Construye GetPricingUseCase (SPEC-12)."""
    return GetPricingUseCase(repository=repo, generate_use_case=generate_use_case)


def get_evaluate_governance_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
) -> EvaluateGovernanceLevelUseCase:
    """Construye EvaluateGovernanceLevelUseCase (SPEC-13)."""
    return EvaluateGovernanceLevelUseCase(repository=repo)


def get_cast_committee_vote_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
    evaluate_use_case: Annotated[EvaluateGovernanceLevelUseCase, Depends(get_evaluate_governance_use_case)],
) -> CastCommitteeVoteUseCase:
    """Construye CastCommitteeVoteUseCase (SPEC-13)."""
    return CastCommitteeVoteUseCase(repository=repo, evaluate_use_case=evaluate_use_case)


def get_get_committee_resolution_use_case(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
    evaluate_use_case: Annotated[EvaluateGovernanceLevelUseCase, Depends(get_evaluate_governance_use_case)],
) -> GetCommitteeResolutionUseCase:
    """Construye GetCommitteeResolutionUseCase (SPEC-13)."""
    return GetCommitteeResolutionUseCase(repository=repo, evaluate_use_case=evaluate_use_case)



