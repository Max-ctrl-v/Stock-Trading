import json
import numpy as np
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from backend.services.stock_data import get_quote, get_history
from backend.services.portfolio import get_positions

JOURNAL_FILE = Path(__file__).parent.parent.parent / "data" / "journal.json"


def _load_journal() -> list[dict]:
    """Load closed trades from journal.json."""
    try:
        if JOURNAL_FILE.exists():
            with open(JOURNAL_FILE, "r") as f:
                data = json.load(f)
            return data.get("trades", [])
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# 1. Allocation breakdown
# ---------------------------------------------------------------------------

def get_allocation(positions: list[dict], quotes: dict[str, dict]) -> dict:
    """Portfolio allocation by ticker and sector."""
    items = []
    total_value = 0.0

    for pos in positions:
        ticker = pos["ticker"]
        quote = quotes.get(ticker, {})
        price = quote.get("price", pos.get("avg_cost", 0))
        mv = round(pos["shares"] * price, 2)
        total_value += mv
        items.append({
            "ticker": ticker,
            "market_value": mv,
            "pct": 0.0,
            "sector": quote.get("sector", "Unknown"),
        })

    by_sector: dict[str, float] = {}
    for item in items:
        if total_value > 0:
            item["pct"] = round(item["market_value"] / total_value * 100, 2)
        sector = item["sector"]
        by_sector[sector] = round(by_sector.get(sector, 0) + item["pct"], 2)

    return {"items": items, "by_sector": by_sector}


# ---------------------------------------------------------------------------
# 2. Correlation matrix
# ---------------------------------------------------------------------------

def get_correlation_matrix(tickers: list[str]) -> dict:
    """Compute pairwise correlation of daily close prices over 3 months."""
    if not tickers:
        return {"tickers": [], "matrix": []}

    def _fetch_close(t: str) -> pd.Series | None:
        try:
            df = get_history(t, period="3mo", interval="1d")
            if df is not None and not df.empty:
                return df["Close"].rename(t)
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_fetch_close, tickers))

    series = [s for s in results if s is not None]
    if len(series) < 2:
        return {"tickers": [s.name for s in series], "matrix": [[1.0]] if series else []}

    combined = pd.concat(series, axis=1).dropna()
    corr = combined.corr()
    valid_tickers = list(corr.columns)
    matrix = [[round(corr.loc[r, c], 2) for c in valid_tickers] for r in valid_tickers]

    return {"tickers": valid_tickers, "matrix": matrix}


# ---------------------------------------------------------------------------
# 3. Portfolio beta
# ---------------------------------------------------------------------------

def get_portfolio_beta(positions: list[dict], quotes: dict[str, dict]) -> dict:
    """Compute individual betas vs SPY and portfolio-weighted beta."""
    tickers = [p["ticker"] for p in positions]
    all_tickers = list(set(tickers + ["SPY"]))

    def _fetch_returns(t: str) -> tuple[str, pd.Series | None]:
        try:
            df = get_history(t, period="6mo", interval="1d")
            if df is not None and not df.empty:
                return t, df["Close"].pct_change().dropna()
        except Exception:
            pass
        return t, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(pool.map(_fetch_returns, all_tickers))

    spy_returns = results.get("SPY")
    if spy_returns is None or spy_returns.empty:
        return {"portfolio_beta": None, "holdings": []}

    # Compute weights
    total_value = 0.0
    position_values: dict[str, float] = {}
    for pos in positions:
        ticker = pos["ticker"]
        quote = quotes.get(ticker, {})
        price = quote.get("price", pos.get("avg_cost", 0))
        mv = pos["shares"] * price
        position_values[ticker] = mv
        total_value += mv

    holdings = []
    weighted_beta = 0.0

    for pos in positions:
        ticker = pos["ticker"]
        weight = round(position_values[ticker] / total_value, 4) if total_value > 0 else 0
        stock_returns = results.get(ticker)

        if stock_returns is None or stock_returns.empty:
            holdings.append({"ticker": ticker, "beta": None, "weight": round(weight * 100, 2)})
            continue

        # Align dates
        combined = pd.concat([stock_returns, spy_returns], axis=1, join="inner").dropna()
        if combined.shape[0] < 10:
            holdings.append({"ticker": ticker, "beta": None, "weight": round(weight * 100, 2)})
            continue

        stock_col = combined.iloc[:, 0]
        spy_col = combined.iloc[:, 1]
        cov = stock_col.cov(spy_col)
        var = spy_col.var()
        beta = round(cov / var, 2) if var > 0 else 0.0

        holdings.append({"ticker": ticker, "beta": beta, "weight": round(weight * 100, 2)})
        weighted_beta += beta * weight

    return {"portfolio_beta": round(weighted_beta, 2), "holdings": holdings}


