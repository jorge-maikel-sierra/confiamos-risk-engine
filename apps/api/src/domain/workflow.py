"""StateGraph de LangGraph para la evaluación y suscripción crediticia (SPEC-01).

Implementa la máquina de estados con:
- Ingesta y validación de balances
- Cálculo determinístico de métricas financieras
- Auditoría cualitativa de riesgo con Gemini
- Checkpoint e interrupción para aprobación humana (Human-in-the-loop)
- Finalización y emisión del dictamen para Cooperativa Confiamos
"""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.domain.metrics import FinancialInput, evaluate_financial_health
from src.domain.state import CreditUnderwritingState
from src.infrastructure.gemini_adapter import RiskAuditorProtocol


def create_underwriting_graph(
    auditor: RiskAuditorProtocol,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Crea y compila el StateGraph de evaluación crediticia."""

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

    # 3. Nodo de Auditoría con Gemini
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
        )

        return {
            "ai_verdict": verdict,
            "current_step": "PENDING_HUMAN_REVIEW",
        }

    # 4. Nodo de Revisión Humana (Human-in-the-loop checkpoint)
    async def human_review_node(state: CreditUnderwritingState) -> dict[str, Any]:
        human_approved = state.get("human_approved")
        human_notes = state.get("human_notes", "Sin notas del oficial de crédito")

        step_status = "HUMAN_APPROVED" if human_approved else "HUMAN_REJECTED"
        return {
            "current_step": step_status,
            "human_notes": human_notes,
        }

    # 5. Nodo de Finalización
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
    workflow.add_edge("compute_metrics", "audit_risk")
    workflow.add_edge("audit_risk", "human_review")
    workflow.add_edge("human_review", "finalize")
    workflow.add_edge("finalize", END)

    # Compilación con checkpointing e interrupción antes de la revisión humana
    return workflow.compile(
        checkpointer=checkpointer or MemorySaver(),
        interrupt_before=["human_review"],
    )
