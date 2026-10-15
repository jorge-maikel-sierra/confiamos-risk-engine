"""Servicio de generación y envío de notificaciones y alertas vía Telegram (SPEC-01 y SPEC-06).

Soporta:
1. Storytelling de 4 partes para LinkedIn/X (SPEC-01).
2. Alertas operativas y de riesgo crediticio según severidad (SPEC-06).
"""

import os
from typing import Any

import httpx
from pydantic import BaseModel, Field, field_validator

from src.domain.events import CreditUnderwritingEvent, EventSeverity


class DailyPostStory(BaseModel):
    """Estructura de la historia diaria para redes sociales."""

    day_number: int = Field(
        ge=1,
        le=100,
        description="Día del plan de desarrollo y entrega a 100 días para cliente real",
    )
    hook: str = Field(description="Frase de impacto inicial sobre el dolor o error del día")
    conflict: str = Field(description="El trade-off técnico o desafío arquitectónico")
    solution: str = Field(description="Cómo quedó resuelto de forma determinística y testeada")
    project_link: str = Field(
        default="https://github.com/jorge-maikel-sierra/confiamos-risk-engine",
        description="Enlace al repositorio o pull request",
    )
    hashtags: list[str] = Field(
        default_factory=lambda: ["#Fintech", "#SoftwareEngineering", "#AIEngineering"],
        description="Lista de hashtags (exactamente 3)",
    )

    @field_validator("hashtags")
    @classmethod
    def validate_three_hashtags(cls, v: list[str]) -> list[str]:
        if len(v) != 3:
            raise ValueError(f"Se requieren exactamente 3 hashtags, se recibieron {len(v)}.")
        return [h if h.startswith("#") else f"#{h}" for h in v]

    def format_markdown(self) -> str:
        """Formatea la historia con espaciado óptimo para lectura en LinkedIn y X."""
        tags_str = " ".join(self.hashtags)
        return (
            f"🚀 Día {self.day_number}/100 — Confiamos Risk Engine (CRE)\n"
            f"📦 Proyecto de la Vida Real | Entrega Pactada a 100 Días\n\n"
            f"{self.hook}\n\n"
            f"💡 El desafío técnico:\n{self.conflict}\n\n"
            f"🛠️ La solución:\n{self.solution}\n\n"
            f"🔗 Código y trazabilidad en GitHub:\n{self.project_link}\n\n"
            f"{tags_str}"
        )


class TelegramNotifier:
    """Cliente para despachar publicaciones y alertas de riesgo a Telegram."""

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = "https://api.telegram.org"

    def format_risk_alert(self, event: CreditUnderwritingEvent) -> str:
        """Formatea la alerta de riesgo para lectura clara en Telegram."""
        icons = {
            EventSeverity.CRITICAL: "🚨 *ALERTA CRÍTICA DE RIESGO*",
            EventSeverity.WARNING: "⚠️ *ATENCIÓN REQUERIDA (COMITÉ)*",
            EventSeverity.INFO: "✅ *ACTUALIZACIÓN CREDITICIA*",
        }
        header = icons.get(event.severity, "📢 *NOTIFICACIÓN CREDITICIA*")
        amount = event.payload.get("requested_amount_usd", 0.0)
        dscr = event.payload.get("dscr")
        dscr_str = f"{dscr:.2f}" if isinstance(dscr, (int, float)) else "N/A"
        flags = event.payload.get("anomaly_flags", [])
        flags_str = ", ".join(flags) if flags else "Ninguna"
        verdict = event.payload.get("recommendation", "PENDIENTE")

        dashboard_url = os.getenv(
            "WEB_DASHBOARD_URL",
            f"http://localhost:3000/underwritings/{event.application_id}",
        )

        return (
            f"{header}\n\n"
            f"🏢 *Empresa:* {event.business_name}\n"
            f"📋 *Expediente:* `{event.application_id}`\n"
            f"💵 *Monto:* ${amount:,.2f} USD\n"
            f"📊 *DSCR:* {dscr_str}\n"
            f"🚩 *Alertas:* {flags_str}\n"
            f"⚖️ *Dictamen:* {verdict}\n\n"
            f"📝 *Resumen:* {event.summary}\n\n"
            f"🔗 [Ver Expediente en Dashboard Web]({dashboard_url})"
        )

    async def send_story_draft(
        self,
        story: DailyPostStory,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Envía el borrador de storytelling al chat de Telegram configurado."""
        formatted_message = story.format_markdown()

        # Modo Dry Run o credenciales no configuradas
        if dry_run or not self.bot_token or not self.chat_id:
            return {
                "status": "dry_run",
                "delivered": False,
                "message": formatted_message,
                "note": "Modo simulación activo o faltan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID.",
            }

        endpoint = f"{self.base_url}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": formatted_message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(endpoint, json=payload)
            if response.status_code != 200:
                return {
                    "status": "error",
                    "delivered": False,
                    "http_status": response.status_code,
                    "response_text": response.text,
                    "message": formatted_message,
                }

            return {
                "status": "success",
                "delivered": True,
                "telegram_response": response.json(),
                "message": formatted_message,
            }

    async def send_risk_alert(
        self,
        event: CreditUnderwritingEvent,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Envía una alerta estructurada de riesgo a Telegram."""
        formatted_message = self.format_risk_alert(event)

        if dry_run or not self.bot_token or not self.chat_id:
            return {
                "status": "dry_run",
                "delivered": False,
                "message": formatted_message,
                "note": "Modo simulación activo o faltan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID.",
            }

        endpoint = f"{self.base_url}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": formatted_message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(endpoint, json=payload)
            if response.status_code != 200:
                return {
                    "status": "error",
                    "delivered": False,
                    "http_status": response.status_code,
                    "response_text": response.text,
                    "message": formatted_message,
                }

            return {
                "status": "success",
                "delivered": True,
                "telegram_response": response.json(),
                "message": formatted_message,
            }
