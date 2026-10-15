"""Servicio de generación y envío de publicaciones diarias vía Telegram (Issue #5 / SPEC-01).

Formato de Storytelling en 4 partes:
1. Gancho (Hook): El problema o error concreto del día.
2. Conflicto Técnico: La decisión arquitectónica o trade-off.
3. Solución y Enlace: Implementación testeada y link a GitHub.
4. Exactamente 3 hashtags con alcance para LinkedIn y X.
"""

import os
from typing import Any

import httpx
from pydantic import BaseModel, Field, field_validator


class DailyPostStory(BaseModel):
    """Estructura de la historia diaria para redes sociales."""

    day_number: int = Field(ge=1, le=100, description="Número del día en el reto de 100 días")
    hook: str = Field(description="Frase de impacto inicial sobre el dolor o error del día")
    conflict: str = Field(description="El trade-off técnico o desafío arquitectónico")
    solution: str = Field(description="Cómo quedó resuelto de forma determinística y testeada")
    project_link: str = Field(
        default="https://github.com/jorge-maikel-sierra/confiamos-risk-engine",
        description="Enlace al repositorio o pull request",
    )
    hashtags: list[str] = Field(
        default_factory=lambda: ["#100DaysOfCode", "#AIEngineering", "#Fintech"],
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
            f"🚀 Día {self.day_number}/100 — Confiamos Risk Engine (CRE)\n\n"
            f"{self.hook}\n\n"
            f"💡 El desafío técnico:\n{self.conflict}\n\n"
            f"🛠️ La solución:\n{self.solution}\n\n"
            f"🔗 Código y trazabilidad en GitHub:\n{self.project_link}\n\n"
            f"{tags_str}"
        )


class TelegramNotifier:
    """Cliente para despachar borradores de publicaciones a Telegram."""

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = "https://api.telegram.org"

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
