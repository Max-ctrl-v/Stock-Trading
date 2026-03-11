"""External data scanners: insider buying activity and short interest."""

import json
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from backend.services.stock_data import get_quote
from backend.config import DATA_DIR


def _load_sp500_tickers() -> list[str]:
    """Load S&P 500 ticker list from JSON file."""
    with open(DATA_DIR / "sp500_tickers.json", "r") as f:
        return json.load(f)


def _fetch_insider_data(ticker: str) -> dict | None:
    """Fetch insider buying data for a single ticker."""
    try:
        t = yf.Ticker(ticker)
        df = t.insider_transactions

        if df is None or df.empty:
            return None

        cutoff = datetime.now() - timedelta(days=30)

        # Filter for purchases in the last 30 days
        df = df.copy()

        # Normalize column access — yfinance may use different casing
        text_col = None
        date_col = None
        shares_col = None
        value_col = None
        insider_col = None

        for col in df.columns:
            cl = col.lower().strip()
            if cl == "text":
                text_col = col
            elif cl in ("start date", "startdate", "date"):
                date_col = col
            elif cl == "shares":
                shares_col = col
            elif cl == "value":
                value_col = col
            elif cl in ("insider", "insider trading"):
                insider_col = col

        if text_col is None or date_col is None:
            return None

        # Parse dates and filter
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        df = df[df[date_col] >= cutoff]

        # Filter for purchase transactions
        purchase_mask = df[text_col].str.contains("Purchase", case=False, na=False)
        df = df[purchase_mask]

        if df.empty:
            return None

        total_shares = int(df[shares_col].abs().sum()) if shares_col else 0
        total_value = float(df[value_col].abs().sum()) if value_col and value_col in df.columns else 0.0
        buys_count = len(df)
        latest_date = df[date_col].max().strftime("%Y-%m-%d")

        notable_insiders = []
        if insider_col and insider_col in df.columns:
            notable_insiders = df[insider_col].dropna().unique().tolist()[:5]

        quote = get_quote(ticker)

        return {
            "ticker": ticker,
            "name": quote.get("name", ticker),
            "price": quote.get("price", 0.0),
            "change_pct": quote.get("change_pct", 0.0),
            "insider_buys_count": buys_count,
            "total_shares_bought": total_shares,
            "total_value": total_value,
            "latest_buy_date": latest_date,
            "notable_insiders": notable_insiders,
        }
    except Exception:
        return None


def scan_insider_buying(tickers: list[str] | None = None) -> list[dict]:
    """Scan for stocks with recent insider buying activity.

    Args:
        tickers: List of ticker symbols to scan. Defaults to S&P 500.

    Returns:
        List of dicts sorted by total_value descending.
    """
    if tickers is None:
        tickers = _load_sp500_tickers()

    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_fetch_insider_data, t): t for t in tickers}
        for future in futures:
            result = future.result()
            if result is not None:
                results.append(result)

    results.sort(key=lambda x: x["total_value"], reverse=True)
    return results


def _fetch_short_interest(ticker: str, min_short_pct: float) -> dict | None:
    """Fetch short interest data for a single ticker."""
    try:
        t = yf.Ticker(ticker)
        info = t.info

        if not info:
            return None

        short_pct = info.get("shortPercentOfFloat")
        if short_pct is None:
            return None

        # yfinance returns as decimal (e.g. 0.15 = 15%) — normalize to percentage
        if short_pct < 1.0:
            short_pct = short_pct * 100.0

        if short_pct < min_short_pct:
            return None

        shares_short = info.get("sharesShort", 0) or 0
        short_ratio = info.get("shortRatio", 0.0) or 0.0
        shares_short_prior = info.get("sharesShortPriorMonth", 0) or 0
        avg_volume = info.get("averageVolume", 0) or 0

        # Calculate month-over-month change in short interest
        short_change_mom = 0.0
        if shares_short_prior and shares_short_prior > 0:
            short_change_mom = ((shares_short - shares_short_prior) / shares_short_prior) * 100.0

        quote = get_quote(ticker)

        return {
            "ticker": ticker,
            "name": quote.get("name", ticker),
            "price": quote.get("price", 0.0),
            "change_pct": quote.get("change_pct", 0.0),
            "short_pct_of_float": round(short_pct, 2),
            "shares_short": int(shares_short),
            "short_ratio": round(float(short_ratio), 2),
            "short_change_mom": round(short_change_mom, 2),
            "avg_volume": int(avg_volume),
        }
    except Exception:
        return None


def scan_short_interest(
    tickers: list[str] | None = None, min_short_pct: float = 10.0
) -> list[dict]:
    """Scan for stocks with high short interest (potential squeeze candidates).

    Args:
        tickers: List of ticker symbols to scan. Defaults to S&P 500.
        min_short_pct: Minimum short percent of float to include.

    Returns:
        List of dicts sorted by short_pct_of_float descending.
    """
    if tickers is None:
        tickers = _load_sp500_tickers()

    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_fetch_short_interest, t, min_short_pct): t
            for t in tickers
        }
        for future in futures:
            result = future.result()
            if result is not None:
                results.append(result)

    results.sort(key=lambda x: x["short_pct_of_float"], reverse=True)
    return results
