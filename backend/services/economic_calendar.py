import json
from pathlib import Path
from datetime import date, datetime
from uuid import uuid4
from pydantic import BaseModel

DATA_DIR = Path(__file__).parent.parent.parent / "data"
CALENDAR_FILE = DATA_DIR / "economic_calendar.json"

VALID_CATEGORIES = {"fed", "inflation", "employment", "gdp", "other"}
VALID_IMPORTANCE = {"high", "medium", "low"}


class EconomicEvent(BaseModel):
    id: str
    title: str
    date: str
    category: str
    importance: str
    notes: str = ""


def _load_events() -> list[dict]:
    if not CALENDAR_FILE.exists():
        return []
    try:
        with open(CALENDAR_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def _save_events(events: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CALENDAR_FILE, "w") as f:
        json.dump(events, f, indent=2)


def get_all_events() -> list[dict]:
    events = _load_events()
    today = date.today().isoformat()
    upcoming = [e for e in events if e.get("date", "") >= today]
    upcoming.sort(key=lambda e: e.get("date", ""))
    return upcoming


def get_upcoming_events(days: int = 30) -> list[dict]:
    events = _load_events()
    today = date.today()
    cutoff = date.fromordinal(today.toordinal() + days).isoformat()
    today_str = today.isoformat()
    filtered = [
        e for e in events
        if today_str <= e.get("date", "") <= cutoff
    ]
    filtered.sort(key=lambda e: e.get("date", ""))
    return filtered


def add_event(title: str, event_date: str, category: str, importance: str, notes: str = "") -> dict:
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category: {category}. Must be one of {VALID_CATEGORIES}")
    if importance not in VALID_IMPORTANCE:
        raise ValueError(f"Invalid importance: {importance}. Must be one of {VALID_IMPORTANCE}")

    # Validate date format
    try:
        datetime.strptime(event_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD")

    event = {
        "id": str(uuid4()),
        "title": title,
        "date": event_date,
        "category": category,
        "importance": importance,
        "notes": notes,
    }

    events = _load_events()
    events.append(event)
    _save_events(events)
    return event


def delete_event(event_id: str) -> bool:
    events = _load_events()
    original_len = len(events)
    events = [e for e in events if e.get("id") != event_id]
    if len(events) == original_len:
        return False
    _save_events(events)
    return True


def seed_events() -> list[dict]:
    """Seed calendar with known major economic events for 2025-2026."""
    seeded: list[dict] = []

    # FOMC meeting dates (announcement dates)
    fomc_dates = [
        # 2025
        "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30",
        "2025-09-17", "2025-10-29", "2025-12-17",
        # 2026
        "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
        "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-16",
    ]
    for d in fomc_dates:
        seeded.append({
            "id": str(uuid4()),
            "title": "FOMC Interest Rate Decision",
            "date": d,
            "category": "fed",
            "importance": "high",
            "notes": "Federal Reserve monetary policy announcement",
        })

    # CPI release dates (typically second or third week of month)
    cpi_dates = [
        # 2025
        "2025-03-12", "2025-04-10", "2025-05-13", "2025-06-11",
        "2025-07-10", "2025-08-12", "2025-09-10", "2025-10-14",
        "2025-11-12", "2025-12-10",
        # 2026
        "2026-01-13", "2026-02-11", "2026-03-11", "2026-04-14",
        "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12",
        "2026-09-10", "2026-10-13", "2026-11-10", "2026-12-10",
    ]
    for d in cpi_dates:
        seeded.append({
            "id": str(uuid4()),
            "title": "CPI Report",
            "date": d,
            "category": "inflation",
            "importance": "high",
            "notes": "Consumer Price Index release",
        })

    # Non-Farm Payrolls (first Friday of each month, approximately)
    nfp_dates = [
        # 2025
        "2025-03-07", "2025-04-04", "2025-05-02", "2025-06-06",
        "2025-07-03", "2025-08-01", "2025-09-05", "2025-10-03",
        "2025-11-07", "2025-12-05",
        # 2026
        "2026-01-09", "2026-02-06", "2026-03-06", "2026-04-03",
        "2026-05-08", "2026-06-05", "2026-07-02", "2026-08-07",
        "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04",
    ]
    for d in nfp_dates:
        seeded.append({
            "id": str(uuid4()),
            "title": "Non-Farm Payrolls",
            "date": d,
            "category": "employment",
            "importance": "high",
            "notes": "Monthly jobs report",
        })

    # Load existing events and add seeded ones
    events = _load_events()
    events.extend(seeded)
    _save_events(events)
    return seeded
