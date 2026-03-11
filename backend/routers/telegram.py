"""Telegram notification config and test endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel
from backend.services.telegram import send_message, save_settings, is_configured, _load_settings

router = APIRouter()


class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str


@router.get("/status")
async def telegram_status():
    """Check if Telegram is configured."""
    s = _load_settings()
    return {
        "configured": is_configured(),
        "chat_id": s["chat_id"] if s["chat_id"] else None,
        "bot_token_set": bool(s["bot_token"]),
    }


@router.post("/config")
async def configure_telegram(config: TelegramConfig):
    """Save Telegram bot token and chat ID."""
    save_settings(config.bot_token, config.chat_id)
    return {"ok": True, "message": "Telegram configured"}


@router.post("/test")
async def test_telegram():
    """Send a test message to verify the configuration works."""
    result = send_message("✅ <b>Stock Tool Alert Test</b>\nTelegram notifications are working!")
    return result
