import pandas as pd
import numpy as np
from typing import Optional


def detect_support_resistance(df: pd.DataFrame, window: int = 20) -> dict:
    """Detect support and resistance levels from price history using pivot points.

    Args:
        df: DataFrame with High, Low, Close columns (standard yfinance format).
        window: Rolling window size for finding local extrema.

    Returns:
        Dict with support_levels, resistance_levels, nearest_support, nearest_resistance.
    """
    if df is None or len(df) < window * 2 + 1:
        return {
            "support_levels": [],
            "resistance_levels": [],
            "nearest_support": None,
            "nearest_resistance": None,
        }

    highs: np.ndarray = df["High"].values
    lows: np.ndarray = df["Low"].values
    current_price: float = float(df["Close"].iloc[-1])

    # Find pivot highs (resistance candidates)
    pivot_highs: list[float] = []
    for i in range(window, len(highs) - window):
        if highs[i] == np.max(highs[i - window : i + window + 1]):
            pivot_highs.append(float(highs[i]))

    # Find pivot lows (support candidates)
    pivot_lows: list[float] = []
    for i in range(window, len(lows) - window):
        if lows[i] == np.min(lows[i - window : i + window + 1]):
            pivot_lows.append(float(lows[i]))

    support_levels = _cluster_levels(pivot_lows, max_levels=5, threshold_pct=1.5)
    resistance_levels = _cluster_levels(pivot_highs, max_levels=5, threshold_pct=1.5)

    # Nearest support below current price
    supports_below = [s for s in support_levels if s < current_price]
    nearest_support: Optional[float] = max(supports_below) if supports_below else None

    # Nearest resistance above current price
    resistances_above = [r for r in resistance_levels if r > current_price]
    nearest_resistance: Optional[float] = min(resistances_above) if resistances_above else None

    return {
        "support_levels": sorted(support_levels),
        "resistance_levels": sorted(resistance_levels),
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
    }


def _cluster_levels(
    prices: list[float], max_levels: int = 5, threshold_pct: float = 1.5
) -> list[float]:
    """Cluster nearby price levels and return the strongest (most touches).

    Args:
        prices: Raw pivot prices.
        max_levels: Maximum number of levels to return.
        threshold_pct: Percentage threshold for grouping nearby levels.

    Returns:
        List of clustered price levels sorted by touch count (descending), then by price.
    """
    if not prices:
        return []

    sorted_prices = sorted(prices)
    clusters: list[list[float]] = []
    current_cluster: list[float] = [sorted_prices[0]]

    for price in sorted_prices[1:]:
        cluster_mean = np.mean(current_cluster)
        if abs(price - cluster_mean) / cluster_mean * 100 <= threshold_pct:
            current_cluster.append(price)
        else:
            clusters.append(current_cluster)
            current_cluster = [price]
    clusters.append(current_cluster)

    # Sort clusters by number of touches (descending), take top N
    clusters.sort(key=lambda c: len(c), reverse=True)
    top_clusters = clusters[:max_levels]

    # Return the mean price of each cluster
    levels = [float(np.mean(c)) for c in top_clusters]
    return sorted(levels)


def calculate_fibonacci_levels(df: pd.DataFrame) -> dict:
    """Calculate Fibonacci retracement levels from recent swing high/low.

    Args:
        df: DataFrame with High, Low, Close columns (standard yfinance format).

    Returns:
        Dict with swing_high, swing_low, levels, and trend.
    """
    if df is None or len(df) < 2:
        return {
            "swing_high": 0.0,
            "swing_low": 0.0,
            "levels": [],
            "trend": "unknown",
        }

    # Use last 120 bars or all available
    recent = df.tail(120)

    swing_high: float = float(recent["High"].max())
    swing_low: float = float(recent["Low"].min())
    current_price: float = float(df["Close"].iloc[-1])

    diff = swing_high - swing_low

    ratios = [
        (0.0, "0%"),
        (0.236, "23.6%"),
        (0.382, "38.2%"),
        (0.5, "50%"),
        (0.618, "61.8%"),
        (0.786, "78.6%"),
        (1.0, "100%"),
    ]

    levels: list[dict] = []
    fib_50_price = swing_high - diff * 0.5

    for ratio, label in ratios:
        # Retracement from high: price = swing_high - diff * ratio
        price = round(swing_high - diff * ratio, 2)
        levels.append({
            "ratio": ratio,
            "label": label,
            "price": price,
        })

    trend: str = "uptrend" if current_price > fib_50_price else "downtrend"

    return {
        "swing_high": round(swing_high, 2),
        "swing_low": round(swing_low, 2),
        "levels": levels,
        "trend": trend,
    }
