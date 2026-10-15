"""Router de FastAPI para evaluación crediticia (SPEC-01 a SPEC-06)."""

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
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
from src.bot.telegram_notifier import TelegramNotifier
from src.domain.crypto_seal import CryptoSealService
from src.domain.events import (
    CreditEventType,
    CreditUnderwritingEvent,
    EventSeverity,
    IEventPublisher,
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
from src.infrastructure.aws_sns_adapter import (
    get_event_publisher,
    global_event_broadcaster,
)
from src.infrastructure.database import get_db_session
from src.infrastructure.embedding_adapter import get_embedding_generator
from src.infrastructure.excel_generator import ExcelFinancialGenerator
from src.infrastructure.gemini_adapter import (
    GeminiRiskAuditor,
    MockGeminiAuditor,
    RiskAuditorProtocol,
)
from src.infrastructure.observability import (
    IObservabilityTracker,
    get_observability_tracker,
)
from src.infrastructure.pdf_generator import PdfDossierGenerator
from src.infrastructure.vector_repository import PostgresVectorSearchRepository

router = APIRouter(tags=["Credit Underwriting"])

# Checkpointer persistente en memoria para la sesión de la API
_checkpointer = MemorySaver()
_fallback_repo = InMemoryUnderwritingRepository()
_fallback_vector_repo = MockVectorSearchRepository()
_telegram_notifier = TelegramNotifier()


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


def get_event_publisher_dep() -> IEventPublisher:
    """Inyector de dependencias para el publicador de eventos en tiempo real (AWS SNS)."""
    return get_event_publisher()


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


@router.get(
    "/events",
    summary="Streaming de eventos crediticios en tiempo real (SSE)",
    description="Transmite eventos del ciclo de vida crediticio vía Server-Sent Events (SPEC-06).",
)
async def stream_underwriting_events() -> StreamingResponse:
    async def event_generator():
        # Suscribir la cola antes del yield para que esté lista para recibir eventos
        queue = global_event_broadcaster.create_subscription()
        try:
            # Heartbeat inicial para confirmar handshake y apertura del canal SSE
            yield ": ping\n\n"
            while True:
                event = await queue.get()
                yield event.to_sse_message()
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            global_event_broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
    background_tasks: BackgroundTasks,
    graph: Annotated[Any, Depends(get_workflow_graph)],
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
    tracker: Annotated[IObservabilityTracker, Depends(get_observability_tracker)],
    publisher: Annotated[IEventPublisher, Depends(get_event_publisher_dep)],
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

    # 6. Publicación reactiva de eventos y alertas (SPEC-06: AWS SNS + Telegram + SSE)
    is_critical = False
    if metrics_data:
        has_critical_anomaly = any(
            flag in metrics_data.get("anomaly_flags", [])
            for flag in [
                "FLAG_DEFICIT_DSCR",
                "FLAG_NEGATIVE_OPERATING_CASH_FLOW",
                "FLAG_OVERDRAFT_DETECTED",
                "ALERTA_RAG_PRECEDENTE_HISTORICO_DEFAULT",
            ]
        )
        if not metrics_data.get("is_solvent") or has_critical_anomaly:
            is_critical = True

    event_severity = EventSeverity.CRITICAL if is_critical else EventSeverity.WARNING
    event_type = (
        CreditEventType.CRITICAL_RISK_DETECTED
        if is_critical
        else CreditEventType.PENDING_HUMAN_REVIEW
    )

    verdict_summary = "Solicitud en espera de resolución de comité."
    recommendation = "PENDIENTE"
    if verdict_data:
        verdict_summary = verdict_data.get("executive_summary", verdict_summary)
        recommendation = verdict_data.get("recommendation", recommendation)

    credit_event = CreditUnderwritingEvent(
        event_type=event_type,
        severity=event_severity,
        application_id=application_id,
        associated_id=payload.associated_id,
        business_name=payload.business_name,
        summary=verdict_summary,
        payload={
            "requested_amount_usd": payload.requested_amount_usd,
            "term_months": payload.term_months,
            "dscr": metrics_data.get("dscr") if metrics_data else None,
            "anomaly_flags": metrics_data.get("anomaly_flags", []) if metrics_data else [],
            "recommendation": recommendation,
        },
    )

    await publisher.publish_event(credit_event)
    background_tasks.add_task(_telegram_notifier.send_risk_alert, credit_event)

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
    background_tasks: BackgroundTasks,
    graph: Annotated[Any, Depends(get_workflow_graph)],
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
    tracker: Annotated[IObservabilityTracker, Depends(get_observability_tracker)],
    publisher: Annotated[IEventPublisher, Depends(get_event_publisher_dep)],
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

    # Publicar evento de resolución final (SPEC-06: AWS SNS + Telegram + SSE)
    resolution_severity = EventSeverity.INFO if payload.approved else EventSeverity.WARNING
    resolution_status = "APROBADO" if payload.approved else "RECHAZADO"
    resolution_event = CreditUnderwritingEvent(
        event_type=CreditEventType.HUMAN_RESOLVED,
        severity=resolution_severity,
        application_id=application_id,
        associated_id=record.get("associated_id", ""),
        business_name=record.get("business_name", ""),
        summary=(
            f"Resolución de oficial de crédito: {resolution_status}. Condiciones: {payload.notes}"
        ),
        payload={
            "approved": payload.approved,
            "notes": payload.notes,
            "requested_amount_usd": record.get("requested_amount_usd", 0.0),
            "recommendation": resolution_status,
        },
    )

    await publisher.publish_event(resolution_event)
    background_tasks.add_task(_telegram_notifier.send_risk_alert, resolution_event)

    return _format_underwrite_response(application_id, final_snapshot.values)


def _prepare_export_data(record: dict[str, Any], app_id: str) -> dict[str, Any]:
    """Extrae y normaliza los datos canónicos necesarios para renderizar y sellar el legajo."""
    metrics_obj = record.get("metrics") or {}
    metrics_dict = {}
    if isinstance(metrics_obj, dict):
        dscr_val = metrics_obj.get("dscr")
        if dscr_val is None and "dscr_result" in metrics_obj:
            dscr_val = metrics_obj["dscr_result"].get("dscr")
        metrics_dict = {
            "dscr": dscr_val,
            "current_ratio": metrics_obj.get("current_ratio", 0.0),
            "runway_months": metrics_obj.get("runway_months"),
            "operating_cash_flow": metrics_obj.get("operating_cash_flow", 0.0),
            "annual_debt_service": metrics_obj.get("annual_debt_service", 0.0),
            "is_debt_free": metrics_obj.get("is_debt_free", False),
        }
    elif hasattr(metrics_obj, "dscr_result"):
        metrics_dict = {
            "dscr": metrics_obj.dscr_result.dscr,
            "current_ratio": metrics_obj.current_ratio,
            "runway_months": metrics_obj.runway_months,
            "operating_cash_flow": getattr(metrics_obj, "operating_cash_flow", 0.0),
            "annual_debt_service": getattr(metrics_obj, "annual_debt_service", 0.0),
            "is_debt_free": metrics_obj.dscr_result.is_debt_free,
        }

    precedents = []
    for p in record.get("historical_precedents") or []:
        if isinstance(p, dict):
            precedents.append(p)
        elif hasattr(p, "to_dict"):
            precedents.append(p.to_dict())

    raw_fin = record.get("financial_data") or record.get("raw_financials") or {}
    ai_v = record.get("ai_verdict") or {}
    if hasattr(ai_v, "model_dump"):
        ai_v = ai_v.model_dump()

    export_data = {
        "id": app_id,
        "associated_id": record.get("associated_id", "N/A"),
        "business_name": record.get("business_name", "N/A"),
        "requested_amount_usd": float(record.get("requested_amount_usd", 0.0)),
        "term_months": int(record.get("term_months", 0)),
        "created_at": str(record.get("created_at", "N/A")),
        "metrics": metrics_dict,
        "ai_verdict": ai_v,
        "precedents": precedents,
        "raw_financials": raw_fin,
    }

    crypto_hash = CryptoSealService.compute_canonical_hash(export_data)
    export_data["crypto_hash"] = crypto_hash
    return export_data


@router.get(
    "/{application_id}/export/pdf",
    summary="Exportar dictamen formal en PDF bancario",
    description=(
        "Genera el acta oficial de dictamen crediticio con sello criptográfico "
        "de integridad SHA-256."
    ),
)
async def export_pdf(
    application_id: str,
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
) -> Response:
    record = await repo.get_by_id(application_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la solicitud de crédito con ID: {application_id}",
        )
    data = _prepare_export_data(record, application_id)
    pdf_bytes = PdfDossierGenerator().generate(data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="dictamen-credito-{application_id}.pdf"'
        },
    )


