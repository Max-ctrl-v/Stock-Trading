from fastapi import APIRouter, HTTPException
from backend.services.watchlist import (
    get_watchlist_with_quotes,
    add_to_watchlist,
    remove_from_watchlist,
)
from backend.models.schemas import WatchlistResponse, WatchlistItem

router = APIRouter()


@router.get("", response_model=WatchlistResponse)
async def get_watchlist():
    """Get all watchlist items with live quotes and signals."""
    data = get_watchlist_with_quotes()
    return WatchlistResponse(
        items=[WatchlistItem(**item) for item in data["items"]],
        updated_at=data["updated_at"],
    )


@router.post("/{ticker}")
async def add_ticker(ticker: str):
    """Add a ticker to the watchlist."""
    result = add_to_watchlist(ticker)
    return result


@router.delete("/{ticker}")
async def remove_ticker(ticker: str):
    """Remove a ticker from the watchlist."""
    removed = remove_from_watchlist(ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"{ticker} not found in watchlist")
    return {"status": "removed", "ticker": ticker.upper()}
