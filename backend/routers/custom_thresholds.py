from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import RSI_OVERSOLD, RSI_OVERBOUGHT
from backend.services.custom_thresholds import (
    get_thresholds,
    set_thresholds,
    delete_thresholds,
    list_all_thresholds,
)

router = APIRouter()


class ThresholdUpdate(BaseModel):
    rsi_oversold: Optional[float] = None
    rsi_overbought: Optional[float] = None
    signal_score_threshold: Optional[float] = None


@router.get("/")
async def get_all_thresholds() -> dict:
    """List all custom thresholds."""
    return list_all_thresholds()


@router.get("/{ticker}")
async def get_ticker_thresholds(ticker: str) -> dict:
    """Get thresholds for a specific ticker (custom or defaults)."""
    return get_thresholds(ticker)


@router.put("/{ticker}")
async def update_ticker_thresholds(ticker: str, body: ThresholdUpdate) -> dict:
    """Set or update custom thresholds for a ticker."""
    if body.rsi_oversold is None and body.rsi_overbought is None and body.signal_score_threshold is None:
        raise HTTPException(status_code=400, detail="At least one threshold field must be provided")

    try:
        result = set_thresholds(
            ticker=ticker,
            rsi_oversold=body.rsi_oversold,
            rsi_overbought=body.rsi_overbought,
            signal_score_threshold=body.signal_score_threshold,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return result


@router.delete("/{ticker}")
async def remove_ticker_thresholds(ticker: str) -> dict:
    """Delete custom thresholds for a ticker, reverting to defaults."""
    deleted = delete_thresholds(ticker)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No custom thresholds found for {ticker.upper()}")
    return {"deleted": True, "ticker": ticker.upper()}
