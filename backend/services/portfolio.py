import json
from pathlib import Path
from datetime import datetime

DATA_FILE = Path(__file__).parent.parent.parent / "data" / "portfolio.json"


def _load() -> dict:
    if not DATA_FILE.exists():
        return {"positions": [], "settings": {"account_size": 10000, "risk_pct": 2.5}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def _save(data: dict):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_positions() -> list[dict]:
    return _load()["positions"]


def add_position(ticker: str, shares: float, avg_cost: float) -> dict:
    data = _load()
    position = {
        "ticker": ticker.upper(),
        "shares": shares,
        "avg_cost": avg_cost,
        "added_at": datetime.now().isoformat(),
    }

    # Check if position already exists — average in
    for p in data["positions"]:
        if p["ticker"] == ticker.upper():
            total_shares = p["shares"] + shares
            p["avg_cost"] = round(
                (p["avg_cost"] * p["shares"] + avg_cost * shares) / total_shares, 2
            )
            p["shares"] = total_shares
            _save(data)
            return p

    data["positions"].append(position)
    _save(data)
    return position


def remove_position(ticker: str) -> bool:
    data = _load()
    original_len = len(data["positions"])
    data["positions"] = [p for p in data["positions"] if p["ticker"] != ticker.upper()]
    if len(data["positions"]) < original_len:
        _save(data)
        return True
    return False


def get_settings() -> dict:
    return _load().get("settings", {"account_size": 10000, "risk_pct": 2.5})


def update_settings(account_size: float = None, risk_pct: float = None) -> dict:
    data = _load()
    if "settings" not in data:
        data["settings"] = {"account_size": 10000, "risk_pct": 2.5}
    if account_size is not None:
        data["settings"]["account_size"] = account_size
    if risk_pct is not None:
        data["settings"]["risk_pct"] = risk_pct
    _save(data)
    return data["settings"]
