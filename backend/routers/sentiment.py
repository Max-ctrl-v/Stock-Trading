from fastapi import APIRouter
from backend.services.sentiment import get_social_sentiment, get_reddit_sentiment

router = APIRouter()


@router.get("/{ticker}/reddit")
async def reddit_sentiment(ticker: str):
    return get_reddit_sentiment(ticker.upper())


@router.get("/{ticker}")
async def social_sentiment(ticker: str):
    return get_social_sentiment(ticker.upper())
