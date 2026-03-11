from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.services.journal import add_trade, close_trade, delete_trade, get_all_trades, compute_stats
from backend.models.schemas import TradeEntry, JournalStats, JournalResponse

router = APIRouter()


class AddTradeRequest(BaseModel):
    ticker: str
    direction: str = "BUY"
    entry_price: float
    shares: float
    notes: str = ""
    tags: list[str] = []


class CloseTradeRequest(BaseModel):
    exit_price: float


@router.get("", response_model=JournalResponse)
async def get_journal():
    trades = get_all_trades()
    stats = compute_stats()
    return JournalResponse(
        trades=[TradeEntry(**t) for t in trades],
        stats=JournalStats(**stats),
    )


@router.post("")
async def log_trade(req: AddTradeRequest):
    trade = add_trade(req.ticker, req.direction, req.entry_price, req.shares, req.notes, req.tags)
    return TradeEntry(**trade)


@router.post("/{trade_id}/close")
async def close_existing_trade(trade_id: str, req: CloseTradeRequest):
    result = close_trade(trade_id, req.exit_price)
    if not result:
        raise HTTPException(status_code=404, detail="Trade not found or already closed")
    return TradeEntry(**result)


@router.delete("/{trade_id}")
async def remove_trade(trade_id: str):
    removed = delete_trade(trade_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"status": "deleted", "id": trade_id}


@router.get("/stats", response_model=JournalStats)
async def get_stats():
    stats = compute_stats()
    return JournalStats(**stats)
