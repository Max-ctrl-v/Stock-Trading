from fastapi import APIRouter, HTTPException, Query

from backend.services.options import get_options_chain, get_expirations

router = APIRouter()


@router.get("/{ticker}/expirations")
async def expirations(ticker: str):
    """List all available expiration dates for a ticker."""
    try:
        return get_expirations(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch expirations for {ticker}: {str(e)}")


@router.get("/{ticker}/chain")
async def chain(ticker: str, expiry: str | None = Query(default=None)):
    """Get options chain (calls and puts) for a ticker. Defaults to nearest expiry."""
    try:
        result = get_options_chain(ticker, expiry)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch options chain for {ticker}: {str(e)}")

    if not result.expirations:
        raise HTTPException(status_code=404, detail=f"No options data available for {ticker}")

    return result
