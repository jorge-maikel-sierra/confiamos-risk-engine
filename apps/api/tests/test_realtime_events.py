"""Tests unitarios y de integración para la arquitectura de eventos en tiempo real (SPEC-06).

Cubre:
1. Creación y serialización de eventos de dominio (CreditUnderwritingEvent).
2. Formato estándar Server-Sent Events (SSE).
3. Distribución asíncrona mediante EventBroadcaster y MockEventPublisher.
4. Adaptador de AWS SNS con fallback resiliente para pruebas offline.
5. Formateo y despacho de alertas a Telegram según severidad.
6. Endpoint HTTP de streaming SSE (/api/v1/underwritings/events).
"""

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from src.bot.telegram_notifier import TelegramNotifier
from src.domain.events import (
    CreditEventType,
    CreditUnderwritingEvent,
    EventBroadcaster,
    EventSeverity,
    MockEventPublisher,
)
from src.infrastructure.aws_sns_adapter import (
    AwsSnsEventPublisher,
    global_event_broadcaster,
)
from src.main import app


def test_credit_underwriting_event_creation_and_defaults():
    """Valida la instanciación de CreditUnderwritingEvent con UUIDs y timestamps automáticos."""
    event = CreditUnderwritingEvent(
        event_type=CreditEventType.APPLICATION_SUBMITTED,
        severity=EventSeverity.INFO,
        application_id="APP-TEST01",
        associated_id="CONF-101",
        business_name="Ferretería El Tornillo SAS",
        summary="Nueva solicitud recibida.",
        payload={"requested_amount_usd": 50000.0},
    )

    assert event.event_id is not None
    assert len(event.event_id) > 10
    assert event.event_type == CreditEventType.APPLICATION_SUBMITTED
    assert event.severity == EventSeverity.INFO
    assert event.application_id == "APP-TEST01"
    assert "T" in event.timestamp  # ISO format UTC


def test_credit_underwriting_event_to_sse_message():
    """Valida la serialización estándar SSE con id, evento y data en formato JSON."""
    event = CreditUnderwritingEvent(
        event_type=CreditEventType.CRITICAL_RISK_DETECTED,
        severity=EventSeverity.CRITICAL,
        application_id="APP-RISK99",
        associated_id="CONF-999",
        business_name="Comercializadora Al Límite",
        summary="Déficit severo de cobertura de deuda.",
        payload={"dscr": 0.65, "anomaly_flags": ["FLAG_DEFICIT_DSCR"]},
    )

    sse_str = event.to_sse_message()
    assert sse_str.startswith("event: credit_event\n")
    assert f"id: {event.event_id}\n" in sse_str
    assert "data: {" in sse_str
    assert sse_str.endswith("\n\n")

    # Extraer el bloque data y validar JSON
    data_line = [line for line in sse_str.split("\n") if line.startswith("data: ")][0]
    data_json = json.loads(data_line.replace("data: ", ""))
    assert data_json["event_type"] == "CRITICAL_RISK_DETECTED"
    assert data_json["severity"] == "CRITICAL"
    assert data_json["payload"]["dscr"] == 0.65


@pytest.mark.asyncio
async def test_event_broadcaster_pub_sub():
    """Valida que EventBroadcaster entregue eventos a suscriptores asíncronos y limpie la cola."""
    broadcaster = EventBroadcaster()
    received_events: list[CreditUnderwritingEvent] = []

    test_event = CreditUnderwritingEvent(
        event_type=CreditEventType.PENDING_HUMAN_REVIEW,
        severity=EventSeverity.WARNING,
        application_id="APP-REV01",
        associated_id="CONF-303",
        business_name="Servicios Integrales SAS",
        summary="En espera de resolución de comité.",
    )

    async def subscriber_task():
        gen = broadcaster.subscribe()
        try:
            async for ev in gen:
                received_events.append(ev)
                break  # Desconectar tras recibir un evento
        finally:
            await gen.aclose()

    task = asyncio.create_task(subscriber_task())
    await asyncio.sleep(0.01)

    assert len(broadcaster._subscribers) == 1

    await broadcaster.broadcast(test_event)
    await task

    assert len(received_events) == 1
    assert received_events[0].application_id == "APP-REV01"
    # Verificar que el suscriptor fue retirado al finalizar el generador
    assert len(broadcaster._subscribers) == 0


@pytest.mark.asyncio
async def test_mock_event_publisher():
    """Valida que MockEventPublisher registre eventos y los entregue al broadcaster."""
    broadcaster = EventBroadcaster()
    publisher = MockEventPublisher(broadcaster=broadcaster)
    received = []

    async def sub():
        async for ev in broadcaster.subscribe():
            received.append(ev)
            break

    task = asyncio.create_task(sub())
    await asyncio.sleep(0.01)

    event = CreditUnderwritingEvent(
        event_type=CreditEventType.HUMAN_RESOLVED,
        severity=EventSeverity.INFO,
        application_id="APP-OK44",
        associated_id="CONF-404",
        business_name="Tecnología Futura SAS",
        summary="Aprobado por comité.",
    )

    delivery_id = await publisher.publish_event(event)
    await task

    assert delivery_id.startswith("mock-msg-")
    assert len(publisher.published_events) == 1
    assert len(received) == 1
    assert received[0].event_id == event.event_id


@pytest.mark.asyncio
async def test_aws_sns_publisher_fallback_in_test_mode(monkeypatch):
    """Valida que AwsSnsEventPublisher retorne ID simulado sin invocar AWS en entorno de prueba."""
    monkeypatch.setenv("TESTING", "true")
    broadcaster = EventBroadcaster()
    publisher = AwsSnsEventPublisher(
        topic_arn="arn:aws:sns:us-east-1:111122223333:cre-events",
        region_name="us-east-1",
        broadcaster=broadcaster,
    )

    event = CreditUnderwritingEvent(
        event_type=CreditEventType.APPLICATION_SUBMITTED,
        severity=EventSeverity.INFO,
        application_id="APP-SNS-01",
        associated_id="CONF-505",
        business_name="Agropecuaria El Roble",
        summary="Solicitud recibida.",
    )

    msg_id = await publisher.publish_event(event)
    assert msg_id.startswith("mock-sns-delivered-")


@pytest.mark.asyncio
async def test_aws_sns_publisher_calls_boto3_when_configured(monkeypatch):
    """Valida la invocación a client.publish de boto3 con atributos de mensaje tipados."""
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "mock_key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "mock_secret")

    publisher = AwsSnsEventPublisher(
        topic_arn="arn:aws:sns:us-east-1:111122223333:cre-events",
        region_name="us-east-1",
    )

    mock_client = MagicMock()
    mock_client.publish.return_value = {"MessageId": "sns-msg-987654321"}
    publisher._client = mock_client

    event = CreditUnderwritingEvent(
        event_type=CreditEventType.CRITICAL_RISK_DETECTED,
        severity=EventSeverity.CRITICAL,
        application_id="APP-SNS-CRIT",
        associated_id="CONF-909",
        business_name="Riesgo Extremo SAS",
        summary="Alerta crítica.",
    )

    msg_id = await publisher.publish_event(event)
    assert msg_id == "sns-msg-987654321"

    mock_client.publish.assert_called_once()
    call_kwargs = mock_client.publish.call_args.kwargs
    assert call_kwargs["TopicArn"] == "arn:aws:sns:us-east-1:111122223333:cre-events"
    assert call_kwargs["MessageAttributes"]["severity"]["StringValue"] == "CRITICAL"
    assert call_kwargs["MessageAttributes"]["event_type"]["StringValue"] == "CRITICAL_RISK_DETECTED"
    assert call_kwargs["MessageAttributes"]["application_id"]["StringValue"] == "APP-SNS-CRIT"


