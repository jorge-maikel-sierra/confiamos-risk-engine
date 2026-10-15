"""Router de FastAPI para evaluación y suscripción crediticia (SPEC-01, SPEC-02 y SPEC-05)."""

import os
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    HistoricalPrecedentSchema,
    HumanReviewRequestSchema,
    MetricsSummarySchema,
    PaginatedUnderwritingListSchema,
    UnderwriteRequestSchema,
    UnderwriteResponseSchema,
)
from src.domain.repositories import (
    InMemoryUnderwritingRepository,
    IUnderwritingRepository,
    PostgresUnderwritingRepository,
)
from src.domain.state import CreditUnderwritingState
from src.domain.vector_search import (
    IEmbeddingGenerator,
    IVectorSearchRepository,
    MockVectorSearchRepository,
)
from src.domain.workflow import create_underwriting_graph
from src.infrastructure.database import get_db_session
from src.infrastructure.embedding_adapter import get_embedding_generator
from src.infrastructure.gemini_adapter import (
    GeminiRiskAuditor,
    MockGeminiAuditor,
    RiskAuditorProtocol,
)
from src.infrastructure.observability import (
    IObservabilityTracker,
    get_observability_tracker,
)
from src.infrastructure.vector_repository import PostgresVectorSearchRepository

router = APIRouter(tags=["Credit Underwriting"])

# Checkpointer persistente en memoria para la sesión de la API
_checkpointer = MemorySaver()
_fallback_repo = InMemoryUnderwritingRepository()
_fallback_vector_repo = MockVectorSearchRepository()


def get_risk_auditor(
    tracker: Annotated[IObservabilityTracker, Depends(get_observability_tracker)],
) -> RiskAuditorProtocol:
    """Retorna el auditor real si existe GEMINI_API_KEY configurada y no estamos en test."""
    if os.getenv("TESTING") == "true":
        return MockGeminiAuditor(tracker=tracker)

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key and api_key != "your_gemini_api_key_here":
        return GeminiRiskAuditor(api_key=api_key, tracker=tracker)
    return MockGeminiAuditor(tracker=tracker)


def get_embedding_generator_dep() -> IEmbeddingGenerator:
    """Inyector de dependencias para el generador de embeddings."""
    return get_embedding_generator()


async def get_optional_db_session() -> AsyncGenerator[AsyncSession | None, None]:
    """Generador seguro de sesión de BD que no falla en entornos de pruebas offline."""
    if os.getenv("TESTING") == "true":
        yield None
        return

    try:
        async for session in get_db_session():
            yield session
    except Exception:
        yield None


async def get_underwriting_repository(
    session: Annotated[AsyncSession | None, Depends(get_optional_db_session)],
) -> IUnderwritingRepository:
    """Inyector de dependencias para el repositorio desacoplado."""
    if session is not None and os.getenv("TESTING") != "true":
        return PostgresUnderwritingRepository(session)
    return _fallback_repo


async def get_vector_search_repository(
    session: Annotated[AsyncSession | None, Depends(get_optional_db_session)],
    embedder: Annotated[IEmbeddingGenerator, Depends(get_embedding_generator_dep)],
) -> IVectorSearchRepository:
    """Inyector de dependencias para el repositorio de búsqueda vectorial."""
    if session is not None and os.getenv("TESTING") != "true":
        return PostgresVectorSearchRepository(session, embedder=embedder)
    return _fallback_vector_repo


def get_workflow_graph(
    auditor: Annotated[RiskAuditorProtocol, Depends(get_risk_auditor)],
    vector_repo: Annotated[IVectorSearchRepository, Depends(get_vector_search_repository)],
    embedder: Annotated[IEmbeddingGenerator, Depends(get_embedding_generator_dep)],
    tracker: Annotated[IObservabilityTracker, Depends(get_observability_tracker)],
):
    """Retorna la instancia del grafo compilado con checkpointer y RAG vectorial."""
    return create_underwriting_graph(
        auditor=auditor,
        checkpointer=_checkpointer,
        vector_repo=vector_repo,
        embedder=embedder,
        tracker=tracker,
    )


