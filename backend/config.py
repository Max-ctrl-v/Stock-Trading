import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Data directory — use /tmp on Vercel (serverless has no persistent filesystem)
_is_vercel = bool(os.environ.get("VERCEL", ""))
DATA_DIR: Path = Path("/tmp/data") if _is_vercel else Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY", "").strip()
ETORO_API_KEY: str = os.getenv("ETORO_API_KEY", "").strip()
ETORO_USER_KEY: str = os.getenv("ETORO_USER_KEY", "").strip()

# Cache TTLs in seconds
QUOTE_CACHE_TTL: int = 60
HISTORY_CACHE_TTL: int = 300
NEWS_CACHE_TTL: int = 900

# Trading defaults
DEFAULT_RISK_PCT: float = 0.025  # 2.5% risk per trade
RSI_OVERSOLD: float = 35.0
RSI_OVERBOUGHT: float = 65.0

# Signal defaults
SIGNAL_SCORE_THRESHOLD: float = 10.0  # score above which BUY/SELL triggers
SIGNAL_HISTORY_MAX: int = 500  # max signal history records

# Screener
SCREENER_CACHE_TTL: int = 1800  # 30 minutes

# Chart timeframe mappings: label -> (yfinance period, yfinance interval)
TIMEFRAME_MAP: dict[str, tuple[str, str]] = {
    "1D": ("1d", "5m"),
    "1W": ("5d", "15m"),
    "1M": ("1mo", "1h"),
    "3M": ("3mo", "1d"),
    "6M": ("6mo", "1d"),
    "1Y": ("1y", "1d"),
}