def test_telegram_risk_alert_formatting():
    """Valida el formateo Markdown de alertas para Telegram según severidad."""
    notifier = TelegramNotifier()

    # 1. Alerta Crítica
    crit_event = CreditUnderwritingEvent(
        event_type=CreditEventType.CRITICAL_RISK_DETECTED,
        severity=EventSeverity.CRITICAL,
        application_id="APP-CRIT-99",
        associated_id="CONF-123",
        business_name="Manufacturas Andinas SAS",
        summary="Déficit de liquidez e insolvencia estructural.",
        payload={
            "requested_amount_usd": 120000.0,
            "dscr": 0.72,
            "anomaly_flags": ["FLAG_DEFICIT_DSCR", "FLAG_OVERDRAFT_DETECTED"],
            "recommendation": "RECHAZADO",
        },
    )

    crit_md = notifier.format_risk_alert(crit_event)
    assert "🚨 *ALERTA CRÍTICA DE RIESGO*" in crit_md
    assert "Manufacturas Andinas SAS" in crit_md
    assert "`APP-CRIT-99`" in crit_md
    assert "$120,000.00 USD" in crit_md
    assert "0.72" in crit_md
    assert "FLAG_DEFICIT_DSCR, FLAG_OVERDRAFT_DETECTED" in crit_md
    assert "RECHAZADO" in crit_md
    assert "[Ver Expediente en Dashboard Web]" in crit_md

    # 2. Alerta de Advertencia
    warn_event = CreditUnderwritingEvent(
        event_type=CreditEventType.PENDING_HUMAN_REVIEW,
        severity=EventSeverity.WARNING,
        application_id="APP-WARN-11",
        associated_id="CONF-456",
        business_name="Soluciones Logísticas",
        summary="Concentración elevada de cartera en un solo cliente.",
        payload={"requested_amount_usd": 30000.0},
    )
    warn_md = notifier.format_risk_alert(warn_event)
    assert "⚠️ *ATENCIÓN REQUERIDA (COMITÉ)*" in warn_md

    # 3. Alerta Informativa
    info_event = CreditUnderwritingEvent(
        event_type=CreditEventType.HUMAN_RESOLVED,
        severity=EventSeverity.INFO,
        application_id="APP-OK-01",
        associated_id="CONF-789",
        business_name="Textiles del Valle",
        summary="Aprobado por oficial de crédito.",
        payload={"requested_amount_usd": 50000.0, "recommendation": "APROBADO"},
    )
    info_md = notifier.format_risk_alert(info_event)
    assert "✅ *ACTUALIZACIÓN CREDITICIA*" in info_md


@pytest.mark.asyncio
async def test_telegram_send_risk_alert_dry_run():
    """Valida que send_risk_alert retorne simulación en modo dry_run o sin credenciales."""
    notifier = TelegramNotifier()
    event = CreditUnderwritingEvent(
        event_type=CreditEventType.APPLICATION_SUBMITTED,
        severity=EventSeverity.INFO,
        application_id="APP-TGMOCK",
        associated_id="CONF-111",
        business_name="Panificadora La Espiga",
        summary="Radicación registrada.",
    )

    result = await notifier.send_risk_alert(event, dry_run=True)
    assert result["status"] == "dry_run"
    assert result["delivered"] is False
    assert "Panificadora La Espiga" in result["message"]


@pytest.mark.asyncio
async def test_sse_endpoint_header_and_streaming():
    """Valida que el endpoint /events responda text/event-stream y emita eventos."""
    from fastapi.responses import StreamingResponse

    from src.api.routes.underwriting import stream_underwriting_events

    # 1. Validar que la ruta canónica esté registrada en el esquema OpenAPI de FastAPI
    assert "/api/v1/underwritings/events" in app.openapi()["paths"]

    # 2. Invocar endpoint y validar cabeceras SSE estándar
    response = await stream_underwriting_events()
    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"
    assert response.headers.get("Cache-Control") == "no-cache"
    assert response.headers.get("Connection") == "keep-alive"
    assert response.headers.get("X-Accel-Buffering") == "no"

    iter_body = response.body_iterator

    # 3. Leer el heartbeat inicial que confirma la apertura y suscripción del canal SSE
    ping_chunk = await anext(iter_body)
    assert ping_chunk == ": ping\n\n"
    assert len(global_event_broadcaster._subscribers) >= 1

    # 4. Difundir evento de prueba mediante el broadcaster global
    event = CreditUnderwritingEvent(
        event_type=CreditEventType.APPLICATION_SUBMITTED,
        severity=EventSeverity.INFO,
        application_id="APP-SSE-TEST",
        associated_id="CONF-999",
        business_name="Compañía de Prueba SSE",
        summary="Evento para prueba de streaming.",
    )
    await global_event_broadcaster.broadcast(event)

    # 5. Leer el evento emitido a través del iterador SSE
    event_chunk = await anext(iter_body)
    assert "event: credit_event" in event_chunk
    assert "APP-SSE-TEST" in event_chunk
    assert "Compañía de Prueba SSE" in event_chunk

    # 6. Cerrar iterador y verificar limpieza de cola de suscriptor
    await iter_body.aclose()
