from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from carbon import best_window_before


def _slot(hours_ahead: float, intensity: int) -> dict:
    base = datetime.now(timezone.utc)
    frm  = base + timedelta(hours=hours_ahead)
    to   = frm  + timedelta(minutes=30)
    return {"from": frm.isoformat(), "to": to.isoformat(), "intensity": {"forecast": intensity}}


def _deadline(hours: float) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def test_picks_lowest_intensity():
    slots = [_slot(1, 200), _slot(2, 80), _slot(3, 150)]
    with patch("carbon.get_forecast", return_value=slots):
        _, gco2 = best_window_before(_deadline(6))
    assert gco2 == 80


def test_excludes_slots_beyond_deadline():
    slots = [_slot(1, 300), _slot(5, 50)]
    with patch("carbon.get_forecast", return_value=slots):
        _, gco2 = best_window_before(_deadline(3))
    assert gco2 == 300


def test_returns_none_on_empty_forecast():
    with patch("carbon.get_forecast", return_value=[]):
        window, gco2 = best_window_before(_deadline(4))
    assert window is None and gco2 is None


def test_excludes_past_slots():
    slots = [_slot(-1, 50), _slot(1, 200)]
    with patch("carbon.get_forecast", return_value=slots):
        _, gco2 = best_window_before(_deadline(3))
    assert gco2 == 200


def test_skips_malformed_slots():
    slots = [{"from": "bad", "to": "bad", "intensity": {"forecast": 10}}, _slot(1, 180)]
    with patch("carbon.get_forecast", return_value=slots):
        _, gco2 = best_window_before(_deadline(3))
    assert gco2 == 180


def test_returns_none_when_forecast_unavailable():
    with patch("carbon.get_forecast", return_value=None):
        window, gco2 = best_window_before(_deadline(4))
    assert window is None and gco2 is None
