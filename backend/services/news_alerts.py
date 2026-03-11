import json
import time
import uuid
from typing import Optional

import httpx
from pydantic import BaseModel

from backend.config import PERPLEXITY_API_KEY, DATA_DIR
NEWS_ALERTS_FILE = DATA_DIR / "news_alerts.json"

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


class NewsAlertRule(BaseModel):
    id: str
    ticker: str
    keywords: list[str]
    notify: bool = True
    created_at: str
    updated_at: Optional[str] = None


class TriggeredAlert(BaseModel):
    alert_id: str
    ticker: str
    keyword_matched: str
    headline: str
    snippet: str
    checked_at: str


class CreateNewsAlertRequest(BaseModel):
    ticker: str
    keywords: list[str]
    notify: bool = True


class UpdateNewsAlertRequest(BaseModel):
    ticker: Optional[str] = None
    keywords: Optional[list[str]] = None
    notify: Optional[bool] = None


def _load_alerts() -> list[dict]:
    if NEWS_ALERTS_FILE.exists():
        with open(NEWS_ALERTS_FILE) as f:
            return json.load(f)
    return []


def _save_alerts(alerts: list[dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(NEWS_ALERTS_FILE, "w") as f:
        json.dump(alerts, f, indent=2)


def create_alert(ticker: str, keywords: list[str], notify: bool = True) -> dict:
    """Create a new news keyword alert rule."""
    alerts = _load_alerts()
    alert = {
        "id": str(uuid.uuid4())[:8],
        "ticker": ticker.upper(),
        "keywords": [k.lower().strip() for k in keywords],
        "notify": notify,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "updated_at": None,
    }
    alerts.append(alert)
    _save_alerts(alerts)
    return alert


def get_alerts() -> list[dict]:
    """Return all news alert rules."""
    return _load_alerts()


def delete_alert(alert_id: str) -> bool:
    """Delete an alert rule by ID. Returns True if found and deleted."""
    alerts = _load_alerts()
    original_len = len(alerts)
    alerts = [a for a in alerts if a["id"] != alert_id]
    if len(alerts) == original_len:
        return False
    _save_alerts(alerts)
    return True


def update_alert(alert_id: str, ticker: Optional[str] = None,
                 keywords: Optional[list[str]] = None,
                 notify: Optional[bool] = None) -> Optional[dict]:
    """Update an existing alert rule. Returns updated alert or None if not found."""
    alerts = _load_alerts()
    for alert in alerts:
        if alert["id"] == alert_id:
            if ticker is not None:
                alert["ticker"] = ticker.upper()
            if keywords is not None:
                alert["keywords"] = [k.lower().strip() for k in keywords]
            if notify is not None:
                alert["notify"] = notify
            alert["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            _save_alerts(alerts)
            return alert
    return None


async def _perplexity_news_search(ticker: str, keywords: list[str]) -> str:
    """Search for recent news about a ticker containing specific keywords."""
    if not PERPLEXITY_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY not configured")

    keywords_str = ", ".join(keywords)
    query = (
        f"Search for recent news articles about {ticker} stock related to any of these topics: "
        f"{keywords_str}. For each matching article found, format as:\n"
        f"MATCH: <keyword> | <headline> | <brief snippet>\n"
        f"Only include articles from the past 7 days. If no matches, say NO_MATCHES."
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            PERPLEXITY_URL,
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [
                    {
                        "role": "system",
                        "content": "Search for recent financial news matching the keywords I give you. Just the facts.",
                    },
                    {"role": "user", "content": query},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def _parse_matches(raw_text: str, alert: dict) -> list[TriggeredAlert]:
    """Parse Perplexity response into triggered alert objects."""
    triggered: list[TriggeredAlert] = []
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    if "NO_MATCHES" in raw_text.upper():
        return triggered

    for line in raw_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        if "MATCH:" in line:
            parts = line.split("MATCH:")[-1].split("|")
            if len(parts) >= 3:
                triggered.append(TriggeredAlert(
                    alert_id=alert["id"],
                    ticker=alert["ticker"],
                    keyword_matched=parts[0].strip(),
                    headline=parts[1].strip(),
                    snippet=parts[2].strip(),
                    checked_at=now,
                ))
                continue

        # Fallback: check if any keyword appears in the line
        for kw in alert["keywords"]:
            if kw.lower() in line.lower() and len(line) > 15:
                triggered.append(TriggeredAlert(
                    alert_id=alert["id"],
                    ticker=alert["ticker"],
                    keyword_matched=kw,
                    headline=line[:150],
                    snippet=line,
                    checked_at=now,
                ))
                break

    return triggered


async def check_all_alerts() -> list[TriggeredAlert]:
    """Check all active alert rules against recent news. Returns triggered alerts."""
    alerts = _load_alerts()
    if not alerts:
        return []

    all_triggered: list[TriggeredAlert] = []
    for alert in alerts:
        if not alert.get("notify", True):
            continue
        try:
            raw = await _perplexity_news_search(alert["ticker"], alert["keywords"])
            matches = _parse_matches(raw, alert)
            all_triggered.extend(matches)
        except Exception:
            continue

    return all_triggered
