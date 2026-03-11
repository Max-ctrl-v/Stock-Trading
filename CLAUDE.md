# Stock Analysis Tool

## Project Overview
Local stock analysis web app for aggressive, high-frequency trading. Python FastAPI backend + single-file HTML/Tailwind/Alpine.js frontend. Provides buy/sell signals with position sizing powered by technical indicators + AI analysis (ChatGPT + Perplexity).


## Always Do First
- **Invoke the `frontend-design` skill** before writing any frontend code, every session, no exceptions.


## Local Server
- **Always serve on localhost** — never screenshot a `file:///` URL.
- Start the dev server: `node serve.mjs` (serves the project root at `http://localhost:1001`)
- `serve.mjs` lives in the project root. Start it in the background before taking any screenshots.
- If the server is already running, do not start a second instance.
```

## Tech Stack
- **Backend:** Python 3.x, FastAPI, uvicorn, yfinance, pandas, ta, openai, httpx
- **Frontend:** Single `index.html` — Tailwind CSS (CDN), Alpine.js (CDN), Chart.js (CDN)
- **Data:** JSON file storage (`data/portfolio.json`, `watchlist.json`, `alerts.json`, `journal.json`, `screener_results.json`, `sp500_tickers.json`), no database
- **Markets:** US Stocks, ETFs, Forex — no crypto

## Screenshot Workflow
- Puppeteer is installed locally (`npm install puppeteer`). Chrome cache is at `C:/Users/maxno/.cache/puppeteer/`.
- **Always screenshot from localhost:** `node screenshot.mjs http://localhost:1001`
- Screenshots are saved automatically to `./temporary screenshots/screenshot-N.png` (auto-incremented, never overwritten).
- Optional label suffix: `node screenshot.mjs http://localhost:1001 label` → saves as `screenshot-N-label.png`
- `screenshot.mjs` lives in the project root. Use it as-is.
- After screenshotting, read the PNG from `temporary screenshots/` with the Read tool — Claude can see and analyze the image directly.
- When comparing, be specific: "heading is 32px but reference shows ~24px", "card gap is 16px but should be 24px"
- Check: spacing/padding, font size/weight/line-height, colors (exact hex), alignment, border-radius, shadows, image sizing
- Screenshots in `temporary screenshots/` are automatically deleted after 3 days.


# Hard Rules
- Do not add sections, features, or content not in the reference
- Do not "improve" a reference design — match it
- Do not stop after one screenshot pass
- Do not use `transition-all`
- Do not use default Tailwind blue/indigo as primary color
-after every correction update ur @CLAUDE.md so u dont make the same mistake again

## Project Structure
- `backend/routers/` — FastAPI route handlers (one file per resource)
- `backend/services/` — Business logic (one file per domain)
- `backend/models/schemas.py` — All Pydantic models
- `frontend/index.html` — Entire frontend in one file
- `data/` — Local JSON persistence (created at runtime)
- `.env` — API keys (never commit)

## Code Conventions
- Python: snake_case, type hints on all function signatures, async where possible
- All API responses use Pydantic models defined in schemas.py
- Services never import from routers; routers call services
- Error handling: raise HTTPException with meaningful detail messages
- Frontend: Alpine.js x-data for state, fetch() for API calls, Tailwind for all styling
- No CSS files — Tailwind utility classes only
- Use Chart.js for all charts

## API Keys Required (.env)
```
OPENAI_API_KEY=sk-...
PERPLEXITY_API_KEY=pplx-...
ETORO_API_KEY=eyJ...
ETORO_USER_KEY=...
```

## eToro Integration
- Portfolio sync via eToro Public API (`https://public-api.etoro.com/api/v1/`)
- Auth: dual-key — `x-api-key` + `x-user-key` headers (both from `.env`)
- Router: `backend/routers/etoro.py` — mounted at `/api/etoro/`
- Service: `backend/services/etoro.py` — fetches and normalizes positions
- Endpoints: `POST /api/etoro/sync`, `GET /api/etoro/status`
- Positions are imported into local `portfolio.json` on sync
- API keys are NEVER committed — `.gitignore` blocks `.env` files

