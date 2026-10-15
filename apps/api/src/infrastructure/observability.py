"""Capa de observabilidad con Langfuse para evaluación crediticia (SPEC-03 / Issue #19).

Implementa trazabilidad empresarial basada en OpenTelemetry y la API de Langfuse v5.0.1,
estructurada en un árbol jerárquico de spans:
- Span Raíz: credit_underwriting_lifecycle (input, output, session_id y user_id)
- Span Hijo (tool): compute_financial_metrics (cálculo determinístico de DSCR y liquidez)
- Span Hijo (generation): gemini_risk_auditor (inferencia cualitativa, tokens y latencia)
- Score: human_approval (dictamen del oficial de crédito para evaluación continua)
"""

import hashlib
import os
import uuid
from typing import Any, Protocol


def to_otel_trace_id(raw_id: str) -> str:
    """Convierte un ID arbitrario o UUID a un formato trace_id OpenTelemetry válido (32 hex)."""
    try:
        return uuid.UUID(raw_id).hex
    except ValueError:
        return hashlib.md5(raw_id.encode("utf-8")).hexdigest()


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
        """Registra la inferencia cualitativa realizada por Gemini."""
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
        """Registra el dictamen humano como un score en Langfuse."""
        ...

    def flush(self) -> None:
        """Fuerza el envío de eventos pendientes."""
        ...


class MockObservabilityTracker:
    """Implementación en memoria para tests unitarios y entornos de desarrollo offline."""

    def __init__(self) -> None:
        self.traces: list[dict[str, Any]] = []
        self.spans: list[dict[str, Any]] = []
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
                "output": None,
            }
        )

    def record_span(
        self,
        application_id: str,
        name: str,
        input: Any,
        output: Any,
        as_type: str = "tool",
    ) -> None:
        self.spans.append(
            {
                "trace_id": application_id,
                "name": name,
                "input": input,
                "output": output,
                "as_type": as_type,
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

    def update_trace_output(
        self,
        application_id: str,
        output: dict[str, Any],
    ) -> None:
        for t in self.traces:
            if t["id"] == application_id:
                t["output"] = output
                break

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
    """Implementación de producción que despacha eventos a Langfuse Cloud vía OpenTelemetry."""

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
        self._active_spans: dict[str, Any] = {}

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
            from langfuse.types import TraceContext

            tid = to_otel_trace_id(application_id)
            root_span = self._client.start_observation(
                name="credit_underwriting_lifecycle",
                as_type="span",
                input={
                    "business_name": business_name,
                    "requested_amount_usd": requested_amount_usd,
                    "term_months": term_months,
                    "associated_id": associated_id,
                },
                metadata={
                    "application_id": application_id,
                    "associated_id": associated_id,
                    "environment": os.getenv("APP_ENV", "production"),
                    "tags": ["underwriting", "confiamos-risk-engine", "commercial-credit"],
                },
                trace_context=TraceContext(trace_id=tid),
            )
            self._active_spans[application_id] = root_span
        except Exception:
            pass

    def record_span(
        self,
        application_id: str,
        name: str,
        input: Any,
        output: Any,
        as_type: str = "tool",
    ) -> None:
        if not self._client:
            return
        try:
            from langfuse.types import TraceContext

            tid = to_otel_trace_id(application_id)
            span = self._client.start_observation(
                name=name,
                as_type=as_type,
                input=input,
                output=output,
                trace_context=TraceContext(trace_id=tid),
            )
            span.end()
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
            from langfuse.types import TraceContext

            tid = to_otel_trace_id(application_id)
            gen = self._client.start_observation(
                name="gemini_risk_auditor",
                as_type="generation",
                model=model_name,
                input=prompt,
                output=output,
                usage_details=usage,
                metadata={"latency_ms": latency_ms, "application_id": application_id},
                trace_context=TraceContext(trace_id=tid),
            )
            gen.end()
        except Exception:
            pass

    def update_trace_output(
        self,
        application_id: str,
        output: dict[str, Any],
    ) -> None:
        if not self._client:
            return
        try:
            root_span = self._active_spans.get(application_id)
            if root_span:
                root_span.update(output=output)
                if output.get("is_completed"):
                    root_span.end()
                    self._active_spans.pop(application_id, None)
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
            tid = to_otel_trace_id(application_id)
            self._client.create_score(
                trace_id=tid,
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
