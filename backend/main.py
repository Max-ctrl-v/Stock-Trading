import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path

from backend.routers import (
    stocks, analysis, signals, portfolio, news, etoro, watchlist, screener,
    alerts, journal, backtest, market, scanners, signal_history, custom_thresholds,
    portfolio_analytics,
    # Trading & Execution (features 31-38)
    paper_trading, trade_templates, trailing_stop, position_scaling, multi_leg,
    options, risk_reward, trade_replay,
    # News & Sentiment (features 39-45)
    earnings, economic_calendar, sentiment, analyst_ratings,
    sec_filings, competitors, news_alerts,
    # Recommendations & Sell Signals
    recommendations, sell_signals,
)
from backend.routers import auth as auth_router
from backend.middleware.auth import AuthMiddleware

# Detect environment
is_vercel = bool(os.environ.get("VERCEL", ""))
is_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT", ""))
is_production = is_vercel or is_railway

# On Vercel: copy static data files to /tmp so they're accessible
if is_vercel:
    import shutil
    src_data = Path(__file__).parent.parent / "data"
    dst_data = Path("/tmp/data")
    dst_data.mkdir(parents=True, exist_ok=True)
    for f in ["sp500_tickers.json"]:
        src = src_data / f
        dst = dst_data / f
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)

app = FastAPI(
    title="Stock Analysis Tool",
    version="1.0.0",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

# GZIP compression for faster responses
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS — restrict to known origins
ALLOWED_ORIGINS = [
    "http://localhost:1001",
    "http://127.0.0.1:1001",
    "https://stock-trading-seven.vercel.app",
]
# Add Railway URL if set
railway_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
if railway_url:
    ALLOWED_ORIGINS.append(f"https://{railway_url}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Auth middleware — checks JWT on all /api/ routes except /api/auth/login
app.add_middleware(AuthMiddleware)


# Security headers + request timing middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Response-Time"] = f"{(time.time() - start)*1000:.0f}ms"
    return response


# Health check (public, no auth needed)
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "environment": "railway" if is_railway else "vercel" if is_vercel else "local", "version": "v2-etoro-pnl"}


# Auth router (public — no token needed for login)
app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])

# Register routers
app.include_router(stocks.router, prefix="/api/stocks", tags=["stocks"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(signal_history.router, prefix="/api/signals", tags=["signal-history"])
app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
app.include_router(portfolio_analytics.router, prefix="/api/portfolio/analytics", tags=["portfolio-analytics"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(etoro.router, prefix="/api/etoro", tags=["etoro"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(screener.router, prefix="/api/screener", tags=["screener"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(journal.router, prefix="/api/journal", tags=["journal"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(scanners.router, prefix="/api/scanners", tags=["scanners"])
app.include_router(custom_thresholds.router, prefix="/api/thresholds", tags=["thresholds"])

# Trading & Execution routers (features 31-38)
app.include_router(paper_trading.router, prefix="/api/paper-trading", tags=["paper-trading"])
app.include_router(trade_templates.router, prefix="/api/templates", tags=["templates"])
app.include_router(trailing_stop.router, prefix="/api/trailing-stop", tags=["trailing-stop"])
app.include_router(position_scaling.router, prefix="/api/position-scaling", tags=["position-scaling"])
app.include_router(multi_leg.router, prefix="/api/multi-leg", tags=["multi-leg"])
app.include_router(options.router, prefix="/api/options", tags=["options"])
app.include_router(risk_reward.router, prefix="/api/risk-reward", tags=["risk-reward"])
app.include_router(trade_replay.router, prefix="/api/trade-replay", tags=["trade-replay"])

# News & Sentiment routers (features 39-45)
app.include_router(earnings.router, prefix="/api/earnings", tags=["earnings"])
app.include_router(economic_calendar.router, prefix="/api/economic-calendar", tags=["economic-calendar"])
app.include_router(sentiment.router, prefix="/api/sentiment", tags=["sentiment"])
app.include_router(analyst_ratings.router, prefix="/api/analyst-ratings", tags=["analyst-ratings"])
app.include_router(sec_filings.router, prefix="/api/sec-filings", tags=["sec-filings"])
app.include_router(competitors.router, prefix="/api/competitors", tags=["competitors"])
app.include_router(news_alerts.router, prefix="/api/news-alerts", tags=["news-alerts"])

# Recommendations & Sell Signals
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["recommendations"])
app.include_router(sell_signals.router, prefix="/api/sell-signals", tags=["sell-signals"])

# Serve frontend
frontend_dir = Path(__file__).parent.parent / "frontend"


@app.get("/")
async def serve_frontend():
    return FileResponse(frontend_dir / "index.html")
