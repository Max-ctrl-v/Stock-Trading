from fastapi import APIRouter, HTTPException
from backend.services.portfolio import add_position
from backend.services.etoro import sync_portfolio as etoro_sync
from backend.config import ETORO_API_KEY, ETORO_USER_KEY
from backend.services.etoro import get_account_info

router = APIRouter()


@router.get("/status")
async def etoro_connection_status():
    """Check if eToro API connection is working."""
    if not ETORO_API_KEY or not ETORO_USER_KEY:
        return {"connected": False, "error": "ETORO_API_KEY and/or ETORO_USER_KEY not configured in .env"}

    info = get_account_info()
    if "error" in info:
        return {"connected": False, "error": info["error"], "detail": info.get("detail", "")}

    return {"connected": True, "account": info}


@router.post("/sync")
async def sync_etoro_portfolio():
    """Sync portfolio from eToro. Stores each position individually with eToro P&L."""
    result = etoro_sync()

    if "error" in result and result["error"]:
        raise HTTPException(status_code=400, detail=result["error"])

    etoro_positions = result.get("positions", [])

    # Replace strategy: remove ALL etoro-sourced positions, then insert fresh ones
    from backend.services.portfolio import _load, _save
    data = _load()

    # Remove old eToro positions (identified by source field)
    data["positions"] = [
        p for p in data["positions"]
        if p.get("source") != "etoro"
    ]

    # Add fresh eToro positions - each one individually
    from datetime import datetime
    for pos in etoro_positions:
        data["positions"].append({
            "ticker": pos["ticker"].upper(),
            "shares": pos["shares"],
            "avg_cost": pos["avg_cost"],
            "current_price": pos.get("current_price"),
            "invested": pos.get("invested", 0),
            "pnl": pos.get("pnl", 0),
            "source": "etoro",
            "instrument_id": pos.get("instrument_id"),
            "position_id": pos.get("position_id"),
            "added_at": datetime.now().isoformat(),
        })

    # Store eToro's total P&L at the top level
    data["etoro_total_pnl"] = result.get("total_pnl", 0)
    data["etoro_synced_at"] = result.get("synced_at", "")

    _save(data)

    return {
        "status": "ok",
        "imported": len(etoro_positions),
        "synced_at": result.get("synced_at", ""),
        "total_pnl": result.get("total_pnl", 0),
        "positions": etoro_positions,
    }