def _format_underwrite_response(app_id: str, values: dict[str, Any]) -> UnderwriteResponseSchema:
    """Convierte el diccionario de valores o entidad relacional en el esquema de respuesta."""
    metrics_summary = None
    metrics_obj = values.get("metrics")
    if metrics_obj:
        if isinstance(metrics_obj, dict):
            dscr_val = metrics_obj.get("dscr")
            if dscr_val is None and "dscr_result" in metrics_obj:
                dscr_val = metrics_obj["dscr_result"].get("dscr")

            is_solvent = metrics_obj.get("is_solvent", False)
            if "dscr_result" in metrics_obj:
                is_solvent = metrics_obj["dscr_result"].get("is_solvent", False)

            is_debt_free = metrics_obj.get("is_debt_free", False)
            if "dscr_result" in metrics_obj:
                is_debt_free = metrics_obj["dscr_result"].get("is_debt_free", False)

            metrics_summary = MetricsSummarySchema(
                dscr=dscr_val,
                current_ratio=metrics_obj.get("current_ratio"),
                runway_months=metrics_obj.get("runway_months"),
                is_solvent=is_solvent,
                is_debt_free=is_debt_free,
                anomaly_flags=metrics_obj.get("anomaly_flags", []),
            )
        else:
            metrics_summary = MetricsSummarySchema(
                dscr=metrics_obj.dscr_result.dscr,
                current_ratio=metrics_obj.current_ratio,
                runway_months=metrics_obj.runway_months,
                is_solvent=metrics_obj.dscr_result.is_solvent,
                is_debt_free=metrics_obj.dscr_result.is_debt_free,
                anomaly_flags=metrics_obj.anomaly_flags,
            )

    historical_precedents: list[HistoricalPrecedentSchema] = []
    raw_precs = values.get("historical_precedents") or []
    for item in raw_precs:
        if isinstance(item, HistoricalPrecedentSchema):
            historical_precedents.append(item)
        elif hasattr(item, "to_dict"):
            historical_precedents.append(HistoricalPrecedentSchema(**item.to_dict()))
        elif isinstance(item, dict):
            historical_precedents.append(HistoricalPrecedentSchema(**item))

    return UnderwriteResponseSchema(
        application_id=app_id,
        associated_id=values.get("associated_id", ""),
        business_name=values.get("business_name", ""),
        sector=values.get("sector", "Comercio y Servicios"),
        current_step=values.get("current_step", "INITIALIZED"),
        is_completed=values.get("is_completed", False),
        metrics=metrics_summary,
        ai_verdict=values.get("ai_verdict"),
        historical_precedents=historical_precedents,
        human_approved=values.get("human_approved"),
        human_notes=values.get("human_notes"),
        errors=values.get("errors", []),
    )


@router.post(
    "",
    response_model=UnderwriteResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar evaluación crediticia",
    description=(
        "Persiste la solicitud y ejecuta el StateGraph hasta pausar en PENDING_HUMAN_REVIEW."
    ),
)
async def start_underwriting(
    payload: UnderwriteRequestSchema,
    graph: Annotated[Any, Depends(get_workflow_graph)],
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
    tracker: Annotated[IObservabilityTracker, Depends(get_observability_tracker)],
) -> UnderwriteResponseSchema:
    application_id = f"APP-{uuid.uuid4().hex[:8].upper()}"
    config = {"configurable": {"thread_id": application_id}}

    # 1. Iniciar traza de observabilidad en Langfuse
    tracker.trace_start(
        application_id=application_id,
        associated_id=payload.associated_id,
        business_name=payload.business_name,
        requested_amount_usd=payload.requested_amount_usd,
        term_months=payload.term_months,
    )

    # 2. Registrar solicitud inicial en repositorio
    await repo.create_application(
        application_id=application_id,
        associated_id=payload.associated_id,
        business_name=payload.business_name,
        requested_amount_usd=payload.requested_amount_usd,
        term_months=payload.term_months,
        raw_financials=payload.financial_data.model_dump(),
    )

    initial_state: CreditUnderwritingState = {
        "application_id": application_id,
        "associated_id": payload.associated_id,
        "business_name": payload.business_name,
        "sector": payload.sector,
        "requested_amount_usd": payload.requested_amount_usd,
        "term_months": payload.term_months,
        "raw_financials": payload.financial_data.model_dump(),
    }

    # 3. Ejecutar StateGraph hasta la interrupción (incluye cálculo, pgvector y auditoría)
    await graph.ainvoke(initial_state, config=config)
    snapshot = await graph.aget_state(config)

    # 4. Serializar y actualizar snapshot en la base de datos
    metrics_data = None
    if snapshot.values.get("metrics"):
        m = snapshot.values["metrics"]
        metrics_data = {
            "dscr": m.dscr_result.dscr,
            "is_solvent": m.dscr_result.is_solvent,
            "is_debt_free": m.dscr_result.is_debt_free,
            "current_ratio": m.current_ratio,
            "runway_months": m.runway_months,
            "anomaly_flags": m.anomaly_flags,
        }

    verdict_data = None
    if snapshot.values.get("ai_verdict"):
        v = snapshot.values["ai_verdict"]
        verdict_data = v.model_dump() if hasattr(v, "model_dump") else v

    precedents_data = None
    if snapshot.values.get("historical_precedents"):
        precs = snapshot.values["historical_precedents"]
        precedents_data = [p.to_dict() if hasattr(p, "to_dict") else p for p in precs]

    await repo.update_snapshot(
        application_id=application_id,
        current_step=snapshot.values.get("current_step", "PENDING_HUMAN_REVIEW"),
        metrics=metrics_data,
        ai_verdict=verdict_data,
        historical_precedents=precedents_data,
    )

    # 5. Registrar span de cálculo determinístico y actualizar output del ciclo de vida
    if metrics_data:
        tracker.record_span(
            application_id=application_id,
            name="compute_financial_metrics",
            input=payload.financial_data.model_dump(),
            output=metrics_data,
            as_type="tool",
        )

    tracker.update_trace_output(
        application_id=application_id,
        output={
            "current_step": snapshot.values.get("current_step", "PENDING_HUMAN_REVIEW"),
            "ai_verdict": verdict_data,
            "is_completed": snapshot.values.get("is_completed", False),
        },
    )

    return _format_underwrite_response(application_id, snapshot.values)


