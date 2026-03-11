"""
Market Events Scanner — earnings movers and recent IPO detection.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

from backend.services.stock_data import get_quote, get_history
from backend.config import DATA_DIR

logger = logging.getLogger(__name__)


def _load_sp500_tickers() -> list[str]:
    sp500_path = DATA_DIR / "sp500_tickers.json"
    with open(sp500_path, "r") as f:
        return json.load(f)


def _check_earnings_mover(ticker: str, min_move_pct: float) -> dict | None:
    """Check a single ticker for recent earnings and post-earnings move."""
    try:
        yf_ticker = yf.Ticker(ticker)
        now = datetime.now()
        cutoff = now - timedelta(days=7)
        earnings_date = None

        # Try earnings_dates first (historical actual dates)
        try:
            ed = yf_ticker.earnings_dates
            if ed is not None and not ed.empty:
                for dt_idx in ed.index:
                    dt_val = dt_idx.to_pydatetime().replace(tzinfo=None)
                    if cutoff <= dt_val <= now:
                        earnings_date = dt_val
                        break
        except Exception:
            pass

        # Fallback: check calendar for upcoming/recent earnings
        if earnings_date is None:
            try:
                cal = yf_ticker.calendar
                if cal is not None:
                    ed_key = None
                    for k in ("Earnings Date", "earnings_date"):
                        if k in cal:
                            ed_key = k
                            break
                    if ed_key is not None:
                        val = cal[ed_key]
                        dates_to_check = val if isinstance(val, list) else [val]
                        for d in dates_to_check:
                            if isinstance(d, str):
                                d = pd.Timestamp(d)
                            if hasattr(d, "to_pydatetime"):
                                d = d.to_pydatetime()
                            if hasattr(d, "replace"):
                                d = d.replace(tzinfo=None)
                            if isinstance(d, datetime) and cutoff <= d <= now:
                                earnings_date = d
                                break
            except Exception:
                pass

        if earnings_date is None:
            return None

        # Get price history around earnings
        hist = get_history(ticker, period="1mo", interval="1d")
        if hist is None or hist.empty or len(hist) < 2:
            return None

        # Find the trading day before earnings
        earnings_date_only = earnings_date.date()
        pre_earnings_rows = hist[hist.index.date < earnings_date_only]
        if pre_earnings_rows.empty:
            return None

        pre_earnings_price = float(pre_earnings_rows["Close"].iloc[-1])
        current_price_row = hist["Close"].iloc[-1]
        current_price = float(current_price_row)

        move_pct = ((current_price - pre_earnings_price) / pre_earnings_price) * 100

        if abs(move_pct) < min_move_pct:
            return None

        # Volume ratio: current avg vs pre-earnings avg
        quote = get_quote(ticker)
        avg_volume_pre = float(pre_earnings_rows["Volume"].mean()) if len(pre_earnings_rows) > 0 else 1.0
        current_volume = float(hist["Volume"].iloc[-1])
        volume_ratio = round(current_volume / avg_volume_pre, 2) if avg_volume_pre > 0 else 0.0

        return {
            "ticker": ticker,
            "name": quote.get("name", ticker) if quote else ticker,
            "price": round(current_price, 2),
            "earnings_date": earnings_date.strftime("%Y-%m-%d"),
            "move_pct": round(move_pct, 2),
            "move_direction": "UP" if move_pct > 0 else "DOWN",
            "volume_ratio": volume_ratio,
            "pre_earnings_price": round(pre_earnings_price, 2),
        }
    except Exception as e:
        logger.debug(f"Error checking earnings for {ticker}: {e}")
        return None


def scan_earnings_movers(
    tickers: list[str] | None = None, min_move_pct: float = 5.0
) -> list[dict]:
    """
    Find stocks that recently reported earnings and had big post-earnings moves.

    Args:
        tickers: List of tickers to scan. Defaults to S&P 500.
        min_move_pct: Minimum absolute price move percentage to include.

    Returns:
        List of dicts sorted by abs(move_pct) descending.
    """
    if tickers is None:
        tickers = _load_sp500_tickers()

    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_check_earnings_mover, ticker, min_move_pct): ticker
            for ticker in tickers
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.debug(f"Earnings scan future error for {futures[future]}: {e}")

    results.sort(key=lambda x: abs(x["move_pct"]), reverse=True)
    return results


def _check_ipo_candidate(ticker: str, cutoff_epoch: float, min_momentum_pct: float) -> dict | None:
    """Check a single ticker for recent IPO status and compute momentum."""
    try:
        yf_ticker = yf.Ticker(ticker)
        info = yf_ticker.info
        if not info:
            return None

        first_trade = info.get("firstTradeDateEpochUtc")
        if first_trade is None:
            return None

        if first_trade < cutoff_epoch:
            return None

        ipo_date = datetime.utcfromtimestamp(first_trade)
        days_since_ipo = (datetime.now() - ipo_date).days
        if days_since_ipo < 0:
            return None

        # Get history from IPO to now
        hist = get_history(ticker, period="3mo", interval="1d")
        if hist is None or hist.empty:
            return None

        ipo_price = float(hist["Open"].iloc[0])
        if ipo_price <= 0:
            return None

        quote = get_quote(ticker)
        if not quote:
            return None

        current_price = quote.get("price", 0.0)
        if not current_price or current_price <= 0:
            return None

        change_since_ipo_pct = ((current_price - ipo_price) / ipo_price) * 100

        if change_since_ipo_pct < min_momentum_pct:
            return None

        return {
            "ticker": ticker,
            "name": quote.get("name", ticker),
            "price": round(current_price, 2),
            "ipo_date": ipo_date.strftime("%Y-%m-%d"),
            "ipo_price": round(ipo_price, 2),
            "change_since_ipo_pct": round(change_since_ipo_pct, 2),
            "days_since_ipo": days_since_ipo,
            "volume": int(quote.get("volume", 0) or 0),
            "market_cap": quote.get("market_cap"),
        }
    except Exception as e:
        logger.debug(f"Error checking IPO for {ticker}: {e}")
        return None


def scan_recent_ipos(min_momentum_pct: float = 0.0) -> list[dict]:
    """
    Find recently IPO'd stocks (listed within last 90 days) with momentum.

    Loads candidates from data/ipo_watchlist.json if available, otherwise
    scans S&P 500 tickers by checking firstTradeDateEpochUtc.

    Args:
        min_momentum_pct: Minimum change since IPO percentage to include.

    Returns:
        List of dicts sorted by change_since_ipo_pct descending.
    """
    cutoff = datetime.now() - timedelta(days=90)
    cutoff_epoch = cutoff.timestamp()

    # Try loading curated IPO watchlist first
    ipo_watchlist_path = DATA_DIR / "ipo_watchlist.json"
    if ipo_watchlist_path.exists():
        try:
            with open(ipo_watchlist_path, "r") as f:
                tickers = json.load(f)
        except Exception:
            tickers = _load_sp500_tickers()
    else:
        tickers = _load_sp500_tickers()

    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_check_ipo_candidate, ticker, cutoff_epoch, min_momentum_pct): ticker
            for ticker in tickers
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.debug(f"IPO scan future error for {futures[future]}: {e}")

    results.sort(key=lambda x: x["change_since_ipo_pct"], reverse=True)
    return results
