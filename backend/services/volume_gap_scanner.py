"""
Volume, Gap, and 52-Week Proximity Scanners.

Three standalone scanners that identify unusual trading activity
across S&P 500 stocks using yfinance data.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from backend.services.stock_data import get_quote, get_history
from backend.config import DATA_DIR


def _load_default_tickers() -> list[str]:
    """Load S&P 500 tickers from the JSON file."""
    with open(DATA_DIR / "sp500_tickers.json", "r") as f:
        return json.load(f)


def scan_unusual_volume(
    tickers: list[str] | None = None, threshold: float = 3.0
) -> list[dict]:
    """
    Scan for stocks with today's volume >= threshold * 20-day average volume.

    Args:
        tickers: List of ticker symbols to scan. Defaults to S&P 500.
        threshold: Minimum volume ratio to include (default 3.0x).

    Returns:
        List of dicts sorted by volume_ratio descending.
    """
    if tickers is None:
        tickers = _load_default_tickers()

    results: list[dict] = []

    def _check_ticker(ticker: str) -> dict | None:
        try:
            hist = get_history(ticker, period="1mo", interval="1d")
            if hist is None or len(hist) < 2:
                return None

            avg_volume_20d = hist["Volume"].tail(20).mean()
            if avg_volume_20d == 0:
                return None

            current_volume = int(hist["Volume"].iloc[-1])
            volume_ratio = current_volume / avg_volume_20d

            if volume_ratio < threshold:
                return None

            quote = get_quote(ticker)
            return {
                "ticker": ticker,
                "name": quote.get("name", ticker),
                "price": quote.get("price", float(hist["Close"].iloc[-1])),
                "change_pct": quote.get("change_pct", 0.0),
                "volume": current_volume,
                "avg_volume": int(avg_volume_20d),
                "volume_ratio": round(volume_ratio, 2),
            }
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_check_ticker, t): t for t in tickers}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                results.append(result)

    results.sort(key=lambda x: x["volume_ratio"], reverse=True)
    return results


def scan_gaps(
    tickers: list[str] | None = None, min_gap_pct: float = 2.0
) -> list[dict]:
    """
    Scan for stocks that gapped up or down significantly at today's open
    vs yesterday's close.

    Args:
        tickers: List of ticker symbols to scan. Defaults to S&P 500.
        min_gap_pct: Minimum absolute gap percentage to include (default 2.0%).

    Returns:
        List of dicts sorted by abs(gap_pct) descending.
    """
    if tickers is None:
        tickers = _load_default_tickers()

    results: list[dict] = []

    def _check_ticker(ticker: str) -> dict | None:
        try:
            hist_5d = get_history(ticker, period="5d", interval="1d")
            if hist_5d is None or len(hist_5d) < 2:
                return None

            today = hist_5d.iloc[-1]
            yesterday = hist_5d.iloc[-2]

            prev_close = float(yesterday["Close"])
            open_price = float(today["Open"])

            if prev_close == 0:
                return None

            gap_pct = (open_price - prev_close) / prev_close * 100

            if abs(gap_pct) < min_gap_pct:
                return None

            # Compute volume ratio using 1mo history
            hist_1mo = get_history(ticker, period="1mo", interval="1d")
            avg_volume_20d = hist_1mo["Volume"].tail(20).mean() if hist_1mo is not None and len(hist_1mo) > 0 else 1
            current_volume = int(today["Volume"])
            volume_ratio = current_volume / avg_volume_20d if avg_volume_20d > 0 else 0.0

            quote = get_quote(ticker)
            return {
                "ticker": ticker,
                "name": quote.get("name", ticker),
                "price": quote.get("price", float(today["Close"])),
                "gap_pct": round(gap_pct, 2),
                "gap_direction": "UP" if gap_pct > 0 else "DOWN",
                "prev_close": round(prev_close, 2),
                "open_price": round(open_price, 2),
                "volume_ratio": round(volume_ratio, 2),
            }
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_check_ticker, t): t for t in tickers}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                results.append(result)

    results.sort(key=lambda x: abs(x["gap_pct"]), reverse=True)
    return results


def scan_52week_proximity(
    tickers: list[str] | None = None, proximity_pct: float = 5.0
) -> list[dict]:
    """
    Find stocks within proximity_pct of their 52-week high or low.

    Args:
        tickers: List of ticker symbols to scan. Defaults to S&P 500.
        proximity_pct: Maximum percentage distance from 52w extreme (default 5.0%).

    Returns:
        List of dicts sorted by proximity to the nearest extreme (closest first).
    """
    if tickers is None:
        tickers = _load_default_tickers()

    results: list[dict] = []

    def _check_ticker(ticker: str) -> dict | None:
        try:
            hist = get_history(ticker, period="1y", interval="1d")
            if hist is None or len(hist) < 20:
                return None

            high_52w = float(hist["High"].max())
            low_52w = float(hist["Low"].min())
            current_price = float(hist["Close"].iloc[-1])

            if high_52w == 0 or low_52w == 0:
                return None

            pct_from_high = (high_52w - current_price) / high_52w * 100
            pct_from_low = (current_price - low_52w) / low_52w * 100

            near_high = pct_from_high <= proximity_pct
            near_low = pct_from_low <= proximity_pct

            if not near_high and not near_low:
                return None

            # Determine which extreme is closer
            if near_high and near_low:
                proximity_type = "HIGH" if pct_from_high <= pct_from_low else "LOW"
            elif near_high:
                proximity_type = "HIGH"
            else:
                proximity_type = "LOW"

            quote = get_quote(ticker)
            return {
                "ticker": ticker,
                "name": quote.get("name", ticker),
                "price": quote.get("price", current_price),
                "change_pct": quote.get("change_pct", 0.0),
                "high_52w": round(high_52w, 2),
                "low_52w": round(low_52w, 2),
                "pct_from_high": round(pct_from_high, 2),
                "pct_from_low": round(pct_from_low, 2),
                "proximity_type": proximity_type,
            }
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_check_ticker, t): t for t in tickers}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                results.append(result)

    # Sort by proximity to the nearest extreme (closest first)
    def _sort_key(item: dict) -> float:
        if item["proximity_type"] == "HIGH":
            return item["pct_from_high"]
        return item["pct_from_low"]

    results.sort(key=_sort_key)
    return results
