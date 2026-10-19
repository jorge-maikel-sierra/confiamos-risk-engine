"""Caso de Uso: Emitir Resolución de Oficial de Crédito (SubmitHumanReviewUseCase).

Permite la intervención humana (Human-in-the-Loop) reanudando el StateGraph
y actualizando la persistencia del expediente.
"""

from dataclasses import dataclass
from typing import Any

from src.application.exceptions import ApplicationConflictError, ApplicationNotFoundError
from src.domain.events import (
    CreditEventType,
    CreditUnderwritingEvent,
    EventSeverity,
    IEventPublisher,
)
from src.domain.ports import IObservabilityTracker
from src.domain.repositories import IUnderwritingRepository


@dataclass(frozen=True)
class SubmitHumanReviewCommand:
    """Parámetros de entrada para el caso de uso."""

    application_id: str
    approved: bool
    notes: str


class SubmitHumanReviewUseCase:
    """Implementa la orquestación de la resolución definitiva del oficial de crédito."""

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

    async def execute(self, command: SubmitHumanReviewCommand) -> dict[str, Any]:
        """Ejecuta la revisión humana y finaliza el ciclo del expediente."""
        app_id = command.application_id
        record = await self.repository.get_by_id(app_id)
        if not record:
            raise ApplicationNotFoundError(app_id)

        if record.get("is_completed"):
            raise ApplicationConflictError(
                application_id=app_id,
                reason="La solicitud ya ha sido finalizada previamente.",
            )

        config = {"configurable": {"thread_id": app_id}}

        # 1. Reanudar el StateGraph interviniendo en el checkpoint human_review
        await self.graph.aupdate_state(
            config,
            {
                "human_approved": command.approved,
                "human_notes": command.notes,
            },
            as_node="human_review",
        )

        await self.graph.ainvoke(None, config=config)
        final_snapshot = await self.graph.aget_state(config)

        # 2. Actualizar persistencia en repositorio
        updated_record = await self.repository.submit_human_review(
            application_id=app_id,
            approved=command.approved,
            notes=command.notes,
            current_step=final_snapshot.values.get("current_step", "COMPLETED"),
        )

        # 3. Registrar observabilidad en Langfuse
        self.tracker.record_human_score(
            application_id=app_id,
            approved=command.approved,
            notes=command.notes,
        )

        self.tracker.update_trace_output(
            application_id=app_id,
            output={
                "current_step": final_snapshot.values.get("current_step", "COMPLETED"),
                "human_approved": command.approved,
                "human_notes": command.notes,
                "is_completed": final_snapshot.values.get("is_completed", True),
            },
        )

        # 4. Publicar evento de resolución final
        resolution_severity = EventSeverity.INFO if command.approved else EventSeverity.WARNING
        resolution_status = "APROBADO" if command.approved else "RECHAZADO"

        resolution_event = CreditUnderwritingEvent(
            event_type=CreditEventType.HUMAN_RESOLVED,
            severity=resolution_severity,
            application_id=app_id,
            associated_id=record.get("associated_id", ""),
            business_name=record.get("business_name", ""),
            summary=(
                f"Resolución de oficial de crédito: {resolution_status}. "
                f"Condiciones: {command.notes}"
            ),
            payload={
                "approved": command.approved,
                "notes": command.notes,
                "completed_at": record.get("updated_at"),
            },
        )
        await self.event_publisher.publish_event(resolution_event)

        return updated_record
