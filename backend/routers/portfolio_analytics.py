from fastapi import APIRouter, HTTPException, Query
from concurrent.futures import ThreadPoolExecutor
from backend.services.portfolio import get_positions
from backend.services.stock_data import get_quote
from backend.services.portfolio_analytics import (
    get_allocation, get_correlation_matrix, get_portfolio_beta,
    get_pnl_history, get_dividends, get_tax_lots, get_position_aging,
    get_rebalancing, get_exposure_warnings, get_pnl_breakdown,
)
from backend.models.schemas import (
    AllocationResponse, CorrelationResponse, PortfolioBetaResponse,
    PnlHistoryResponse, DividendResponse, TaxLotResponse,
    PositionAgingResponse, RebalanceResponse, ExposureResponse,
    PnlBreakdownResponse,
)
import json

router = APIRouter()


def _fetch_quotes(positions: list[dict]) -> dict[str, dict]:
    quotes = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(get_quote, p["ticker"]): p["ticker"] for p in positions}
        for f in futures:
            try:
                quotes[futures[f]] = f.result()
            except:
                pass
    return quotes


@router.get("/allocation", response_model=AllocationResponse)
async def allocation() -> AllocationResponse:
    positions = get_positions()
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    quotes = _fetch_quotes(positions)
    data = get_allocation(positions, quotes)
    return AllocationResponse(**data)


@router.get("/correlation", response_model=CorrelationResponse)
async def correlation() -> CorrelationResponse:
    positions = get_positions()
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    tickers = [p["ticker"] for p in positions]
    data = get_correlation_matrix(tickers)
    return CorrelationResponse(**data)


@router.get("/beta", response_model=PortfolioBetaResponse)
async def beta() -> PortfolioBetaResponse:
    positions = get_positions()
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    quotes = _fetch_quotes(positions)
    data = get_portfolio_beta(positions, quotes)
    return PortfolioBetaResponse(**data)


@router.get("/pnl-history", response_model=PnlHistoryResponse)
async def pnl_history() -> PnlHistoryResponse:
    positions = get_positions()
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    snapshots = get_pnl_history(positions)
    return PnlHistoryResponse(snapshots=snapshots)


@router.get("/dividends", response_model=DividendResponse)
async def dividends() -> DividendResponse:
    positions = get_positions()
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    data = get_dividends(positions)
    return DividendResponse(**data)


@router.get("/tax-lots", response_model=TaxLotResponse)
async def tax_lots() -> TaxLotResponse:
    positions = get_positions()
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    holdings = get_tax_lots(positions)
    return TaxLotResponse(holdings=holdings)


@router.get("/aging", response_model=PositionAgingResponse)
async def aging() -> PositionAgingResponse:
    positions = get_positions()
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    data = get_position_aging(positions)
    return PositionAgingResponse(**data)


@router.get("/rebalance", response_model=RebalanceResponse)
async def rebalance(targets: str = Query(None)) -> RebalanceResponse:
    positions = get_positions()
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    quotes = _fetch_quotes(positions)
    if targets:
        target_dict = json.loads(targets)
    else:
        equal_pct = round(100.0 / len(positions), 2)
        target_dict = {p["ticker"]: equal_pct for p in positions}
    data = get_rebalancing(positions, quotes, target_dict)
    return RebalanceResponse(**data)


@router.get("/exposure", response_model=ExposureResponse)
async def exposure(limit: float = Query(20.0)) -> ExposureResponse:
    positions = get_positions()
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    quotes = _fetch_quotes(positions)
    data = get_exposure_warnings(positions, quotes, limit)
    return ExposureResponse(**data)


@router.get("/pnl-breakdown", response_model=PnlBreakdownResponse)
async def pnl_breakdown() -> PnlBreakdownResponse:
    positions = get_positions()
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    quotes = _fetch_quotes(positions)
    data = get_pnl_breakdown(positions, quotes)
    return PnlBreakdownResponse(**data)
