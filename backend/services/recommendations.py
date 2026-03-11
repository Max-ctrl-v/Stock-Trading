"""
Recommendations service — screens ~100 popular eToro-tradable tickers
and scores them for short-term (+10% in 30d) and medium-term (+50% in 6m)
upside probability.  Returns top 10 picks with AI-generated reasoning.
"""

import time
import logging
import math
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import yfinance as yf
import pandas as pd
import openai
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from ta.trend import MACD

from backend.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Curated ticker universe (~100 popular eToro-tradable stocks)
# ---------------------------------------------------------------------------
RECOMMENDATION_TICKERS: list[str] = [
    # Mega-cap tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    # Semis
    "AMD", "TSM", "AVGO", "QCOM", "MU", "INTC", "TXN", "LRCX", "AMAT",
    "KLAC", "ASML", "ARM", "SMCI",
    # Enterprise / cloud
    "DELL", "HPE", "NOW", "CRM", "ADBE", "ORCL", "IBM", "SAP", "INTU",
    "WDAY", "VEEV", "HUBS", "SNOW", "DDOG", "MDB", "TEAM", "OKTA",
    # Cybersecurity
    "CRWD", "NET", "ZS", "PANW", "FTNT",
    # Consumer internet / fintech
    "PLTR", "SOFI", "SQ", "COIN", "DKNG", "ABNB", "UBER", "LYFT",
    "SNAP", "PINS", "RBLX", "U", "TTD", "ROKU", "SHOP",
    # Crypto-adjacent
    "MARA", "RIOT",
    # International ADRs
    "BABA", "JD", "NIO",
    # Streaming / media
    "NFLX", "DIS", "WBD", "PARA", "CMCSA",
    # EV
    "RIVN", "LCID",
    # Pharma / biotech
    "LLY", "NVO", "MRNA", "PFE", "JNJ", "UNH", "ABBV", "BMY", "GILD",
    "REGN", "ISRG", "DXCM", "BIIB",
    # Industrials / defense
    "BA", "LMT", "RTX", "GE", "CAT", "DE",
    # Financials
    "V", "MA", "AXP", "GS", "JPM", "MS", "C", "BAC", "WFC", "BRK-B",
    # Energy
    "XOM", "CVX", "COP", "SLB", "OXY",
]

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
RECOMMENDATIONS_CACHE_TTL: int = 1800  # 30 minutes

_cache: dict = {
    "results": None,          # RecommendationsResponse dict
    "scanned_at": 0.0,        # epoch
    "scanning": False,
}


def _is_cache_fresh() -> bool:
    if _cache["results"] is None:
        return False
    return (time.time() - _cache["scanned_at"]) < RECOMMENDATIONS_CACHE_TTL


# ---------------------------------------------------------------------------
# Per-ticker screening
# ---------------------------------------------------------------------------

