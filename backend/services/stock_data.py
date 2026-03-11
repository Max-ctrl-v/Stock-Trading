import time
import yfinance as yf
import pandas as pd
import httpx
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


def get_usd_to_eur() -> float:
    """Get USD→EUR rate. Tries ECB open API first, falls back to yfinance."""
    cache_key = "forex:usd_eur"
    cached = _get_cached(cache_key, 600)  # 10-min cache
    if cached is not None:
        return cached

    # Primary: ECB / exchangerate-api (free, no key)
    try:
        r = httpx.get("https://open.er-api.com/v6/latest/USD", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            rate = data.get("rates", {}).get("EUR")
            if rate and rate > 0:
                _set_cached(cache_key, float(rate))
                return float(rate)
    except Exception:
        pass

    # Fallback: yfinance EURUSD=X
    try:
        t = yf.Ticker("EURUSD=X")
        h = t.history(period="1d")
        if len(h) > 0:
            eur_usd = float(h["Close"].iloc[-1])
            rate = 1.0 / eur_usd
            _set_cached(cache_key, rate)
            return rate
    except Exception:
        pass

    return 0.92  # hardcoded fallback


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
