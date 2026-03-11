import json
from datetime import datetime
import pandas as pd
import ta
import yfinance as yf
from pydantic import BaseModel
from backend.config import DATA_DIR
JOURNAL_FILE = DATA_DIR / "journal.json"


class DayData(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    rsi: float | None
    macd: float | None
    macd_signal: float | None
    macd_hist: float | None
    trades: list[dict]


class ReplayResponse(BaseModel):
    ticker: str
    start_date: str
    end_date: str
    days: list[DayData]
    trades_in_range: list[dict]


def _load_journal() -> list[dict]:
    """Load journal trades from disk."""
    if JOURNAL_FILE.exists():
        with open(JOURNAL_FILE) as f:
            return json.load(f)
    return []


def _get_trades_for_ticker_in_range(
    ticker: str, start_date: str, end_date: str
) -> list[dict]:
    """Filter journal trades for a ticker within a date range."""
    trades = _load_journal()
    result = []
    ticker_upper = ticker.upper()
    for t in trades:
        if t.get("ticker", "").upper() != ticker_upper:
            continue
        entry_date = t.get("entry_date", "")[:10]
        exit_date = (t.get("exit_date") or "")[:10]
        # Include trade if entry or exit falls in the range
        if entry_date and start_date <= entry_date <= end_date:
            result.append(t)
        elif exit_date and start_date <= exit_date <= end_date:
            result.append(t)
    return result


def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add RSI, MACD columns to a DataFrame."""
    if len(df) < 14:
        df["rsi"] = None
        df["macd"] = None
        df["macd_signal"] = None
        df["macd_hist"] = None
        return df

    close = df["Close"]

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    df["rsi"] = rsi

    if len(df) >= 26:
        macd_obj = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
        df["macd"] = macd_obj.macd()
        df["macd_signal"] = macd_obj.macd_signal()
        df["macd_hist"] = macd_obj.macd_diff()
    else:
        df["macd"] = None
        df["macd_signal"] = None
        df["macd_hist"] = None

    return df


def _trades_on_date(trades: list[dict], date_str: str) -> list[dict]:
    """Find trades with entry or exit on a specific date."""
    result = []
    for t in trades:
        entry_date = t.get("entry_date", "")[:10]
        exit_date = (t.get("exit_date") or "")[:10]
        if entry_date == date_str or exit_date == date_str:
            result.append(t)
    return result


def get_replay_range(
    ticker: str, start_date: str, end_date: str
) -> ReplayResponse:
    """Get daily OHLCV + indicators for a date range with journal trade overlay."""
    # Fetch extra data before start_date for indicator warmup
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    # Download with 60 days of extra data for indicator warmup
    warmup_start = start_dt - pd.Timedelta(days=90)

    t = yf.Ticker(ticker)
    hist = t.history(start=warmup_start.strftime("%Y-%m-%d"), end=end_date)
    if hist.empty:
        raise ValueError(f"No historical data available for {ticker} in the specified range")

    hist = _compute_indicators(hist)

    # Filter to requested range after computing indicators
    hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index
    mask = (hist.index >= pd.Timestamp(start_date)) & (hist.index <= pd.Timestamp(end_date))
    display_df = hist.loc[mask]

    trades_in_range = _get_trades_for_ticker_in_range(ticker, start_date, end_date)

    days: list[DayData] = []
    for idx, row in display_df.iterrows():
        date_str = idx.strftime("%Y-%m-%d")

        def safe_round(val, decimals: int = 4):
            if val is None or (isinstance(val, float) and val != val):
                return None
            return round(float(val), decimals)

        days.append(DayData(
            date=date_str,
            open=round(float(row["Open"]), 2),
            high=round(float(row["High"]), 2),
            low=round(float(row["Low"]), 2),
            close=round(float(row["Close"]), 2),
            volume=int(row["Volume"]),
            rsi=safe_round(row.get("rsi")),
            macd=safe_round(row.get("macd")),
            macd_signal=safe_round(row.get("macd_signal")),
            macd_hist=safe_round(row.get("macd_hist")),
            trades=_trades_on_date(trades_in_range, date_str),
        ))

    return ReplayResponse(
        ticker=ticker.upper(),
        start_date=start_date,
        end_date=end_date,
        days=days,
        trades_in_range=trades_in_range,
    )


def get_replay_day(ticker: str, date: str) -> DayData:
    """Get a single day's data with indicators and trade overlay."""
    # Need warmup data for indicators
    target_dt = datetime.strptime(date, "%Y-%m-%d")
    warmup_start = target_dt - pd.Timedelta(days=90)

    t = yf.Ticker(ticker)
    hist = t.history(start=warmup_start.strftime("%Y-%m-%d"), end=(target_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    if hist.empty:
        raise ValueError(f"No data available for {ticker} on {date}")

    hist = _compute_indicators(hist)

    hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index
    target_ts = pd.Timestamp(date)
    if target_ts not in hist.index:
        # Try to find the closest trading day
        mask = hist.index == target_ts
        if not mask.any():
            raise ValueError(f"No trading data for {ticker} on {date} (market may have been closed)")

    row = hist.loc[target_ts]

    trades = _get_trades_for_ticker_in_range(ticker, date, date)

    def safe_round(val, decimals: int = 4):
        if val is None or (isinstance(val, float) and val != val):
            return None
        return round(float(val), decimals)

    return DayData(
        date=date,
        open=round(float(row["Open"]), 2),
        high=round(float(row["High"]), 2),
        low=round(float(row["Low"]), 2),
        close=round(float(row["Close"]), 2),
        volume=int(row["Volume"]),
        rsi=safe_round(row.get("rsi")),
        macd=safe_round(row.get("macd")),
        macd_signal=safe_round(row.get("macd_signal")),
        macd_hist=safe_round(row.get("macd_hist")),
        trades=_trades_on_date(trades, date),
    )
