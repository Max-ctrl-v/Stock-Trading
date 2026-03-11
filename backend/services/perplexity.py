import time
import json
import httpx
from backend.config import PERPLEXITY_API_KEY, NEWS_CACHE_TTL

_news_cache: dict[str, tuple] = {}

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


def get_news_sentiment(ticker: str) -> dict:
    # Check cache
    if ticker in _news_cache:
        data, ts = _news_cache[ticker]
        if time.time() - ts < NEWS_CACHE_TTL:
            return data

    if not PERPLEXITY_API_KEY:
        return _empty_news(ticker)

    prompt = f"""What's going on with {ticker} in the last 48 hours? I need:
1. Any breaking news or earnings
2. Analyst upgrades/downgrades
3. Insider buys or sells
4. Unusual options flow
5. What Reddit/Twitter are saying

Rate sentiment BULLISH, BEARISH, or NEUTRAL with a score from -1.0 to 1.0.

Format your response as JSON:
{{
  "sentiment": "bullish" or "bearish" or "neutral",
  "sentiment_score": float (-1 to 1),
  "headlines": [
    {{"headline": "...", "summary": "...", "sentiment": "bullish/bearish/neutral"}}
  ],
  "raw_analysis": "2-3 sentence summary"
}}"""

    try:
        response = httpx.post(
            PERPLEXITY_URL,
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 800,
            },
            timeout=30.0,
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]
        # Strip markdown code blocks if present
        if "```" in content:
            content = content.split("```json")[-1] if "```json" in content else content.split("```")[1]
            content = content.split("```")[0]

        parsed = json.loads(content.strip())

        result = {
            "ticker": ticker.upper(),
            "sentiment": parsed.get("sentiment", "neutral"),
            "sentiment_score": float(parsed.get("sentiment_score", 0)),
            "items": [
                {
                    "headline": h.get("headline", ""),
                    "summary": h.get("summary", ""),
                    "sentiment": h.get("sentiment", "neutral"),
                }
                for h in parsed.get("headlines", [])
            ],
            "raw_analysis": parsed.get("raw_analysis", ""),
        }

        _news_cache[ticker] = (result, time.time())
        return result

    except Exception:
        return _empty_news(ticker)


def _empty_news(ticker: str) -> dict:
    return {
        "ticker": ticker.upper(),
        "sentiment": "neutral",
        "sentiment_score": 0.0,
        "items": [],
        "raw_analysis": "Could not pull news right now.",
    }
