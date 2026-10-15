"""Tests unitarios y de integración para búsqueda semántica con pgvector (SPEC-05 / Issue #27).

Verifica:
- Generación de texto de perfil y embeddings determinísticos de 768 dimensiones.
- Precisión matemática de similitud coseno.
- Repositorio mock y persistencia relacional con seed de 20 casos.
- Integración en LangGraph (nodo retrieve_precedents) y observabilidad retriever en Langfuse.
- Enriquecimiento del prompt del auditor de riesgo con precedentes de cartera.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.metrics import FinancialInput, evaluate_financial_health
from src.domain.state import CreditUnderwritingState
from src.domain.vector_search import (
    SEED_HISTORICAL_LOANS,
    HistoricalLoanPrecedent,
    LoanOutcome,
    MockEmbeddingGenerator,
    MockVectorSearchRepository,
    build_credit_profile_text,
    compute_cosine_similarity,
)
from src.domain.workflow import create_underwriting_graph
from src.infrastructure.database import Base
from src.infrastructure.gemini_adapter import MockGeminiAuditor
from src.infrastructure.observability import MockObservabilityTracker
from src.infrastructure.vector_repository import PostgresVectorSearchRepository


def test_build_credit_profile_text() -> None:
    """Verifica que la síntesis de perfil crediticio sea rica y estructurada."""
    text = build_credit_profile_text(
        business_name="Textiles del Norte",
        sector="Manufactura",
        requested_amount_usd=50000.0,
        term_months=36,
        dscr=1.35,
        current_ratio=1.42,
        runway_months=8.5,
        anomaly_flags=["FLAG_SEASONAL_VARIATION"],
    )

    assert "Textiles del Norte" in text
    assert "Manufactura" in text
    assert "$50,000.00 USD" in text
    assert "DSCR: 1.35" in text
    assert "FLAG_SEASONAL_VARIATION" in text


@pytest.mark.asyncio
async def test_mock_embedding_generator_dimensions_and_determinism() -> None:
    """Verifica que el generador devuelva 768 dimensiones normalizadas determinísticamente."""
    embedder = MockEmbeddingGenerator(dimension=768)

    vec1 = await embedder.generate_embedding("Crédito PyME Agroindustrial")
    vec2 = await embedder.generate_embedding("Crédito PyME Agroindustrial")
    vec_diff = await embedder.generate_embedding("Comercio de calzado al por mayor")

    assert len(vec1) == 768
    assert vec1 == vec2  # Mismo texto produce exactamente el mismo vector
    assert vec1 != vec_diff  # Textos diferentes producen vectores distintos

    # Norma euclídea cercana a 1.0 (vector unitario)
    norm = sum(v * v for v in vec1) ** 0.5
    assert abs(norm - 1.0) < 1e-4


def test_compute_cosine_similarity_edge_cases() -> None:
    """Verifica el cálculo de similitud coseno en casos idénticos, ortogonales y opuestos."""
    vec_a = [1.0, 0.0, 0.0]
    vec_identical = [1.0, 0.0, 0.0]
    vec_orthogonal = [0.0, 1.0, 0.0]
    vec_opposite = [-1.0, 0.0, 0.0]

    assert abs(compute_cosine_similarity(vec_a, vec_identical) - 1.0) < 1e-6
    assert abs(compute_cosine_similarity(vec_a, vec_orthogonal) - 0.0) < 1e-6
    assert abs(compute_cosine_similarity(vec_a, vec_opposite) - (-1.0)) < 1e-6


@pytest.mark.asyncio
async def test_mock_vector_search_repository_seed_and_retrieval() -> None:
    """Verifica la carga del dataset semilla y la recuperación de los 3 casos más cercanos."""
    embedder = MockEmbeddingGenerator(dimension=768)
    repo = MockVectorSearchRepository(embedder=embedder)

    assert len(SEED_HISTORICAL_LOANS) == 20
    await repo.seed_dataset_if_empty()

    # Perfil de prueba para empresa agrícola
    query_text = build_credit_profile_text(
        business_name="Agrícola La Finca",
        sector="Agroindustria",
        requested_amount_usd=40000.0,
        term_months=36,
        dscr=1.20,
        current_ratio=1.15,
        runway_months=10.0,
        anomaly_flags=["FLAG_SEASONAL_VARIATION"],
    )
    query_vec = await embedder.generate_embedding(query_text)

    results = await repo.search_similar_loans(query_vec, limit=3)

    assert len(results) == 3
    # Los resultados deben estar ordenados de mayor a menor similitud
    assert results[0].similarity_score >= results[1].similarity_score >= results[2].similarity_score
    for item in results:
        assert isinstance(item, HistoricalLoanPrecedent)
        assert item.loan_id.startswith("HIST-")
        assert item.outcome in [
            LoanOutcome.CARTERA_SANA,
            LoanOutcome.DEFAULT_MORA,
            LoanOutcome.REESTRUCTURADO,
        ]
        assert 0.0 <= item.similarity_score <= 1.0


@pytest.mark.asyncio
async def test_postgres_vector_search_repository_with_async_sqlite() -> None:
    """Verifica PostgresVectorSearchRepository con motor asíncrono SQLite en memoria."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    embedder = MockEmbeddingGenerator(dimension=768)

    async with session_factory() as session:
        repo = PostgresVectorSearchRepository(session, embedder=embedder)
        await repo.seed_dataset_if_empty()

        query_vec = await embedder.generate_embedding("Comercio ferretería sobregiro")
        results = await repo.search_similar_loans(query_vec, limit=3)

        assert len(results) == 3
        assert results[0].similarity_score >= results[1].similarity_score
        assert results[0].sector != ""
        assert results[0].outcome_summary != ""


