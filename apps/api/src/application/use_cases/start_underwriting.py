"""Caso de Uso: Iniciar Evaluación Crediticia (StartUnderwritingUseCase).

Orquesta el ciclo de vida inicial de la solicitud conforme al flujo determinístico
de LangGraph y la persistencia del estado en el repositorio.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from src.domain.events import (
    CreditEventType,
    CreditUnderwritingEvent,
    EventSeverity,
    IEventPublisher,
)
from src.domain.ports import IObservabilityTracker
from src.domain.repositories import IUnderwritingRepository
from src.domain.state import CreditUnderwritingState


@dataclass(frozen=True)
class StartUnderwritingCommand:
    """Parámetros de entrada para el caso de uso."""

    associated_id: str
    business_name: str
    requested_amount_usd: float
    term_months: int
    financial_data: dict[str, Any]
    sector: str | None = None
    application_id: str | None = None


class StartUnderwritingUseCase:
    """Implementa la orquestación del inicio de evaluación crediticia."""

    def __init__(
        self,
        repository: IUnderwritingRepository,
        graph: Any,
        tracker: IObservabilityTracker,
        event_publisher: IEventPublisher,
    ) -> None:
        self.repository = repository
        self.graph = graph
        self.tracker = tracker
        self.event_publisher = event_publisher

    async def execute(self, command: StartUnderwritingCommand) -> dict[str, Any]:
        """Ejecuta el StateGraph hasta la pausa por revisión humana y persiste el snapshot."""
        app_id = command.application_id or f"APP-{uuid.uuid4().hex[:8].upper()}"
        config = {"configurable": {"thread_id": app_id}}

        # 1. Iniciar traza de observabilidad
        self.tracker.trace_start(
            application_id=app_id,
            associated_id=command.associated_id,
            business_name=command.business_name,
            requested_amount_usd=command.requested_amount_usd,
            term_months=command.term_months,
        )

        # 2. Registrar solicitud inicial en repositorio
        await self.repository.create_application(
            application_id=app_id,
            associated_id=command.associated_id,
            business_name=command.business_name,
            requested_amount_usd=command.requested_amount_usd,
            term_months=command.term_months,
            raw_financials=command.financial_data,
        )

        initial_state: CreditUnderwritingState = {
            "application_id": app_id,
            "associated_id": command.associated_id,
            "business_name": command.business_name,
            "sector": command.sector,
            "requested_amount_usd": command.requested_amount_usd,
            "term_months": command.term_months,
            "raw_financials": command.financial_data,
        }

        # 3. Ejecutar StateGraph hasta la interrupción (cálculo, precedentes pgvector,
        # dictamen y scoring)
        await self.graph.ainvoke(initial_state, config=config)
        snapshot = await self.graph.aget_state(config)

        # 4. Extraer y formatear snapshot de métricas
        metrics_data = None
        if snapshot.values.get("metrics"):
            m = snapshot.values["metrics"]
            metrics_data = {
                "dscr": m.dscr_result.dscr,
                "is_solvent": m.dscr_result.is_solvent,
                "is_debt_free": m.dscr_result.is_debt_free,
                "current_ratio": m.current_ratio,
                "runway_months": m.runway_months,
                "anomaly_flags": m.anomaly_flags,
            }

        verdict_data = None
        if snapshot.values.get("ai_verdict"):
            v = snapshot.values["ai_verdict"]
            verdict_data = v.model_dump() if hasattr(v, "model_dump") else v

        precedents_data = None
        if snapshot.values.get("historical_precedents"):
            precs = snapshot.values["historical_precedents"]
            precedents_data = [p.to_dict() if hasattr(p, "to_dict") else p for p in precs]

        scorecard_data = snapshot.values.get("scorecard")

        # 5. Persistir estado en la base de datos
        updated_record = await self.repository.update_snapshot(
            application_id=app_id,
            current_step=snapshot.values.get("current_step", "PENDING_HUMAN_REVIEW"),
            metrics=metrics_data,
            ai_verdict=verdict_data,
            historical_precedents=precedents_data,
            scorecard=scorecard_data,
        )

        # 6. Registrar span en observabilidad
        if metrics_data:
            self.tracker.record_span(
                application_id=app_id,
                name="compute_financial_metrics",
                input=command.financial_data,
                output=metrics_data,
                as_type="tool",
            )

        self.tracker.update_trace_output(
            application_id=app_id,
            output={
                "current_step": snapshot.values.get("current_step", "PENDING_HUMAN_REVIEW"),
                "ai_verdict": verdict_data,
                "is_completed": snapshot.values.get("is_completed", False),
            },
        )

        # 7. Despacho reactivo de eventos de dominio
        await self._dispatch_events(
            app_id=app_id,
            command=command,
            metrics_data=metrics_data,
            verdict_data=verdict_data,
        )

        return updated_record

    async def _dispatch_events(
        self,
        app_id: str,
        command: StartUnderwritingCommand,
        metrics_data: dict[str, Any] | None,
        verdict_data: dict[str, Any] | None,
    ) -> None:
        """Emite eventos de dominio y alertas hacia el bus de mensajería."""
        # Evento: Solicitud radicada
        event_submitted = CreditUnderwritingEvent(
            event_type=CreditEventType.APPLICATION_SUBMITTED,
            severity=EventSeverity.INFO,
            application_id=app_id,
            associated_id=command.associated_id,
            business_name=command.business_name,
            summary=f"Solicitud radicada por ${command.requested_amount_usd:,.2f} USD.",
            payload={
                "requested_amount_usd": command.requested_amount_usd,
                "term_months": command.term_months,
            },
        )
        await self.event_publisher.publish_event(event_submitted)

        if not metrics_data:
            return

        # Detección de severidad crítica
        critical_flags = [
            "FLAG_DEFICIT_DSCR",
            "FLAG_NEGATIVE_OPERATING_CASH_FLOW",
            "FLAG_OVERDRAFT_DETECTED",
            "ALERTA_RAG_PRECEDENTE_HISTORICO_DEFAULT",
        ]
        has_critical = any(f in metrics_data.get("anomaly_flags", []) for f in critical_flags)
        is_rejected = verdict_data and verdict_data.get("recommendation") == "RECHAZADO"

        if has_critical or is_rejected:
            critical_event = CreditUnderwritingEvent(
                event_type=CreditEventType.CRITICAL_RISK_DETECTED,
                severity=EventSeverity.CRITICAL,
                application_id=app_id,
                associated_id=command.associated_id,
                business_name=command.business_name,
                summary="Se detectaron banderas críticas o dictamen de rechazo en la evaluación.",
                payload={
                    "anomaly_flags": metrics_data.get("anomaly_flags", []),
                    "dscr": metrics_data.get("dscr"),
                    "recommendation": verdict_data.get("recommendation") if verdict_data else None,
                    "requested_amount_usd": command.requested_amount_usd,
                },
            )
            await self.event_publisher.publish_event(critical_event)

        # Evento: En espera de comité
        event_pending = CreditUnderwritingEvent(
            event_type=CreditEventType.PENDING_HUMAN_REVIEW,
            severity=EventSeverity.WARNING if (has_critical or is_rejected) else EventSeverity.INFO,
            application_id=app_id,
            associated_id=command.associated_id,
            business_name=command.business_name,
            summary="Evaluación pausada esperando resolución definitiva de comité.",
            payload={
                "requested_amount_usd": command.requested_amount_usd,
                "dscr": metrics_data.get("dscr"),
                "recommendation": verdict_data.get("recommendation") if verdict_data else None,
                "anomaly_flags": metrics_data.get("anomaly_flags", []),
            },
        )
        await self.event_publisher.publish_event(event_pending)
