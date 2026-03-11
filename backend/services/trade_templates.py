import json
import uuid
from pathlib import Path
from datetime import datetime

import yfinance as yf
from pydantic import BaseModel

DATA_DIR = Path(__file__).parent.parent.parent / "data"
TEMPLATES_FILE = DATA_DIR / "trade_templates.json"


class TradeTemplate(BaseModel):
    id: str
    name: str
    direction: str  # BUY or SHORT
    risk_pct: float
    stop_loss_pct: float
    take_profit_1_pct: float
    take_profit_2_pct: float | None = None
    notes: str = ""
    created_at: str


class AppliedTemplate(BaseModel):
    template_name: str
    ticker: str
    direction: str
    current_price: float
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float | None = None
    risk_per_share: float
    reward_risk_ratio_tp1: float
    reward_risk_ratio_tp2: float | None = None


def _load_templates() -> list[dict]:
    if TEMPLATES_FILE.exists():
        with open(TEMPLATES_FILE) as f:
            return json.load(f)
    return []


def _save_templates(templates: list[dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(TEMPLATES_FILE, "w") as f:
        json.dump(templates, f, indent=2)


def _get_live_price(ticker: str) -> float:
    stock = yf.Ticker(ticker)
    info = stock.fast_info
    price = getattr(info, "last_price", None)
    if price is None:
        hist = stock.history(period="1d")
        if hist.empty:
            raise ValueError(f"Cannot get price for {ticker}")
        price = float(hist["Close"].iloc[-1])
    return round(float(price), 2)


def get_all_templates() -> list[dict]:
    return _load_templates()


def get_template(template_id: str) -> dict | None:
    templates = _load_templates()
    for t in templates:
        if t["id"] == template_id:
            return t
    return None


def create_template(
    name: str,
    direction: str,
    risk_pct: float,
    stop_loss_pct: float,
    take_profit_1_pct: float,
    take_profit_2_pct: float | None = None,
    notes: str = "",
) -> dict:
    direction = direction.upper()
    if direction not in ("BUY", "SHORT"):
        raise ValueError("Direction must be BUY or SHORT")

    templates = _load_templates()
    template = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "direction": direction,
        "risk_pct": risk_pct,
        "stop_loss_pct": stop_loss_pct,
        "take_profit_1_pct": take_profit_1_pct,
        "take_profit_2_pct": take_profit_2_pct,
        "notes": notes,
        "created_at": datetime.now().isoformat(),
    }
    templates.append(template)
    _save_templates(templates)
    return template


def delete_template(template_id: str) -> bool:
    templates = _load_templates()
    new_templates = [t for t in templates if t["id"] != template_id]
    if len(new_templates) == len(templates):
        return False
    _save_templates(new_templates)
    return True


def apply_template(template_id: str, ticker: str) -> dict:
    template = get_template(template_id)
    if not template:
        raise ValueError("Template not found")

    ticker = ticker.upper()
    current_price = _get_live_price(ticker)
    direction = template["direction"]

    if direction == "BUY":
        stop_loss = round(current_price * (1 - template["stop_loss_pct"] / 100), 2)
        tp1 = round(current_price * (1 + template["take_profit_1_pct"] / 100), 2)
        tp2 = (
            round(current_price * (1 + template["take_profit_2_pct"] / 100), 2)
            if template.get("take_profit_2_pct")
            else None
        )
        risk_per_share = round(current_price - stop_loss, 2)
    else:  # SHORT
        stop_loss = round(current_price * (1 + template["stop_loss_pct"] / 100), 2)
        tp1 = round(current_price * (1 - template["take_profit_1_pct"] / 100), 2)
        tp2 = (
            round(current_price * (1 - template["take_profit_2_pct"] / 100), 2)
            if template.get("take_profit_2_pct")
            else None
        )
        risk_per_share = round(stop_loss - current_price, 2)

    reward1 = abs(tp1 - current_price)
    rr1 = round(reward1 / risk_per_share, 2) if risk_per_share > 0 else 0

    rr2 = None
    if tp2 is not None:
        reward2 = abs(tp2 - current_price)
        rr2 = round(reward2 / risk_per_share, 2) if risk_per_share > 0 else 0

    return {
        "template_name": template["name"],
        "ticker": ticker,
        "direction": direction,
        "current_price": current_price,
        "entry_price": current_price,
        "stop_loss": stop_loss,
        "take_profit_1": tp1,
        "take_profit_2": tp2,
        "risk_per_share": risk_per_share,
        "reward_risk_ratio_tp1": rr1,
        "reward_risk_ratio_tp2": rr2,
    }
