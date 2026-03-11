import yfinance as yf
from pydantic import BaseModel


class ScalingLevel(BaseModel):
    level: int
    price: float
    shares: int
    cost: float
    cumulative_shares: int
    cumulative_cost: float
    new_avg_price: float
    total_exposure_pct: float
    risk_at_level: float


class ScalingResult(BaseModel):
    ticker: str
    current_price: float
    initial_entry: float
    initial_shares: int
    account_size: float
    max_risk_pct: float
    levels: list[ScalingLevel]
    total_shares: int
    total_cost: float
    weighted_avg_price: float
    total_exposure_pct: float


def _get_live_price(ticker: str) -> float:
    stock = yf.Ticker(ticker)
    info = stock.fast_info
    price = getattr(info, "last_price", None)
    if price is None:
        hist = stock.history(period="1d")
        if hist.empty:
            raise ValueError(f"Cannot get price for {ticker}")
        price = float(hist["Close"].iloc[-1])
    return round(float(price), 2)


def calculate_scaling(
    ticker: str,
    initial_entry: float,
    initial_shares: int,
    account_size: float,
    max_risk_pct: float,
    scaling_levels: list[float],
    use_percentage: bool = False,
) -> dict:
    """
    Calculate position scaling levels.

    scaling_levels: list of price levels to add at, or percentage increments above entry.
    use_percentage: if True, scaling_levels are treated as % above initial_entry.
    """
    ticker = ticker.upper()
    current_price = _get_live_price(ticker)
    max_risk_amount = account_size * (max_risk_pct / 100)

    # Convert percentage increments to absolute prices if needed
    if use_percentage:
        price_levels = [round(initial_entry * (1 + pct / 100), 2) for pct in scaling_levels]
    else:
        price_levels = [round(p, 2) for p in scaling_levels]

    levels: list[dict] = []
    cumulative_shares = initial_shares
    cumulative_cost = initial_entry * initial_shares

    # Level 0: initial position
    levels.append({
        "level": 0,
        "price": initial_entry,
        "shares": initial_shares,
        "cost": round(initial_entry * initial_shares, 2),
        "cumulative_shares": cumulative_shares,
        "cumulative_cost": round(cumulative_cost, 2),
        "new_avg_price": round(cumulative_cost / cumulative_shares, 2),
        "total_exposure_pct": round((cumulative_cost / account_size) * 100, 2),
        "risk_at_level": 0.0,
    })

    for i, price in enumerate(price_levels, start=1):
        # Calculate max shares we can add without exceeding risk
        remaining_risk = max_risk_amount - (cumulative_cost / account_size * 100)
        risk_per_share_at_level = price - initial_entry  # profit cushion per share

        # Scale shares: each subsequent add is smaller (pyramid up)
        # Use decreasing allocation: initial / level_number
        target_shares = max(1, initial_shares // i)

        add_cost = price * target_shares
        cumulative_shares += target_shares
        cumulative_cost += add_cost
        new_avg = cumulative_cost / cumulative_shares
        exposure_pct = (cumulative_cost / account_size) * 100

        # Risk at this level: if price drops to initial entry, loss from this add
        risk_at = round(abs(price - initial_entry) * target_shares, 2)

        levels.append({
            "level": i,
            "price": price,
            "shares": target_shares,
            "cost": round(add_cost, 2),
            "cumulative_shares": cumulative_shares,
            "cumulative_cost": round(cumulative_cost, 2),
            "new_avg_price": round(new_avg, 2),
            "total_exposure_pct": round(exposure_pct, 2),
            "risk_at_level": risk_at,
        })

    return {
        "ticker": ticker,
        "current_price": current_price,
        "initial_entry": initial_entry,
        "initial_shares": initial_shares,
        "account_size": account_size,
        "max_risk_pct": max_risk_pct,
        "levels": levels,
        "total_shares": cumulative_shares,
        "total_cost": round(cumulative_cost, 2),
        "weighted_avg_price": round(cumulative_cost / cumulative_shares, 2),
        "total_exposure_pct": round((cumulative_cost / account_size) * 100, 2),
    }
