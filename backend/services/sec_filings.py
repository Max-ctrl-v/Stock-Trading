import json
import time
from typing import Optional

import httpx
import openai
from pydantic import BaseModel

from backend.config import OPENAI_API_KEY, PERPLEXITY_API_KEY, DATA_DIR
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


class SECFiling(BaseModel):
    filing_type: str
    date: str
    title: str
    summary: str


class SECFilingsResponse(BaseModel):
    ticker: str
    filings: list[SECFiling]
    fetched_at: str


def _load_portfolio_tickers() -> list[str]:
    """Read ticker symbols from portfolio.json."""
    if not PORTFOLIO_FILE.exists():
        return []
    with open(PORTFOLIO_FILE) as f:
        data = json.load(f)
    if isinstance(data, list):
        return [p.get("ticker", p.get("symbol", "")).upper() for p in data if isinstance(p, dict)]
    if isinstance(data, dict) and "positions" in data:
        return [p.get("ticker", p.get("symbol", "")).upper() for p in data["positions"] if isinstance(p, dict)]
    return []


async def _perplexity_search(query: str) -> str:
    """Send a query to Perplexity sonar model and return the response text."""
    if not PERPLEXITY_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            PERPLEXITY_URL,
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [
                    {
                        "role": "system",
                        "content": "Look up SEC filings. Be specific with dates and numbers. No fluff.",
                    },
                    {"role": "user", "content": query},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def get_filings_for_ticker(ticker: str) -> SECFilingsResponse:
    """Fetch recent SEC filings for a single ticker using Perplexity."""
    query = (
        f"List the most recent SEC filings (10-K, 10-Q, 8-K) for {ticker.upper()} stock "
        f"from the past 12 months. For each filing, provide: filing type, date filed, title, "
        f"and a one-sentence summary. Format each filing as:\n"
        f"FILING: <type> | <date YYYY-MM-DD> | <title> | <summary>\n"
        f"List up to 10 filings, most recent first."
    )

    raw = await _perplexity_search(query)
    filings = _parse_filings(raw)

    return SECFilingsResponse(
        ticker=ticker.upper(),
        filings=filings,
        fetched_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def _parse_filings(raw_text: str) -> list[SECFiling]:
    """Parse Perplexity response into structured filing objects."""
    filings: list[SECFiling] = []
    for line in raw_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Try structured format first
        if "FILING:" in line:
            parts = line.split("FILING:")[-1].split("|")
            if len(parts) >= 4:
                filings.append(SECFiling(
                    filing_type=parts[0].strip(),
                    date=parts[1].strip(),
                    title=parts[2].strip(),
                    summary=parts[3].strip(),
                ))
                continue

        # Fallback: try to extract filing info from natural language
        filing_type = ""
        for ft in ["10-K", "10-Q", "8-K"]:
            if ft in line:
                filing_type = ft
                break
        if filing_type and len(line) > 20:
            filings.append(SECFiling(
                filing_type=filing_type,
                date="",
                title=line[:120],
                summary=line,
            ))

    return filings


async def get_filings_for_portfolio() -> list[SECFilingsResponse]:
    """Fetch SEC filings for all portfolio tickers."""
    tickers = _load_portfolio_tickers()
    if not tickers:
        return []

    results: list[SECFilingsResponse] = []
    for ticker in tickers:
        try:
            resp = await get_filings_for_ticker(ticker)
            results.append(resp)
        except Exception:
            results.append(SECFilingsResponse(
                ticker=ticker,
                filings=[],
                fetched_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            ))
    return results


async def get_filing_summary(ticker: str) -> dict:
    """Get a detailed AI summary of the most recent filing for a ticker."""
    # Step 1: Use Perplexity to get the most recent filing details
    query = (
        f"What is the most recent SEC filing (10-K, 10-Q, or 8-K) for {ticker.upper()}? "
        f"Provide the filing type, date, and key details/highlights from the filing. "
        f"Include any important financial figures, risk factors, or material events mentioned."
    )
    filing_details = await _perplexity_search(query)

    # Step 2: Use OpenAI to produce a structured summary
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured")

    client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    completion = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Summarize this SEC filing for a trader. Keep it short. "
                    "What's the filing type, what matters, what are the numbers, "
                    "what are the risks, and should I care for my positions?"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Summarize this SEC filing information for {ticker.upper()}:\n\n"
                    f"{filing_details}"
                ),
            },
        ],
        temperature=0.3,
        max_tokens=800,
    )

    summary_text = completion.choices[0].message.content or ""

    return {
        "ticker": ticker.upper(),
        "raw_details": filing_details,
        "summary": summary_text,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
