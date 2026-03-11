from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.services.multi_leg import (
    get_all_trades,
    get_trade,
    create_trade,
    add_leg,
    close_trade,
    delete_trade,
)

router = APIRouter()


class CreateMultiLegRequest(BaseModel):
    ticker: str
    direction: str = "BUY"
    notes: str = ""


class AddLegRequest(BaseModel):
    action: str  # BUY or SELL
    price: float
    shares: float
    date: Optional[str] = None


@router.get("")
async def list_trades():
    return get_all_trades()


@router.post("")
async def create(req: CreateMultiLegRequest):
    try:
        return create_trade(req.ticker, req.direction, req.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{trade_id}/leg")
async def add_trade_leg(trade_id: str, req: AddLegRequest):
    try:
        result = add_leg(trade_id, req.action, req.price, req.shares, req.date)
        if not result:
            raise HTTPException(status_code=404, detail="Trade not found")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{trade_id}/close")
async def close(trade_id: str):
    result = close_trade(trade_id)
    if not result:
        raise HTTPException(status_code=404, detail="Trade not found or already closed")
    return result


@router.get("/{trade_id}")
async def get_single(trade_id: str):
    trade = get_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.delete("/{trade_id}")
async def remove(trade_id: str):
    if not delete_trade(trade_id):
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"status": "deleted", "id": trade_id}