@router.get(
    "",
    response_model=PaginatedUnderwritingListSchema,
    summary="Bandeja de solicitudes de crédito",
    description="Retorna la lista paginada de solicitudes con opción de filtrado por estado.",
)
async def list_underwritings(
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
    limit: int = Query(default=20, ge=1, le=100, description="Cantidad máxima de registros"),
    offset: int = Query(default=0, ge=0, description="Desplazamiento inicial"),
    status_filter: str | None = Query(
        default=None, alias="status", description="Filtrar por estado del workflow"
    ),
) -> PaginatedUnderwritingListSchema:
    records = await repo.list_applications(limit=limit, offset=offset, status=status_filter)
    items = [_format_underwrite_response(r["application_id"], r) for r in records]
    return PaginatedUnderwritingListSchema(
        items=items,
        total=len(items),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{application_id}",
    response_model=UnderwriteResponseSchema,
    summary="Consultar estado de la solicitud",
    description="Retorna el snapshot persistido de la evaluación crediticia.",
)
async def get_underwriting_status(
    application_id: str,
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
) -> UnderwriteResponseSchema:
    record = await repo.get_by_id(application_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la solicitud de crédito con ID: {application_id}",
        )

    return _format_underwrite_response(application_id, record)


@router.post(
    "/{application_id}/review",
    response_model=UnderwriteResponseSchema,
    include_in_schema=False,
)
@router.post(
    "/{application_id}/reviews",
    response_model=UnderwriteResponseSchema,
    summary="Emitir resolución del oficial de crédito",
    description="Reanuda la ejecución del StateGraph y persiste la resolución en base de datos.",
)
async def submit_human_review(
    application_id: str,
    payload: HumanReviewRequestSchema,
    graph: Annotated[Any, Depends(get_workflow_graph)],
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
    tracker: Annotated[IObservabilityTracker, Depends(get_observability_tracker)],
) -> UnderwriteResponseSchema:
    record = await repo.get_by_id(application_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la solicitud de crédito con ID: {application_id}",
        )

    if record.get("is_completed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La solicitud {application_id} ya ha sido finalizada previamente.",
        )

    config = {"configurable": {"thread_id": application_id}}

    # Actualizar estado e intervenir como nodo human_review
    await graph.aupdate_state(
        config,
        {
            "human_approved": payload.approved,
            "human_notes": payload.notes,
        },
        as_node="human_review",
    )

    # Reanudar ejecución
    await graph.ainvoke(None, config=config)
    final_snapshot = await graph.aget_state(config)

    # Actualizar resolución en repositorio
    await repo.submit_human_review(
        application_id=application_id,
        approved=payload.approved,
        notes=payload.notes,
        current_step=final_snapshot.values.get("current_step", "COMPLETED"),
    )

    # Registrar score de aprobación humana en Langfuse
    tracker.record_human_score(
        application_id=application_id,
        approved=payload.approved,
        notes=payload.notes,
    )

    # Actualizar y finalizar output de la traza raíz
    tracker.update_trace_output(
        application_id=application_id,
        output={
            "current_step": final_snapshot.values.get("current_step", "COMPLETED"),
            "human_approved": payload.approved,
            "human_notes": payload.notes,
            "is_completed": final_snapshot.values.get("is_completed", True),
        },
    )

    return _format_underwrite_response(application_id, final_snapshot.values)
