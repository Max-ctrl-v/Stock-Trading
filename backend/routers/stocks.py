from fastapi import APIRouter, HTTPException
from backend.services.stock_data import get_quote, get_history, history_to_dict
from backend.services.technical import compute_indicators
from backend.config import TIMEFRAME_MAP
from backend.models.schemas import StockData, StockQuote, OHLCV, ChartData, IndicatorValues

router = APIRouter()


@router.get("/{ticker}/chart", response_model=ChartData)
async def get_chart_data(ticker: str, timeframe: str = "3M"):
    try:
        tf = TIMEFRAME_MAP.get(timeframe, ("3mo", "1d"))
        period, interval = tf
        df = get_history(ticker, period=period, interval=interval)
        history_data = history_to_dict(df)
        indicators = compute_indicators(df)

        return ChartData(
            ohlcv=OHLCV(**history_data),
            indicators=IndicatorValues(**indicators),
            timestamps=history_data["timestamp"],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Chart data failed for {ticker}: {str(e)}")


@router.get("/{ticker}", response_model=StockData)
async def get_stock(ticker: str, period: str = "3mo", interval: str = "1d"):
    try:
        quote_data = get_quote(ticker)
        df = get_history(ticker, period=period, interval=interval)
        history_data = history_to_dict(df)

        return StockData(
            quote=StockQuote(**quote_data),
            history=OHLCV(**history_data),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch data for {ticker}: {str(e)}")
