"""Puertos abstractos de salida (Driven Ports) del Dominio (Arquitectura Hexagonal Pura).

Define las interfaces e invariantes que los adaptadores de infraestructura deben implementar.
El dominio NO importa nada de infraestructura; toda dependencia apunta hacia adentro.
"""

from typing import Any, Protocol

from src.domain.metrics import FinancialHealthMetrics
from src.domain.state import UnderwritingVerdict
from src.domain.stress_testing import StressParameters, StressTestingAnalysis
from src.domain.vector_search import HistoricalLoanPrecedent


class RiskAuditorProtocol(Protocol):
    """Puerto de salida para el auditor de riesgo cualitativo con IA."""

    async def audit_application(
        self,
        business_name: str,
        requested_amount_usd: float,
        term_months: int,
        metrics: FinancialHealthMetrics,
        application_id: str | None = None,
        associated_id: str | None = None,
        precedents: list[HistoricalLoanPrecedent] | None = None,
    ) -> UnderwritingVerdict:
        """Emite el dictamen estructurado de riesgo para una solicitud."""
        ...


class IObservabilityTracker(Protocol):
    """Puerto de salida para el sistema de observabilidad y trazabilidad (Langfuse/OTEL)."""

    def trace_start(
        self,
        application_id: str,
        associated_id: str,
        business_name: str,
        requested_amount_usd: float,
        term_months: int,
    ) -> None:
        """Inicia el contexto de la traza para una solicitud crediticia."""
        ...

    def record_span(
        self,
        application_id: str,
        name: str,
        input: Any,
        output: Any,
        as_type: str = "tool",
    ) -> None:
        """Registra una operación intermedia como span hijo (e.g. cálculo financiero)."""
        ...

    def record_generation(
        self,
        application_id: str,
        model_name: str,
        prompt: str,
        output: dict[str, Any],
        usage: dict[str, int] | None = None,
        latency_ms: float = 0.0,
    ) -> None:
        """Registra la inferencia cualitativa realizada por el modelo de lenguaje."""
        ...

    def update_trace_output(
        self,
        application_id: str,
        output: dict[str, Any],
    ) -> None:
        """Actualiza el output del span raíz al finalizar o pausar una etapa."""
        ...

    def record_human_score(
        self,
        application_id: str,
        approved: bool,
        notes: str,
    ) -> None:
        """Registra el score de feedback humano (comité) para evaluación de LLMOps."""
        ...

    def flush(self) -> None:
        """Fuerza el envío de eventos pendientes."""
        ...


class StressTestingServicePort(Protocol):
    """Puerto de dominio para la simulación y análisis de estrés financiero (SPEC-10)."""

    async def execute_stress_test(
        self,
        application_id: str,
        custom_scenario: StressParameters | None = None,
    ) -> StressTestingAnalysis:
        """Ejecuta la simulación completa de pruebas de estrés para el expediente."""
        ...

