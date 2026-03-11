import time
from datetime import datetime, timezone
from typing import Optional

import openai
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from ta.trend import MACD, SMAIndicator

from backend.config import OPENAI_API_KEY
from backend.services.portfolio import _load
from backend.models.schemas import SellSignal, SellSignalsResponse

# Cache: { "all": (timestamp, SellSignalsResponse), "TICKER": (timestamp, SellSignal) }
_cache: dict[str, tuple[float, object]] = {}
SELL_SIGNAL_CACHE_TTL: int = 600  # 10 minutes

client = openai.OpenAI(api_key=OPENAI_API_KEY)


def _get_cached(key: str) -> Optional[object]:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < SELL_SIGNAL_CACHE_TTL:
            return data
    return None


def _set_cache(key: str, data: object) -> None:
    _cache[key] = (time.time(), data)


def _aggregate_positions(positions: list[dict]) -> dict[str, dict]:
    """Group positions by ticker and compute weighted avg cost, total shares, total P&L."""
    grouped: dict[str, dict] = {}
    for pos in positions:
        ticker = pos["ticker"]
        if ticker not in grouped:
            grouped[ticker] = {
                "ticker": ticker,
                "total_shares": 0.0,
                "total_invested": 0.0,
                "total_pnl": 0.0,
                "current_price": pos.get("current_price", 0.0),
            }
        shares = pos.get("shares", 0.0)
        avg_cost = pos.get("avg_cost", 0.0)
        grouped[ticker]["total_shares"] += shares
        grouped[ticker]["total_invested"] += shares * avg_cost
        grouped[ticker]["total_pnl"] += pos.get("pnl", 0.0)

    # Compute weighted avg cost and pnl %
    for ticker, g in grouped.items():
        if g["total_shares"] > 0:
            g["avg_cost"] = g["total_invested"] / g["total_shares"]
        else:
            g["avg_cost"] = 0.0
        if g["total_invested"] > 0:
            g["pnl_pct"] = (g["total_pnl"] / g["total_invested"]) * 100
        else:
            g["pnl_pct"] = 0.0

    return grouped


def _analyze_ticker(ticker: str, pnl_pct: float, current_price: float) -> SellSignal:
    """Run technical analysis on a single ticker and score hold vs sell."""
    factors: list[str] = []
    sell_score = 0  # accumulate sell pressure points

    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y", interval="1d")
        if df.empty or len(df) < 50:
            return SellSignal(
                ticker=ticker,
                action="HOLD",
                urgency=1,
                current_pnl_pct=round(pnl_pct, 2),
                ai_reasoning="Insufficient data to analyze.",
                factors=["Not enough historical data"],
            )

        close = df["Close"]
        volume = df["Volume"]

        # RSI
        rsi_ind = RSIIndicator(close=close, window=14)
        rsi_series = rsi_ind.rsi()
        rsi_val = rsi_series.iloc[-1] if not rsi_series.empty else None

        if rsi_val is not None and rsi_val > 70:
            sell_score += 2
            factors.append(f"RSI overbought at {rsi_val:.1f}")
        elif rsi_val is not None and rsi_val > 65:
            sell_score += 1
            factors.append(f"RSI elevated at {rsi_val:.1f}")

        # MACD
        macd_ind = MACD(close=close)
        macd_line = macd_ind.macd()
        macd_signal = macd_ind.macd_signal()
        if len(macd_line) >= 2 and len(macd_signal) >= 2:
            prev_diff = macd_line.iloc[-2] - macd_signal.iloc[-2]
            curr_diff = macd_line.iloc[-1] - macd_signal.iloc[-1]
            if prev_diff > 0 and curr_diff <= 0:
                sell_score += 2
                factors.append("MACD bearish crossover")
            elif curr_diff < 0:
                sell_score += 1
                factors.append("MACD below signal line")

        # Bollinger Bands
        bb = BollingerBands(close=close, window=20, window_dev=2)
        bb_upper = bb.bollinger_hband().iloc[-1]
        current = close.iloc[-1]
        if current >= bb_upper:
            sell_score += 2
            factors.append(f"Price at/above Bollinger upper band (${bb_upper:.2f})")
        elif current >= bb_upper * 0.98:
            sell_score += 1
            factors.append("Price near Bollinger upper band")

        # SMA50
        sma50 = SMAIndicator(close=close, window=50).sma_indicator()
        sma50_val = sma50.iloc[-1] if not sma50.empty else None
        vs_sma50 = ""
        if sma50_val is not None:
            if current < sma50_val:
                sell_score += 2
                factors.append(f"Price below SMA50 (${sma50_val:.2f})")
                vs_sma50 = "below"
            else:
                vs_sma50 = "above"

        # Volume declining on price rise (bearish divergence)
        if len(close) >= 10 and len(volume) >= 10:
            price_change = close.iloc[-1] - close.iloc[-10]
            vol_avg_recent = volume.iloc[-5:].mean()
            vol_avg_prior = volume.iloc[-10:-5].mean()
            if price_change > 0 and vol_avg_prior > 0 and vol_avg_recent < vol_avg_prior * 0.8:
                sell_score += 1
                factors.append("Volume declining on price rise (bearish divergence)")

        # P&L-based factors
        if pnl_pct > 30:
            sell_score += 2
            factors.append(f"P&L at +{pnl_pct:.1f}% - consider taking profits")
        elif pnl_pct > 20:
            sell_score += 1
            factors.append(f"P&L at +{pnl_pct:.1f}% - approaching profit target")

        if pnl_pct < -15:
            sell_score += 2
            factors.append(f"P&L at {pnl_pct:.1f}% - consider stop loss")
        elif pnl_pct < -10:
            sell_score += 1
            factors.append(f"P&L at {pnl_pct:.1f}% - approaching stop loss zone")

        # 52-week high
        high_52w = close.max()
        near_52w_high = False
        if high_52w > 0 and current >= high_52w * 0.95:
            near_52w_high = True
            sell_score += 1
            factors.append(f"Price within 5% of 52-week high (${high_52w:.2f})")

        # Determine action
        if sell_score >= 6:
            action = "SELL"
            urgency = min(5, sell_score - 1)
        elif sell_score >= 3:
            action = "TRIM"
            urgency = min(4, sell_score)
        else:
            action = "HOLD"
            urgency = max(1, sell_score)

        # AI reasoning
        ai_reasoning = _get_ai_reasoning(
            ticker=ticker,
            rsi=rsi_val,
            macd_bearish="MACD bearish crossover" in " ".join(factors),
            vs_sma50=vs_sma50,
            near_52w_high=near_52w_high,
            pnl_pct=pnl_pct,
            factors=factors,
        )

        return SellSignal(
            ticker=ticker,
            action=action,
            urgency=urgency,
            current_pnl_pct=round(pnl_pct, 2),
            rsi=round(rsi_val, 2) if rsi_val is not None else None,
            vs_sma50=vs_sma50,
            near_52w_high=near_52w_high,
            ai_reasoning=ai_reasoning,
            factors=factors,
        )

    except Exception as e:
        return SellSignal(
            ticker=ticker,
            action="HOLD",
            urgency=1,
            current_pnl_pct=round(pnl_pct, 2),
            ai_reasoning=f"Analysis failed: {str(e)}",
            factors=[f"Error during analysis: {str(e)}"],
        )