# ---------------------------------------------------------------------------
# 4. P&L history
# ---------------------------------------------------------------------------

def get_pnl_history(positions: list[dict]) -> list[dict]:
    """Daily portfolio value over 3 months."""
    if not positions:
        return []

    def _fetch_close(pos: dict) -> tuple[dict, pd.Series | None]:
        try:
            df = get_history(pos["ticker"], period="3mo", interval="1d")
            if df is not None and not df.empty:
                return pos, df["Close"]
        except Exception:
            pass
        return pos, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_fetch_close, positions))

    # Build daily portfolio value
    daily_values: dict[str, float] = {}
    daily_costs: dict[str, float] = {}

    for pos, close_series in results:
        if close_series is None:
            continue
        shares = pos["shares"]
        cost = pos["shares"] * pos["avg_cost"]
        for dt, price in close_series.items():
            date_str = dt.strftime("%Y-%m-%d")
            daily_values[date_str] = daily_values.get(date_str, 0) + shares * price
            daily_costs[date_str] = daily_costs.get(date_str, 0) + cost

    history = []
    for date_str in sorted(daily_values.keys()):
        tv = round(daily_values[date_str], 2)
        tc = round(daily_costs[date_str], 2)
        history.append({
            "date": date_str,
            "total_value": tv,
            "total_cost": tc,
            "total_pnl": round(tv - tc, 2),
        })

    return history


# ---------------------------------------------------------------------------
# 5. Dividends
# ---------------------------------------------------------------------------

def get_dividends(positions: list[dict]) -> dict:
    """Dividend info for each holding."""
    def _fetch_div(pos: dict) -> dict:
        ticker = pos["ticker"]
        shares = pos["shares"]
        try:
            info = yf.Ticker(ticker).info
            rate = info.get("dividendRate", 0) or 0
            yld = info.get("dividendYield", 0) or 0
            ex_date = info.get("exDividendDate", None)
            if isinstance(ex_date, (int, float)):
                ex_date = datetime.fromtimestamp(ex_date).strftime("%Y-%m-%d")
            annual_income = round(rate * shares, 2)
            return {
                "ticker": ticker,
                "annual_dividend": round(rate, 2),
                "dividend_yield": round(yld * 100, 2),
                "ex_date": ex_date,
                "shares": shares,
                "annual_income": annual_income,
            }
        except Exception:
            return {
                "ticker": ticker,
                "annual_dividend": 0,
                "dividend_yield": 0,
                "ex_date": None,
                "shares": shares,
                "annual_income": 0,
            }

    with ThreadPoolExecutor(max_workers=8) as pool:
        holdings = list(pool.map(_fetch_div, positions))

    total_annual_income = round(sum(h["annual_income"] for h in holdings), 2)
    return {"holdings": holdings, "total_annual_income": total_annual_income}


# ---------------------------------------------------------------------------
# 6. Tax lots
# ---------------------------------------------------------------------------

def get_tax_lots(positions: list[dict]) -> list[dict]:
    """Each position treated as a single tax lot."""
    result = []
    for pos in positions:
        lot = {
            "shares": pos["shares"],
            "cost_per_share": pos["avg_cost"],
            "date": pos.get("added_at", None),
            "total_cost": round(pos["shares"] * pos["avg_cost"], 2),
        }
        total_cost = lot["total_cost"]
        result.append({
            "ticker": pos["ticker"],
            "lots": [lot],
            "fifo_cost_basis": total_cost,
            "lifo_cost_basis": total_cost,
        })
    return result


# ---------------------------------------------------------------------------
# 7. Position aging
# ---------------------------------------------------------------------------

