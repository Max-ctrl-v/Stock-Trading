import json
import time
from concurrent.futures import ThreadPoolExecutor
from backend.services.stock_data import get_quote
from backend.services.technical import compute_indicators
from backend.services.stock_data import get_history
from backend.services.signals import generate_signal
from backend.config import DATA_DIR
WATCHLIST_FILE = DATA_DIR / "watchlist.json"


def _load_watchlist() -> list[dict]:
    if WATCHLIST_FILE.exists():
        with open(WATCHLIST_FILE, "r") as f:
            return json.load(f)
    return []


def _save_watchlist(items: list[dict]):
    DATA_DIR.mkdir(exist_ok=True)
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(items, f, indent=2)


def add_to_watchlist(ticker: str) -> dict:
    items = _load_watchlist()
    ticker = ticker.upper()

    # Don't add duplicates
    if any(item["ticker"] == ticker for item in items):
        return {"status": "already_exists", "ticker": ticker}

    items.append({
        "ticker": ticker,
        "added_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })
    _save_watchlist(items)
    return {"status": "added", "ticker": ticker}


def remove_from_watchlist(ticker: str) -> bool:
    items = _load_watchlist()
    ticker = ticker.upper()
    new_items = [item for item in items if item["ticker"] != ticker]
    if len(new_items) == len(items):
        return False
    _save_watchlist(new_items)
    return True


def _fetch_watchlist_item(item: dict) -> dict:
    """Fetch live data for a single watchlist ticker."""
    ticker = item["ticker"]
    try:
        quote = get_quote(ticker)

        # Try to get a quick signal
        signal_direction = "HOLD"
        confidence = 0.0
        try:
            df = get_history(ticker, period="3mo", interval="1d")
            indicators = compute_indicators(df)
            signal = generate_signal(indicators, quote)
            signal_direction = signal["direction"]
            confidence = signal["confidence"]
        except Exception:
            pass

        return {
            "ticker": ticker,
            "name": quote.get("name", ticker),
            "price": quote.get("price", 0),
            "change_pct": round(quote.get("change_pct", 0), 2),
            "signal_direction": signal_direction,
            "confidence": confidence,
            "added_at": item.get("added_at", ""),
        }
    except Exception:
        return {
            "ticker": ticker,
            "name": ticker,
            "price": 0,
            "change_pct": 0,
            "signal_direction": "HOLD",
            "confidence": 0,
            "added_at": item.get("added_at", ""),
        }


def get_watchlist_with_quotes() -> dict:
    """Get all watchlist items with live quotes and signals."""
    items = _load_watchlist()
    if not items:
        return {"items": [], "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    # Fetch all quotes in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(_fetch_watchlist_item, items))

    return {
        "items": results,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
