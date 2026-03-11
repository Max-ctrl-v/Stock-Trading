import json
import os
from backend.config import RSI_OVERSOLD, RSI_OVERBOUGHT, DATA_DIR
THRESHOLDS_FILE = DATA_DIR / "custom_thresholds.json"

DEFAULT_SIGNAL_SCORE_THRESHOLD: float = 10.0


def _load_thresholds() -> dict:
    """Load custom thresholds from JSON file. Creates file if missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not THRESHOLDS_FILE.exists():
        _save_thresholds({})
        return {}
    with open(THRESHOLDS_FILE, "r") as f:
        return json.load(f)


def _save_thresholds(data: dict) -> None:
    """Save custom thresholds to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(THRESHOLDS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_thresholds(ticker: str) -> dict:
    """Return custom thresholds for a ticker, or defaults if none set."""
    ticker = ticker.upper()
    all_thresholds = _load_thresholds()

    if ticker in all_thresholds:
        entry = all_thresholds[ticker]
        return {
            "ticker": ticker,
            "rsi_oversold": entry.get("rsi_oversold", RSI_OVERSOLD),
            "rsi_overbought": entry.get("rsi_overbought", RSI_OVERBOUGHT),
            "signal_score_threshold": entry.get("signal_score_threshold", DEFAULT_SIGNAL_SCORE_THRESHOLD),
            "use_custom": True,
        }

    return {
        "ticker": ticker,
        "rsi_oversold": RSI_OVERSOLD,
        "rsi_overbought": RSI_OVERBOUGHT,
        "signal_score_threshold": DEFAULT_SIGNAL_SCORE_THRESHOLD,
        "use_custom": False,
    }


def set_thresholds(
    ticker: str,
    rsi_oversold: float | None = None,
    rsi_overbought: float | None = None,
    signal_score_threshold: float | None = None,
) -> dict:
    """Set custom thresholds for a ticker. Only updates provided values.

    Validates:
        rsi_oversold: 10-50
        rsi_overbought: 50-90
        signal_score_threshold: 5-50

    Returns the updated thresholds dict.
    Raises ValueError on invalid input.
    """
    ticker = ticker.upper()

    if rsi_oversold is not None and not (10.0 <= rsi_oversold <= 50.0):
        raise ValueError("rsi_oversold must be between 10 and 50")
    if rsi_overbought is not None and not (50.0 <= rsi_overbought <= 90.0):
        raise ValueError("rsi_overbought must be between 50 and 90")
    if signal_score_threshold is not None and not (5.0 <= signal_score_threshold <= 50.0):
        raise ValueError("signal_score_threshold must be between 5 and 50")

    all_thresholds = _load_thresholds()

    existing = all_thresholds.get(ticker, {})

    if rsi_oversold is not None:
        existing["rsi_oversold"] = rsi_oversold
    if rsi_overbought is not None:
        existing["rsi_overbought"] = rsi_overbought
    if signal_score_threshold is not None:
        existing["signal_score_threshold"] = signal_score_threshold

    all_thresholds[ticker] = existing
    _save_thresholds(all_thresholds)

    return get_thresholds(ticker)


def delete_thresholds(ticker: str) -> bool:
    """Remove custom thresholds for a ticker. Returns True if deleted, False if not found."""
    ticker = ticker.upper()
    all_thresholds = _load_thresholds()

    if ticker not in all_thresholds:
        return False

    del all_thresholds[ticker]
    _save_thresholds(all_thresholds)
    return True


def list_all_thresholds() -> dict:
    """Return all custom thresholds as a dict keyed by ticker."""
    return _load_thresholds()
