import time
from concurrent.futures import ThreadPoolExecutor
from backend.services.stock_data import get_quote, get_history

SECTOR_ETFS = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Energy": "XLE",
    "Healthcare": "XLV",
    "Communication": "XLC",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Consumer Staples": "XLP",
    "Consumer Disc.": "XLY",
}

INDEX_TICKERS = ["SPY", "QQQ", "DIA", "IWM", "^VIX"]


def _get_sector_data(name_ticker: tuple[str, str]) -> dict:
    name, ticker = name_ticker
    try:
        quote = get_quote(ticker)
        df = get_history(ticker, period="1mo", interval="1d")

        close = df["Close"] if not df.empty else None
        change_1w = 0
        change_1m = 0

        if close is not None and len(close) >= 5:
            change_1w = round((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100, 2)
        if close is not None and len(close) >= 20:
            change_1m = round((close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100, 2)

        return {
            "name": name,
            "ticker": ticker,
            "change_1d_pct": round(quote.get("change_pct", 0), 2),
            "change_1w_pct": change_1w,
            "change_1m_pct": change_1m,
        }
    except Exception:
        return {
            "name": name,
            "ticker": ticker,
            "change_1d_pct": 0,
            "change_1w_pct": 0,
            "change_1m_pct": 0,
        }


def get_sector_performance() -> list[dict]:
    items = list(SECTOR_ETFS.items())
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(_get_sector_data, items))
    return results


def get_market_overview() -> dict:
    indices = {}

    def _fetch_index(ticker):
        try:
            quote = get_quote(ticker)
            return ticker, {
                "name": quote.get("name", ticker),
                "price": round(quote.get("price", 0), 2),
                "change_pct": round(quote.get("change_pct", 0), 2),
            }
        except Exception:
            return ticker, {"name": ticker, "price": 0, "change_pct": 0}

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(_fetch_index, INDEX_TICKERS))

    for ticker, data in results:
        indices[ticker] = data

    sectors = get_sector_performance()

    return {
        "sectors": sectors,
        "indices": indices,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
