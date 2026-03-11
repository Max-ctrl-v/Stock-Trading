from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.trailing_stop import calculate_trailing_stop, get_all_stop_levels

router = APIRouter()


class TrailingStopRequest(BaseModel):
    ticker: str
    entry_price: float
    trail_type: str = "percentage"  # percentage, atr, chandelier
    trail_value: float = 3.0


@router.post("/calculate")
async def calc_trailing_stop(req: TrailingStopRequest):
    try:
        return calculate_trailing_stop(
            ticker=req.ticker,
            entry_price=req.entry_price,
            trail_type=req.trail_type,
            trail_value=req.trail_value,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticker}/levels")
async def stop_levels(ticker: str):
    try:
        return get_all_stop_levels(ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
