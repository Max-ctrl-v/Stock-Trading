import uuid
import time
import json
import httpx
from backend.config import ETORO_API_KEY, ETORO_USER_KEY

ETORO_BASE_URL = "https://public-api.etoro.com/api/v1"
ETORO_METADATA_URL = "https://api.etorostatic.com/sapi/instrumentsmetadata/V1.1/instruments"

# Cache eToro data
_etoro_cache: dict[str, tuple] = {}
ETORO_CACHE_TTL = 120
INSTRUMENT_CACHE_TTL = 86400  # 24 hours for instrument metadata

# In-memory instrument ID -> ticker mapping
_instrument_map: dict[int, dict] = {}


def _get_headers() -> dict:
    """Build authentication headers for eToro API requests."""
    if not ETORO_API_KEY or not ETORO_USER_KEY:
        raise ValueError("ETORO_API_KEY and ETORO_USER_KEY must be configured in .env")

    return {
        "X-Request-Id": str(uuid.uuid4()),
        "X-Api-Key": ETORO_API_KEY,
        "X-User-Key": ETORO_USER_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _get_cached(key: str, ttl: int = ETORO_CACHE_TTL) -> dict | None:
    if key in _etoro_cache:
        data, ts = _etoro_cache[key]
        if time.time() - ts < ttl:
            return data
    return None


def _set_cached(key: str, data):
    _etoro_cache[key] = (data, time.time())


def resolve_instrument(instrument_id: int) -> dict:
    """Resolve eToro instrument ID to ticker symbol and name using public metadata API."""
    if instrument_id in _instrument_map:
        return _instrument_map[instrument_id]

    cache_key = f"instrument:{instrument_id}"
    cached = _get_cached(cache_key, INSTRUMENT_CACHE_TTL)
    if cached:
        _instrument_map[instrument_id] = cached
        return cached

    try:
        response = httpx.get(
            f"{ETORO_METADATA_URL}?InstrumentIds={instrument_id}",
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        instruments = data.get("InstrumentDisplayDatas", [])

        if instruments:
            inst = instruments[0]
            result = {
                "ticker": inst.get("SymbolFull", f"ETORO_{instrument_id}"),
                "name": inst.get("InstrumentDisplayName", "Unknown"),
                "instrument_id": instrument_id,
            }
        else:
            result = {"ticker": f"ETORO_{instrument_id}", "name": "Unknown", "instrument_id": instrument_id}

        _instrument_map[instrument_id] = result
        _set_cached(cache_key, result)
        return result

    except Exception:
        result = {"ticker": f"ETORO_{instrument_id}", "name": "Unknown", "instrument_id": instrument_id}
        _instrument_map[instrument_id] = result
        return result


def resolve_instruments_batch(instrument_ids: list[int]) -> dict[int, dict]:
    """Resolve multiple instrument IDs in a single API call."""
    unknown_ids = [iid for iid in set(instrument_ids) if iid not in _instrument_map]

    if unknown_ids:
        try:
            ids_param = ",".join(str(i) for i in unknown_ids)
            response = httpx.get(
                f"{ETORO_METADATA_URL}?InstrumentIds={ids_param}",
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()

            for inst in data.get("InstrumentDisplayDatas", []):
                iid = inst.get("InstrumentID")
                if iid:
                    result = {
                        "ticker": inst.get("SymbolFull", f"ETORO_{iid}"),
                        "name": inst.get("InstrumentDisplayName", "Unknown"),
                        "instrument_id": iid,
                    }
                    _instrument_map[iid] = result
                    _set_cached(f"instrument:{iid}", result)

        except Exception:
            pass

        # Fill in any still-unknown IDs
        for iid in unknown_ids:
            if iid not in _instrument_map:
                _instrument_map[iid] = {"ticker": f"ETORO_{iid}", "name": "Unknown", "instrument_id": iid}

    return {iid: _instrument_map.get(iid, {"ticker": f"ETORO_{iid}", "name": "Unknown"}) for iid in instrument_ids}


def get_account_info() -> dict:
    """Get authenticated user identity and account IDs."""
    cached = _get_cached("account_info")
    if cached:
        return cached

    try:
        response = httpx.get(
            f"{ETORO_BASE_URL}/me",
            headers=_get_headers(),
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        _set_cached("account_info", data)
        return data
    except httpx.HTTPStatusError as e:
        return {"error": f"eToro API error: {e.response.status_code}", "detail": e.response.text}
    except Exception as e:
        return {"error": f"Connection failed: {str(e)}"}


def get_portfolio() -> dict:
    """Fetch the user's eToro portfolio with open positions and P&L."""
    cached = _get_cached("portfolio")
    if cached:
        return cached

    try:
        response = httpx.get(
            f"{ETORO_BASE_URL}/trading/info/real/pnl",
            headers=_get_headers(),
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        _set_cached("portfolio", data)
        return data

    except httpx.HTTPStatusError as e:
        return {"error": f"eToro API error: {e.response.status_code}", "detail": e.response.text}
    except Exception as e:
        return {"error": f"Connection failed: {str(e)}"}


def parse_positions(portfolio_data: dict) -> list[dict]:
    """Convert eToro portfolio data into individual positions (not aggregated)."""
    positions_raw = portfolio_data.get("clientPortfolio", {}).get("positions", [])

    if not positions_raw:
        return []

    # Resolve all instrument IDs in one batch call
    instrument_ids = [p["instrumentID"] for p in positions_raw]
    instruments = resolve_instruments_batch(instrument_ids)

    # Return each position individually - no aggregation
    results = []
    for pos in positions_raw:
        iid = pos["instrumentID"]
        inst_info = instruments.get(iid, {"ticker": f"ETORO_{iid}", "name": "Unknown"})
        units = float(pos.get("units", 0))
        open_rate = float(pos.get("openRate", 0))
        amount = float(pos.get("amount", 0))

        # Use eToro's own P&L - don't recalculate
        pnl_data = pos.get("unrealizedPnL", {})
        pnl = float(pnl_data.get("pnL", 0)) if pnl_data else 0
        close_rate = float(pnl_data.get("closeRate", 0)) if pnl_data else 0

        if units > 0:
            results.append({
                "ticker": inst_info["ticker"],
                "name": inst_info["name"],
                "shares": round(units, 6),
                "avg_cost": round(open_rate, 2),
                "current_price": round(close_rate, 2) if close_rate > 0 else None,
                "invested": round(amount, 2),
                "pnl": round(pnl, 2),
                "source": "etoro",
                "instrument_id": iid,
                "position_id": pos.get("positionID", None),
            })

    return results


def sync_portfolio() -> dict:
    """Main function: fetch eToro portfolio and return normalized positions."""
    if not ETORO_API_KEY or not ETORO_USER_KEY:
        return {"error": "ETORO_API_KEY and ETORO_USER_KEY must be set in .env", "positions": []}

    portfolio_data = get_portfolio()

    if "error" in portfolio_data:
        return {"error": portfolio_data["error"], "detail": portfolio_data.get("detail", ""), "positions": []}

    positions = parse_positions(portfolio_data)
    # eToro's own total unrealized P&L (accurate, in account currency)
    total_pnl = portfolio_data.get("clientPortfolio", {}).get("unrealizedPnL", 0)

    return {
        "source": "etoro",
        "synced_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "positions": positions,
        "count": len(positions),
        "total_pnl": round(float(total_pnl), 2),
    }
