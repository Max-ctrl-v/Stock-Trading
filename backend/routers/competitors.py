from fastapi import APIRouter, HTTPException

from backend.services.competitors import get_competitors, get_performance_comparison

router = APIRouter()


@router.get("/{ticker}/performance")
async def competitor_performance(ticker: str, period: str = "3M"):
    """Compare normalized price performance of a ticker vs its competitors."""
    valid_periods = ["1M", "3M", "6M", "1Y"]
    if period.upper() not in valid_periods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period '{period}'. Must be one of: {', '.join(valid_periods)}",
        )
    try:
        result = await get_performance_comparison(ticker, period)
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compare performance: {str(e)}")


@router.get("/{ticker}")
async def competitor_comparison(ticker: str):
    """Identify competitors and compare key metrics."""
    try:
        result = await get_competitors(ticker)
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch competitors for {ticker}: {str(e)}")
