import json
import uuid
from datetime import datetime

from pydantic import BaseModel
from backend.config import DATA_DIR
MULTI_LEG_FILE = DATA_DIR / "multi_leg_trades.json"


class Leg(BaseModel):
    id: str
    action: str  # BUY or SELL
    price: float
    shares: float
    date: str


class MultiLegTrade(BaseModel):
    id: str
    ticker: str
    direction: str  # BUY or SHORT
    notes: str
    legs: list[Leg]
    status: str  # open or closed
    created_at: str
    closed_at: str | None = None
    avg_entry: float | None = None
    avg_exit: float | None = None
    total_shares_bought: float
    total_shares_sold: float
    total_pnl: float | None = None


def _load_trades() -> list[dict]:
    if MULTI_LEG_FILE.exists():
        with open(MULTI_LEG_FILE) as f:
            return json.load(f)
    return []


def _save_trades(trades: list[dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(MULTI_LEG_FILE, "w") as f:
        json.dump(trades, f, indent=2)


def _compute_trade_stats(trade: dict) -> dict:
    """Compute avg entry, avg exit, total P&L from legs."""
    legs = trade.get("legs", [])
    direction = trade["direction"]

    # For BUY direction: BUY legs are entries, SELL legs are exits
    # For SHORT direction: SELL legs are entries, BUY legs are exits
    if direction == "BUY":
        entry_legs = [l for l in legs if l["action"] == "BUY"]
        exit_legs = [l for l in legs if l["action"] == "SELL"]
    else:  # SHORT
        entry_legs = [l for l in legs if l["action"] == "SELL"]
        exit_legs = [l for l in legs if l["action"] == "BUY"]

    total_entry_shares = sum(l["shares"] for l in entry_legs)
    total_exit_shares = sum(l["shares"] for l in exit_legs)

    avg_entry = None
    if total_entry_shares > 0:
        avg_entry = round(
            sum(l["price"] * l["shares"] for l in entry_legs) / total_entry_shares, 2
        )

    avg_exit = None
    if total_exit_shares > 0:
        avg_exit = round(
            sum(l["price"] * l["shares"] for l in exit_legs) / total_exit_shares, 2
        )

    total_pnl = None
    if avg_entry is not None and avg_exit is not None and total_exit_shares > 0:
        if direction == "BUY":
            total_pnl = round((avg_exit - avg_entry) * total_exit_shares, 2)
        else:
            total_pnl = round((avg_entry - avg_exit) * total_exit_shares, 2)

    trade["avg_entry"] = avg_entry
    trade["avg_exit"] = avg_exit
    trade["total_shares_bought"] = sum(l["shares"] for l in legs if l["action"] == "BUY")
    trade["total_shares_sold"] = sum(l["shares"] for l in legs if l["action"] == "SELL")
    trade["total_pnl"] = total_pnl
    return trade


def get_all_trades() -> list[dict]:
    trades = _load_trades()
    return [_compute_trade_stats(t) for t in trades]


def get_trade(trade_id: str) -> dict | None:
    trades = _load_trades()
    for t in trades:
        if t["id"] == trade_id:
            return _compute_trade_stats(t)
    return None


def create_trade(ticker: str, direction: str, notes: str = "") -> dict:
    ticker = ticker.upper()
    direction = direction.upper()
    if direction not in ("BUY", "SHORT"):
        raise ValueError("Direction must be BUY or SHORT")

    trades = _load_trades()
    trade = {
        "id": str(uuid.uuid4())[:8],
        "ticker": ticker,
        "direction": direction,
        "notes": notes,
        "legs": [],
        "status": "open",
        "created_at": datetime.now().isoformat(),
        "closed_at": None,
        "avg_entry": None,
        "avg_exit": None,
        "total_shares_bought": 0,
        "total_shares_sold": 0,
        "total_pnl": None,
    }
    trades.append(trade)
    _save_trades(trades)
    return trade


def add_leg(
    trade_id: str, action: str, price: float, shares: float, date: str | None = None
) -> dict | None:
    action = action.upper()
    if action not in ("BUY", "SELL"):
        raise ValueError("Action must be BUY or SELL")
    if shares <= 0:
        raise ValueError("Shares must be positive")
    if price <= 0:
        raise ValueError("Price must be positive")

    trades = _load_trades()
    for trade in trades:
        if trade["id"] == trade_id:
            if trade["status"] != "open":
                raise ValueError("Cannot add legs to a closed trade")

            leg = {
                "id": str(uuid.uuid4())[:8],
                "action": action,
                "price": price,
                "shares": shares,
                "date": date or datetime.now().isoformat(),
            }
            trade["legs"].append(leg)
            _save_trades(trades)
            return _compute_trade_stats(trade)
    return None


def close_trade(trade_id: str) -> dict | None:
    trades = _load_trades()
    for trade in trades:
        if trade["id"] == trade_id and trade["status"] == "open":
            trade["status"] = "closed"
            trade["closed_at"] = datetime.now().isoformat()
            _save_trades(trades)
            return _compute_trade_stats(trade)
    return None


def delete_trade(trade_id: str) -> bool:
    trades = _load_trades()
    new_trades = [t for t in trades if t["id"] != trade_id]
    if len(new_trades) == len(trades):
        return False
    _save_trades(new_trades)
    return True
