import json
import uuid
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel

import yfinance as yf

DATA_DIR = Path(__file__).parent.parent.parent / "data"
PAPER_TRADES_FILE = DATA_DIR / "paper_trades.json"
DEFAULT_BALANCE = 100_000.0


class PaperTrade(BaseModel):
    id: str
    ticker: str
    direction: str  # BUY or SHORT
    shares: float
    entry_price: float
    exit_price: float | None = None
    entry_date: str
    exit_date: str | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    status: str  # open or closed


class PaperAccount(BaseModel):
    starting_balance: float
    cash_balance: float
    open_positions: list[PaperTrade]
    closed_trades: int
    total_realized_pnl: float
    total_unrealized_pnl: float
    total_equity: float


def _load_data() -> dict:
    if PAPER_TRADES_FILE.exists():
        with open(PAPER_TRADES_FILE) as f:
            return json.load(f)
    return {
        "starting_balance": DEFAULT_BALANCE,
        "cash_balance": DEFAULT_BALANCE,
        "trades": [],
    }


def _save_data(data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(PAPER_TRADES_FILE, "w") as f:
        json.dump(data, f, indent=2)


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


def get_account_summary() -> dict:
    data = _load_data()
    trades = data["trades"]
    open_trades = [t for t in trades if t["status"] == "open"]
    closed_trades = [t for t in trades if t["status"] == "closed"]

    total_realized = sum(t.get("pnl", 0) or 0 for t in closed_trades)

    # Calculate unrealized P&L for open positions
    total_unrealized = 0.0
    for t in open_trades:
        try:
            current_price = _get_live_price(t["ticker"])
            if t["direction"] == "BUY":
                unrealized = (current_price - t["entry_price"]) * t["shares"]
            else:  # SHORT
                unrealized = (t["entry_price"] - current_price) * t["shares"]
            total_unrealized += unrealized
        except Exception:
            pass

    position_cost = sum(t["entry_price"] * t["shares"] for t in open_trades)

    return {
        "starting_balance": data["starting_balance"],
        "cash_balance": round(data["cash_balance"], 2),
        "open_positions": [PaperTrade(**t).model_dump() for t in open_trades],
        "closed_trades": len(closed_trades),
        "total_realized_pnl": round(total_realized, 2),
        "total_unrealized_pnl": round(total_unrealized, 2),
        "total_equity": round(data["cash_balance"] + position_cost + total_unrealized, 2),
    }


def open_trade(ticker: str, direction: str, shares: float) -> dict:
    ticker = ticker.upper()
    direction = direction.upper()
    if direction not in ("BUY", "SHORT"):
        raise ValueError("Direction must be BUY or SHORT")
    if shares <= 0:
        raise ValueError("Shares must be positive")

    entry_price = _get_live_price(ticker)
    cost = entry_price * shares

    data = _load_data()
    if cost > data["cash_balance"]:
        raise ValueError(
            f"Insufficient balance. Need ${cost:,.2f}, have ${data['cash_balance']:,.2f}"
        )

    trade = {
        "id": str(uuid.uuid4())[:8],
        "ticker": ticker,
        "direction": direction,
        "shares": shares,
        "entry_price": entry_price,
        "exit_price": None,
        "entry_date": datetime.now().isoformat(),
        "exit_date": None,
        "pnl": None,
        "pnl_pct": None,
        "status": "open",
    }

    data["cash_balance"] -= cost
    data["trades"].append(trade)
    _save_data(data)
    return trade


def close_trade(trade_id: str) -> dict | None:
    data = _load_data()
    for trade in data["trades"]:
        if trade["id"] == trade_id and trade["status"] == "open":
            exit_price = _get_live_price(trade["ticker"])
            trade["exit_price"] = exit_price
            trade["exit_date"] = datetime.now().isoformat()
            trade["status"] = "closed"

            if trade["direction"] == "BUY":
                trade["pnl"] = round((exit_price - trade["entry_price"]) * trade["shares"], 2)
                trade["pnl_pct"] = round(
                    (exit_price - trade["entry_price"]) / trade["entry_price"] * 100, 2
                )
            else:  # SHORT
                trade["pnl"] = round((trade["entry_price"] - exit_price) * trade["shares"], 2)
                trade["pnl_pct"] = round(
                    (trade["entry_price"] - exit_price) / trade["entry_price"] * 100, 2
                )

            # Return cash: entry cost + P&L
            data["cash_balance"] += trade["entry_price"] * trade["shares"] + trade["pnl"]
            _save_data(data)
            return trade
    return None


def get_trade_history() -> list[dict]:
    data = _load_data()
    return [t for t in data["trades"] if t["status"] == "closed"]


def reset_account() -> dict:
    data = {
        "starting_balance": DEFAULT_BALANCE,
        "cash_balance": DEFAULT_BALANCE,
        "trades": [],
    }
    _save_data(data)
    return {"status": "reset", "balance": DEFAULT_BALANCE}
