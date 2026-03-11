import yfinance as yf
import pandas as pd
import ta
from pydantic import BaseModel


class RiskRewardZone(BaseModel):
    label: str
    price_low: float
    price_high: float
    color: str


class RiskRewardResult(BaseModel):
    ticker: str
    current_price: float
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float | None
    shares: float
    risk_amount: float
    reward_amount_1: float
    reward_amount_2: float | None
    risk_reward_ratio_1: float
    risk_reward_ratio_2: float | None
    loss_pct: float
    gain_pct_1: float
    gain_pct_2: float | None
    price_to_stop_pct: float
    price_to_target_pct: float
    zones: list[RiskRewardZone]


def _get_current_price(ticker: str) -> float:
    """Fetch current price from yfinance."""
    t = yf.Ticker(ticker)
    info = t.info
    price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
    if price is None:
        hist = t.history(period="5d")
        if hist.empty:
            raise ValueError(f"Cannot fetch price for {ticker}")
        price = float(hist["Close"].iloc[-1])
    return round(float(price), 2)


def calculate_risk_reward(
    ticker: str,
    entry_price: float,
    stop_loss: float,
    target_1: float,
    target_2: float | None,
    shares: float,
) -> RiskRewardResult:
    """Calculate risk/reward metrics and chart zones."""
    current_price = _get_current_price(ticker)

    risk_per_share = abs(entry_price - stop_loss)
    reward_per_share_1 = abs(target_1 - entry_price)

    risk_amount = round(risk_per_share * shares, 2)
    reward_amount_1 = round(reward_per_share_1 * shares, 2)

    rr_ratio_1 = round(reward_per_share_1 / risk_per_share, 2) if risk_per_share > 0 else 0.0
    loss_pct = round((risk_per_share / entry_price) * 100, 2) if entry_price > 0 else 0.0
    gain_pct_1 = round((reward_per_share_1 / entry_price) * 100, 2) if entry_price > 0 else 0.0

    price_to_stop_pct = round(((current_price - stop_loss) / current_price) * 100, 2) if current_price > 0 else 0.0
    price_to_target_pct = round(((target_1 - current_price) / current_price) * 100, 2) if current_price > 0 else 0.0

    # Target 2 calculations
    reward_amount_2 = None
    rr_ratio_2 = None
    gain_pct_2 = None
    if target_2 is not None:
        reward_per_share_2 = abs(target_2 - entry_price)
        reward_amount_2 = round(reward_per_share_2 * shares, 2)
        rr_ratio_2 = round(reward_per_share_2 / risk_per_share, 2) if risk_per_share > 0 else 0.0
        gain_pct_2 = round((reward_per_share_2 / entry_price) * 100, 2) if entry_price > 0 else 0.0

    # Build zones for chart overlay
    zones: list[RiskRewardZone] = []

    # Determine direction: long or short
    is_long = entry_price > stop_loss

    if is_long:
        zones.append(RiskRewardZone(
            label="Risk Zone",
            price_low=stop_loss,
            price_high=entry_price,
            color="#ef4444",  # red
        ))
        zones.append(RiskRewardZone(
            label="Target 1 Zone",
            price_low=entry_price,
            price_high=target_1,
            color="#22c55e",  # green
        ))
        if target_2 is not None:
            zones.append(RiskRewardZone(
                label="Target 2 Zone",
                price_low=target_1,
                price_high=target_2,
                color="#16a34a",  # darker green
            ))
    else:
        zones.append(RiskRewardZone(
            label="Risk Zone",
            price_low=entry_price,
            price_high=stop_loss,
            color="#ef4444",
        ))
        zones.append(RiskRewardZone(
            label="Target 1 Zone",
            price_low=target_1,
            price_high=entry_price,
            color="#22c55e",
        ))
        if target_2 is not None:
            zones.append(RiskRewardZone(
                label="Target 2 Zone",
                price_low=target_2,
                price_high=target_1,
                color="#16a34a",
            ))

    return RiskRewardResult(
        ticker=ticker.upper(),
        current_price=current_price,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
        shares=shares,
        risk_amount=risk_amount,
        reward_amount_1=reward_amount_1,
        reward_amount_2=reward_amount_2,
        risk_reward_ratio_1=rr_ratio_1,
        risk_reward_ratio_2=rr_ratio_2,
        loss_pct=loss_pct,
        gain_pct_1=gain_pct_1,
        gain_pct_2=gain_pct_2,
        price_to_stop_pct=price_to_stop_pct,
        price_to_target_pct=price_to_target_pct,
        zones=zones,
    )


def auto_risk_reward(ticker: str) -> RiskRewardResult:
    """Auto-calculate risk/reward using current price and ATR."""
    t = yf.Ticker(ticker)
    hist = t.history(period="3mo")
    if hist.empty or len(hist) < 20:
        raise ValueError(f"Insufficient historical data for {ticker}")

    current_price = round(float(hist["Close"].iloc[-1]), 2)

    atr_series = ta.volatility.AverageTrueRange(
        hist["High"], hist["Low"], hist["Close"], window=14
    ).average_true_range()
    atr = float(atr_series.dropna().iloc[-1])

    entry_price = current_price
    stop_loss = round(current_price - 2 * atr, 2)
    target_1 = round(current_price + 2 * atr, 2)
    target_2 = round(current_price + 3 * atr, 2)

    # Default to 100 shares for auto calculation
    shares = 100.0

    return calculate_risk_reward(
        ticker=ticker,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
        shares=shares,
    )
