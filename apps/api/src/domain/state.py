"""Estado y modelos de datos para el StateGraph crediticio (SPEC-01 y SPEC-05)."""

from enum import StrEnum
from typing import Any, TypedDict

from pydantic import BaseModel, Field

from src.domain.metrics import FinancialHealthMetrics, FinancialInput
from src.domain.vector_search import HistoricalLoanPrecedent


class CreditRecommendation(StrEnum):
    """Recomendación crediticia emitida para el comité de crédito."""

    APROBADO = "APROBADO"
    APROBADO_CONDICIONADO = "APROBADO_CONDICIONADO"
    RECHAZADO = "RECHAZADO"


class UnderwritingVerdict(BaseModel):
    """Dictamen estructurado emitido por el modelo de IA (Gemini)."""

    recommendation: CreditRecommendation
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="Nivel de certeza del modelo (0.0 a 1.0)"
    )
    executive_summary: str = Field(
        description="Resumen ejecutivo del análisis para el oficial de crédito"
    )
    key_strengths: list[str] = Field(
        default_factory=list, description="Puntos fuertes de la solicitud"
    )
    identified_risks: list[str] = Field(
        default_factory=list, description="Riesgos financieros detectados"
    )
    due_diligence_questions: list[str] = Field(
        default_factory=list, description="Preguntas de auditoría sugeridas para el cliente"
    )


class CreditUnderwritingState(TypedDict, total=False):
    """Estado tipado que transita a través de los nodos del StateGraph."""

    # Datos iniciales de la solicitud
    application_id: str
    associated_id: str
    business_name: str
    sector: str
    requested_amount_usd: float
    term_months: int
    raw_financials: dict[str, Any]

    # Datos validados
    financial_input: FinancialInput | None

    # Resultados determinísticos
    metrics: FinancialHealthMetrics | None

    # Precedentes históricos de crédito (RAG pgvector - SPEC-05)
    historical_precedents: list[HistoricalLoanPrecedent] | None

    # Razonamiento cualitativo de IA
    ai_verdict: UnderwritingVerdict | None

    # Scoring regulatorio y provisiones (SPEC-09)
    scorecard: dict[str, Any] | None

    # Intervención humana (Human-in-the-loop)
    human_approved: bool | None
    human_notes: str | None

    # Control de flujo y auditoría
    current_step: str
    errors: list[str]
    is_completed: bool
