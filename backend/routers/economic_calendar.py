from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from backend.services.economic_calendar import (
    get_all_events,
    get_upcoming_events,
    add_event,
    delete_event,
    seed_events,
)

router = APIRouter()


class CreateEventRequest(BaseModel):
    title: str
    date: str
    category: str
    importance: str
    notes: str = ""


@router.get("")
async def list_events():
    events = get_all_events()
    return {"events": events}


@router.get("/upcoming")
async def upcoming_events(days: int = Query(30, ge=1, le=365)):
    events = get_upcoming_events(days)
    return {"events": events, "days": days}


@router.post("/event")
async def create_event(req: CreateEventRequest):
    try:
        event = add_event(
            title=req.title,
            event_date=req.date,
            category=req.category,
            importance=req.importance,
            notes=req.notes,
        )
        return event
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/event/{event_id}")
async def remove_event(event_id: str):
    removed = delete_event(event_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"status": "deleted", "id": event_id}


@router.post("/seed")
async def seed_calendar():
    seeded = seed_events()
    return {"status": "seeded", "count": len(seeded)}
