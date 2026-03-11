import json
import uuid
import time
from backend.config import DATA_DIR
from backend.services.stock_data import get_quote
ALERTS_FILE = DATA_DIR / "alerts.json"


def _load_alerts() -> list[dict]:
    if ALERTS_FILE.exists():
        with open(ALERTS_FILE) as f:
            return json.load(f)
    return []


def _save_alerts(alerts: list[dict]):
    DATA_DIR.mkdir(exist_ok=True)
    with open(ALERTS_FILE, "w") as f:
        json.dump(alerts, f, indent=2)


def create_alert(ticker: str, condition: str, target_price: float) -> dict:
    alerts = _load_alerts()
    alert = {
        "id": str(uuid.uuid4())[:8],
        "ticker": ticker.upper(),
        "condition": condition,
        "target_price": target_price,
        "active": True,
        "triggered": False,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    alerts.append(alert)
    _save_alerts(alerts)
    return alert


def get_alerts() -> list[dict]:
    return _load_alerts()


def delete_alert(alert_id: str) -> bool:
    alerts = _load_alerts()
    new_alerts = [a for a in alerts if a["id"] != alert_id]
    if len(new_alerts) == len(alerts):
        return False
    _save_alerts(new_alerts)
    return True


def check_alerts() -> dict:
    """Check all active alerts against current prices."""
    alerts = _load_alerts()
    triggered = []
    changed = False

    for alert in alerts:
        if not alert["active"] or alert["triggered"]:
            continue
        try:
            quote = get_quote(alert["ticker"])
            price = quote.get("price", 0)

            hit = False
            if alert["condition"] == "above" and price >= alert["target_price"]:
                hit = True
            elif alert["condition"] == "below" and price <= alert["target_price"]:
                hit = True

            if hit:
                alert["triggered"] = True
                alert["active"] = False
                triggered.append(alert)
                changed = True
        except Exception:
            pass

    if changed:
        _save_alerts(alerts)

    active = [a for a in alerts if a["active"] and not a["triggered"]]
    return {"alerts": active, "triggered": triggered}
