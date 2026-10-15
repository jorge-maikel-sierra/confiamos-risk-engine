"""Tests unitarios y de integración para el StateGraph de LangGraph (SPEC-01).

Valida:
1. Transición de nodos determinísticos (Ingesta -> Métricas -> Auditoría).
2. Interrupción en el punto de revisión humana (Human-in-the-loop).
3. Reanudación tras la aprobación del oficial de crédito de Cooperativa Confiamos.
4. Manejo de fallos en la validación contable.
"""

import pytest

from src.domain.state import CreditRecommendation, CreditUnderwritingState
from src.domain.workflow import create_underwriting_graph
from src.infrastructure.gemini_adapter import MockGeminiAuditor


@pytest.mark.asyncio
async def test_graph_pauses_for_human_review() -> None:
    """Verifica que el grafo transite los nodos y se detenga antes de human_review."""
    auditor = MockGeminiAuditor()
    graph = create_underwriting_graph(auditor=auditor)

    initial_state: CreditUnderwritingState = {
        "application_id": "APP-001",
        "associated_id": "CONF-98214",
        "business_name": "Distribuidora Andina SAS",
        "requested_amount_usd": 75000.0,
        "term_months": 24,
        "raw_financials": {
            "operating_cash_flow": 48500.0,
            "annual_debt_service": 24000.0,
            "current_assets": 120000.0,
            "current_liabilities": 65000.0,
            "cash_balance": 35000.0,
            "monthly_burn_rate": 0.0,
            "negative_balance_days": 0,
            "top_client_revenue_percentage": 22.5,
        },
    }

    config = {"configurable": {"thread_id": "app-thread-001"}}

    # Ejecutar primera fase del grafo
    await graph.ainvoke(initial_state, config=config)

    # Inspeccionar estado pausado
    snapshot = await graph.aget_state(config)
    assert snapshot.next == ("human_review",)
    values = snapshot.values
    assert values["current_step"] == "PENDING_HUMAN_REVIEW"
    assert values["metrics"] is not None
    assert round(values["metrics"].dscr_result.dscr, 4) == 2.0208
    assert values["ai_verdict"] is not None
    assert values["ai_verdict"].recommendation == CreditRecommendation.APROBADO
    assert auditor.call_count == 1


@pytest.mark.asyncio
async def test_graph_resumes_after_human_approval() -> None:
    """Verifica que el oficial de crédito pueda aprobar y completar la solicitud."""
    auditor = MockGeminiAuditor()
    graph = create_underwriting_graph(auditor=auditor)

    initial_state: CreditUnderwritingState = {
        "application_id": "APP-002",
        "associated_id": "CONF-11029",
        "business_name": "Café Central PyME",
        "requested_amount_usd": 30000.0,
        "term_months": 12,
        "raw_financials": {
            "operating_cash_flow": 30000.0,
            "annual_debt_service": 15000.0,
            "current_assets": 50000.0,
            "current_liabilities": 25000.0,
            "cash_balance": 20000.0,
        },
    }

    config = {"configurable": {"thread_id": "app-thread-002"}}

    # 1. Ejecutar hasta interrupción
    await graph.ainvoke(initial_state, config=config)

    # 2. El oficial humano revisa y aprueba
    await graph.aupdate_state(
        config,
        {"human_approved": True, "human_notes": "Aprobado por comité de crédito ordinario."},
        as_node="human_review",
    )

    # 3. Reanudar ejecución pasando None
    final_result = await graph.ainvoke(None, config=config)

    # 4. Verificar finalización exitosa
    assert final_result["is_completed"] is True
    assert final_result["current_step"] == "COMPLETED"
    assert final_result["human_approved"] is True
    assert "Aprobado por comité" in final_result["human_notes"]

    # Verificar que el grafo quedó cerrado
    final_snapshot = await graph.aget_state(config)
    assert final_snapshot.next == ()


@pytest.mark.asyncio
async def test_graph_validation_error_handling() -> None:
    """Verifica que datos contables no numéricos o inválidos detengan el flujo."""
    auditor = MockGeminiAuditor()
    graph = create_underwriting_graph(auditor=auditor)

    invalid_state: CreditUnderwritingState = {
        "application_id": "APP-ERR",
        "business_name": "Invalida Corp",
        "raw_financials": {
            "operating_cash_flow": "NO_ES_NUMERO",
        },
    }

    config = {"configurable": {"thread_id": "app-thread-err"}}
    result = await graph.ainvoke(invalid_state, config=config)

    assert result["current_step"] == "VALIDATION_FAILED"
    assert len(result["errors"]) > 0
    assert result["is_completed"] is True
    assert auditor.call_count == 0  # No debe llamar al auditor si falló la validación
