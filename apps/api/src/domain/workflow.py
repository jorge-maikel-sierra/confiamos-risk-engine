"""StateGraph de LangGraph para la evaluación y suscripción crediticia (SPEC-01 y SPEC-05).

Implementa la máquina de estados con:
- Ingesta y validación de balances
- Cálculo determinístico de métricas financieras
- Búsqueda semántica de precedentes históricos con pgvector (RAG crediticio)
- Auditoría cualitativa de riesgo con Gemini asistido por precedentes
- Checkpoint e interrupción para aprobación humana (Human-in-the-loop)
- Finalización y emisión del dictamen para Cooperativa Confiamos
"""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.domain.metrics import FinancialInput, evaluate_financial_health
from src.domain.state import CreditUnderwritingState
from src.domain.vector_search import (
    IEmbeddingGenerator,
    IVectorSearchRepository,
    MockEmbeddingGenerator,
    MockVectorSearchRepository,
    build_credit_profile_text,
)
from src.infrastructure.gemini_adapter import RiskAuditorProtocol
from src.infrastructure.observability import IObservabilityTracker


def create_underwriting_graph(
    auditor: RiskAuditorProtocol,
    checkpointer: BaseCheckpointSaver | None = None,
    vector_repo: IVectorSearchRepository | None = None,
    embedder: IEmbeddingGenerator | None = None,
    tracker: IObservabilityTracker | None = None,
):
    """Crea y compila el StateGraph de evaluación crediticia con RAG vectorial."""
    resolved_embedder = embedder or MockEmbeddingGenerator()
    resolved_vector_repo = vector_repo or MockVectorSearchRepository(embedder=resolved_embedder)

    # 1. Nodo de Ingesta y Validación
    async def validate_ingestion_node(state: CreditUnderwritingState) -> dict[str, Any]:
        raw = state.get("raw_financials", {})
        try:
            financial_input = FinancialInput(
                operating_cash_flow=float(raw.get("operating_cash_flow", 0.0)),
                annual_debt_service=float(raw.get("annual_debt_service", 0.0)),
                current_assets=float(raw.get("current_assets", 0.0)),
                current_liabilities=float(raw.get("current_liabilities", 0.0)),
                cash_balance=float(raw.get("cash_balance", 0.0)),
                monthly_burn_rate=float(raw.get("monthly_burn_rate", 0.0)),
                negative_balance_days=int(raw.get("negative_balance_days", 0)),
                top_client_revenue_percentage=float(raw.get("top_client_revenue_percentage", 0.0)),
            )
            return {
                "financial_input": financial_input,
                "current_step": "VALIDATED",
                "errors": [],
            }
        except Exception as exc:
            return {
                "financial_input": None,
                "current_step": "VALIDATION_FAILED",
                "errors": [f"Error de validación contable: {exc!s}"],
                "is_completed": True,
            }

    # 2. Nodo de Cálculo Determinístico
    async def compute_metrics_node(state: CreditUnderwritingState) -> dict[str, Any]:
        financial_input = state.get("financial_input")
        if not financial_input:
            return {
                "current_step": "METRICS_FAILED",
                "errors": ["No se dispone de datos financieros validados."],
                "is_completed": True,
            }

        metrics = evaluate_financial_health(financial_input)
        return {
            "metrics": metrics,
            "current_step": "METRICS_COMPUTED",
        }

    # 3. Nodo de Búsqueda Semántica de Precedentes Históricos (RAG con pgvector)
    async def retrieve_precedents_node(state: CreditUnderwritingState) -> dict[str, Any]:
        metrics = state.get("metrics")
        if not metrics:
            return {
                "current_step": "RETRIEVAL_SKIPPED",
                "historical_precedents": [],
            }

        business_name = state.get("business_name", "Empresa Solicitante")
        sector = state.get("sector", "Comercio y Servicios")
        requested_amount = state.get("requested_amount_usd", 0.0)
        term_months = state.get("term_months", 12)
        dscr = metrics.dscr_result.dscr
        current_ratio = metrics.current_ratio or 1.0
        runway = metrics.runway_months or 0.0
        flags = metrics.anomaly_flags

        profile_text = build_credit_profile_text(
            business_name=business_name,
            sector=sector,
            requested_amount_usd=requested_amount,
            term_months=term_months,
            dscr=dscr,
            current_ratio=current_ratio,
            runway_months=runway,
            anomaly_flags=flags,
        )

        embedding = await resolved_embedder.generate_embedding(profile_text)
        precedents = await resolved_vector_repo.search_similar_loans(embedding, limit=3)

        app_id = state.get("application_id")
        if tracker and app_id:
            tracker.record_span(
                application_id=app_id,
                name="historical_precedents_search",
                input={"profile_text": profile_text, "limit": 3},
                output={"precedents": [p.to_dict() for p in precedents]},
                as_type="retriever",
            )

        return {
            "historical_precedents": precedents,
            "current_step": "PRECEDENTS_RETRIEVED",
        }

    # 4. Nodo de Auditoría con Gemini (Enriquecido con Precedentes)
    async def audit_risk_node(state: CreditUnderwritingState) -> dict[str, Any]:
        metrics = state.get("metrics")
        if not metrics:
            return {
                "current_step": "AUDIT_FAILED",
                "errors": ["Métricas no disponibles para auditoría."],
                "is_completed": True,
            }

        verdict = await auditor.audit_application(
            business_name=state.get("business_name", "Empresa Solicitante"),
            requested_amount_usd=state.get("requested_amount_usd", 0.0),
            term_months=state.get("term_months", 12),
            metrics=metrics,
            application_id=state.get("application_id"),
            associated_id=state.get("associated_id"),
            precedents=state.get("historical_precedents"),
        )

        return {
            "ai_verdict": verdict,
            "current_step": "PENDING_HUMAN_REVIEW",
        }

    # 5. Nodo de Revisión Humana (Human-in-the-loop checkpoint)
    async def human_review_node(state: CreditUnderwritingState) -> dict[str, Any]:
        human_approved = state.get("human_approved")
        human_notes = state.get("human_notes", "Sin notas del oficial de crédito")

        step_status = "HUMAN_APPROVED" if human_approved else "HUMAN_REJECTED"
        return {
            "current_step": step_status,
            "human_notes": human_notes,
        }

    # 6. Nodo de Finalización
    async def finalize_node(state: CreditUnderwritingState) -> dict[str, Any]:
        return {
            "current_step": "COMPLETED",
            "is_completed": True,
        }

    # Enrutamiento condicional post-validación
    def route_after_validation(state: CreditUnderwritingState) -> str:
        if state.get("errors"):
            return "end"
        return "compute_metrics"

    # Construcción del Grafo
    workflow = StateGraph(CreditUnderwritingState)

    workflow.add_node("validate_ingestion", validate_ingestion_node)
    workflow.add_node("compute_metrics", compute_metrics_node)
    workflow.add_node("retrieve_precedents", retrieve_precedents_node)
    workflow.add_node("audit_risk", audit_risk_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("finalize", finalize_node)

    workflow.add_edge(START, "validate_ingestion")
    workflow.add_conditional_edges(
        "validate_ingestion",
        route_after_validation,
        {
            "compute_metrics": "compute_metrics",
            "end": END,
        },
    )
    workflow.add_edge("compute_metrics", "retrieve_precedents")
    workflow.add_edge("retrieve_precedents", "audit_risk")
    workflow.add_edge("audit_risk", "human_review")
    workflow.add_edge("human_review", "finalize")
    workflow.add_edge("finalize", END)

    # Compilación con checkpointing e interrupción antes de la revisión humana
    return workflow.compile(
        checkpointer=checkpointer or MemorySaver(),
        interrupt_before=["human_review"],
    )
