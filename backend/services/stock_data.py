import time
import yfinance as yf
import pandas as pd
from backend.config import QUOTE_CACHE_TTL, HISTORY_CACHE_TTL

# In-memory cache: {key: (data, timestamp)}
_cache: dict[str, tuple] = {}


def _get_cached(key: str, ttl: int):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < ttl:
            return data
    return None


def _set_cached(key: str, data):
    _cache[key] = (data, time.time())


def get_quote(ticker: str) -> dict:
    cache_key = f"quote:{ticker}"
    cached = _get_cached(cache_key, QUOTE_CACHE_TTL)
    if cached:
        return cached

    stock = yf.Ticker(ticker)
    info = stock.info

    price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0

    # Prefer computed change from previousClose for accuracy;
    # fall back to yfinance's reported values if previousClose is missing.
    if prev_close and price:
        change = round(price - prev_close, 4)
        change_pct = round((change / prev_close) * 100, 4)
    else:
        change = info.get("regularMarketChange", 0)
        change_pct = info.get("regularMarketChangePercent", 0)

    quote = {
        "ticker": ticker.upper(),
        "name": info.get("shortName", info.get("longName", ticker)),
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "volume": info.get("regularMarketVolume", 0),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "sector": info.get("sector"),
        "exchange": info.get("exchange"),
    }

    _set_cached(cache_key, quote)
    return quote


def get_history(ticker: str, period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    cache_key = f"history:{ticker}:{period}:{interval}"
    cached = _get_cached(cache_key, HISTORY_CACHE_TTL)
    if cached is not None:
        return cached

    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval)

    if df.empty:
        return df

    _set_cached(cache_key, df)
    return df


def history_to_dict(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"timestamp": [], "open": [], "high": [], "low": [], "close": [], "volume": []}

    # Use datetime format for intraday data
    timestamps = []
    for ts in df.index:
        if hasattr(ts, 'hour') and (ts.hour != 0 or ts.minute != 0):
            timestamps.append(ts.strftime("%Y-%m-%dT%H:%M"))
        else:
            timestamps.append(ts.strftime("%Y-%m-%d"))

    return {
        "timestamp": timestamps,
        "open": [round(v, 2) for v in df["Open"].tolist()],
        "high": [round(v, 2) for v in df["High"].tolist()],
        "low": [round(v, 2) for v in df["Low"].tolist()],
        "close": [round(v, 2) for v in df["Close"].tolist()],
        "volume": [int(v) for v in df["Volume"].tolist()],
    }
