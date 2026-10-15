"""Script ejecutable para enviar la publicación diaria a Telegram (SPEC-01 / Automations)."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Cargar variables de entorno desde apps/api/.env
api_root = Path(__file__).resolve().parent.parent.parent
env_file = api_root / ".env"
load_dotenv(env_file)

if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

from src.bot.telegram_notifier import DailyPostStory, TelegramNotifier


async def send_daily_post(day_number: int = 10, dry_run: bool = False) -> dict:
    story = DailyPostStory(
        day_number=day_number,
        hook="Aprobamos créditos con IA, pero la Superintendencia no acepta 'el modelo dijo que sí' como garantía contable.",
        conflict="Los modelos probabilísticos no pueden fijar reservas bancarias ni responder ante auditorías sin una matriz de ponderación determinística y trazable.",
        solution="Diseñamos una matriz de scoring multicriterio A–E (DSCR 35%, Liquidez 30%, Concentración 20%, IA 15%) que calcula la provisión contable en USD y sella el legajo con SHA-256.",
        project_link="https://github.com/jorge-maikel-sierra/confiamos-risk-engine",
        hashtags=["#100DaysOfCode", "#AIEngineering", "#Fintech"],
    )

    notifier = TelegramNotifier()
    print(f"Despachando historia técnica del Día {story.day_number} a Telegram...")
    res = await notifier.send_story_draft(story, dry_run=dry_run)
    return res


if __name__ == "__main__":
    day = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 10
    is_dry = "--dry-run" in sys.argv
    result = asyncio.run(send_daily_post(day_number=day, dry_run=is_dry))
    if result.get("delivered"):
        print("✅ Mensaje enviado exitosamente a Telegram!")
    elif result.get("status") == "dry_run":
        print("ℹ️ Mensaje generado en modo simulación (dry_run):")
        print(result.get("message"))
    else:
        print(f"❌ Error al enviar mensaje: {result}")
        sys.exit(1)
