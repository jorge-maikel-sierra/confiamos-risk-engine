"""Adaptador de infraestructura para publicación de eventos en Amazon SNS (SPEC-06).

Implementa la integración con AWS SNS usando boto3, incluyendo atributos de mensaje para filtrado.
"""

import os
from typing import Any

from src.domain.events import (
    CreditUnderwritingEvent,
    EventBroadcaster,
    IEventPublisher,
    MockEventPublisher,
)


class AwsSnsEventPublisher:
    """Publicador de eventos empresariales en Amazon Simple Notification Service (AWS SNS)."""

    def __init__(
        self,
        topic_arn: str | None = None,
        region_name: str | None = None,
        broadcaster: EventBroadcaster | None = None,
    ) -> None:
        self.topic_arn = topic_arn or os.getenv(
            "AWS_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:confiamos-risk-events"
        )
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-1")
        self.broadcaster = broadcaster
        self._client: Any = None

    def _get_sns_client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("sns", region_name=self.region_name)
        return self._client

    async def publish_event(self, event: CreditUnderwritingEvent) -> str:
        """Publica el evento en el topic de Amazon SNS con atributos tipados."""
        # En streaming local hacia el frontend, difundir siempre vía SSE si hay broadcaster
        if self.broadcaster:
            await self.broadcaster.broadcast(event)

        # Entornos de test offline o sin credenciales de AWS
        if os.getenv("TESTING") == "true" or not os.getenv("AWS_ACCESS_KEY_ID"):
            return f"mock-sns-delivered-{event.event_id[:8]}"

        try:
            client = self._get_sns_client()
            response = client.publish(
                TopicArn=self.topic_arn,
                Message=event.model_dump_json(),
                Subject=(
                    f"[{event.severity.value}] {event.event_type.value} - {event.business_name}"
                )[:100],
                MessageAttributes={
                    "severity": {
                        "DataType": "String",
                        "StringValue": event.severity.value,
                    },
                    "event_type": {
                        "DataType": "String",
                        "StringValue": event.event_type.value,
                    },
                    "application_id": {
                        "DataType": "String",
                        "StringValue": event.application_id,
                    },
                },
            )
            return response.get("MessageId", "sns-unknown")
        except Exception:
            # Fallback seguro que no interrumpe el flujo principal si AWS no responde
            return f"fallback-sns-local-{event.event_id[:8]}"

    async def publish(self, event: CreditUnderwritingEvent) -> str:
        """Alias para publicación de eventos."""
        return await self.publish_event(event)


# Broadcaster global singleton para SSE
global_event_broadcaster = EventBroadcaster()
_default_publisher = MockEventPublisher(broadcaster=global_event_broadcaster)


def get_event_publisher() -> IEventPublisher:
    """Factoría que resuelve el publicador activo según la configuración."""
    if os.getenv("TESTING") == "true":
        return _default_publisher

    if os.getenv("AWS_SNS_TOPIC_ARN") and os.getenv("AWS_ACCESS_KEY_ID"):
        return AwsSnsEventPublisher(broadcaster=global_event_broadcaster)

    return _default_publisher
