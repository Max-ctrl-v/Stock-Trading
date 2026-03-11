"""Telegram notification service — sends alerts via Telegram Bot API."""

import httpx
import os
import json
from backend.config import DATA_DIR

_SETTINGS_FILE = DATA_DIR / "telegram_settings.json"
_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _load_settings() -> dict:
    """Load Telegram settings (bot_token, chat_id) from file or env."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # File-stored settings override env vars (user set via UI)
    if _SETTINGS_FILE.exists():
        try:
            with open(_SETTINGS_FILE, "r") as f:
                data = json.load(f)
                bot_token = data.get("bot_token", bot_token)
                chat_id = data.get("chat_id", chat_id)
        except Exception:
            pass

    return {"bot_token": bot_token, "chat_id": chat_id}


def save_settings(bot_token: str, chat_id: str) -> None:
    """Persist Telegram settings to file."""
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_FILE, "w") as f:
        json.dump({"bot_token": bot_token.strip(), "chat_id": chat_id.strip()}, f)


def is_configured() -> bool:
    s = _load_settings()
    return bool(s["bot_token"] and s["chat_id"])


def send_message(text: str) -> dict:
    """Send a Telegram message. Returns {ok, error}."""
    s = _load_settings()
    if not s["bot_token"] or not s["chat_id"]:
        return {"ok": False, "error": "Telegram not configured"}

    url = _TELEGRAM_API.format(token=s["bot_token"])
    try:
        r = httpx.post(
            url,
            json={"chat_id": s["chat_id"], "text": text, "parse_mode": "HTML"},
            timeout=10.0,
        )
        if r.status_code == 200:
            return {"ok": True}
        return {"ok": False, "error": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def notify_price_alert(ticker: str, condition: str, target: float, current: float) -> None:
    """Send a price alert notification."""
    arrow = "📈" if condition == "above" else "📉"
    send_message(
        f"{arrow} <b>Price Alert: {ticker}</b>\n"
        f"Price {condition} <b>${target:.2f}</b>\n"
        f"Current: <b>${current:.2f}</b>"
    )


def notify_signal_change(ticker: str, old_dir: str, new_dir: str, confidence: float) -> None:
    """Send a signal direction change notification."""
    emoji = "🟢" if new_dir == "BUY" else ("🔴" if new_dir == "SELL" else "🟡")
    send_message(
        f"{emoji} <b>Signal Change: {ticker}</b>\n"
        f"{old_dir} → <b>{new_dir}</b>\n"
        f"Confidence: {confidence:.0f}%"
    )


def notify_portfolio_move(total_pnl: float, total_pnl_pct: float) -> None:
    """Send a portfolio P&L alert when it moves more than 2%."""
    arrow = "📈" if total_pnl >= 0 else "📉"
    sign = "+" if total_pnl >= 0 else ""
    send_message(
        f"{arrow} <b>Portfolio Update</b>\n"
        f"P&L: <b>{sign}€{total_pnl:,.2f}</b> ({sign}{total_pnl_pct:.2f}%)"
    )
