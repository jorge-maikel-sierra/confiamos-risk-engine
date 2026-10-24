"""Modelos ORM relacionales para la persistencia de crédito (SPEC-02 y SPEC-05)."""

from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.infrastructure.database import Base

# Tipo JSON compatible con PostgreSQL (JSONB nativo) y SQLite (JSON estándar)
JSONType = JSON().with_variant(JSONB, "postgresql")
# Tipo Vector compatible con PostgreSQL (pgvector de 768 dim)
# y SQLite (JSON en memoria para testing)
VectorType = Vector(768).with_variant(JSON, "sqlite")


def utc_now() -> datetime:
    return datetime.now(UTC)


class CreditApplicationModel(Base):
    """Entidad relacional para solicitudes de crédito de asociados de la cooperativa."""

    __tablename__ = "credit_applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    associated_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    business_name: Mapped[str] = mapped_column(String(150), nullable=False)
    requested_amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    current_step: Mapped[str] = mapped_column(
        String(50), nullable=False, default="INITIALIZED", index=True
    )
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    raw_financials: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    ai_verdict: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    scorecard: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    historical_precedents: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONType, nullable=True
    )
    stress_test_results: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True
    )
    collateral_analysis: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True
    )

    human_approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    human_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )

    def to_dict(self) -> dict[str, Any]:
        """Serializa la entidad a diccionario compatible con los esquemas de API."""
        return {
            "application_id": self.id,
            "associated_id": self.associated_id,
            "business_name": self.business_name,
            "requested_amount_usd": self.requested_amount_usd,
            "term_months": self.term_months,
            "current_step": self.current_step,
            "is_completed": self.is_completed,
            "raw_financials": self.raw_financials,
            "metrics": self.metrics,
            "ai_verdict": self.ai_verdict,
            "scorecard": self.scorecard,
            "historical_precedents": self.historical_precedents or [],
            "stress_test_results": self.stress_test_results,
            "collateral_analysis": self.collateral_analysis,
            "human_approved": self.human_approved,
            "human_notes": self.human_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class HistoricalLoanModel(Base):
    """Entidad relacional para la cartera histórica de créditos con embeddings (SPEC-05)."""

    __tablename__ = "historical_loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loan_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    associated_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    requested_amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    dscr: Mapped[float] = mapped_column(Float, nullable=False)
    current_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    anomaly_flags: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    outcome_summary: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(VectorType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )

    def to_dict(self) -> dict[str, Any]:
        """Serializa el registro histórico a diccionario."""
        return {
            "loan_id": self.loan_id,
            "associated_id": self.associated_id,
            "business_name": self.business_name,
            "sector": self.sector,
            "requested_amount_usd": self.requested_amount_usd,
            "term_months": self.term_months,
            "dscr": self.dscr,
            "current_ratio": self.current_ratio,
            "anomaly_flags": self.anomaly_flags,
            "outcome": self.outcome,
            "outcome_summary": self.outcome_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
