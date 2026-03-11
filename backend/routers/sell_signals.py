from fastapi import APIRouter, HTTPException
from backend.services.sell_signals import get_all_sell_signals, get_sell_signal_for_ticker
from backend.models.schemas import SellSignal, SellSignalsResponse

router = APIRouter()


@router.get("/", response_model=SellSignalsResponse)
async def get_sell_signals() -> SellSignalsResponse:
    """Get sell signals for all portfolio positions."""
    try:
        return get_all_sell_signals()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze portfolio: {str(e)}")


@router.get("/{ticker}", response_model=SellSignal)
async def get_ticker_sell_signal(ticker: str) -> SellSignal:
    """Get sell signal for a specific ticker in portfolio."""
    signal = get_sell_signal_for_ticker(ticker)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"{ticker.upper()} not found in portfolio")
    return signal
