from fastapi import APIRouter, HTTPException
import logging
from backend.services.portfolio import (
    get_positions, add_position, remove_position,
    get_settings, update_settings, _load,
)
from backend.services.stock_data import get_quote
from backend.models.schemas import (
    PortfolioSummary, PortfolioHolding, PortfolioGroup, PortfolioPosition, Settings,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_eur_rate_cache: dict = {}


def _get_usd_to_eur() -> float:
    """Get USD to EUR conversion rate, cached 10 min."""
    import time
    if _eur_rate_cache.get("ts") and time.time() - _eur_rate_cache["ts"] < 600:
        return _eur_rate_cache["rate"]
    try:
        import yfinance as yf
        t = yf.Ticker("EURUSD=X")
        h = t.history(period="1d")
        if len(h) > 0:
            eur_usd = float(h["Close"].iloc[-1])
            rate = 1.0 / eur_usd  # USD -> EUR
            _eur_rate_cache["rate"] = rate
            _eur_rate_cache["ts"] = time.time()
            return rate
    except Exception:
        pass
    return 0.92  # fallback


def _fetch_etoro_api_data() -> dict | None:
    """Fetch raw eToro portfolio data. Returns API response or None on failure."""
    try:
        from backend.services.etoro import get_portfolio as etoro_get_portfolio
        data = etoro_get_portfolio()
        if "error" in data:
            logger.warning("eToro API error: %s", data["error"])
            return None
        return data
    except Exception as e:
        logger.warning("Failed to fetch eToro data: %s", e)
        return None


def _get_fresh_etoro_pnl(etoro_data: dict | None) -> dict[int, dict] | None:
    """Extract {position_id: pnl_data} from eToro API response."""
    if not etoro_data:
        return None
    positions_raw = etoro_data.get("clientPortfolio", {}).get("positions", [])
    result = {}
    for pos in positions_raw:
        pid = pos.get("positionID")
        pnl_data = pos.get("unrealizedPnL", {})
        result[pid] = {
            "pnl": float(pnl_data.get("pnL", 0)) if pnl_data else 0,
            "close_rate": float(pnl_data.get("closeRate", 0)) if pnl_data else 0,
        }
    return result


def _build_positions_from_etoro(etoro_data: dict) -> list[dict]:
    """Build position list directly from eToro API (when portfolio.json is missing)."""
    from backend.services.etoro import parse_positions, resolve_instruments_batch
    positions_raw = etoro_data.get("clientPortfolio", {}).get("positions", [])
    if not positions_raw:
        return []

    instrument_ids = [p["instrumentID"] for p in positions_raw]
    instruments = resolve_instruments_batch(instrument_ids)

    results = []
    for pos in positions_raw:
        iid = pos["instrumentID"]
        inst_info = instruments.get(iid, {"ticker": f"ETORO_{iid}", "name": "Unknown"})
        units = float(pos.get("units", 0))
        open_rate = float(pos.get("openRate", 0))
        amount = float(pos.get("amount", 0))
        pnl_data = pos.get("unrealizedPnL", {})
        pnl = float(pnl_data.get("pnL", 0)) if pnl_data else 0

        if units > 0:
            results.append({
                "ticker": inst_info["ticker"],
                "shares": round(units, 6),
                "avg_cost": round(open_rate, 2),
                "current_price": round(float(pnl_data.get("closeRate", 0)), 2) if pnl_data else None,
                "invested": round(amount, 2),
                "pnl": round(pnl, 2),
                "source": "etoro",
                "instrument_id": iid,
                "position_id": pos.get("positionID"),
                "added_at": "",
            })
    return results


def _is_eur_ticker(ticker: str) -> bool:
    """Check if ticker trades in EUR (e.g. .DE suffix)."""
    return ticker.upper().endswith((".DE", ".PA", ".AS", ".MI", ".BR"))


@router.get("", response_model=PortfolioSummary)
async def get_portfolio():
    data = _load()
    positions = data.get("positions", [])
    holdings = []
    total_value = 0
    total_cost = 0
    total_pnl_sum = 0
    usd_to_eur = _get_usd_to_eur()

    # Fetch fresh data from eToro API (cached 2 min)
    etoro_data = _fetch_etoro_api_data()
    fresh_etoro = _get_fresh_etoro_pnl(etoro_data)

    # If portfolio.json is empty (e.g. Vercel cold start), build from eToro API
    if not positions and etoro_data:
        positions = _build_positions_from_etoro(etoro_data)

    for p in positions:
        is_etoro = p.get("source") == "etoro"

        if is_etoro:
            invested = p.get("invested", p["shares"] * p["avg_cost"])
            cost_basis = round(invested, 2)

            # Use fresh eToro P&L if available, otherwise stored
            pid = p.get("position_id")
            if fresh_etoro and pid in fresh_etoro:
                stored_pnl = fresh_etoro[pid]["pnl"]
            else:
                stored_pnl = p.get("pnl", 0)

            market_value = round(cost_basis + stored_pnl, 2)
            pnl = round(stored_pnl, 2)
            pnl_pct = round((pnl / cost_basis) * 100, 2) if cost_basis > 0 else 0

            # eToro values are in USD — convert to EUR
            mv_eur = round(market_value * usd_to_eur, 2)
            cost_eur = round(cost_basis * usd_to_eur, 2)
            pnl_eur = round(pnl * usd_to_eur, 2)

            # avg_cost (openRate) and current_price (closeRate) are in instrument's native
            # currency — USD for US stocks, EUR for .DE stocks. Keep as-is so they match eToro.
            avg_cost_display = round(p["avg_cost"], 2)
            if fresh_etoro and pid in fresh_etoro and fresh_etoro[pid]["close_rate"]:
                cur_price_display = round(fresh_etoro[pid]["close_rate"], 2)
            else:
                cur_price_display = round(p.get("current_price", p["avg_cost"]), 2)
        else:
            # Manual positions: fetch live price and calculate
            try:
                quote = get_quote(p["ticker"])
                current_price = quote["price"]
            except Exception:
                current_price = p.get("current_price") or p["avg_cost"]

            market_value = round(p["shares"] * current_price, 2)
            cost_basis = round(p["shares"] * p["avg_cost"], 2)
            pnl = round(market_value - cost_basis, 2)
            pnl_pct = round((pnl / cost_basis) * 100, 2) if cost_basis > 0 else 0

            mv_eur = round(market_value * usd_to_eur, 2)
            cost_eur = round(cost_basis * usd_to_eur, 2)
            pnl_eur = round(pnl * usd_to_eur, 2)
            avg_cost_display = round(p["avg_cost"], 2)
            cur_price_display = round(current_price, 2)

        holdings.append(PortfolioHolding(
            ticker=p["ticker"],
            shares=p["shares"],
            avg_cost=avg_cost_display,
            current_price=cur_price_display,
            market_value=mv_eur,
            pnl=pnl_eur,
            pnl_pct=pnl_pct,
            added_at=p.get("added_at", ""),
        ))

        total_value += mv_eur
        total_cost += cost_eur
        total_pnl_sum += pnl_eur

    total_pnl_eur = round(total_pnl_sum, 2)
    total_pnl_pct = round((total_pnl_eur / total_cost) * 100, 2) if total_cost > 0 else 0

    # Group holdings by ticker
    from collections import OrderedDict
    grouped: dict[str, list[PortfolioHolding]] = OrderedDict()
    for h in holdings:
        grouped.setdefault(h.ticker, []).append(h)

    groups = []
    for ticker, pos_list in grouped.items():
        g_shares = round(sum(p.shares for p in pos_list), 6)
        g_value = round(sum(p.market_value for p in pos_list), 2)
        g_cost = round(sum(p.market_value - p.pnl for p in pos_list), 2)
        g_pnl = round(sum(p.pnl for p in pos_list), 2)
        g_pnl_pct = round((g_pnl / g_cost) * 100, 2) if g_cost > 0 else 0
        g_price = pos_list[0].current_price
        # Weighted avg entry price in native currency (USD for US, EUR for .DE)
        g_avg_cost = round(sum(p.avg_cost * p.shares for p in pos_list) / g_shares, 2) if g_shares > 0 else 0

        groups.append(PortfolioGroup(
            ticker=ticker,
            total_shares=g_shares,
            avg_cost=g_avg_cost,
            current_price=g_price,
            total_value=g_value,
            total_cost=g_cost,
            pnl=g_pnl,
            pnl_pct=g_pnl_pct,
            positions=pos_list,
        ))

    return PortfolioSummary(
        total_value=round(total_value, 2),
        total_cost=round(total_cost, 2),
        total_pnl=total_pnl_eur,
        total_pnl_pct=total_pnl_pct,
        holdings=holdings,
        groups=groups,
    )


@router.post("/add")
async def add_to_portfolio(position: PortfolioPosition):
    result = add_position(position.ticker, position.shares, position.avg_cost)
    return {"status": "ok", "position": result}


@router.get("/settings", response_model=Settings)
async def get_portfolio_settings():
    s = get_settings()
    return Settings(**s)


@router.post("/settings", response_model=Settings)
async def update_portfolio_settings(settings: Settings):
    s = update_settings(settings.account_size, settings.risk_pct)
    return Settings(**s)


@router.delete("/{ticker}")
async def remove_from_portfolio(ticker: str):
    removed = remove_position(ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Position {ticker} not found")
    return {"status": "ok", "ticker": ticker}
