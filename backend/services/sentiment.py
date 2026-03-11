import time
import json
import httpx
from backend.config import PERPLEXITY_API_KEY

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

_sentiment_cache: dict[str, tuple] = {}
SENTIMENT_CACHE_TTL = 600  # 10 minutes


def _parse_perplexity_json(content: str) -> dict:
    """Extract JSON from Perplexity response, handling markdown code blocks."""
    if "```" in content:
        content = content.split("```json")[-1] if "```json" in content else content.split("```")[1]
        content = content.split("```")[0]
    return json.loads(content.strip())


def _query_perplexity(prompt: str, timeout: float = 30.0) -> str | None:
    if not PERPLEXITY_API_KEY:
        return None
    try:
        response = httpx.post(
            PERPLEXITY_URL,
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1000,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception:
        return None


def get_social_sentiment(ticker: str) -> dict:
    cache_key = f"social_{ticker.upper()}"
    if cache_key in _sentiment_cache:
        data, ts = _sentiment_cache[cache_key]
        if time.time() - ts < SENTIMENT_CACHE_TTL:
            return data

    prompt = f"""What are people saying about {ticker} on Twitter/X, Reddit (WSB, r/stocks, r/investing), and StockTwits right now? Last 48 hours only.

Return JSON:
{{
  "overall_sentiment": "bullish" or "bearish" or "neutral",
  "mention_volume": "high" or "medium" or "low",
  "sentiment_score": float from -1.0 (very bearish) to 1.0 (very bullish),
  "key_topics": ["topic1", "topic2", "topic3"],
  "summary": "2-3 sentence summary of social media discussion"
}}"""

    content = _query_perplexity(prompt)
    if content is None:
        return _empty_sentiment(ticker)

    try:
        parsed = _parse_perplexity_json(content)
        result = {
            "ticker": ticker.upper(),
            "overall_sentiment": parsed.get("overall_sentiment", "neutral"),
            "mention_volume": parsed.get("mention_volume", "low"),
            "sentiment_score": float(parsed.get("sentiment_score", 0)),
            "key_topics": parsed.get("key_topics", []),
            "summary": parsed.get("summary", ""),
        }
        _sentiment_cache[cache_key] = (result, time.time())
        return result
    except Exception:
        return _empty_sentiment(ticker)


def get_reddit_sentiment(ticker: str) -> dict:
    cache_key = f"reddit_{ticker.upper()}"
    if cache_key in _sentiment_cache:
        data, ts = _sentiment_cache[cache_key]
        if time.time() - ts < SENTIMENT_CACHE_TTL:
            return data

    prompt = f"""What's the Reddit buzz on {ticker}? Check r/wallstreetbets, r/stocks, r/investing, r/options. Last 48-72 hours.

Return JSON:
{{
  "overall_sentiment": "bullish" or "bearish" or "neutral",
  "mention_volume": "high" or "medium" or "low",
  "sentiment_score": float from -1.0 (very bearish) to 1.0 (very bullish),
  "key_topics": ["topic1", "topic2", "topic3"],
  "top_subreddits": ["r/wallstreetbets", "r/stocks"],
  "summary": "2-3 sentence summary of Reddit discussion"
}}"""

    content = _query_perplexity(prompt)
    if content is None:
        return _empty_reddit_sentiment(ticker)

    try:
        parsed = _parse_perplexity_json(content)
        result = {
            "ticker": ticker.upper(),
            "overall_sentiment": parsed.get("overall_sentiment", "neutral"),
            "mention_volume": parsed.get("mention_volume", "low"),
            "sentiment_score": float(parsed.get("sentiment_score", 0)),
            "key_topics": parsed.get("key_topics", []),
            "top_subreddits": parsed.get("top_subreddits", []),
            "summary": parsed.get("summary", ""),
        }
        _sentiment_cache[cache_key] = (result, time.time())
        return result
    except Exception:
        return _empty_reddit_sentiment(ticker)


def _empty_sentiment(ticker: str) -> dict:
    return {
        "ticker": ticker.upper(),
        "overall_sentiment": "neutral",
        "mention_volume": "low",
        "sentiment_score": 0.0,
        "key_topics": [],
        "summary": "Could not pull social data right now.",
    }


def _empty_reddit_sentiment(ticker: str) -> dict:
    return {
        "ticker": ticker.upper(),
        "overall_sentiment": "neutral",
        "mention_volume": "low",
        "sentiment_score": 0.0,
        "key_topics": [],
        "top_subreddits": [],
        "summary": "Could not pull Reddit data right now.",
    }
