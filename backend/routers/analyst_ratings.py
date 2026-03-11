from fastapi import APIRouter
from backend.services.analyst_ratings import (
    get_analyst_rating,
    get_rating_history,
    get_portfolio_ratings,
)

router = APIRouter()


@router.get("/portfolio")
async def ratings_portfolio():
    results = get_portfolio_ratings()
    return {"ratings": results}


@router.get("/{ticker}/history")
async def rating_history(ticker: str):
    history = get_rating_history(ticker.upper())
    return {"ticker": ticker.upper(), "history": history}


@router.get("/{ticker}")
async def rating_ticker(ticker: str):
    return get_analyst_rating(ticker.upper())