@pytest.mark.asyncio
async def test_langgraph_workflow_with_vector_retrieval_and_observability() -> None:
    """Verifica la ejecución del StateGraph con el nodo retrieve_precedents y span retriever."""
    tracker = MockObservabilityTracker()
    embedder = MockEmbeddingGenerator(dimension=768)
    vector_repo = MockVectorSearchRepository(embedder=embedder)
    auditor = MockGeminiAuditor(tracker=tracker)

    graph = create_underwriting_graph(
        auditor=auditor,
        vector_repo=vector_repo,
        embedder=embedder,
        tracker=tracker,
    )

    app_id = "APP-VEC-TEST-01"
    tracker.trace_start(
        application_id=app_id,
        associated_id="CONF-VEC-88",
        business_name="Transportes Rápidos del Sur",
        requested_amount_usd=50000.0,
        term_months=36,
    )

    initial_state: CreditUnderwritingState = {
        "application_id": app_id,
        "associated_id": "CONF-VEC-88",
        "business_name": "Transportes Rápidos del Sur",
        "sector": "Transporte y Logística",
        "requested_amount_usd": 50000.0,
        "term_months": 36,
        "raw_financials": {
            "operating_cash_flow": 25000.0,
            "annual_debt_service": 15000.0,
            "current_assets": 40000.0,
            "current_liabilities": 30000.0,
            "cash_balance": 10000.0,
            "monthly_burn_rate": 2000.0,
            "negative_balance_days": 0,
            "top_client_revenue_percentage": 25.0,
        },
    }

    config = {"configurable": {"thread_id": app_id}}
    await graph.ainvoke(initial_state, config=config)
    snapshot = await graph.aget_state(config)

    # 1. El grafo debió pausar antes de human_review
    assert snapshot.next == ("human_review",)
    assert snapshot.values.get("current_step") == "PENDING_HUMAN_REVIEW"

    # 2. Los precedentes históricos debieron recuperarse y guardarse en el estado
    precedents = snapshot.values.get("historical_precedents")
    assert precedents is not None
    assert len(precedents) == 3

    # 3. Span de observabilidad de tipo 'retriever' registrado en Langfuse
    retriever_spans = [s for s in tracker.spans if s["as_type"] == "retriever"]
    assert len(retriever_spans) == 1
    assert retriever_spans[0]["name"] == "historical_precedents_search"
    assert "precedents" in retriever_spans[0]["output"]

    # 4. Dictamen de IA emitido considerando los precedentes
    ai_verdict = snapshot.values.get("ai_verdict")
    assert ai_verdict is not None
    assert ai_verdict.recommendation in ["APROBADO", "APROBADO_CONDICIONADO"]


@pytest.mark.asyncio
async def test_mock_gemini_auditor_reacts_to_default_precedents() -> None:
    """Verifica que el auditor mock active alertas si un precedente de alta similitud es DEFAULT."""
    auditor = MockGeminiAuditor()

    # Precedente con DEFAULT y alta similitud
    default_precedent = HistoricalLoanPrecedent(
        loan_id="HIST-999",
        business_name="Empresa Fallida S.A.",
        sector="Comercio",
        requested_amount_usd=50000.0,
        dscr=1.10,
        current_ratio=0.95,
        anomaly_flags=["FLAG_OVERDRAFT_DETECTED"],
        outcome=LoanOutcome.DEFAULT_MORA,
        outcome_summary="Cesación de pagos a los 6 meses por pérdida de contrato.",
        similarity_score=0.92,
    )

    metrics = evaluate_financial_health(
        FinancialInput(
            operating_cash_flow=30000.0,
            annual_debt_service=15000.0,
            current_assets=50000.0,
            current_liabilities=30000.0,
            cash_balance=10000.0,
            monthly_burn_rate=2000.0,
            negative_balance_days=0,
            top_client_revenue_percentage=20.0,
        )
    )

    verdict = await auditor.audit_application(
        business_name="Comercializadora Nueva",
        requested_amount_usd=50000.0,
        term_months=36,
        metrics=metrics,
        precedents=[default_precedent],
    )

    # Debe ser APROBADO_CONDICIONADO por la alerta RAG de precedente en mora
    assert verdict.recommendation.value == "APROBADO_CONDICIONADO"
    assert "ALERTA_RAG_PRECEDENTE_HISTORICO_DEFAULT" in verdict.identified_risks
    assert "Alerta RAG" in verdict.executive_summary
