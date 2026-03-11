"""Signal history router for tracking and evaluating signal accuracy."""

from fastapi import APIRouter, HTTPException, Query

from backend.services.signal_history import (
    evaluate_signals,
    get_accuracy_stats,
    get_signal_history,
    _load_history,
    _save_history,
)

router = APIRouter()


@router.get("/history")
async def get_history(
    ticker: str = Query(None, description="Filter by ticker symbol"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
) -> list[dict]:
    """Get signal history, optionally filtered by ticker."""
    return get_signal_history(ticker=ticker, limit=limit)


@router.get("/history/stats")
async def get_stats(
    ticker: str = Query(None, description="Filter by ticker symbol"),
) -> dict:
    """Get signal accuracy statistics."""
    return get_accuracy_stats(ticker=ticker)


@router.post("/history/evaluate")
async def trigger_evaluation() -> dict:
    """Evaluate all pending signals against current market prices."""
    return evaluate_signals()


@router.delete("/history/{signal_id}")
async def delete_signal(signal_id: str) -> dict:
    """Delete a specific signal record by ID."""
    records = _load_history()
    original_len = len(records)
    records = [r for r in records if r["id"] != signal_id]

    if len(records) == original_len:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    _save_history(records)
    return {"deleted": signal_id}
