from fastapi import APIRouter, HTTPException, Query
from backend.services.earnings import get_earnings, get_upcoming_earnings, get_portfolio_earnings

router = APIRouter()


@router.get("/portfolio")
async def earnings_portfolio():
    results = get_portfolio_earnings()
    return {"earnings": [r.model_dump() for r in results]}


@router.get("/upcoming")
async def earnings_upcoming(tickers: str = Query(..., description="Comma-separated tickers")):
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="No tickers provided")
    results = get_upcoming_earnings(ticker_list)
    return {"earnings": [r.model_dump() for r in results]}


@router.get("/{ticker}")
async def earnings_ticker(ticker: str):
    result = get_earnings(ticker.upper())
    return result.model_dump()
