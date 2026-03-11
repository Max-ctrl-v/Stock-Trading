def calculate_position(
    account_size: float,
    entry_price: float,
    stop_loss: float,
    risk_pct: float = 0.025,
) -> dict:
    risk_amount = account_size * risk_pct
    risk_per_share = abs(entry_price - stop_loss)

    if risk_per_share == 0:
        risk_per_share = entry_price * 0.02  # fallback: 2% of price

    shares = int(risk_amount / risk_per_share)
    if shares < 1:
        shares = 1

    dollar_amount = shares * entry_price

    return {
        "shares": shares,
        "dollar_amount": round(dollar_amount, 2),
        "risk_amount": round(risk_amount, 2),
        "risk_pct": round(risk_pct * 100, 2),
    }
