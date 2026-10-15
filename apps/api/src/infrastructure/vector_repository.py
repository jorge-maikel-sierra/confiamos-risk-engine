"""Repositorio de persistencia vectorial con pgvector para PostgreSQL (SPEC-05)."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.vector_search import (
    SEED_HISTORICAL_LOANS,
    HistoricalLoanPrecedent,
    IEmbeddingGenerator,
    IVectorSearchRepository,
    LoanOutcome,
    MockEmbeddingGenerator,
    build_credit_profile_text,
    compute_cosine_similarity,
)
from src.infrastructure.models import HistoricalLoanModel


class PostgresVectorSearchRepository(IVectorSearchRepository):
    """Implementación de búsqueda vectorial sobre PostgreSQL con pgvector."""

    def __init__(
        self,
        session: AsyncSession,
        embedder: IEmbeddingGenerator | None = None,
    ) -> None:
        self.session = session
        self.embedder = embedder or MockEmbeddingGenerator()

    async def seed_dataset_if_empty(self) -> None:
        """Siembra los 20 casos de crédito histórico en la tabla si se encuentra vacía."""
        count_stmt = select(func.count()).select_from(HistoricalLoanModel)
        result = await self.session.execute(count_stmt)
        total = result.scalar() or 0

        if total > 0:
            return

        for raw in SEED_HISTORICAL_LOANS:
            text = build_credit_profile_text(
                business_name=raw["business_name"],
                sector=raw["sector"],
                requested_amount_usd=raw["requested_amount_usd"],
                term_months=raw["term_months"],
                dscr=raw["dscr"],
                current_ratio=raw["current_ratio"],
                runway_months=12.0,
                anomaly_flags=raw.get("anomaly_flags", []),
            )
            emb = await self.embedder.generate_embedding(text)
            model_item = HistoricalLoanModel(
                loan_id=raw["loan_id"],
                associated_id=raw["associated_id"],
                business_name=raw["business_name"],
                sector=raw["sector"],
                requested_amount_usd=raw["requested_amount_usd"],
                term_months=raw["term_months"],
                dscr=raw["dscr"],
                current_ratio=raw["current_ratio"],
                anomaly_flags=raw.get("anomaly_flags", []),
                outcome=raw["outcome"].value
                if isinstance(raw["outcome"], LoanOutcome)
                else str(raw["outcome"]),
                outcome_summary=raw["outcome_summary"],
                embedding=emb,
            )
            self.session.add(model_item)

        await self.session.commit()

    async def search_similar_loans(
        self,
        embedding: list[float],
        limit: int = 3,
    ) -> list[HistoricalLoanPrecedent]:
        """Consulta los k vecinos más cercanos por similitud coseno."""
        # Detectar si el dialecto activo soporta el operador nativo de pgvector
        bind = self.session.bind
        dialect_name = bind.dialect.name if bind else "postgresql"

        if dialect_name == "postgresql":
            # Operador nativo pgvector (<=>)
            distance_expr = HistoricalLoanModel.embedding.cosine_distance(embedding).label(
                "distance"
            )
            stmt = select(HistoricalLoanModel, distance_expr).order_by("distance").limit(limit)
            result = await self.session.execute(stmt)
            rows = result.all()

            precedents: list[HistoricalLoanPrecedent] = []
            for model, distance in rows:
                dist_val = float(distance) if distance is not None else 1.0
                similarity = round(max(0.0, 1.0 - dist_val), 4)
                precedents.append(
                    HistoricalLoanPrecedent(
                        loan_id=model.loan_id,
                        business_name=model.business_name,
                        sector=model.sector,
                        requested_amount_usd=model.requested_amount_usd,
                        dscr=model.dscr,
                        current_ratio=model.current_ratio,
                        anomaly_flags=model.anomaly_flags,
                        outcome=LoanOutcome(model.outcome),
                        outcome_summary=model.outcome_summary,
                        similarity_score=similarity,
                    )
                )
            return precedents

        # Fallback en memoria para motores sin extensión pgvector (ej. SQLite en tests)
        stmt = select(HistoricalLoanModel)
        result = await self.session.execute(stmt)
        all_models = result.scalars().all()

        scored: list[tuple[float, Any]] = []
        for model in all_models:
            emb = model.embedding
            if isinstance(emb, list):
                sim = compute_cosine_similarity(embedding, emb)
                scored.append((sim, model))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_k = scored[:limit]

        return [
            HistoricalLoanPrecedent(
                loan_id=m.loan_id,
                business_name=m.business_name,
                sector=m.sector,
                requested_amount_usd=m.requested_amount_usd,
                dscr=m.dscr,
                current_ratio=m.current_ratio,
                anomaly_flags=m.anomaly_flags,
                outcome=LoanOutcome(m.outcome),
                outcome_summary=m.outcome_summary,
                similarity_score=round(score, 4),
            )
            for score, m in top_k
        ]
