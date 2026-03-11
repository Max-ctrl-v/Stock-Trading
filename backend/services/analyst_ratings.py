import json
import yfinance as yf
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _get_portfolio_tickers() -> list[str]:
    portfolio_path = DATA_DIR / "portfolio.json"
    if not portfolio_path.exists():
        return []
    try:
        with open(portfolio_path, "r") as f:
            data = json.load(f)
        return [item["ticker"] for item in data if "ticker" in item]
    except Exception:
        return []


def _fetch_single_rating(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker.upper())
        info = t.info or {}

        # Get recommendation summary
        buy_count = 0
        hold_count = 0
        sell_count = 0
        total_analysts = 0

        try:
            rec_summary = t.recommendations_summary
            if rec_summary is not None and not rec_summary.empty:
                latest = rec_summary.iloc[0]
                buy_count = int(latest.get("strongBuy", 0)) + int(latest.get("buy", 0))
                hold_count = int(latest.get("hold", 0))
                sell_count = int(latest.get("sell", 0)) + int(latest.get("strongSell", 0))
                total_analysts = buy_count + hold_count + sell_count
        except Exception:
            pass

        # Determine consensus
        consensus = "N/A"
        if total_analysts > 0:
            buy_pct = buy_count / total_analysts
            sell_pct = sell_count / total_analysts
            if buy_pct >= 0.7:
                consensus = "Strong Buy"
            elif buy_pct >= 0.5:
                consensus = "Buy"
            elif sell_pct >= 0.5:
                consensus = "Sell"
            elif sell_pct >= 0.7:
                consensus = "Strong Sell"
            else:
                consensus = "Hold"

        # Price target
        average_target_price: float | None = None
        try:
            targets = t.analyst_price_targets
            if targets is not None:
                if isinstance(targets, dict):
                    average_target_price = targets.get("mean") or targets.get("current")
                elif hasattr(targets, "mean"):
                    average_target_price = getattr(targets, "mean", None)
        except Exception:
            pass

        # Fallback to info for target price
        if average_target_price is None:
            average_target_price = info.get("targetMeanPrice")

        current_price = info.get("currentPrice") or info.get("regularMarketPrice")

        upside_pct: float | None = None
        if average_target_price and current_price and current_price > 0:
            upside_pct = round(((average_target_price - current_price) / current_price) * 100, 2)

        return {
            "ticker": ticker.upper(),
            "consensus": consensus,
            "total_analysts": total_analysts,
            "buy_count": buy_count,
            "hold_count": hold_count,
            "sell_count": sell_count,
            "average_target_price": round(average_target_price, 2) if average_target_price else None,
            "current_price": round(current_price, 2) if current_price else None,
            "upside_pct": upside_pct,
        }
    except Exception as e:
        return {
            "ticker": ticker.upper(),
            "consensus": "N/A",
            "total_analysts": 0,
            "buy_count": 0,
            "hold_count": 0,
            "sell_count": 0,
            "average_target_price": None,
            "current_price": None,
            "upside_pct": None,
            "error": str(e),
        }


def get_analyst_rating(ticker: str) -> dict:
    return _fetch_single_rating(ticker)


def get_rating_history(ticker: str) -> list[dict]:
    try:
        t = yf.Ticker(ticker.upper())
        recs = t.recommendations
        if recs is None or recs.empty:
            return []

        history = []
        for idx, row in recs.tail(20).iterrows():
            entry = {
                "date": str(idx) if not hasattr(idx, "isoformat") else idx.isoformat(),
                "firm": row.get("Firm", "Unknown"),
                "to_grade": row.get("To Grade", ""),
                "from_grade": row.get("From Grade", ""),
                "action": row.get("Action", ""),
            }
            history.append(entry)

        history.reverse()
        return history
    except Exception:
        return []


def get_portfolio_ratings() -> list[dict]:
    tickers = _get_portfolio_tickers()
    if not tickers:
        return []
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(_fetch_single_rating, tickers))
    return results
