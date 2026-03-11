import json
import yfinance as yf
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel
from backend.config import DATA_DIR


class EarningsInfo(BaseModel):
    ticker: str
    earnings_date: str | None = None
    days_until: int | None = None
    is_before_market: bool | None = None
    error: str | None = None


def _get_portfolio_tickers() -> list[str]:
    portfolio_path = DATA_DIR / "portfolio.json"
    if not portfolio_path.exists():
        return []
    try:
        with open(portfolio_path, "r") as f:
            data = json.load(f)
        return [item["ticker"] for item in data if "ticker" in item]
    except Exception:
        return []


def _fetch_single_earnings(ticker: str) -> EarningsInfo:
    try:
        t = yf.Ticker(ticker.upper())
        earnings_date_val: date | None = None
        is_before_market: bool | None = None

        # Try earnings_dates first (returns a DataFrame with upcoming/past dates)
        try:
            ed = t.earnings_dates
            if ed is not None and not ed.empty:
                now = datetime.now()
                # Filter future dates
                future_dates = [
                    d for d in ed.index
                    if d.to_pydatetime().replace(tzinfo=None) >= now
                ]
                if future_dates:
                    next_date = min(future_dates)
                    earnings_date_val = next_date.to_pydatetime().replace(tzinfo=None).date()
                    # Check hour for before/after market
                    hour = next_date.to_pydatetime().hour
                    if hour > 0:
                        is_before_market = hour < 12
        except Exception:
            pass

        # Fallback: try calendar
        if earnings_date_val is None:
            try:
                cal = t.calendar
                if cal is not None:
                    if isinstance(cal, dict):
                        ed_val = cal.get("Earnings Date")
                        if ed_val:
                            if isinstance(ed_val, list) and len(ed_val) > 0:
                                ed_val = ed_val[0]
                            if hasattr(ed_val, "date"):
                                earnings_date_val = ed_val.date() if callable(ed_val.date) else ed_val.date
                            elif isinstance(ed_val, str):
                                earnings_date_val = datetime.strptime(ed_val[:10], "%Y-%m-%d").date()
            except Exception:
                pass

        if earnings_date_val is None:
            return EarningsInfo(ticker=ticker.upper(), error="Earnings date not available")

        days_until = (earnings_date_val - date.today()).days

        return EarningsInfo(
            ticker=ticker.upper(),
            earnings_date=earnings_date_val.isoformat(),
            days_until=days_until,
            is_before_market=is_before_market,
        )
    except Exception as e:
        return EarningsInfo(ticker=ticker.upper(), error=str(e))


def get_earnings(ticker: str) -> EarningsInfo:
    return _fetch_single_earnings(ticker)


def get_upcoming_earnings(tickers: list[str]) -> list[EarningsInfo]:
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(_fetch_single_earnings, tickers))

    # Sort by earnings_date (None dates go to the end)
    results.sort(key=lambda x: x.earnings_date or "9999-12-31")
    return results


def get_portfolio_earnings() -> list[EarningsInfo]:
    tickers = _get_portfolio_tickers()
    if not tickers:
        return []
    return get_upcoming_earnings(tickers)
