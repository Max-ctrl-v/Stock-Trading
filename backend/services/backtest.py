import pandas as pd
from backend.services.stock_data import get_history
from backend.services.technical import compute_indicators
from backend.services.signals import generate_signal


def run_backtest(
    ticker: str,
    period: str = "1y",
    slippage: float = 0.001,   # 0.1% slippage per fill
    commission: float = 1.0,   # $1 per trade commission
) -> dict:
    """Walk-forward backtest using the signal engine with realistic execution costs."""
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
            "slippage_pct": slippage * 100,
            "commission_per_trade": commission,
        }

    trades = []
    equity = [100.0]  # Start with 100 base
    position = None  # {"direction", "entry_price", "entry_date", "stop", "target"}

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
                # Apply slippage on exit
                if position["direction"] == "BUY":
                    exit_fill = close_price * (1 - slippage)
                    pnl_pct = (exit_fill - position["entry_price"]) / position["entry_price"] * 100
                else:
                    exit_fill = close_price * (1 + slippage)
                    pnl_pct = (position["entry_price"] - exit_fill) / position["entry_price"] * 100

                # Commission cost as % of equity
                commission_pct = (commission * 2) / equity[-1]  # entry + exit commission
                pnl_pct -= commission_pct

                trades.append({
                    "entry_date": position["entry_date"],
                    "exit_date": date_str,
                    "direction": position["direction"],
                    "entry_price": round(position["entry_price"], 2),
                    "exit_price": round(exit_fill, 2),
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
                indicators = compute_indicators(window)
                quote = {"price": close_price, "volume": int(window["Volume"].iloc[-1])}
                signal = generate_signal(indicators, quote)

                if signal["direction"] in ("BUY", "SELL"):
                    # Apply slippage on entry
                    if signal["direction"] == "BUY":
                        entry_fill = close_price * (1 + slippage)
                    else:
                        entry_fill = close_price * (1 - slippage)

                    position = {
                        "direction": signal["direction"],
                        "entry_price": entry_fill,
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
            exit_fill = last_price * (1 - slippage)
            pnl_pct = (exit_fill - position["entry_price"]) / position["entry_price"] * 100
        else:
            exit_fill = last_price * (1 + slippage)
            pnl_pct = (position["entry_price"] - exit_fill) / position["entry_price"] * 100
        commission_pct = (commission * 2) / equity[-1]
        pnl_pct -= commission_pct
        trades.append({
            "entry_date": position["entry_date"],
            "exit_date": last_date,
            "direction": position["direction"],
            "entry_price": round(position["entry_price"], 2),
            "exit_price": round(exit_fill, 2),
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
            "slippage_pct": slippage * 100, "commission_per_trade": commission,
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
        "slippage_pct": slippage * 100,
        "commission_per_trade": commission,
    }
