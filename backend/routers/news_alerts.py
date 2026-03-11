from fastapi import APIRouter, HTTPException

from backend.services.news_alerts import (
    create_alert,
    get_alerts,
    delete_alert,
    update_alert,
    check_all_alerts,
    CreateNewsAlertRequest,
    UpdateNewsAlertRequest,
)

router = APIRouter()


@router.get("")
async def list_news_alerts():
    """List all keyword alert rules."""
    return get_alerts()


@router.post("")
async def add_news_alert(req: CreateNewsAlertRequest):
    """Create a new keyword alert rule."""
    if not req.ticker or not req.keywords:
        raise HTTPException(status_code=400, detail="ticker and keywords are required")
    alert = create_alert(req.ticker, req.keywords, req.notify)
    return alert


@router.delete("/{alert_id}")
async def remove_news_alert(alert_id: str):
    """Delete a keyword alert rule."""
    removed = delete_alert(alert_id)
    if not removed:
        raise HTTPException(status_code=404, detail="News alert not found")
    return {"status": "deleted", "id": alert_id}


@router.put("/{alert_id}")
async def modify_news_alert(alert_id: str, req: UpdateNewsAlertRequest):
    """Update an existing keyword alert rule."""
    updated = update_alert(alert_id, req.ticker, req.keywords, req.notify)
    if updated is None:
        raise HTTPException(status_code=404, detail="News alert not found")
    return updated


@router.get("/check")
async def check_news_alerts():
    """Check all active alerts against recent news."""
    try:
        triggered = await check_all_alerts()
        return {
            "triggered": [t.model_dump() for t in triggered],
            "count": len(triggered),
            "checked_at": triggered[0].checked_at if triggered else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check news alerts: {str(e)}")
