import asyncio
from fastapi import APIRouter, Query
from backend.services.screener import (
    run_screener_scan, get_scan_status, run_watchlist_scan,
    run_sector_scan, get_preset_results, list_presets,
)
from backend.models.schemas import ScreenerResponse, ScreenerPick

router = APIRouter()


@router.get("/presets")
async def get_presets():
    """List all available screener presets."""
    return list_presets()


@router.get("/presets/{preset_key}")
async def get_preset(preset_key: str):
    """Get screener results filtered by a preset."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, get_preset_results, preset_key)
    return result


@router.post("/scan")
async def start_scan():
    """Kick off a background screener scan."""
    status = get_scan_status()
    if status["status"] == "scanning":
        return {"status": "already_scanning", "progress": status["progress"]}

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_screener_scan)

    return {"status": "scanning", "message": "Scan started"}


@router.post("/scan/watchlist")
async def scan_watchlist():
    """Scan only tickers from the user's watchlist."""
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, run_watchlist_scan)
    picks = [ScreenerPick(**p) for p in results]
    return ScreenerResponse(
        status="ready",
        scanned_at="",
        total_scanned=len(picks),
        progress=0,
        picks=picks,
    )


@router.post("/scan/sector")
async def scan_sector(sector: str = Query(..., description="Sector name, e.g. 'Technology', 'Healthcare'")):
    """Scan only tickers from a specific sector."""
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, run_sector_scan, sector)
    picks = [ScreenerPick(**p) for p in results]
    return ScreenerResponse(
        status="ready",
        scanned_at="",
        total_scanned=len(picks),
        progress=0,
        picks=picks,
    )


@router.get("/results", response_model=ScreenerResponse)
async def get_results():
    """Get screener results."""
    data = get_scan_status()
    picks = [ScreenerPick(**p) for p in data.get("picks", [])]
    return ScreenerResponse(
        status=data["status"],
        scanned_at=data.get("scanned_at", ""),
        total_scanned=data.get("total_scanned", 0),
        progress=data.get("progress", 0),
        picks=picks,
    )
