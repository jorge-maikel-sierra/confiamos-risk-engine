"""Dominio de eventos de negocio y mensajería reactiva en tiempo real (SPEC-06).

Define entidades de eventos inmutables, niveles de severidad y protocolos de publicación y difusión.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class EventSeverity(StrEnum):
    """Severidad del evento para enrutamiento y priorización de alertas."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class CreditEventType(StrEnum):
    """Tipos de eventos en el ciclo de vida de la evaluación crediticia."""

    APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
    METRICS_CALCULATED = "METRICS_CALCULATED"
    CRITICAL_RISK_DETECTED = "CRITICAL_RISK_DETECTED"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    HUMAN_RESOLVED = "HUMAN_RESOLVED"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class CreditUnderwritingEvent(BaseModel):
    """Evento inmutable del ciclo de vida crediticio para distribución Pub/Sub."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: CreditEventType
    severity: EventSeverity
    application_id: str
    associated_id: str
    business_name: str
    timestamp: str = Field(default_factory=utc_now_iso)
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_sse_message(self) -> str:
        """Serializa el evento en formato estándar Server-Sent Events (SSE)."""
        data = self.model_dump_json()
        return f"event: credit_event\nid: {self.event_id}\ndata: {data}\n\n"


class IEventPublisher(Protocol):
    """Protocolo desacoplado para publicación de eventos en broker (AWS SNS o InMemory)."""

    async def publish_event(self, event: CreditUnderwritingEvent) -> str:
        """Publica el evento y retorna el ID único de entrega emitido por el broker."""
        ...


class EventBroadcaster:
    """Distribuidor asíncrono en memoria para streaming SSE hacia clientes web conectados."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[CreditUnderwritingEvent]] = set()

    def create_subscription(self) -> asyncio.Queue[CreditUnderwritingEvent]:
        """Crea y registra una nueva cola de eventos para un suscriptor SSE."""
        queue: asyncio.Queue[CreditUnderwritingEvent] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[CreditUnderwritingEvent]) -> None:
        """Desregistra una cola de suscriptor al cerrarse la conexión SSE."""
        self._subscribers.discard(queue)

    async def subscribe(self) -> AsyncGenerator[CreditUnderwritingEvent, None]:
        """Generador asíncrono que entrega eventos a un cliente SSE individual."""
        queue = self.create_subscription()
        try:
            while True:
                event = await queue.get()
                yield event
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            self.unsubscribe(queue)

    async def broadcast(self, event: CreditUnderwritingEvent) -> None:
        """Difunde el evento a todas las colas de suscriptores web activas."""
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass


class MockEventPublisher:
    """Implementación en memoria para tests unitarios y desarrollo offline."""

    def __init__(self, broadcaster: EventBroadcaster | None = None) -> None:
        self.published_events: list[CreditUnderwritingEvent] = []
        self.broadcaster = broadcaster

    async def publish_event(self, event: CreditUnderwritingEvent) -> str:
        """Registra el evento en memoria y lo difunde a clientes SSE si hay broadcaster."""
        self.published_events.append(event)
        if self.broadcaster:
            await self.broadcaster.broadcast(event)
        msg_id = f"mock-msg-{uuid.uuid4().hex[:8]}"
        return msg_id