def _screen_ticker(ticker: str) -> Optional[dict]:
    """Download 1-year daily data for *ticker*, compute indicators, and
    return a raw score dict.  Returns None on failure."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y", interval="1d")
        if hist.empty or len(hist) < 60:
            return None

        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        volume = hist["Volume"]
        price = float(close.iloc[-1])

        # --- Technical indicators ---
        rsi_indicator = RSIIndicator(close=close, window=14)
        rsi_series = rsi_indicator.rsi()
        rsi = float(rsi_series.iloc[-1]) if not math.isnan(rsi_series.iloc[-1]) else 50.0

        macd_indicator = MACD(close=close)
        macd_line = macd_indicator.macd()
        macd_signal = macd_indicator.macd_signal()
        macd_hist = macd_indicator.macd_diff()
        macd_hist_val = float(macd_hist.iloc[-1]) if not math.isnan(macd_hist.iloc[-1]) else 0.0
        macd_hist_prev = float(macd_hist.iloc[-2]) if len(macd_hist) >= 2 and not math.isnan(macd_hist.iloc[-2]) else 0.0

        bb = BollingerBands(close=close, window=20, window_dev=2)
        bb_upper = float(bb.bollinger_hband().iloc[-1]) if not math.isnan(bb.bollinger_hband().iloc[-1]) else price
        bb_lower = float(bb.bollinger_lband().iloc[-1]) if not math.isnan(bb.bollinger_lband().iloc[-1]) else price
        bb_width = (bb_upper - bb_lower) / price if price > 0 else 0.0

        # Volume ratio (today vs 20-day avg)
        vol_sma = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else float(volume.mean())
        current_vol = float(volume.iloc[-1])
        volume_ratio = current_vol / vol_sma if vol_sma > 0 else 1.0

        # 52-week range
        high_52w = float(high.max())
        low_52w = float(low.min())
        pct_from_52w_low = ((price - low_52w) / low_52w * 100) if low_52w > 0 else 0.0
        pct_from_52w_high = ((high_52w - price) / high_52w * 100) if high_52w > 0 else 0.0

        # Recent performance
        change_5d_pct = ((price / float(close.iloc[-6]) - 1) * 100) if len(close) >= 6 else 0.0
        change_1m_pct = ((price / float(close.iloc[-22]) - 1) * 100) if len(close) >= 22 else 0.0

        # SMA positions
        sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else price
        sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else price

        # --- Name ---
        info = stock.info or {}
        name = info.get("shortName", info.get("longName", ticker))

        # -----------------------------------------------------------------
        # SCORING — short-term (30d, +10%) and medium-term (6m, +50%)
        # -----------------------------------------------------------------

        # --- RSI score: oversold = higher upside ---
        # RSI < 30 → max score, RSI > 70 → min score
        rsi_score = max(0, min(100, (70 - rsi) * (100 / 40)))  # linear 30-70 mapped to 100-0

        # --- MACD momentum: rising histogram = bullish ---
        macd_crossover_score = 0.0
        if macd_hist_val > 0 and macd_hist_prev <= 0:
            macd_crossover_score = 90  # fresh bullish crossover
        elif macd_hist_val > 0 and macd_hist_val > macd_hist_prev:
            macd_crossover_score = 70  # accelerating bullish
        elif macd_hist_val > 0:
            macd_crossover_score = 50  # bullish but decelerating
        elif macd_hist_val < 0 and macd_hist_val > macd_hist_prev:
            macd_crossover_score = 35  # bearish but recovering
        else:
            macd_crossover_score = 10  # bearish and falling

        # --- Bollinger Band squeeze: tight bands = incoming big move ---
        # Narrow width → higher score (coiled spring)
        bb_squeeze_score = max(0, min(100, (1 - bb_width / 0.15) * 100)) if bb_width < 0.15 else 0

        # --- Volume surge ---
        volume_score = min(100, (volume_ratio - 1) * 50) if volume_ratio > 1 else 0

        # --- Price position in 52w range ---
        # Closer to 52w low = more upside room
        range_score = max(0, min(100, pct_from_52w_high * 2))  # 50% below high → 100

        # --- Price vs moving averages ---
        sma_score = 0.0
        if price > sma_50 > sma_200:
            sma_score = 70  # uptrend
        elif price > sma_50:
            sma_score = 50
        elif price < sma_50 and price < sma_200:
            # Deep pullback in downtrend — could be reversal candidate
            sma_score = 40
        else:
            sma_score = 30

        # --- SHORT-TERM (30d, +10%) ---
        # Weight: RSI 25%, MACD 25%, BB squeeze 20%, volume 15%, range 15%
        score_30d = (
            rsi_score * 0.25 +
            macd_crossover_score * 0.25 +
            bb_squeeze_score * 0.20 +
            volume_score * 0.15 +
            range_score * 0.15
        )

        # --- MEDIUM-TERM (6m, +50%) ---
        # Weight: range 30%, SMA trend 20%, RSI 15%, MACD 15%, BB 10%, volume 10%
        score_6m = (
            range_score * 0.30 +
            sma_score * 0.20 +
            rsi_score * 0.15 +
            macd_crossover_score * 0.15 +
            bb_squeeze_score * 0.10 +
            volume_score * 0.10
        )

        combined_score = score_30d * 0.4 + score_6m * 0.6

        return {
            "ticker": ticker,
            "name": name,
            "price": round(price, 2),
            "score_30d": round(score_30d, 1),
            "score_6m": round(score_6m, 1),
            "combined_score": round(combined_score, 1),
            "rsi": round(rsi, 1),
            "change_5d_pct": round(change_5d_pct, 2),
            "change_1m_pct": round(change_1m_pct, 2),
            "pct_from_52w_low": round(pct_from_52w_low, 1),
            "volume_ratio": round(volume_ratio, 2),
            "ai_reasoning": "",
        }

    except Exception as exc:
        logger.warning("Failed to screen %s: %s", ticker, exc)
        return None


# ---------------------------------------------------------------------------
# AI reasoning via OpenAI
# ---------------------------------------------------------------------------

def _generate_ai_reasoning(picks: list[dict]) -> list[dict]:
    """Call gpt-4o-mini once for the top 10 picks to generate reasoning."""
    if not OPENAI_API_KEY:
        for p in picks:
            p["ai_reasoning"] = "AI reasoning unavailable — no API key configured."
        return picks

    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    for pick in picks:
        try:
            prompt = (
                f"You're a momentum trader. Look at these numbers for {pick['ticker']} ({pick['name']}) "
                f"and tell me in 2-3 sentences why it could run or why it won't. "
                f"Be specific about catalysts and risks. No fluff.\n\n"
                f"Price: ${pick['price']}\n"
                f"RSI(14): {pick['rsi']}\n"
                f"5-day change: {pick['change_5d_pct']}%\n"
                f"1-month change: {pick['change_1m_pct']}%\n"
                f"From 52-week low: {pick['pct_from_52w_low']}%\n"
                f"Volume ratio (vs 20d avg): {pick['volume_ratio']}x\n"
                f"Short-term score (30d +10%): {pick['score_30d']}/100\n"
                f"Medium-term score (6m +50%): {pick['score_6m']}/100\n"
            )

            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.7,
            )
            pick["ai_reasoning"] = resp.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("AI reasoning failed for %s: %s", pick["ticker"], exc)
            pick["ai_reasoning"] = "AI reasoning unavailable."

    return picks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_cached_recommendations() -> dict:
    """Return cached results or scanning status."""
    if _cache["scanning"]:
        return {
            "status": "scanning",
            "scanned_at": "",
            "total_scanned": 0,
            "picks": [],
        }
    if _cache["results"] is not None:
        return _cache["results"]
    return {
        "status": "empty",
        "scanned_at": "",
        "total_scanned": 0,
        "picks": [],
    }


def run_scan() -> dict:
    """Run the full screening pipeline.  Meant to be called from a
    background thread so it doesn't block the event loop."""

    _cache["scanning"] = True
    scanned = 0
    scored: list[dict] = []

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(_screen_ticker, t): t for t in RECOMMENDATION_TICKERS}
            for future in as_completed(futures):
                result = future.result()
                scanned += 1
                if result is not None:
                    scored.append(result)

        # Sort by combined score descending, take top 10
        scored.sort(key=lambda x: x["combined_score"], reverse=True)
        top_picks = scored[:10]

        # Generate AI reasoning for top picks
        top_picks = _generate_ai_reasoning(top_picks)

        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        result = {
            "status": "ready",
            "scanned_at": now,
            "total_scanned": scanned,
            "picks": top_picks,
        }

        _cache["results"] = result
        _cache["scanned_at"] = time.time()

    except Exception as exc:
        logger.error("Recommendation scan failed: %s", exc)
        _cache["results"] = {
            "status": "empty",
            "scanned_at": "",
            "total_scanned": 0,
            "picks": [],
        }

    finally:
        _cache["scanning"] = False

    return _cache["results"]


def is_scanning() -> bool:
    return _cache["scanning"]