## Key Design Decisions
- yfinance for stock data (free, no key needed)
- gpt-4o-mini for analysis (cost-effective for frequent calls)
- Perplexity sonar model for real-time news
- Aggressive trading defaults: RSI thresholds 35/65, 2-3% risk per trade
- Account size is user-configurable in the UI
- All state is local (portfolio.json, watchlist.json) — single-user personal tool

## Charting
- Multi-panel chart system: candlestick (price), volume bars, indicator panel (RSI/MACD toggle)
- 6 timeframes: 1D, 1W, 1M, 3M, 6M, 1Y — mapped via `TIMEFRAME_MAP` in config.py
- Chart endpoint: `GET /api/stocks/{ticker}/chart?timeframe=3M` — returns OHLCV + indicators
- Uses `chartjs-chart-financial` for candlesticks, `luxon` adapter for time axis
- SignalResponse also includes `ohlcv` field for initial chart render

## Watchlist
- Router: `backend/routers/watchlist.py` — mounted at `/api/watchlist/`
- Service: `backend/services/watchlist.py` — CRUD on `data/watchlist.json`
- Endpoints: `GET /api/watchlist`, `POST /api/watchlist/{ticker}`, `DELETE /api/watchlist/{ticker}`
- Fetches live quotes + signals in parallel via ThreadPoolExecutor
- Frontend auto-refreshes every 60 seconds

## Stock Screener
- Router: `backend/routers/screener.py` — mounted at `/api/screener/`
- Service: `backend/services/screener.py` — background scanning with ThreadPoolExecutor(8)
- Scans 50 S&P 500 tickers from `data/sp500_tickers.json`
- Scoring: signal engine (40%), momentum (20%), volume surge (15%), BB squeeze (15%), relative strength vs SPY (10%)
- Endpoints: `POST /api/screener/scan` (background), `GET /api/screener/results`
- Results cached 30 min (`SCREENER_CACHE_TTL` in config.py), also persisted to `data/screener_results.json`

## Price Alerts
- Router: `backend/routers/alerts.py` — mounted at `/api/alerts/`
- Service: `backend/services/alerts.py` — CRUD on `data/alerts.json`
- Endpoints: `POST /api/alerts`, `GET /api/alerts`, `DELETE /api/alerts/{id}`, `GET /api/alerts/check`
- Frontend polls `/check` every 60s, triggers browser notifications

## Trade Journal
- Router: `backend/routers/journal.py` — mounted at `/api/journal/`
- Service: `backend/services/journal.py` — CRUD on `data/journal.json`
- Endpoints: `GET /api/journal` (with stats), `POST /api/journal`, `POST /api/journal/{id}/close`, `DELETE /api/journal/{id}`, `GET /api/journal/stats`
- Stats: win rate, profit factor, avg gain/loss, total P&L

## Backtesting
- Router: `backend/routers/backtest.py` — mounted at `/api/backtest/`
- Service: `backend/services/backtest.py` — walk-forward simulation using signal engine
- Endpoint: `GET /api/backtest/{ticker}?period=1y`
- Returns: trades, win rate, total return, max drawdown, equity curve

## Market Overview
- Router: `backend/routers/market.py` — mounted at `/api/market/`
- Service: `backend/services/market.py` — fetches 11 sector ETFs + 5 major indices
- Endpoints: `GET /api/market/sectors`, `GET /api/market/overview`
- Uses ThreadPoolExecutor for parallel quote fetching

## Route Ordering
- FastAPI matches routes top-to-bottom. Parameterized routes like `/{ticker}` MUST come AFTER specific routes like `/{ticker}/chart`
- When adding new sub-routes under a parameterized prefix, define them BEFORE the catch-all `/{ticker}` route
- This was a past bug: `GET /api/portfolio/etoro-status` was caught by `DELETE /api/portfolio/{ticker}` — fixed by using a separate router

## Skills
- Use `/frontend-design` skill when building or updating the UI
- Frontend must follow the design system: custom colors, paired fonts, layered shadows, grain texture

## When Adding Features
- New endpoint: add router in `backend/routers/`, service in `backend/services/`
- New indicator: add to `backend/services/technical.py`, update schemas.py
- Frontend changes: everything goes in `frontend/index.html`
- Keep the single-file frontend approach — do not split into components
- Always clean `__pycache__` directories after structural changes (stale bytecode causes ghost routes)
- When splitting work across agents, keep shared files (schemas.py, config.py, main.py) in the main context to avoid conflicts
