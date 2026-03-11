import time
from typing import Optional

import openai
import yfinance as yf
import pandas as pd
from pydantic import BaseModel

from backend.config import OPENAI_API_KEY

# In-memory cache: ticker -> (competitors list, timestamp)
_competitor_cache: dict[str, tuple[list[str], float]] = {}
CACHE_TTL = 86400  # 24 hours


class CompetitorMetrics(BaseModel):
    ticker: str
    name: str
    price: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    change_1d_pct: Optional[float] = None
    change_1m_pct: Optional[float] = None
    change_ytd_pct: Optional[float] = None


class CompetitorComparisonResponse(BaseModel):
    ticker: str
    competitors: list[CompetitorMetrics]
    fetched_at: str


class PerformancePoint(BaseModel):
    date: str
    value: float


class TickerPerformance(BaseModel):
    ticker: str
    data: list[PerformancePoint]


class PerformanceComparisonResponse(BaseModel):
    ticker: str
    period: str
    series: list[TickerPerformance]
    fetched_at: str


async def _identify_competitors(ticker: str) -> list[str]:
    """Use OpenAI to identify 4-5 competitors for the given ticker."""
    # Check cache
    if ticker.upper() in _competitor_cache:
        cached, ts = _competitor_cache[ticker.upper()]
        if time.time() - ts < CACHE_TTL:
            return cached

    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured")

    # Get sector/industry info from yfinance for context
    try:
        info = yf.Ticker(ticker).info
        sector = info.get("sector", "Unknown")
        industry = info.get("industry", "Unknown")
        company_name = info.get("shortName", ticker)
        context = f"{company_name} ({ticker}) is in the {industry} industry, {sector} sector."
    except Exception:
        context = f"The stock ticker is {ticker}."

    client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    completion = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Give me 4-5 US-listed competitor tickers, comma-separated. "
                    "Nothing else. No explanations."
                ),
            },
            {
                "role": "user",
                "content": f"What are the main public competitors of {context}",
            },
        ],
        temperature=0.2,
        max_tokens=100,
    )

    raw = completion.choices[0].message.content or ""
    # Parse comma-separated tickers
    competitors = [
        t.strip().upper()
        for t in raw.replace("\n", ",").split(",")
        if t.strip() and t.strip().isalpha() and len(t.strip()) <= 5
    ]
    competitors = competitors[:5]

    # Cache result
    _competitor_cache[ticker.upper()] = (competitors, time.time())

    return competitors


def _get_metrics(ticker: str) -> CompetitorMetrics:
    """Fetch comparative metrics for a single ticker using yfinance."""
    try:
        t = yf.Ticker(ticker)
        info = t.info

        # Current price and basic info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        market_cap = info.get("marketCap")
        pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        name = info.get("shortName", ticker)

        # 1-day change
        change_1d = info.get("regularMarketChangePercent")

        # 1-month change
        change_1m: Optional[float] = None
        try:
            hist = t.history(period="1mo")
            if len(hist) >= 2:
                change_1m = ((hist["Close"].iloc[-1] / hist["Close"].iloc[0]) - 1) * 100
        except Exception:
            pass

        # YTD change
        change_ytd: Optional[float] = None
        try:
            hist_ytd = t.history(period="ytd")
            if len(hist_ytd) >= 2:
                change_ytd = ((hist_ytd["Close"].iloc[-1] / hist_ytd["Close"].iloc[0]) - 1) * 100
        except Exception:
            pass

        return CompetitorMetrics(
            ticker=ticker.upper(),
            name=name,
            price=price,
            market_cap=market_cap,
            pe_ratio=pe_ratio,
            change_1d_pct=round(change_1d, 2) if change_1d is not None else None,
            change_1m_pct=round(change_1m, 2) if change_1m is not None else None,
            change_ytd_pct=round(change_ytd, 2) if change_ytd is not None else None,
        )
    except Exception:
        return CompetitorMetrics(ticker=ticker.upper(), name=ticker)


async def get_competitors(ticker: str) -> CompetitorComparisonResponse:
    """Identify competitors and fetch comparative metrics."""
    competitor_tickers = await _identify_competitors(ticker)

    all_tickers = [ticker.upper()] + competitor_tickers
    metrics: list[CompetitorMetrics] = []
    for t in all_tickers:
        metrics.append(_get_metrics(t))

    return CompetitorComparisonResponse(
        ticker=ticker.upper(),
        competitors=metrics,
        fetched_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


PERIOD_MAP = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
}


async def get_performance_comparison(ticker: str, period: str = "3M") -> PerformanceComparisonResponse:
    """Compare normalized price performance (base 100) over a given period."""
    yf_period = PERIOD_MAP.get(period.upper(), "3mo")

    competitor_tickers = await _identify_competitors(ticker)
    all_tickers = [ticker.upper()] + competitor_tickers

    series: list[TickerPerformance] = []
    for t in all_tickers:
        try:
            hist = yf.Ticker(t).history(period=yf_period)
            if hist.empty or len(hist) < 2:
                continue
            base = hist["Close"].iloc[0]
            if base == 0:
                continue
            normalized = (hist["Close"] / base) * 100
            points = [
                PerformancePoint(
                    date=idx.strftime("%Y-%m-%d"),
                    value=round(float(val), 2),
                )
                for idx, val in normalized.items()
            ]
            series.append(TickerPerformance(ticker=t, data=points))
        except Exception:
            continue

    return PerformanceComparisonResponse(
        ticker=ticker.upper(),
        period=period.upper(),
        series=series,
        fetched_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )
