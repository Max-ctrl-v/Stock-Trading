"""Signal history tracking service for accuracy analysis."""

import json
import uuid
from datetime import datetime, timezone
import yfinance as yf
from backend.config import DATA_DIR
HISTORY_FILE = DATA_DIR / "signal_history.json"
MAX_RECORDS = 500


def _load_history() -> list[dict]:
    """Load signal history from JSON file."""
    if not HISTORY_FILE.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _save_history([])
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_history(records: list[dict]) -> None:
    """Save signal history to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def log_signal(
    ticker: str,
    direction: str,
    confidence: float,
    entry_price: float,
    stop_loss: float,
    take_profit_1: float,
    indicators_snapshot: dict,
) -> dict:
    """Log a new signal record and append to history."""
    record = {
        "id": uuid.uuid4().hex[:8],
        "ticker": ticker.upper(),
        "direction": direction,
        "confidence": confidence,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit_1": take_profit_1,
        "indicators_snapshot": indicators_snapshot,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "outcome": None,
        "outcome_price": None,
        "outcome_date": None,
    }

    records = _load_history()
    records.append(record)

    # Trim oldest if over max
    if len(records) > MAX_RECORDS:
        records = records[-MAX_RECORDS:]

    _save_history(records)
    return record


def get_signal_history(ticker: str = None, limit: int = 50) -> list[dict]:
    """Return signal history, optionally filtered by ticker, newest first."""
    records = _load_history()

    if ticker:
        records = [r for r in records if r["ticker"] == ticker.upper()]

    # Sort newest first
    records.sort(key=lambda r: r["timestamp"], reverse=True)

    return records[:limit]


def evaluate_signals() -> dict:
    """Evaluate pending signals against current prices."""
    records = _load_history()
    pending = [r for r in records if r["outcome"] is None]

    if not pending:
        total = len(records)
        correct = sum(1 for r in records if r["outcome"] == "correct")
        incorrect = sum(1 for r in records if r["outcome"] == "incorrect")
        expired = sum(1 for r in records if r["outcome"] == "expired")
        still_pending = 0
        resolved = correct + incorrect
        accuracy = (correct / resolved * 100) if resolved > 0 else 0.0
        return {
            "evaluated": 0,
            "correct": correct,
            "incorrect": incorrect,
            "expired": expired,
            "pending": still_pending,
            "accuracy_pct": round(accuracy, 1),
        }

    # Batch fetch current prices
    tickers = list({r["ticker"] for r in pending})
    current_prices: dict[str, float] = {}
    try:
        data = yf.download(tickers, period="1d", progress=False)
        if len(tickers) == 1:
            close = data.get("Close")
            if close is not None and len(close) > 0:
                current_prices[tickers[0]] = float(close.iloc[-1])
        else:
            close = data.get("Close")
            if close is not None:
                for t in tickers:
                    if t in close.columns and len(close[t].dropna()) > 0:
                        current_prices[t] = float(close[t].dropna().iloc[-1])
    except Exception:
        # Fallback: fetch individually
        for t in tickers:
            try:
                info = yf.Ticker(t)
                hist = info.history(period="1d")
                if len(hist) > 0:
                    current_prices[t] = float(hist["Close"].iloc[-1])
            except Exception:
                pass

    now = datetime.now(timezone.utc)
    evaluated = 0

    for record in records:
        if record["outcome"] is not None:
            continue

        ticker_sym = record["ticker"]
        price = current_prices.get(ticker_sym)
        if price is None:
            continue

        evaluated += 1
        direction = record["direction"].lower()
        stop = record["stop_loss"]
        tp1 = record["take_profit_1"]

        hit_tp = (price >= tp1) if direction == "buy" else (price <= tp1)
        hit_sl = (price <= stop) if direction == "buy" else (price >= stop)

        if hit_tp:
            record["outcome"] = "correct"
            record["outcome_price"] = price
            record["outcome_date"] = now.isoformat()
        elif hit_sl:
            record["outcome"] = "incorrect"
            record["outcome_price"] = price
            record["outcome_date"] = now.isoformat()
        else:
            # Check if older than 5 days
            signal_time = datetime.fromisoformat(record["timestamp"])
            if signal_time.tzinfo is None:
                signal_time = signal_time.replace(tzinfo=timezone.utc)
            age_days = (now - signal_time).total_seconds() / 86400
            if age_days > 5:
                record["outcome"] = "expired"
                record["outcome_price"] = price
                record["outcome_date"] = now.isoformat()

    _save_history(records)

    correct = sum(1 for r in records if r["outcome"] == "correct")
    incorrect = sum(1 for r in records if r["outcome"] == "incorrect")
    expired_count = sum(1 for r in records if r["outcome"] == "expired")
    still_pending = sum(1 for r in records if r["outcome"] is None)
    resolved = correct + incorrect
    accuracy = (correct / resolved * 100) if resolved > 0 else 0.0

    return {
        "evaluated": evaluated,
        "correct": correct,
        "incorrect": incorrect,
        "expired": expired_count,
        "pending": still_pending,
        "accuracy_pct": round(accuracy, 1),
    }


def get_accuracy_stats(ticker: str = None) -> dict:
    """Return accuracy statistics, optionally filtered by ticker."""
    records = _load_history()

    if ticker:
        records = [r for r in records if r["ticker"] == ticker.upper()]

    total = len(records)
    correct = sum(1 for r in records if r["outcome"] == "correct")
    incorrect = sum(1 for r in records if r["outcome"] == "incorrect")
    expired = sum(1 for r in records if r["outcome"] == "expired")
    pending = sum(1 for r in records if r["outcome"] is None)
    resolved = correct + incorrect
    accuracy = (correct / resolved * 100) if resolved > 0 else 0.0

    return {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "expired": expired,
        "pending": pending,
        "accuracy_pct": round(accuracy, 1),
    }
