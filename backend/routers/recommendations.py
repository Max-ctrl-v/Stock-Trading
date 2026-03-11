"""
Router for stock recommendations — screens ~100 popular tickers and
returns top 10 picks scored for short-term and medium-term upside.
"""

import threading

from fastapi import APIRouter, HTTPException

from backend.services.recommendations import (
    get_cached_recommendations,
    is_scanning,
    run_scan,
)

router = APIRouter()


@router.post("/scan")
async def trigger_scan() -> dict:
    """Kick off a background recommendation scan.  Returns immediately."""
    if is_scanning():
        return {"message": "Scan already in progress"}

    thread = threading.Thread(target=run_scan, daemon=True)
    thread.start()
    return {"message": "Recommendation scan started"}


@router.get("/")
async def get_recommendations() -> dict:
    """Return cached recommendation results or current scanning status."""
    return get_cached_recommendations()
