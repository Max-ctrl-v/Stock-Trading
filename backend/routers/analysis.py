from fastapi import APIRouter, HTTPException
from backend.services.stock_data import get_quote, get_history, history_to_dict
from backend.services.technical import compute_indicators
from backend.models.schemas import AnalysisResponse, StockQuote, IndicatorValues

router = APIRouter()


@router.get("/{ticker}", response_model=AnalysisResponse)
async def get_analysis(ticker: str, period: str = "6mo", interval: str = "1d"):
    try:
        quote_data = get_quote(ticker)
        df = get_history(ticker, period=period, interval=interval)
        indicators = compute_indicators(df)
        history = history_to_dict(df)

        return AnalysisResponse(
            ticker=ticker.upper(),
            quote=StockQuote(**quote_data),
            indicators=IndicatorValues(**indicators),
            timestamps=history["timestamp"][-60:],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Analysis failed for {ticker}: {str(e)}")
