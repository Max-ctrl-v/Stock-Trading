from fastapi import APIRouter
from backend.services.market import get_sector_performance, get_market_overview
from backend.models.schemas import SectorPerformance, MarketOverview

router = APIRouter()


@router.get("/sectors")
async def sectors():
    data = get_sector_performance()
    return [SectorPerformance(**s) for s in data]


@router.get("/overview", response_model=MarketOverview)
async def overview():
    data = get_market_overview()
    return MarketOverview(
        sectors=[SectorPerformance(**s) for s in data["sectors"]],
        indices=data["indices"],
        updated_at=data["updated_at"],
    )
