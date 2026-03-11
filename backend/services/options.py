import yfinance as yf
from pydantic import BaseModel


class OptionsChainResponse(BaseModel):
    ticker: str
    expiry: str
    expirations: list[str]
    calls: list[dict]
    puts: list[dict]


class ExpirationsResponse(BaseModel):
    ticker: str
    expirations: list[str]


def _format_chain(df) -> list[dict]:
    """Convert options DataFrame to list of dicts with key fields."""
    if df is None or df.empty:
        return []
    cols = [
        "strike", "lastPrice", "bid", "ask",
        "volume", "openInterest", "impliedVolatility",
    ]
    result = []
    for _, row in df.iterrows():
        entry = {}
        for col in cols:
            val = row.get(col)
            if val is None:
                entry[col] = None
            elif col in ("volume", "openInterest"):
                entry[col] = int(val) if val == val else 0  # NaN check
            else:
                entry[col] = round(float(val), 4) if val == val else None
        result.append(entry)
    return result


def get_expirations(ticker: str) -> ExpirationsResponse:
    """Return all available expiration dates for a ticker."""
    t = yf.Ticker(ticker)
    try:
        expirations = list(t.options)
    except Exception:
        expirations = []

    return ExpirationsResponse(
        ticker=ticker.upper(),
        expirations=expirations,
    )


def get_options_chain(ticker: str, expiry: str | None = None) -> OptionsChainResponse:
    """Return options chain for a given ticker and optional expiry date."""
    t = yf.Ticker(ticker)

    try:
        expirations = list(t.options)
    except Exception:
        expirations = []

    if not expirations:
        return OptionsChainResponse(
            ticker=ticker.upper(),
            expiry="",
            expirations=[],
            calls=[],
            puts=[],
        )

    # Use specified expiry or default to nearest
    selected_expiry = expiry if expiry and expiry in expirations else expirations[0]

    try:
        chain = t.option_chain(selected_expiry)
        calls = _format_chain(chain.calls)
        puts = _format_chain(chain.puts)
    except Exception:
        calls = []
        puts = []

    return OptionsChainResponse(
        ticker=ticker.upper(),
        expiry=selected_expiry,
        expirations=expirations,
        calls=calls,
        puts=puts,
    )
