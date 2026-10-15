"""Capa de observabilidad y trazabilidad con Langfuse para evaluación crediticia (SPEC-03)."""

import os
from typing import Any, Protocol


class IObservabilityTracker(Protocol):
    """Protocolo abstracto para la observabilidad y trazabilidad de IA."""

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

    def record_generation(
        self,
        application_id: str,
        model_name: str,
        prompt: str,
        output: dict[str, Any],
        usage: dict[str, int] | None = None,
        latency_ms: float = 0.0,
    ) -> None:
        """Registra la inferencia cualitativa realizada por Gemini."""
        ...

    def record_human_score(
        self,
        application_id: str,
        approved: bool,
        notes: str,
    ) -> None:
        """Registra el dictamen humano como un score en Langfuse."""
        ...

    def flush(self) -> None:
        """Fuerza el envío de eventos pendientes."""
        ...


class MockObservabilityTracker:
    """Implementación en memoria para tests unitarios y entornos de desarrollo offline."""

    def __init__(self) -> None:
        self.traces: list[dict[str, Any]] = []
        self.generations: list[dict[str, Any]] = []
        self.scores: list[dict[str, Any]] = []

    def trace_start(
        self,
        application_id: str,
        associated_id: str,
        business_name: str,
        requested_amount_usd: float,
        term_months: int,
    ) -> None:
        self.traces.append(
            {
                "id": application_id,
                "user_id": associated_id,
                "business_name": business_name,
                "requested_amount_usd": requested_amount_usd,
                "term_months": term_months,
            }
        )

    def record_generation(
        self,
        application_id: str,
        model_name: str,
        prompt: str,
        output: dict[str, Any],
        usage: dict[str, int] | None = None,
        latency_ms: float = 0.0,
    ) -> None:
        self.generations.append(
            {
                "trace_id": application_id,
                "model_name": model_name,
                "prompt": prompt,
                "output": output,
                "usage": usage or {},
                "latency_ms": latency_ms,
            }
        )

    def record_human_score(
        self,
        application_id: str,
        approved: bool,
        notes: str,
    ) -> None:
        self.scores.append(
            {
                "trace_id": application_id,
                "name": "human_approval",
                "value": 1.0 if approved else 0.0,
                "comment": notes,
            }
        )

    def flush(self) -> None:
        pass


class LangfuseTracker:
    """Implementación de producción que despacha eventos a Langfuse Cloud."""

    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str | None = None,
    ) -> None:
        self.public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
        self.secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")
        self.host = host or os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        self._client = None

        if self.public_key and self.secret_key:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.host,
                )
            except Exception:
                self._client = None

    def trace_start(
        self,
        application_id: str,
        associated_id: str,
        business_name: str,
        requested_amount_usd: float,
        term_months: int,
    ) -> None:
        if not self._client:
            return
        try:
            self._client.trace(
                id=application_id,
                user_id=associated_id,
                name="credit_underwriting_lifecycle",
                tags=["underwriting", "confiamos-risk-engine", "commercial-credit"],
                metadata={
                    "business_name": business_name,
                    "requested_amount_usd": requested_amount_usd,
                    "term_months": term_months,
                },
            )
        except Exception:
            pass

    def record_generation(
        self,
        application_id: str,
        model_name: str,
        prompt: str,
        output: dict[str, Any],
        usage: dict[str, int] | None = None,
        latency_ms: float = 0.0,
    ) -> None:
        if not self._client:
            return
        try:
            trace = self._client.trace(id=application_id)
            trace.generation(
                name="gemini_risk_auditor",
                model=model_name,
                input=prompt,
                output=output,
                usage=usage,
                metadata={"latency_ms": latency_ms},
            )
        except Exception:
            pass

    def record_human_score(
        self,
        application_id: str,
        approved: bool,
        notes: str,
    ) -> None:
        if not self._client:
            return
        try:
            self._client.score(
                trace_id=application_id,
                name="human_approval",
                value=1.0 if approved else 0.0,
                comment=notes,
            )
        except Exception:
            pass

    def flush(self) -> None:
        if self._client:
            try:
                self._client.flush()
            except Exception:
                pass


_mock_tracker = MockObservabilityTracker()


def get_observability_tracker() -> IObservabilityTracker:
    """Retorna el tracker real o mock según el entorno de ejecución."""
    if os.getenv("TESTING") == "true":
        return _mock_tracker

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if public_key and secret_key and public_key != "your_langfuse_public_key":
        return LangfuseTracker(public_key=public_key, secret_key=secret_key)
    return _mock_tracker
