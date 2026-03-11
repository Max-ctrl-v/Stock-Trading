from backend.config import RSI_OVERSOLD, RSI_OVERBOUGHT
from backend.services.stock_data import get_history
from backend.services.technical import compute_indicators


def generate_signal(indicators: dict, quote: dict, custom_thresholds: dict | None = None) -> dict:
    price = quote.get("price", 0)
    if price == 0:
        return _neutral_signal(price)

    # Use custom thresholds if provided, otherwise defaults
    rsi_oversold = RSI_OVERSOLD
    rsi_overbought = RSI_OVERBOUGHT
    score_threshold = 10
    if custom_thresholds and custom_thresholds.get("use_custom"):
        rsi_oversold = custom_thresholds.get("rsi_oversold", RSI_OVERSOLD)
        rsi_overbought = custom_thresholds.get("rsi_overbought", RSI_OVERBOUGHT)
        score_threshold = custom_thresholds.get("signal_score_threshold", 10)

    score = 0  # positive = bullish, negative = bearish
    weights = []

    # RSI signal (weight: 25)
    rsi = indicators.get("rsi")
    if rsi is not None:
        if rsi < rsi_oversold:
            s = 25 * (rsi_oversold - rsi) / rsi_oversold
            weights.append(("RSI oversold", s))
            score += s
        elif rsi > rsi_overbought:
            s = -25 * (rsi - rsi_overbought) / (100 - rsi_overbought)
            weights.append(("RSI overbought", s))
            score += s

    # MACD signal (weight: 25)
    macd_hist = indicators.get("macd_histogram")
    macd_line = indicators.get("macd_line")
    macd_signal = indicators.get("macd_signal")
    if macd_line is not None and macd_signal is not None:
        if macd_line > macd_signal:
            s = min(15, abs(macd_line - macd_signal) / price * 5000)
            weights.append(("MACD bullish crossover", s))
            score += s
        else:
            s = -min(15, abs(macd_line - macd_signal) / price * 5000)
            weights.append(("MACD bearish crossover", s))
            score += s
    if macd_hist is not None:
        if macd_hist > 0:
            score += 10
            weights.append(("MACD histogram positive", 10))
        else:
            score -= 10
            weights.append(("MACD histogram negative", -10))

    # Bollinger Bands signal (weight: 20)
    bb_lower = indicators.get("bb_lower")
    bb_upper = indicators.get("bb_upper")
    bb_middle = indicators.get("bb_middle")
    if bb_lower is not None and bb_upper is not None:
        if price <= bb_lower:
            score += 20
            weights.append(("Price at lower BB", 20))
        elif price >= bb_upper:
            score -= 20
            weights.append(("Price at upper BB", -20))
        elif bb_middle is not None:
            if price > bb_middle:
                score += 5
            else:
                score -= 5

    # Moving average trend (weight: 20)
    sma_20 = indicators.get("sma_20")
    sma_50 = indicators.get("sma_50")
    ema_12 = indicators.get("ema_12")
    ema_26 = indicators.get("ema_26")
    if sma_20 is not None and sma_50 is not None:
        if sma_20 > sma_50:
            score += 10
            weights.append(("SMA 20 > 50 (uptrend)", 10))
        else:
            score -= 10
            weights.append(("SMA 20 < 50 (downtrend)", -10))
    if ema_12 is not None and ema_26 is not None:
        if ema_12 > ema_26:
            score += 10
            weights.append(("EMA 12 > 26 (bullish)", 10))
        else:
            score -= 10
            weights.append(("EMA 12 < 26 (bearish)", -10))

    # Volume confirmation (weight: 10)
    vol_sma = indicators.get("volume_sma")
    volume = quote.get("volume", 0)
    if vol_sma and vol_sma > 0 and volume > 0:
        if volume > vol_sma * 1.5:
            bonus = 10 if score > 0 else -10  # confirms the direction
            score += bonus
            weights.append(("High volume confirmation", bonus))

    # --- NEW INDICATORS ---

    # Stochastic RSI signal (weight: 15)
    stoch_k = indicators.get("stoch_rsi_k")
    stoch_d = indicators.get("stoch_rsi_d")
    if stoch_k is not None and stoch_d is not None:
        if stoch_k < 20 and stoch_d < 20:
            s = 15
            weights.append(("StochRSI oversold", s))
            score += s
        elif stoch_k > 80 and stoch_d > 80:
            s = -15
            weights.append(("StochRSI overbought", s))
            score += s
        elif stoch_k > stoch_d:
            s = 5
            weights.append(("StochRSI K > D (bullish)", s))
            score += s
        elif stoch_k < stoch_d:
            s = -5
            weights.append(("StochRSI K < D (bearish)", s))
            score += s

    # OBV trend (weight: 10)
    obv_history = indicators.get("obv_history", [])
    if len(obv_history) >= 10:
        obv_recent = obv_history[-5:]
        obv_prior = obv_history[-10:-5]
        obv_recent_avg = sum(obv_recent) / len(obv_recent)
        obv_prior_avg = sum(obv_prior) / len(obv_prior)
        if obv_prior_avg != 0:
            obv_change = (obv_recent_avg - obv_prior_avg) / abs(obv_prior_avg)
            if obv_change > 0.05:
                s = 10
                weights.append(("OBV rising (accumulation)", s))
                score += s
            elif obv_change < -0.05:
                s = -10
                weights.append(("OBV falling (distribution)", s))
                score += s

    # ADX trend strength (weight: 15)
    adx = indicators.get("adx")
    adx_pos = indicators.get("adx_pos")
    adx_neg = indicators.get("adx_neg")
    if adx is not None and adx_pos is not None and adx_neg is not None:
        if adx > 25:  # strong trend
            if adx_pos > adx_neg:
                s = 15
                weights.append(("ADX strong uptrend", s))
                score += s
            else:
                s = -15
                weights.append(("ADX strong downtrend", s))
                score += s
        elif adx < 20:
            weights.append(("ADX weak trend (ranging)", 0))

    # VWAP signal (weight: 10)
    vwap = indicators.get("vwap")
    if vwap is not None and price > 0:
        if price > vwap * 1.01:
            s = 10
            weights.append(("Price above VWAP (bullish)", s))
            score += s
        elif price < vwap * 0.99:
            s = -10
            weights.append(("Price below VWAP (bearish)", s))
            score += s

    # Ichimoku Cloud signal (weight: 15)
    ichi_conv = indicators.get("ichimoku_conv")
    ichi_base = indicators.get("ichimoku_base")
    ichi_a = indicators.get("ichimoku_a")
    ichi_b = indicators.get("ichimoku_b")
    if all(v is not None for v in [ichi_conv, ichi_base, ichi_a, ichi_b]):
        cloud_top = max(ichi_a, ichi_b)
        cloud_bottom = min(ichi_a, ichi_b)
        if price > cloud_top:
            s = 10
            weights.append(("Price above Ichimoku cloud", s))
            score += s
        elif price < cloud_bottom:
            s = -10
            weights.append(("Price below Ichimoku cloud", s))
            score += s
        if ichi_conv > ichi_base:
            s = 5
            weights.append(("Ichimoku TK cross bullish", s))
            score += s
        elif ichi_conv < ichi_base:
            s = -5
            weights.append(("Ichimoku TK cross bearish", s))
            score += s

    # Determine direction and confidence
    confidence = min(100, abs(score))
    atr = indicators.get("atr")
    if atr is None or atr == 0:
        atr = price * 0.02

    if score > score_threshold:
        direction = "BUY"
        stop_loss = round(price - 2 * atr, 2)
        tp1 = round(price + 2 * atr, 2)
        tp2 = round(price + 4 * atr, 2)
    elif score < -score_threshold:
        direction = "SELL"
        stop_loss = round(price + 2 * atr, 2)
        tp1 = round(price - 2 * atr, 2)
        tp2 = round(price - 4 * atr, 2)
    else:
        return _neutral_signal(price)

    risk = abs(price - stop_loss)
    reward = abs(tp1 - price)
    rr = round(reward / risk, 2) if risk > 0 else 0

    return {
        "direction": direction,
        "confidence": round(confidence, 1),
        "entry_price": round(price, 2),
        "stop_loss": stop_loss,
        "take_profit_1": tp1,
        "take_profit_2": tp2,
        "risk_reward": rr,
    }