def _get_ai_reasoning(
    ticker: str,
    rsi: Optional[float],
    macd_bearish: bool,
    vs_sma50: str,
    near_52w_high: bool,
    pnl_pct: float,
    factors: list[str],
) -> str:
    """Get AI-generated reasoning for hold/sell decision."""
    if not OPENAI_API_KEY:
        return "AI analysis unavailable (no API key)."

    technicals_summary = ", ".join(factors) if factors else "No strong signals detected"

    prompt = (
        f"You're an aggressive short-term trader reviewing a position. "
        f"Based on these technicals for {ticker}, should I hold or sell? "
        f"Current P&L is {pnl_pct:.1f}%. "
        f"RSI: {f'{rsi:.1f}' if rsi else 'N/A'}, "
        f"Price vs SMA50: {vs_sma50 or 'N/A'}, "
        f"MACD bearish crossover: {'yes' if macd_bearish else 'no'}, "
        f"Near 52-week high: {'yes' if near_52w_high else 'no'}. "
        f"Key factors: {technicals_summary}. "
        f"Be direct and specific - tell me exactly what you'd do and why. No hedging."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an aggressive short-term stock trader. Keep responses to 2-4 sentences. Be blunt and actionable."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=200,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"AI analysis failed: {str(e)}"


def get_all_sell_signals() -> SellSignalsResponse:
    """Analyze all portfolio positions and return sell signals."""
    cached = _get_cached("all")
    if cached is not None:
        return cached

    portfolio = _load()
    positions = portfolio.get("positions", [])
    if not positions:
        result = SellSignalsResponse(
            signals=[],
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )
        _set_cache("all", result)
        return result

    grouped = _aggregate_positions(positions)
    signals: list[SellSignal] = []

    for ticker, data in grouped.items():
        signal = _analyze_ticker(
            ticker=data["ticker"],
            pnl_pct=data["pnl_pct"],
            current_price=data["current_price"],
        )
        signals.append(signal)
        _set_cache(ticker.upper(), signal)

    # Sort by urgency descending (most urgent first)
    signals.sort(key=lambda s: s.urgency, reverse=True)

    result = SellSignalsResponse(
        signals=signals,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )
    _set_cache("all", result)
    return result


def get_sell_signal_for_ticker(ticker: str) -> Optional[SellSignal]:
    """Get sell signal for a specific ticker. Returns None if ticker not in portfolio."""
    ticker = ticker.upper()

    cached = _get_cached(ticker)
    if cached is not None:
        return cached

    portfolio = _load()
    positions = portfolio.get("positions", [])
    ticker_positions = [p for p in positions if p["ticker"].upper() == ticker]

    if not ticker_positions:
        return None

    grouped = _aggregate_positions(ticker_positions)
    data = grouped[ticker]

    signal = _analyze_ticker(
        ticker=ticker,
        pnl_pct=data["pnl_pct"],
        current_price=data["current_price"],
    )
    _set_cache(ticker, signal)
    return signal
