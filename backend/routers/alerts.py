from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.alerts import create_alert, get_alerts, delete_alert, check_alerts
from backend.models.schemas import AlertRule, AlertsResponse

router = APIRouter()


class CreateAlertRequest(BaseModel):
    ticker: str
    condition: str = "above"
    target_price: float


@router.post("")
async def add_alert(req: CreateAlertRequest):
    alert = create_alert(req.ticker, req.condition, req.target_price)
    return AlertRule(**alert)


@router.get("")
async def list_alerts():
    alerts = get_alerts()
    return [AlertRule(**a) for a in alerts]


@router.delete("/{alert_id}")
async def remove_alert(alert_id: str):
    removed = delete_alert(alert_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "deleted", "id": alert_id}


@router.get("/check")
async def check_active_alerts():
    result = check_alerts()
    return AlertsResponse(
        alerts=[AlertRule(**a) for a in result["alerts"]],
        triggered=[AlertRule(**a) for a in result["triggered"]],
    )
