import pandas as pd
from backend.services.stock_data import get_history
from backend.services.technical import compute_indicators
from backend.services.signals import generate_signal


def run_backtest(ticker: str, period: str = "1y") -> dict:
    """Walk-forward backtest using the signal engine."""
    df = get_history(ticker, period=period, interval="1d")

    if df.empty or len(df) < 60:
        return {
            "ticker": ticker.upper(),
            "period": period,
            "total_trades": 0,
            "win_rate": 0,
            "total_return_pct": 0,
            "max_drawdown_pct": 0,
            "avg_trade_pct": 0,
            "trades": [],
            "equity_curve": [],
        }

    trades = []
    equity = [100.0]  # Start with 100 base
    position = None  # {"direction": "BUY"/"SELL", "entry_price": float, "entry_date": str, "stop": float, "target": float}

    # Walk forward from day 60 (need history for indicators)
    for i in range(60, len(df)):
        window = df.iloc[:i+1]
        close_price = float(window["Close"].iloc[-1])
        date_str = window.index[-1].strftime("%Y-%m-%d")

        # Check if we have an open position
        if position:
            exit_reason = None

            if position["direction"] == "BUY":
                if close_price <= position["stop"]:
                    exit_reason = "stop_hit"
                elif close_price >= position["target"]:
                    exit_reason = "target_hit"
            else:  # SELL
                if close_price >= position["stop"]:
                    exit_reason = "stop_hit"
                elif close_price <= position["target"]:
                    exit_reason = "target_hit"

            if exit_reason:
                if position["direction"] == "BUY":
                    pnl_pct = (close_price - position["entry_price"]) / position["entry_price"] * 100
                else:
                    pnl_pct = (position["entry_price"] - close_price) / position["entry_price"] * 100

                trades.append({
                    "entry_date": position["entry_date"],
                    "exit_date": date_str,
                    "direction": position["direction"],
                    "entry_price": round(position["entry_price"], 2),
                    "exit_price": round(close_price, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "reason": exit_reason,
                })

                equity.append(round(equity[-1] * (1 + pnl_pct / 100), 2))
                position = None
                continue

        # Only check for new signals every 3 days to avoid overtrading
        if (i - 60) % 3 != 0:
            continue

        if position is None:
            try:
                # Use a subset for indicator computation
                indicators = compute_indicators(window)
                quote = {"price": close_price, "volume": int(window["Volume"].iloc[-1])}
                signal = generate_signal(indicators, quote)

                if signal["direction"] in ("BUY", "SELL"):
                    position = {
                        "direction": signal["direction"],
                        "entry_price": close_price,
                        "entry_date": date_str,
                        "stop": signal["stop_loss"],
                        "target": signal["take_profit_1"],
                    }
            except Exception:
                pass

    # Close any remaining position at last price
    if position:
        last_price = float(df["Close"].iloc[-1])
        last_date = df.index[-1].strftime("%Y-%m-%d")
        if position["direction"] == "BUY":
            pnl_pct = (last_price - position["entry_price"]) / position["entry_price"] * 100
        else:
            pnl_pct = (position["entry_price"] - last_price) / position["entry_price"] * 100
        trades.append({
            "entry_date": position["entry_date"],
            "exit_date": last_date,
            "direction": position["direction"],
            "entry_price": round(position["entry_price"], 2),
            "exit_price": round(last_price, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": "end_of_period",
        })
        equity.append(round(equity[-1] * (1 + pnl_pct / 100), 2))

    # Compute stats
    if not trades:
        return {
            "ticker": ticker.upper(), "period": period,
            "total_trades": 0, "win_rate": 0, "total_return_pct": 0,
            "max_drawdown_pct": 0, "avg_trade_pct": 0, "trades": [], "equity_curve": equity,
        }

    wins = [t for t in trades if t["pnl_pct"] > 0]
    pnl_pcts = [t["pnl_pct"] for t in trades]

    # Max drawdown from equity curve
    peak = equity[0]
    max_dd = 0
    for val in equity:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100
        if dd > max_dd:
            max_dd = dd

    total_return = (equity[-1] - equity[0]) / equity[0] * 100

    return {
        "ticker": ticker.upper(),
        "period": period,
        "total_trades": len(trades),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "total_return_pct": round(total_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "avg_trade_pct": round(sum(pnl_pcts) / len(pnl_pcts), 2),
        "trades": trades,
        "equity_curve": equity,
    }
