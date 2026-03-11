"""Claude Opus analysis with adaptive thinking for deep stock analysis."""
import json
import anthropic
from backend.config import ANTHROPIC_API_KEY

SYSTEM_PROMPT = """You are an aggressive short-term trader with 20 years of experience in technical analysis and market microstructure. Be blunt, specific, and actionable. No hedging.

Analyze the provided stock technicals and give a trading recommendation.

Respond ONLY with valid JSON in this exact format:
{
  "direction": "BUY" or "SELL" or "HOLD",
  "conviction": 1-10,
  "analysis": "3-4 sentence deep analysis covering key technical factors and what the chart is telling you",
  "entry": float,
  "stop_loss": float,
  "target_1": float,
  "target_2": float,
  "catalysts": ["catalyst1", "catalyst2"],
  "risks": ["risk1", "risk2"],
  "timeframe": "e.g. 1-3 days or 1-2 weeks",
  "key_levels": {"support": float, "resistance": float}
}"""


def analyze_stock(
    ticker: str,
    price: float,
    indicators: dict,
    news_summary: str = "",
) -> dict | None:
    if not ANTHROPIC_API_KEY:
        return None

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""Trade setup for {ticker}. Current price: ${price:.2f}

Technical Indicators:
- RSI(14): {indicators.get('rsi', 'N/A')}
- MACD Line: {indicators.get('macd_line', 'N/A')} | Signal: {indicators.get('macd_signal', 'N/A')} | Hist: {indicators.get('macd_histogram', 'N/A')}
- Bollinger Bands: Upper {indicators.get('bb_upper', 'N/A')} | Mid {indicators.get('bb_middle', 'N/A')} | Lower {indicators.get('bb_lower', 'N/A')}
- SMA 20: {indicators.get('sma_20', 'N/A')} | SMA 50: {indicators.get('sma_50', 'N/A')} | SMA 200: {indicators.get('sma_200', 'N/A')}
- ATR(14): {indicators.get('atr', 'N/A')}
- ADX: {indicators.get('adx', 'N/A')} | +DI: {indicators.get('adx_pos', 'N/A')} | -DI: {indicators.get('adx_neg', 'N/A')}
- Stoch RSI K: {indicators.get('stoch_rsi_k', 'N/A')} | D: {indicators.get('stoch_rsi_d', 'N/A')}
- OBV: {indicators.get('obv', 'N/A')}"""

    if news_summary:
        prompt += f"\n\nMarket Context:\n{news_summary}"

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response (skip thinking blocks)
        content = ""
        for block in response.content:
            if block.type == "text":
                content = block.text.strip()
                break

        if not content:
            return None

        # Strip markdown code blocks
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]

        return json.loads(content)

    except Exception:
        return None
