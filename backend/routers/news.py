from fastapi import APIRouter, HTTPException
from backend.services.perplexity import get_news_sentiment
from backend.models.schemas import NewsResponse, NewsItem

router = APIRouter()


@router.get("/{ticker}", response_model=NewsResponse)
async def get_news(ticker: str):
    try:
        data = get_news_sentiment(ticker)
        return NewsResponse(
            ticker=data["ticker"],
            sentiment=data["sentiment"],
            sentiment_score=data["sentiment_score"],
            items=[NewsItem(**item) for item in data["items"]],
            raw_analysis=data["raw_analysis"],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"News fetch failed for {ticker}: {str(e)}")
