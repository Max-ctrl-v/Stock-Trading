from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.paper_trading import (
    get_account_summary,
    open_trade,
    close_trade,
    get_trade_history,
    reset_account,
)

router = APIRouter()


class OpenTradeRequest(BaseModel):
    ticker: str
    direction: str = "BUY"
    shares: float


@router.get("/account")
async def account_summary():
    try:
        return get_account_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade")
async def create_trade(req: OpenTradeRequest):
    try:
        trade = open_trade(req.ticker, req.direction, req.shares)
        return trade
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{trade_id}/close")
async def close_existing_trade(trade_id: str):
    try:
        result = close_trade(trade_id)
        if not result:
            raise HTTPException(status_code=404, detail="Trade not found or already closed")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def trade_history():
    return get_trade_history()


@router.post("/reset")
async def reset():
    return reset_account()
