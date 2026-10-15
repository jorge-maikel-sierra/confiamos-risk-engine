"""Tests unitarios para el servicio de notificaciones y storytelling de Telegram.

Issue #5 / SPEC-01.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.bot.telegram_notifier import DailyPostStory, TelegramNotifier


def test_daily_post_story_valid_creation():
    """Valida la creación correcta de la historia y el auto-formato de hashtags."""
    story = DailyPostStory(
        day_number=5,
        hook="Casi rompemos producción por confiar ciegamente en el LLM.",
        conflict="Los modelos probabilísticos alucinan con sumas simples de estados financieros.",
        solution="Separamos la matemática en funciones puras determinísticas y usamos LangGraph.",
        hashtags=["100DaysOfCode", "#AIEngineering", "Fintech"],
    )
    assert story.day_number == 5
    # Auto-prefix '#' en los hashtags sin él
    assert story.hashtags == ["#100DaysOfCode", "#AIEngineering", "#Fintech"]
    md = story.format_markdown()
    assert "🚀 Día 5/100 — Confiamos Risk Engine (CRE)" in md
    assert "Casi rompemos producción" in md
    assert "💡 El desafío técnico:" in md
    assert "🛠️ La solución:" in md
    assert "#100DaysOfCode #AIEngineering #Fintech" in md


def test_daily_post_story_invalid_day():
    """Valida que day_number esté restringido al rango 1-100."""
    with pytest.raises(ValidationError):
        DailyPostStory(
            day_number=0,
            hook="Hook",
            conflict="Conflict",
            solution="Solution",
        )

    with pytest.raises(ValidationError):
        DailyPostStory(
            day_number=101,
            hook="Hook",
            conflict="Conflict",
            solution="Solution",
        )


def test_daily_post_story_requires_exactly_three_hashtags():
    """Valida que se exijan estrictamente 3 hashtags."""
    with pytest.raises(ValidationError, match="Se requieren exactamente 3 hashtags"):
        DailyPostStory(
            day_number=1,
            hook="Hook",
            conflict="Conflict",
            solution="Solution",
            hashtags=["#One", "#Two"],
        )

    with pytest.raises(ValidationError, match="Se requieren exactamente 3 hashtags"):
        DailyPostStory(
            day_number=1,
            hook="Hook",
            conflict="Conflict",
            solution="Solution",
            hashtags=["#One", "#Two", "#Three", "#Four"],
        )


@pytest.mark.asyncio
async def test_telegram_notifier_dry_run_explicit():
    """Verifica que el flag dry_run impida llamadas de red externas."""
    notifier = TelegramNotifier(bot_token="fake_token", chat_id="12345")
    story = DailyPostStory(
        day_number=5,
        hook="Hook test",
        conflict="Conflict test",
        solution="Solution test",
    )
    result = await notifier.send_story_draft(story, dry_run=True)
    assert result["status"] == "dry_run"
    assert result["delivered"] is False
    assert "🚀 Día 5/100" in result["message"]


@pytest.mark.asyncio
async def test_telegram_notifier_dry_run_missing_credentials(monkeypatch):
    """Verifica fallback automático a dry_run ante ausencia de credenciales de Telegram."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    notifier = TelegramNotifier(bot_token=None, chat_id=None)
    story = DailyPostStory(
        day_number=1,
        hook="Hook test",
        conflict="Conflict test",
        solution="Solution test",
    )
    result = await notifier.send_story_draft(story, dry_run=False)
    assert result["status"] == "dry_run"
    assert result["delivered"] is False


@pytest.mark.asyncio
async def test_telegram_notifier_send_success():
    """Verifica envío exitoso mockeando la llamada HTTP POST a Telegram."""
    notifier = TelegramNotifier(bot_token="test_token", chat_id="test_chat_id")
    story = DailyPostStory(
        day_number=3,
        hook="Hook test",
        conflict="Conflict test",
        solution="Solution test",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "result": {"message_id": 99}}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await notifier.send_story_draft(story, dry_run=False)

        assert result["status"] == "success"
        assert result["delivered"] is True
        assert result["telegram_response"] == {"ok": True, "result": {"message_id": 99}}
        mock_post.assert_awaited_once()


@pytest.mark.asyncio
async def test_telegram_notifier_send_http_error():
    """Verifica manejo de errores cuando la API de Telegram responde un error HTTP."""
    notifier = TelegramNotifier(bot_token="test_token", chat_id="test_chat_id")
    story = DailyPostStory(
        day_number=3,
        hook="Hook test",
        conflict="Conflict test",
        solution="Solution test",
    )

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"ok": false, "description": "Chat not found"}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await notifier.send_story_draft(story, dry_run=False)

        assert result["status"] == "error"
        assert result["delivered"] is False
        assert result["http_status"] == 400
        mock_post.assert_awaited_once()