def get_multi_timeframe_confirmation(ticker: str) -> dict:
    """Check if daily and weekly signals align for stronger confirmation."""
    result = {
        "daily": None,
        "weekly": None,
        "aligned": False,
        "alignment_bonus": 0.0,
    }

    try:
        # Daily signal
        df_daily = get_history(ticker, period="6mo", interval="1d")
        if not df_daily.empty:
            ind_daily = compute_indicators(df_daily)
            daily_score = _quick_score(ind_daily)
            daily_dir = "BUY" if daily_score > 10 else ("SELL" if daily_score < -10 else "HOLD")
            result["daily"] = {
                "timeframe": "1D",
                "direction": daily_dir,
                "confidence": min(100, abs(daily_score)),
                "rsi": ind_daily.get("rsi"),
            }
    except Exception:
        pass

    try:
        # Weekly signal
        df_weekly = get_history(ticker, period="1y", interval="1wk")
        if not df_weekly.empty:
            ind_weekly = compute_indicators(df_weekly)
            weekly_score = _quick_score(ind_weekly)
            weekly_dir = "BUY" if weekly_score > 10 else ("SELL" if weekly_score < -10 else "HOLD")
            result["weekly"] = {
                "timeframe": "1W",
                "direction": weekly_dir,
                "confidence": min(100, abs(weekly_score)),
                "rsi": ind_weekly.get("rsi"),
            }
    except Exception:
        pass

    # Check alignment
    if result["daily"] and result["weekly"]:
        d_dir = result["daily"]["direction"]
        w_dir = result["weekly"]["direction"]
        if d_dir == w_dir and d_dir != "HOLD":
            result["aligned"] = True
            result["alignment_bonus"] = 15.0
        elif d_dir != "HOLD" and w_dir != "HOLD" and d_dir != w_dir:
            result["alignment_bonus"] = -10.0  # conflicting signals

    return result


def _quick_score(indicators: dict) -> float:
    """Lightweight scoring for multi-timeframe checks (RSI + MACD + MAs only)."""
    score = 0.0
    rsi = indicators.get("rsi")
    if rsi is not None:
        if rsi < RSI_OVERSOLD:
            score += 20
        elif rsi > RSI_OVERBOUGHT:
            score -= 20

    macd_line = indicators.get("macd_line")
    macd_signal = indicators.get("macd_signal")
    if macd_line is not None and macd_signal is not None:
        if macd_line > macd_signal:
            score += 15
        else:
            score -= 15

    sma_20 = indicators.get("sma_20")
    sma_50 = indicators.get("sma_50")
    if sma_20 is not None and sma_50 is not None:
        if sma_20 > sma_50:
            score += 10
        else:
            score -= 10

    return score


def _neutral_signal(price: float) -> dict:
    return {
        "direction": "HOLD",
        "confidence": 0,
        "entry_price": round(price, 2),
        "stop_loss": round(price * 0.98, 2),
        "take_profit_1": round(price * 1.02, 2),
        "take_profit_2": round(price * 1.04, 2),
        "risk_reward": 1.0,
    }