def get_position_aging(positions: list[dict]) -> dict:
    """Days held for each position."""
    now = datetime.now()
    items = []
    total_days = 0

    for pos in positions:
        added_str = pos.get("added_at")
        if added_str:
            try:
                added = datetime.fromisoformat(added_str)
            except Exception:
                added = now
        else:
            added = now

        days_held = (now - added).days
        weeks_held = round(days_held / 7, 1)
        total_days += days_held

        items.append({
            "ticker": pos["ticker"],
            "added_at": added_str,
            "days_held": days_held,
            "weeks_held": weeks_held,
        })

    avg_days = round(total_days / len(positions), 1) if positions else 0
    return {"positions": items, "avg_days_held": avg_days}


# ---------------------------------------------------------------------------
# 8. Rebalancing suggestions
# ---------------------------------------------------------------------------

def get_rebalancing(
    positions: list[dict],
    quotes: dict[str, dict],
    targets: dict[str, float],
) -> dict:
    """Compare current allocation to targets; suggest buy/sell actions."""
    total_value = 0.0
    current: dict[str, float] = {}

    for pos in positions:
        ticker = pos["ticker"]
        quote = quotes.get(ticker, {})
        price = quote.get("price", pos.get("avg_cost", 0))
        mv = pos["shares"] * price
        current[ticker] = mv
        total_value += mv

    actions = []
    for ticker, target_pct in targets.items():
        cur_pct = round(current.get(ticker, 0) / total_value * 100, 2) if total_value > 0 else 0
        diff = round(target_pct - cur_pct, 2)
        dollar_amount = round(abs(diff) / 100 * total_value, 2)
        action = "BUY" if diff > 0 else "SELL" if diff < 0 else "HOLD"
        actions.append({
            "ticker": ticker,
            "current_pct": cur_pct,
            "target_pct": target_pct,
            "diff_pct": diff,
            "action": action,
            "dollar_amount": dollar_amount,
        })

    return {"actions": actions, "total_value": round(total_value, 2)}


# ---------------------------------------------------------------------------
# 9. Exposure warnings
# ---------------------------------------------------------------------------

def get_exposure_warnings(
    positions: list[dict],
    quotes: dict[str, dict],
    limit_pct: float = 20.0,
) -> dict:
    """Flag holdings that exceed the concentration limit."""
    total_value = 0.0
    values: list[tuple[str, float]] = []

    for pos in positions:
        ticker = pos["ticker"]
        quote = quotes.get(ticker, {})
        price = quote.get("price", pos.get("avg_cost", 0))
        mv = pos["shares"] * price
        values.append((ticker, mv))
        total_value += mv

    holdings = []
    warnings = []

    for ticker, mv in values:
        pct = round(mv / total_value * 100, 2) if total_value > 0 else 0
        over = pct > limit_pct
        holdings.append({
            "ticker": ticker,
            "pct": pct,
            "limit_pct": limit_pct,
            "over_limit": over,
        })
        if over:
            warnings.append(f"{ticker} is {pct}% of portfolio (limit {limit_pct}%)")

    return {"holdings": holdings, "warnings": warnings}


# ---------------------------------------------------------------------------
# 10. P&L breakdown (unrealized + realized)
# ---------------------------------------------------------------------------

def get_pnl_breakdown(positions: list[dict], quotes: dict[str, dict]) -> dict:
    """Unrealized P&L from current holdings, realized from journal."""
    unrealized = []
    total_unrealized = 0.0

    for pos in positions:
        ticker = pos["ticker"]
        quote = quotes.get(ticker, {})
        price = quote.get("price", pos.get("avg_cost", 0))
        u_pnl = round((price - pos["avg_cost"]) * pos["shares"], 2)
        unrealized.append({"ticker": ticker, "unrealized_pnl": u_pnl})
        total_unrealized += u_pnl

    # Realized from journal
    trades = _load_journal()
    total_realized = 0.0
    for trade in trades:
        if trade.get("status") == "closed":
            total_realized += trade.get("pnl", 0)

    return {
        "unrealized": unrealized,
        "total_unrealized": round(total_unrealized, 2),
        "total_realized": round(total_realized, 2),
    }
