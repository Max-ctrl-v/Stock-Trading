from fastapi import APIRouter, HTTPException
from concurrent.futures import ThreadPoolExecutor
from backend.services.portfolio import (
    get_positions, add_position, remove_position,
    get_settings, update_settings, _load,
)
from backend.services.stock_data import get_quote
from backend.models.schemas import (
    PortfolioSummary, PortfolioHolding, PortfolioGroup, PortfolioPosition, Settings,
)

router = APIRouter()

_fx_cache: dict = {}


def _get_fx_rates() -> tuple[float, float]:
    """Get USD↔EUR conversion rates, cached 10 min. Returns (usd_to_eur, eur_to_usd)."""
    import time
    if _fx_cache.get("ts") and time.time() - _fx_cache["ts"] < 600:
        return _fx_cache["usd_to_eur"], _fx_cache["eur_to_usd"]
    try:
        import yfinance as yf
        t = yf.Ticker("EURUSD=X")
        h = t.history(period="1d")
        if len(h) > 0:
            eur_to_usd = float(h["Close"].iloc[-1])  # e.g. 1.09
            usd_to_eur = 1.0 / eur_to_usd              # e.g. 0.917
            _fx_cache["usd_to_eur"] = usd_to_eur
            _fx_cache["eur_to_usd"] = eur_to_usd
            _fx_cache["ts"] = time.time()
            return usd_to_eur, eur_to_usd
    except Exception:
        pass
    return 0.92, 1.09  # fallback


def _is_eur_ticker(ticker: str) -> bool:
    """Check if ticker trades in EUR (e.g. .DE suffix)."""
    return ticker.upper().endswith((".DE", ".PA", ".AS", ".MI", ".BR"))


def _fetch_live_price(ticker: str) -> float | None:
    """Fetch live price from yfinance. Returns None on failure."""
    try:
        quote = get_quote(ticker)
        return quote["price"] if quote["price"] else None
    except Exception:
        return None


@router.get("", response_model=PortfolioSummary)
async def get_portfolio():
    data = _load()
    positions = data.get("positions", [])
    holdings = []
    total_value = 0
    total_cost = 0
    total_pnl_sum = 0
    usd_to_eur, eur_to_usd = _get_fx_rates()

    # Fetch live prices for all unique tickers in parallel
    unique_tickers = list({p["ticker"] for p in positions})
    live_prices: dict[str, float | None] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(_fetch_live_price, unique_tickers))
    for ticker, price in zip(unique_tickers, results):
        live_prices[ticker] = price

    for p in positions:
        is_etoro = p.get("source") == "etoro"
        ticker = p["ticker"]
        is_eur = _is_eur_ticker(ticker)
        live_price = live_prices.get(ticker)

        if is_etoro:
            invested = p.get("invested", p["shares"] * p["avg_cost"])
            cost_basis_usd = round(invested, 2)

            if live_price is not None:
                # Live price available — calculate real-time P&L
                if is_eur:
                    # .DE stocks: yfinance price is in EUR, convert to USD
                    market_value_usd = round(p["shares"] * live_price * eur_to_usd, 2)
                else:
                    # US stocks: yfinance price is in USD
                    market_value_usd = round(p["shares"] * live_price, 2)
                pnl_usd = round(market_value_usd - cost_basis_usd, 2)
            else:
                # Fallback to stored eToro P&L
                pnl_usd = round(p.get("pnl", 0), 2)
                market_value_usd = round(cost_basis_usd + pnl_usd, 2)

            pnl_pct = round((pnl_usd / cost_basis_usd) * 100, 2) if cost_basis_usd > 0 else 0

            # Convert to EUR for display
            mv_eur = round(market_value_usd * usd_to_eur, 2)
            cost_eur = round(cost_basis_usd * usd_to_eur, 2)
            pnl_eur = round(pnl_usd * usd_to_eur, 2)

            if is_eur:
                # avg_cost from eToro is already in EUR for .DE stocks
                avg_cost_eur = round(p["avg_cost"], 2)
                cur_price_eur = round(live_price, 2) if live_price else round(p.get("current_price", p["avg_cost"]), 2)
            else:
                avg_cost_eur = round(p["avg_cost"] * usd_to_eur, 2)
                cur_price_eur = round(live_price * usd_to_eur, 2) if live_price else round(p.get("current_price", p["avg_cost"]) * usd_to_eur, 2)
        else:
            # Manual positions: fetch live price and calculate
            current_price = live_price if live_price else (p.get("current_price") or p["avg_cost"])

            market_value = round(p["shares"] * current_price, 2)
            cost_basis = round(p["shares"] * p["avg_cost"], 2)
            pnl = round(market_value - cost_basis, 2)
            pnl_pct = round((pnl / cost_basis) * 100, 2) if cost_basis > 0 else 0

            # Manual positions assumed USD
            mv_eur = round(market_value * usd_to_eur, 2)
            cost_eur = round(cost_basis * usd_to_eur, 2)
            pnl_eur = round(pnl * usd_to_eur, 2)
            avg_cost_eur = round(p["avg_cost"] * usd_to_eur, 2)
            cur_price_eur = round(current_price * usd_to_eur, 2)

        holdings.append(PortfolioHolding(
            ticker=p["ticker"],
            shares=p["shares"],
            avg_cost=avg_cost_eur,
            current_price=cur_price_eur,
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