@router.get(
    "/{application_id}/export/excel",
    summary="Exportar planilla de trabajo financiero en Excel (.xlsx)",
    description="Genera el libro de cálculo financiero con fórmulas vivas de liquidez y cobertura.",
)
async def export_excel(
    application_id: str,
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
) -> Response:
    record = await repo.get_by_id(application_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la solicitud de crédito con ID: {application_id}",
        )
    data = _prepare_export_data(record, application_id)
    excel_bytes = ExcelFinancialGenerator().generate(data)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="modelo-financiero-{application_id}.xlsx"'
        },
    )


@router.get(
    "/{application_id}/verify-seal",
    summary="Verificar autenticidad del sello criptográfico",
    description="Calcula el hash canónico actual y lo compara contra el hash proporcionado.",
)
async def verify_seal(
    application_id: str,
    repo: Annotated[IUnderwritingRepository, Depends(get_underwriting_repository)],
    hash: str | None = Query(default=None, description="Hash SHA-256 a validar"),
) -> dict[str, Any]:
    record = await repo.get_by_id(application_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la solicitud de crédito con ID: {application_id}",
        )
    data = _prepare_export_data(record, application_id)
    canonical_hash = data["crypto_hash"]
    is_authentic = False
    if hash:
        import hmac

        is_authentic = hmac.compare_digest(canonical_hash, hash)
    else:
        is_authentic = True

    return {
        "application_id": application_id,
        "expected_hash": canonical_hash,
        "provided_hash": hash,
        "is_authentic": is_authentic,
        "verified_at": datetime.now(UTC).isoformat(),
    }

