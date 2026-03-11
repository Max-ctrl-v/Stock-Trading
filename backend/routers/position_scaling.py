from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.position_scaling import calculate_scaling

router = APIRouter()


class ScalingRequest(BaseModel):
    ticker: str
    initial_entry: float
    initial_shares: int
    account_size: float = 100000.0
    max_risk_pct: float = 5.0
    scaling_levels: list[float]
    use_percentage: bool = False


@router.post("/calculate")
async def calc_scaling(req: ScalingRequest):
    try:
        return calculate_scaling(
            ticker=req.ticker,
            initial_entry=req.initial_entry,
            initial_shares=req.initial_shares,
            account_size=req.account_size,
            max_risk_pct=req.max_risk_pct,
            scaling_levels=req.scaling_levels,
            use_percentage=req.use_percentage,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
