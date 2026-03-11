from fastapi import APIRouter, HTTPException
from backend.services.portfolio import (
    get_positions, add_position, remove_position,
    get_settings, update_settings, _load,
)
from backend.services.stock_data import get_quote
from backend.models.schemas import (
    PortfolioSummary, PortfolioHolding, PortfolioGroup, PortfolioPosition, Settings,
)

router = APIRouter()

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
    return 0.86  # fallback


@router.get("", response_model=PortfolioSummary)
async def get_portfolio():
    data = _load()
    positions = data.get("positions", [])
    holdings = []
    total_value = 0
    total_cost = 0
    total_pnl_sum = 0
    usd_to_eur = _get_usd_to_eur()

    for p in positions:
        # Always fetch a live quote for accurate current prices
        try:
            quote = get_quote(p["ticker"])
            current_price = quote["price"]
        except Exception:
            current_price = p.get("current_price") or p["avg_cost"]

        is_etoro = p.get("source") == "etoro"

        if is_etoro:
            # eToro positions: use stored avg_cost & shares but live price
            invested = p.get("invested", p["shares"] * p["avg_cost"])
            cost_basis = round(invested, 2)
            market_value = round(p["shares"] * current_price, 2)
            pnl = round(market_value - cost_basis, 2)
            pnl_pct = round((pnl / cost_basis) * 100, 2) if cost_basis > 0 else 0
        else:
            market_value = round(p["shares"] * current_price, 2)
            cost_basis = round(p["shares"] * p["avg_cost"], 2)
            pnl = round(market_value - cost_basis, 2)
            pnl_pct = round((pnl / cost_basis) * 100, 2) if cost_basis > 0 else 0

        # Convert USD -> EUR
        mv_eur = round(market_value * usd_to_eur, 2)
        cost_eur = round(cost_basis * usd_to_eur, 2)
        pnl_eur = round(pnl * usd_to_eur, 2)

        holdings.append(PortfolioHolding(
            ticker=p["ticker"],
            shares=p["shares"],
            avg_cost=round(p["avg_cost"] * usd_to_eur, 2),
            current_price=round(current_price * usd_to_eur, 2),
            market_value=mv_eur,
            pnl=pnl_eur,
            pnl_pct=pnl_pct,
            added_at=p.get("added_at", ""),
        ))

        total_value += mv_eur
        total_cost += cost_eur
        total_pnl_sum += pnl

    # Always use computed total P&L from live prices
    total_pnl_eur = round(total_pnl_sum * usd_to_eur, 2)

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
        g_avg_cost = round(g_cost / g_shares, 2) if g_shares > 0 else 0

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
