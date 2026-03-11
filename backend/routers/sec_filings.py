from fastapi import APIRouter, HTTPException

from backend.services.sec_filings import (
    get_filings_for_ticker,
    get_filings_for_portfolio,
    get_filing_summary,
)

router = APIRouter()


@router.get("/portfolio")
async def portfolio_filings():
    """Get recent SEC filings for all portfolio stocks."""
    try:
        results = await get_filings_for_portfolio()
        return {"portfolio_filings": [r.model_dump() for r in results]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch portfolio filings: {str(e)}")


@router.get("/{ticker}/summary")
async def filing_summary(ticker: str):
    """Get an AI-generated summary of the most recent SEC filing for a ticker."""
    try:
        result = await get_filing_summary(ticker)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate filing summary: {str(e)}")


@router.get("/{ticker}")
async def ticker_filings(ticker: str):
    """Get recent SEC filings for a specific ticker."""
    try:
        result = await get_filings_for_ticker(ticker)
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch filings for {ticker}: {str(e)}")
