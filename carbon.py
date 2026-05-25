import time
from datetime import datetime, timezone

import httpx

_cache: dict = {"data": None, "ts": 0}
_CACHE_TTL = 300
_BASE = "https://api.carbonintensity.org.uk"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_current_intensity() -> dict:
    r = httpx.get(f"{_BASE}/intensity", timeout=10)
    r.raise_for_status()
    return r.json()["data"][0]["intensity"]


def get_forecast() -> list[dict]:
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < _CACHE_TTL:
        return _cache["data"]
    try:
        r = httpx.get(f"{_BASE}/intensity/fw24h", timeout=10)
        r.raise_for_status()
        slots = r.json()["data"]
        _cache["data"] = slots
        _cache["ts"] = now
        return slots
    except Exception:
        return _cache["data"] or []


def best_window_before(deadline: datetime) -> tuple[datetime | None, float | None]:
    slots = get_forecast()
    if not slots:
        return None, None

    now = _now()
    candidates = []
    for slot in slots:
        try:
            slot_from = datetime.fromisoformat(slot["from"].replace("Z", "+00:00"))
            slot_to   = datetime.fromisoformat(slot["to"].replace("Z", "+00:00"))
            intensity = slot["intensity"]["forecast"]
        except (KeyError, ValueError):
            continue
        if slot_from >= now and slot_to <= deadline:
            candidates.append((slot_from, intensity))

    if not candidates:
        return None, None

    best = min(candidates, key=lambda x: x[1])
    return best[0], best[1]
