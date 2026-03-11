import yfinance as yf
import pandas as pd
from ta.volatility import AverageTrueRange
from pydantic import BaseModel


class TrailingStopResult(BaseModel):
    ticker: str
    current_price: float
    entry_price: float
    trail_type: str
    trail_value: float
    stop_level: float
    distance_pct: float


class StopLevelSet(BaseModel):
    method: str
    label: str
    stop_level: float
    distance_from_current: float
    distance_pct: float


def _get_price_and_history(ticker: str, period: str = "3mo") -> tuple[float, pd.DataFrame]:
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)
    if hist.empty:
        raise ValueError(f"Cannot get data for {ticker}")
    current_price = float(hist["Close"].iloc[-1])
    return round(current_price, 2), hist


def _calc_atr(hist: pd.DataFrame, window: int = 14) -> float:
    atr_indicator = AverageTrueRange(
        high=hist["High"], low=hist["Low"], close=hist["Close"], window=window
    )
    atr_values = atr_indicator.average_true_range()
    return float(atr_values.iloc[-1])


def calculate_trailing_stop(
    ticker: str, entry_price: float, trail_type: str, trail_value: float
) -> dict:
    ticker = ticker.upper()
    trail_type = trail_type.lower()

    current_price, hist = _get_price_and_history(ticker)

    # Highest price since entry (approximated using recent history)
    highest_price = max(current_price, entry_price)
    # Use the max close from history as a proxy for the trailing high
    hist_max = float(hist["Close"].max())
    highest_price = max(highest_price, hist_max)

    if trail_type == "percentage":
        stop_level = round(highest_price * (1 - trail_value / 100), 2)
    elif trail_type == "atr":
        atr = _calc_atr(hist)
        stop_level = round(highest_price - (atr * trail_value), 2)
    elif trail_type == "chandelier":
        atr = _calc_atr(hist, window=22)
        # Chandelier exit: highest high - ATR * multiplier
        highest_high = float(hist["High"].max())
        stop_level = round(highest_high - (atr * trail_value), 2)
    else:
        raise ValueError(f"Unknown trail_type: {trail_type}. Use percentage, atr, or chandelier")

    distance_pct = round((current_price - stop_level) / current_price * 100, 2)

    return {
        "ticker": ticker,
        "current_price": current_price,
        "entry_price": entry_price,
        "trail_type": trail_type,
        "trail_value": trail_value,
        "stop_level": stop_level,
        "distance_pct": distance_pct,
    }


def get_all_stop_levels(ticker: str) -> dict:
    ticker = ticker.upper()
    current_price, hist = _get_price_and_history(ticker)
    atr = _calc_atr(hist)
    highest_high = float(hist["High"].max())
    hist_max = float(hist["Close"].max())

    levels: list[dict] = []

    # Percentage-based stops
    for pct in [2.0, 3.0, 5.0]:
        stop = round(hist_max * (1 - pct / 100), 2)
        levels.append({
            "method": "percentage",
            "label": f"{pct}% trailing",
            "stop_level": stop,
            "distance_from_current": round(current_price - stop, 2),
            "distance_pct": round((current_price - stop) / current_price * 100, 2),
        })

    # ATR-based stops
    for mult in [1.5, 2.0, 3.0]:
        stop = round(hist_max - (atr * mult), 2)
        levels.append({
            "method": "atr",
            "label": f"{mult}x ATR",
            "stop_level": stop,
            "distance_from_current": round(current_price - stop, 2),
            "distance_pct": round((current_price - stop) / current_price * 100, 2),
        })

    return {
        "ticker": ticker,
        "current_price": current_price,
        "atr_14": round(atr, 2),
        "levels": levels,
    }
