import json
import time
import asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from backend.services.stock_data import get_quote, get_history
from backend.services.technical import compute_indicators
from backend.services.signals import generate_signal
from backend.config import SCREENER_CACHE_TTL

DATA_DIR = Path(__file__).parent.parent.parent / "data"
SP500_FILE = DATA_DIR / "sp500_tickers.json"
RESULTS_FILE = DATA_DIR / "screener_results.json"

# In-memory state
_scan_cache: dict = {"results": None, "scanned_at": None, "progress": 0, "scanning": False}


def _load_tickers() -> list[str]:
    if SP500_FILE.exists():
        with open(SP500_FILE) as f:
            return json.load(f)
    return []


def _get_spy_benchmark() -> dict:
    """Get SPY's recent performance for relative strength comparison."""
    try:
        df = get_history("SPY", period="3mo", interval="1d")
        if df.empty or len(df) < 20:
            return {"change_20d": 0}
        close = df["Close"]
        change_20d = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100
        return {"change_20d": change_20d}
    except Exception:
        return {"change_20d": 0}


def score_stock(ticker: str, spy_benchmark: dict) -> dict | None:
    """Score a single stock for screener ranking (0-100)."""
    try:
        quote = get_quote(ticker)
        df = get_history(ticker, period="3mo", interval="1d")

        if df.empty or len(df) < 20:
            return None

        indicators = compute_indicators(df)
        signal = generate_signal(indicators, quote)

        close = df["Close"]
        volume = df["Volume"]

        # 1. Signal Engine Score (40% weight, normalize from -100..100 to 0..40)
        raw_score = signal.get("confidence", 0)
        if signal["direction"] == "SELL":
            raw_score = -raw_score
        signal_score = (raw_score + 100) / 200 * 40  # Maps -100..100 to 0..40

        # 2. Momentum Score (20% weight)
        change_5d = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100 if len(close) >= 5 else 0
        change_20d = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100 if len(close) >= 20 else 0
        # Accelerating momentum bonus
        momentum_raw = change_5d * 2 + change_20d  # Weight recent more
        momentum_score = min(20, max(0, (momentum_raw + 10) / 30 * 20))

        # 3. Volume Surge (15% weight)
        vol_sma = indicators.get("volume_sma", 0) or 1
        current_vol = quote.get("volume", 0)
        vol_ratio = current_vol / vol_sma if vol_sma > 0 else 1
        volume_score = min(15, max(0, (vol_ratio - 0.5) / 2.0 * 15))

        # 4. Bollinger Squeeze/Breakout (15% weight)
        bb_upper = indicators.get("bb_upper", 0) or 0
        bb_lower = indicators.get("bb_lower", 0) or 0
        bb_middle = indicators.get("bb_middle", 0) or 1
        bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
        price = quote.get("price", 0)
        # Tight squeeze (low bandwidth) = potential breakout
        squeeze_score = max(0, (0.1 - bb_width) / 0.1 * 10) if bb_width < 0.1 else 0
        # Breakout bonus if price near/above upper band
        breakout_bonus = 5 if price > bb_upper * 0.98 and vol_ratio > 1.2 else 0
        bb_score = min(15, squeeze_score + breakout_bonus)

        # 5. Relative Strength vs SPY (10% weight)
        spy_change = spy_benchmark.get("change_20d", 0)
        rel_strength = change_20d - spy_change
        rs_score = min(10, max(0, (rel_strength + 5) / 15 * 10))

        total_score = round(signal_score + momentum_score + volume_score + bb_score + rs_score, 1)

        return {
            "ticker": ticker,
            "name": quote.get("name", ticker),
            "price": round(quote.get("price", 0), 2),
            "change_5d_pct": round(change_5d, 2),
            "screener_score": total_score,
            "signal_direction": signal["direction"],
            "confidence": signal["confidence"],
            "volume_ratio": round(vol_ratio, 2),
            "ai_thesis": "",
            "sub_scores": {
                "signal": round(signal_score, 1),
                "momentum": round(momentum_score, 1),
                "volume": round(volume_score, 1),
                "bollinger": round(bb_score, 1),
                "relative_strength": round(rs_score, 1),
            },
        }
    except Exception as e:
        return None


