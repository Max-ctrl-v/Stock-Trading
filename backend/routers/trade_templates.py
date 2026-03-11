from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.services.trade_templates import (
    get_all_templates,
    get_template,
    create_template,
    delete_template,
    apply_template,
)

router = APIRouter()


class CreateTemplateRequest(BaseModel):
    name: str
    direction: str = "BUY"
    risk_pct: float = 2.5
    stop_loss_pct: float = 3.0
    take_profit_1_pct: float = 5.0
    take_profit_2_pct: Optional[float] = None
    notes: str = ""


@router.get("")
async def list_templates():
    return get_all_templates()


@router.post("")
async def create(req: CreateTemplateRequest):
    try:
        return create_template(
            name=req.name,
            direction=req.direction,
            risk_pct=req.risk_pct,
            stop_loss_pct=req.stop_loss_pct,
            take_profit_1_pct=req.take_profit_1_pct,
            take_profit_2_pct=req.take_profit_2_pct,
            notes=req.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{template_id}")
async def get_single(template_id: str):
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.delete("/{template_id}")
async def remove(template_id: str):
    if not delete_template(template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "deleted", "id": template_id}


@router.post("/{template_id}/apply/{ticker}")
async def apply(template_id: str, ticker: str):
    try:
        return apply_template(template_id, ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
