from fastapi import APIRouter, HTTPException, Query

from backend.services.trade_replay import get_replay_range, get_replay_day

router = APIRouter()


@router.get("/{ticker}/day/{date}")
async def replay_day(ticker: str, date: str):
    """Get single day's OHLCV + indicators + journal trades."""
    try:
        return get_replay_day(ticker, date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trade replay failed for {ticker} on {date}: {str(e)}")


@router.get("/{ticker}")
async def replay_range(
    ticker: str,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
):
    """Get daily OHLCV + indicators for a date range with journal trade overlay."""
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    try:
        return get_replay_range(ticker, start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trade replay failed for {ticker}: {str(e)}")
