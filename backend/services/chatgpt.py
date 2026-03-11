import json
from openai import OpenAI
from backend.config import OPENAI_API_KEY

SYSTEM_PROMPT = """You're a short-term trader who trades momentum, breakouts, and mean-reversion. Be blunt. Give exact price levels, not ranges. No hedging, no "it depends."

I'll send you technicals for a stock. Tell me what to do with it.

IMPORTANT: Respond ONLY with valid JSON in this exact format:
{
  "direction": "BUY" or "SELL" or "HOLD",
  "conviction": 1-10,
  "analysis": "2-3 sentence analysis",
  "entry": float,
  "stop_loss": float,
  "target_1": float,
  "target_2": float,
  "catalysts": ["catalyst1", "catalyst2"],
  "risks": ["risk1", "risk2"],
  "timeframe": "1-5 days" or "1-2 weeks" etc
}"""


def analyze_stock(
    ticker: str,
    price: float,
    indicators: dict,
    news_summary: str = "",
) -> dict | None:
    if not OPENAI_API_KEY:
        return None

    client = OpenAI(api_key=OPENAI_API_KEY)

    user_prompt = f"""What's the play on {ticker}? Short-term trade.

Current price: ${price:.2f}

Technical Indicators:
- RSI(14): {indicators.get('rsi', 'N/A')}
- MACD Line: {indicators.get('macd_line', 'N/A')}
- MACD Signal: {indicators.get('macd_signal', 'N/A')}
- MACD Histogram: {indicators.get('macd_histogram', 'N/A')}
- Bollinger Upper: {indicators.get('bb_upper', 'N/A')}
- Bollinger Middle: {indicators.get('bb_middle', 'N/A')}
- Bollinger Lower: {indicators.get('bb_lower', 'N/A')}
- SMA 20: {indicators.get('sma_20', 'N/A')}
- SMA 50: {indicators.get('sma_50', 'N/A')}
- SMA 200: {indicators.get('sma_200', 'N/A')}
- EMA 12: {indicators.get('ema_12', 'N/A')}
- EMA 26: {indicators.get('ema_26', 'N/A')}
- ATR(14): {indicators.get('atr', 'N/A')}"""

    if news_summary:
        user_prompt += f"\n\nRecent News & Sentiment:\n{news_summary}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=500,
        )

        content = response.choices[0].message.content.strip()
        # Strip markdown code blocks if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]

        return json.loads(content)
    except Exception:
        return None
