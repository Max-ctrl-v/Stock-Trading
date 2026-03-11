from fastapi import APIRouter, HTTPException
from backend.services.stock_data import get_quote, get_history, history_to_dict
from backend.services.technical import compute_indicators
from backend.services.signals import generate_signal, get_multi_timeframe_confirmation
from backend.services.position_sizing import calculate_position
from backend.services.chatgpt import analyze_stock
from backend.services.perplexity import get_news_sentiment
from backend.services.support_resistance import detect_support_resistance, calculate_fibonacci_levels
from backend.services.signal_history import log_signal
from backend.services.custom_thresholds import get_thresholds
from backend.services.earnings import get_earnings
from backend.models.schemas import (
    SignalResponse, StockQuote, IndicatorValues,
    SignalDirection, PositionSize, AIAnalysis, OHLCV,
)

router = APIRouter()


@router.get("/{ticker}", response_model=SignalResponse)
async def get_signal(
    ticker: str,
    account_size: float = 10000,
    risk_pct: float = 2.5,
    period: str = "6mo",
):
    try:
        quote_data = get_quote(ticker)
        df = get_history(ticker, period=period, interval="1d")
        indicators = compute_indicators(df)
        history = history_to_dict(df)

        # Get custom thresholds for this ticker (if any)
        custom = get_thresholds(ticker)

        signal = generate_signal(indicators, quote_data, custom_thresholds=custom)
        position = calculate_position(
            account_size=account_size,
            entry_price=signal["entry_price"],
            stop_loss=signal["stop_loss"],
            risk_pct=risk_pct / 100,
        )

        # Support/resistance levels
        sr_data = detect_support_resistance(df)

        # Fibonacci retracement levels
        fib_data = calculate_fibonacci_levels(df)

        # Multi-timeframe confirmation
        mtf_data = get_multi_timeframe_confirmation(ticker)

        # Apply MTF alignment bonus OR conflict cap
        if signal["direction"] != "HOLD":
            if mtf_data.get("conflict"):
                # 1D and 1W disagree — cap confidence at 50% (unreliable)
                signal["confidence"] = min(signal["confidence"], 50)
                mtf_data["warning"] = "Conflicting timeframes: confidence capped at 50%"
            elif mtf_data.get("aligned"):
                signal["confidence"] = min(100, signal["confidence"] + mtf_data["alignment_bonus"])

        # Earnings proximity penalty — risky within 3 days of earnings
        earnings_warning = None
        try:
            earnings_info = get_earnings(ticker)
            days_until = earnings_info.days_until
            if days_until is not None and 0 <= days_until <= 3:
                signal["confidence"] = max(0, signal["confidence"] - 20)
                earnings_warning = f"Earnings in {days_until} day(s) — high risk, confidence reduced"
        except Exception:
            pass

        # Get news for context
        news_data = get_news_sentiment(ticker)
        news_summary = news_data.get("raw_analysis", "")

        # Get AI analysis
        ai_result = analyze_stock(
            ticker=ticker,
            price=quote_data["price"],
            indicators=indicators,
            news_summary=news_summary,
        )

        ai_analysis = None
        if ai_result:
            ai_analysis = AIAnalysis(
                narrative=ai_result.get("analysis", ""),
                conviction=ai_result.get("conviction", 5),
                catalysts=ai_result.get("catalysts", []),
                risks=ai_result.get("risks", []),
                timeframe=ai_result.get("timeframe", ""),
            )

        # Log signal to history
        try:
            log_signal(
                ticker=ticker.upper(),
                direction=signal["direction"],
                confidence=signal["confidence"],
                entry_price=signal["entry_price"],
                stop_loss=signal["stop_loss"],
                take_profit_1=signal["take_profit_1"],
                indicators_snapshot={
                    "rsi": indicators.get("rsi"),
                    "macd_histogram": indicators.get("macd_histogram"),
                    "adx": indicators.get("adx"),
                    "stoch_rsi_k": indicators.get("stoch_rsi_k"),
                },
            )
        except Exception:
            pass  # Don't fail the signal if logging fails

        # Attach earnings warning to mtf_data for frontend display
        if earnings_warning:
            mtf_data["earnings_warning"] = earnings_warning

        return SignalResponse(
            ticker=ticker.upper(),
            quote=StockQuote(**quote_data),
            indicators=IndicatorValues(**indicators),
            signal=SignalDirection(**signal),
            position=PositionSize(**position),
            ai_analysis=ai_analysis,
            ohlcv=OHLCV(**history),
            timestamps=history["timestamp"][-60:],
            support_resistance=sr_data,
            fibonacci=fib_data,
            multi_timeframe=mtf_data,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Signal generation failed for {ticker}: {str(e)}")
