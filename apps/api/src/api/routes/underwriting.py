"""Router de FastAPI para evaluación y suscripción crediticia (SPEC-01)."""

import os
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from langgraph.checkpoint.memory import MemorySaver

from src.api.schemas import (
    HumanReviewRequestSchema,
    MetricsSummarySchema,
    UnderwriteRequestSchema,
    UnderwriteResponseSchema,
)
from src.domain.state import CreditUnderwritingState
from src.domain.workflow import create_underwriting_graph
from src.infrastructure.gemini_adapter import (
    GeminiRiskAuditor,
    MockGeminiAuditor,
    RiskAuditorProtocol,
)

router = APIRouter(prefix="/underwrite", tags=["Credit Underwriting"])

# Checkpointer persistente en memoria para la sesión de la API
_checkpointer = MemorySaver()


def get_risk_auditor() -> RiskAuditorProtocol:
    """Retorna el auditor real si existe GEMINI_API_KEY configurada y no estamos en test."""
    if os.getenv("TESTING") == "true":
        return MockGeminiAuditor()

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key and api_key != "your_gemini_api_key_here":
        return GeminiRiskAuditor(api_key=api_key)
    return MockGeminiAuditor()


def get_workflow_graph(
    auditor: Annotated[RiskAuditorProtocol, Depends(get_risk_auditor)],
):
    """Retorna la instancia del grafo compilado con el checkpointer activo."""
    return create_underwriting_graph(auditor=auditor, checkpointer=_checkpointer)


def _format_underwrite_response(app_id: str, values: dict[str, Any]) -> UnderwriteResponseSchema:
    """Convierte el diccionario de valores del StateGraph en el esquema de respuesta."""
    metrics_summary = None
    metrics_obj = values.get("metrics")
    if metrics_obj:
        metrics_summary = MetricsSummarySchema(
            dscr=metrics_obj.dscr_result.dscr,
            current_ratio=metrics_obj.current_ratio,
            runway_months=metrics_obj.runway_months,
            is_solvent=metrics_obj.dscr_result.is_solvent,
            is_debt_free=metrics_obj.dscr_result.is_debt_free,
            anomaly_flags=metrics_obj.anomaly_flags,
        )

    return UnderwriteResponseSchema(
        application_id=app_id,
        associated_id=values.get("associated_id", ""),
        business_name=values.get("business_name", ""),
        current_step=values.get("current_step", "INITIALIZED"),
        is_completed=values.get("is_completed", False),
        metrics=metrics_summary,
        ai_verdict=values.get("ai_verdict"),
        human_approved=values.get("human_approved"),
        human_notes=values.get("human_notes"),
        errors=values.get("errors", []),
    )


@router.post(
    "",
    response_model=UnderwriteResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar evaluación crediticia",
    description="Ejecuta el StateGraph hasta pausar en PENDING_HUMAN_REVIEW.",
)
async def start_underwriting(
    payload: UnderwriteRequestSchema,
    graph: Annotated[Any, Depends(get_workflow_graph)],
) -> UnderwriteResponseSchema:
    application_id = f"APP-{uuid.uuid4().hex[:8].upper()}"
    config = {"configurable": {"thread_id": application_id}}

    initial_state: CreditUnderwritingState = {
        "application_id": application_id,
        "associated_id": payload.associated_id,
        "business_name": payload.business_name,
        "requested_amount_usd": payload.requested_amount_usd,
        "term_months": payload.term_months,
        "raw_financials": payload.financial_data.model_dump(),
    }

    await graph.ainvoke(initial_state, config=config)

    snapshot = await graph.aget_state(config)
    return _format_underwrite_response(application_id, snapshot.values)


@router.get(
    "/{application_id}",
    response_model=UnderwriteResponseSchema,
    summary="Consultar estado de la solicitud",
    description="Retorna el snapshot actual de la evaluación crediticia.",
)
async def get_underwriting_status(
    application_id: str,
    graph: Annotated[Any, Depends(get_workflow_graph)],
) -> UnderwriteResponseSchema:
    config = {"configurable": {"thread_id": application_id}}
    snapshot = await graph.aget_state(config)

    if not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la solicitud de crédito con ID: {application_id}",
        )

    return _format_underwrite_response(application_id, snapshot.values)


@router.post(
    "/{application_id}/review",
    response_model=UnderwriteResponseSchema,
    summary="Emitir resolución del oficial de crédito",
    description=(
        "Reanuda la ejecución del StateGraph tras la intervención humana y finaliza el crédito."
    ),
)
async def submit_human_review(
    application_id: str,
    payload: HumanReviewRequestSchema,
    graph: Annotated[Any, Depends(get_workflow_graph)],
) -> UnderwriteResponseSchema:
    config = {"configurable": {"thread_id": application_id}}
    snapshot = await graph.aget_state(config)

    if not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la solicitud de crédito con ID: {application_id}",
        )

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
    return _format_underwrite_response(application_id, final_snapshot.values)
