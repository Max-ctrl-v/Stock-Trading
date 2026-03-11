import asyncio
from fastapi import APIRouter, Query
from backend.models.schemas import (
    UnusualVolumeResponse, UnusualVolumeItem,
    GapResponse, GapItem,
    FiftyTwoWeekResponse, FiftyTwoWeekItem,
    EarningsMoversResponse, EarningsMoverItem,
    IPOResponse, IPOItem,
    InsiderBuyResponse, InsiderBuyItem,
    ShortInterestResponse, ShortInterestItem,
)

router = APIRouter()


@router.get("/unusual-volume", response_model=UnusualVolumeResponse)
async def unusual_volume(
    threshold: float = Query(3.0, description="Minimum volume ratio vs 20d average"),
):
    """Scan for stocks with unusual volume (default 3x+ average)."""
    from backend.services.volume_gap_scanner import scan_unusual_volume

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, scan_unusual_volume, None, threshold)
    items = [UnusualVolumeItem(**r) for r in results]
    return UnusualVolumeResponse(count=len(items), threshold=threshold, items=items)


@router.get("/gaps", response_model=GapResponse)
async def gap_scanner(
    min_gap_pct: float = Query(2.0, description="Minimum gap percentage"),
):
    """Scan for stocks that gapped up/down significantly at open."""
    from backend.services.volume_gap_scanner import scan_gaps

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, scan_gaps, None, min_gap_pct)
    items = [GapItem(**r) for r in results]
    return GapResponse(count=len(items), min_gap_pct=min_gap_pct, items=items)


@router.get("/52week", response_model=FiftyTwoWeekResponse)
async def fifty_two_week(
    proximity_pct: float = Query(5.0, description="Proximity to 52w high/low (%)"),
):
    """Find stocks near their 52-week high or low."""
    from backend.services.volume_gap_scanner import scan_52week_proximity

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, scan_52week_proximity, None, proximity_pct)
    items = [FiftyTwoWeekItem(**r) for r in results]
    return FiftyTwoWeekResponse(count=len(items), proximity_pct=proximity_pct, items=items)


@router.get("/earnings-movers", response_model=EarningsMoversResponse)
async def earnings_movers(
    min_move_pct: float = Query(5.0, description="Minimum post-earnings move (%)"),
):
    """Find stocks that moved big after recent earnings."""
    from backend.services.market_events_scanner import scan_earnings_movers

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, scan_earnings_movers, None, min_move_pct)
    items = [EarningsMoverItem(**r) for r in results]
    return EarningsMoversResponse(count=len(items), min_move_pct=min_move_pct, items=items)


@router.get("/ipos", response_model=IPOResponse)
async def recent_ipos(
    min_momentum_pct: float = Query(0.0, description="Minimum momentum since IPO (%)"),
):
    """Find recently IPO'd stocks with momentum."""
    from backend.services.market_events_scanner import scan_recent_ipos

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, scan_recent_ipos, min_momentum_pct)
    items = [IPOItem(**r) for r in results]
    return IPOResponse(count=len(items), items=items)


@router.get("/insider-buying", response_model=InsiderBuyResponse)
async def insider_buying():
    """Scan for stocks with recent insider buying activity."""
    from backend.services.external_data_scanner import scan_insider_buying

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, scan_insider_buying, None)
    items = [InsiderBuyItem(**r) for r in results]
    return InsiderBuyResponse(count=len(items), items=items)


@router.get("/short-interest", response_model=ShortInterestResponse)
async def short_interest(
    min_short_pct: float = Query(10.0, description="Minimum short % of float"),
):
    """Find stocks with high short interest (squeeze candidates)."""
    from backend.services.external_data_scanner import scan_short_interest

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, scan_short_interest, None, min_short_pct)
    items = [ShortInterestItem(**r) for r in results]
    return ShortInterestResponse(count=len(items), min_short_pct=min_short_pct, items=items)
