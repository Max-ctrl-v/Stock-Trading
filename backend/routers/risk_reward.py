from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.risk_reward import calculate_risk_reward, auto_risk_reward

router = APIRouter()


class RiskRewardRequest(BaseModel):
    ticker: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float | None = None
    shares: float


@router.post("/calculate")
async def calculate(req: RiskRewardRequest):
    """Calculate risk/reward given entry, stop, and target prices."""
    if req.entry_price <= 0 or req.stop_loss <= 0 or req.target_1 <= 0:
        raise HTTPException(status_code=400, detail="Prices must be positive numbers")
    if req.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be a positive number")
    try:
        return calculate_risk_reward(
            ticker=req.ticker,
            entry_price=req.entry_price,
            stop_loss=req.stop_loss,
            target_1=req.target_1,
            target_2=req.target_2,
            shares=req.shares,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk/reward calculation failed: {str(e)}")


@router.get("/{ticker}/auto")
async def auto(ticker: str):
    """Auto-calculate risk/reward using ATR-based levels."""
    try:
        return auto_risk_reward(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto risk/reward failed for {ticker}: {str(e)}")
