import json
import uuid
import time
from backend.config import DATA_DIR
JOURNAL_FILE = DATA_DIR / "journal.json"


def _load_journal() -> list[dict]:
    if JOURNAL_FILE.exists():
        with open(JOURNAL_FILE) as f:
            return json.load(f)
    return []


def _save_journal(trades: list[dict]):
    DATA_DIR.mkdir(exist_ok=True)
    with open(JOURNAL_FILE, "w") as f:
        json.dump(trades, f, indent=2)


def add_trade(ticker: str, direction: str, entry_price: float, shares: float,
              notes: str = "", tags: list[str] = None) -> dict:
    trades = _load_journal()
    trade = {
        "id": str(uuid.uuid4())[:8],
        "ticker": ticker.upper(),
        "direction": direction.upper(),
        "entry_price": entry_price,
        "exit_price": None,
        "shares": shares,
        "entry_date": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "exit_date": None,
        "pnl": None,
        "pnl_pct": None,
        "notes": notes,
        "tags": tags or [],
        "status": "open",
    }
    trades.append(trade)
    _save_journal(trades)
    return trade


def close_trade(trade_id: str, exit_price: float) -> dict | None:
    trades = _load_journal()
    for trade in trades:
        if trade["id"] == trade_id and trade["status"] == "open":
            trade["exit_price"] = exit_price
            trade["exit_date"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            trade["status"] = "closed"

            # Calculate P&L
            if trade["direction"] == "BUY":
                trade["pnl"] = round((exit_price - trade["entry_price"]) * trade["shares"], 2)
                trade["pnl_pct"] = round((exit_price - trade["entry_price"]) / trade["entry_price"] * 100, 2)
            else:  # SELL (short)
                trade["pnl"] = round((trade["entry_price"] - exit_price) * trade["shares"], 2)
                trade["pnl_pct"] = round((trade["entry_price"] - exit_price) / trade["entry_price"] * 100, 2)

            _save_journal(trades)
            return trade
    return None


def delete_trade(trade_id: str) -> bool:
    trades = _load_journal()
    new_trades = [t for t in trades if t["id"] != trade_id]
    if len(new_trades) == len(trades):
        return False
    _save_journal(new_trades)
    return True


def get_all_trades() -> list[dict]:
    return _load_journal()


def compute_stats() -> dict:
    trades = _load_journal()
    closed = [t for t in trades if t["status"] == "closed" and t["pnl_pct"] is not None]

    if not closed:
        return {
            "total_trades": len(trades),
            "closed_trades": 0,
            "win_rate": 0,
            "avg_gain_pct": 0,
            "avg_loss_pct": 0,
            "profit_factor": 0,
            "best_trade_pct": 0,
            "worst_trade_pct": 0,
            "total_pnl": 0,
        }

    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] <= 0]

    win_rate = len(wins) / len(closed) * 100 if closed else 0
    avg_gain = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0

    total_gains = sum(t["pnl"] for t in wins)
    total_losses = abs(sum(t["pnl"] for t in losses))
    profit_factor = total_gains / total_losses if total_losses > 0 else float('inf') if total_gains > 0 else 0

    pnl_pcts = [t["pnl_pct"] for t in closed]

    return {
        "total_trades": len(trades),
        "closed_trades": len(closed),
        "win_rate": round(win_rate, 1),
        "avg_gain_pct": round(avg_gain, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else 999.0,
        "best_trade_pct": round(max(pnl_pcts), 2),
        "worst_trade_pct": round(min(pnl_pcts), 2),
        "total_pnl": round(sum(t["pnl"] for t in closed), 2),
    }