def run_screener_scan() -> list[dict]:
    """Run full screener scan on all tickers."""
    _scan_cache["scanning"] = True
    _scan_cache["progress"] = 0

    tickers = _load_tickers()
    if not tickers:
        _scan_cache["scanning"] = False
        return []

    spy_benchmark = _get_spy_benchmark()
    results = []

    def _score_wrapper(ticker):
        result = score_stock(ticker, spy_benchmark)
        _scan_cache["progress"] += 1
        return result

    with ThreadPoolExecutor(max_workers=8) as executor:
        scored = list(executor.map(_score_wrapper, tickers))

    results = [r for r in scored if r is not None]
    results.sort(key=lambda x: x["screener_score"], reverse=True)

    # Cache results
    _scan_cache["results"] = results
    _scan_cache["scanned_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _scan_cache["scanning"] = False

    # Save to file
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with open(RESULTS_FILE, "w") as f:
            json.dump({"results": results, "scanned_at": _scan_cache["scanned_at"]}, f, indent=2)
    except Exception:
        pass

    return results


# --- Screener Presets ---
SCREENER_PRESETS: dict[str, dict] = {
    "breakout_candidates": {
        "name": "Breakout Candidates",
        "description": "Stocks in tight Bollinger squeeze with rising volume",
        "filter": lambda r: (
            r["sub_scores"].get("bollinger", 0) >= 8
            and r["volume_ratio"] >= 1.2
        ),
        "sort_key": "screener_score",
    },
    "oversold_bounces": {
        "name": "Oversold Bounces",
        "description": "Oversold stocks showing early reversal signals",
        "filter": lambda r: (
            r["signal_direction"] == "BUY"
            and r["change_5d_pct"] < 0
            and r["confidence"] >= 50
        ),
        "sort_key": "confidence",
    },
    "momentum_leaders": {
        "name": "Momentum Leaders",
        "description": "Strongest momentum with high relative strength",
        "filter": lambda r: (
            r["sub_scores"].get("momentum", 0) >= 12
            and r["sub_scores"].get("relative_strength", 0) >= 5
        ),
        "sort_key": "screener_score",
    },
}


def _load_watchlist_tickers() -> list[str]:
    """Load tickers from the user's watchlist."""
    watchlist_file = DATA_DIR / "watchlist.json"
    if watchlist_file.exists():
        with open(watchlist_file) as f:
            items = json.load(f)
        return [item["ticker"] for item in items if "ticker" in item]
    return []


def _get_sector_tickers(sector: str) -> list[str]:
    """Filter S&P 500 tickers by sector using yfinance info."""
    all_tickers = _load_tickers()
    if not all_tickers:
        return []

    sector_lower = sector.lower()
    matched = []

    def _check_sector(ticker: str) -> str | None:
        try:
            quote = get_quote(ticker)
            stock_sector = (quote.get("sector") or "").lower()
            if sector_lower in stock_sector:
                return ticker
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(_check_sector, all_tickers))

    return [t for t in results if t is not None]


def run_watchlist_scan() -> list[dict]:
    """Scan only tickers from the user's watchlist."""
    tickers = _load_watchlist_tickers()
    if not tickers:
        return []

    spy_benchmark = _get_spy_benchmark()
    results = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        scored = list(executor.map(lambda t: score_stock(t, spy_benchmark), tickers))

    results = [r for r in scored if r is not None]
    results.sort(key=lambda x: x["screener_score"], reverse=True)
    return results


def run_sector_scan(sector: str) -> list[dict]:
    """Scan only tickers from a specific sector."""
    tickers = _get_sector_tickers(sector)
    if not tickers:
        return []

    spy_benchmark = _get_spy_benchmark()

    with ThreadPoolExecutor(max_workers=8) as executor:
        scored = list(executor.map(lambda t: score_stock(t, spy_benchmark), tickers))

    results = [r for r in scored if r is not None]
    results.sort(key=lambda x: x["screener_score"], reverse=True)
    return results


def get_preset_results(preset_key: str) -> dict:
    """Get screener results filtered by a preset."""
    preset = SCREENER_PRESETS.get(preset_key)
    if not preset:
        return {"error": f"Unknown preset: {preset_key}", "presets": list(SCREENER_PRESETS.keys())}

    # Use cached results if available
    status = get_scan_status()
    if status["status"] != "ready" or not status["picks"]:
        return {"error": "No scan results available. Run a scan first.", "status": status["status"]}

    all_picks = status["picks"]
    filtered = [p for p in all_picks if preset["filter"](p)]
    filtered.sort(key=lambda x: x.get(preset["sort_key"], 0), reverse=True)

    return {
        "preset": preset_key,
        "name": preset["name"],
        "description": preset["description"],
        "count": len(filtered),
        "picks": filtered,
    }


def list_presets() -> list[dict]:
    """List all available screener presets."""
    return [
        {"key": k, "name": v["name"], "description": v["description"]}
        for k, v in SCREENER_PRESETS.items()
    ]


def get_scan_status() -> dict:
    """Get current scan status and results."""
    if _scan_cache["scanning"]:
        return {
            "status": "scanning",
            "progress": _scan_cache["progress"],
            "total_scanned": 0,
            "scanned_at": "",
            "picks": [],
        }

    if _scan_cache["results"] is not None:
        # Check TTL
        if _scan_cache["scanned_at"]:
            return {
                "status": "ready",
                "progress": 0,
                "total_scanned": len(_scan_cache["results"]),
                "scanned_at": _scan_cache["scanned_at"],
                "picks": _scan_cache["results"][:50],
            }

    # Try loading from file
    if RESULTS_FILE.exists():
        try:
            with open(RESULTS_FILE) as f:
                data = json.load(f)
            _scan_cache["results"] = data.get("results", [])
            _scan_cache["scanned_at"] = data.get("scanned_at", "")
            return {
                "status": "ready",
                "total_scanned": len(_scan_cache["results"]),
                "scanned_at": _scan_cache["scanned_at"],
                "progress": 0,
                "picks": _scan_cache["results"][:50],
            }
        except Exception:
            pass

    return {"status": "empty", "progress": 0, "total_scanned": 0, "scanned_at": "", "picks": []}
