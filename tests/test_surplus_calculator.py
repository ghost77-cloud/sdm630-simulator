"""Tests for Story 2.2 — Surplus Calculation with Battery Buffer.

Covers all Acceptance Criteria:
  AC1 — Buffer fills gap to threshold
  AC2 — Ample PV: no buffer needed
  AC3 — SOC exactly at floor: zero buffer available
  AC4 — Cannot meet threshold: INACTIVE
  AC5 — soc_floor_active is populated
  AC6 — Wallbox load included in surplus formula
"""
from __future__ import annotations

import importlib.util
import os
import sys
from datetime import datetime

import pytest

# ---------------------------------------------------------------------------
# Module loading helper — standalone, no HA runtime
# ---------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODULE_PATH = os.path.join(ROOT, "surplus_engine.py")
_MODULE_NAME = "surplus_engine"


@pytest.fixture(scope="module")
def se():
    """Load surplus_engine as standalone module (no HA runtime needed)."""
    sys.modules.pop(_MODULE_NAME, None)
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 6, 15, 12, 0, 0)

# Config with seasonal targets — floor varies by month (June = 70)
STANDARD_CONFIG: dict = {
    "wallbox_threshold_kw": 4.2,
    "max_discharge_kw": 10.0,
    "battery_capacity_kwh": 10.0,
    "hold_time_minutes": 10,
    "time_strategy": [{"default": True, "soc_floor": 50}],
    "seasonal_targets": {
        1: 100, 2: 90, 3: 80, 4: 70, 5: 70, 6: 70,
        7: 70, 8: 70, 9: 80, 10: 90, 11: 100, 12: 100,
    },
}

# Config without seasonal_targets — floor resolves to exactly 50
# (matches AC1/AC3/AC4 spec conditions)
FLOOR_50_CONFIG: dict = {
    "wallbox_threshold_kw": 4.2,
    "max_discharge_kw": 10.0,
    "battery_capacity_kwh": 10.0,
    "hold_time_minutes": 10,
    "time_strategy": [{"default": True, "soc_floor": 50}],
}


def _snap(se, *, pv_w, user_w, soc_pct, forecast=None):
    return se.SensorSnapshot(
        soc_percent=soc_pct,
        power_to_grid_w=0.0,
        pv_production_w=pv_w,
        power_to_user_w=user_w,
        timestamp=NOW,
        sunset_time=None,
        sunrise_time=None,
        forecast=forecast,
    )


# ===========================================================================
# AC1 — Buffer fills gap to threshold
# ===========================================================================

class TestAC1BufferFillsGap:
    """PV=3500 W, user=1200 W, SOC=95%, floor=50 → buffer fills 1.9 kW gap."""

    def test_real_surplus_kw(self, se):
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=3500, user_w=1200, soc_pct=95))
        assert result.real_surplus_kw == pytest.approx(2.3)

    def test_buffer_used_kw(self, se):
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=3500, user_w=1200, soc_pct=95))
        assert result.buffer_used_kw == pytest.approx(1.9)

    def test_reported_kw_at_threshold(self, se):
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=3500, user_w=1200, soc_pct=95))
        assert result.reported_kw == pytest.approx(4.2)

    def test_charging_state_active(self, se):
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=3500, user_w=1200, soc_pct=95))
        assert result.charging_state == "ACTIVE"

    def test_soc_floor_active_is_50(self, se):
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=3500, user_w=1200, soc_pct=95))
        assert result.soc_floor_active == 50

    def test_buffer_used_positive(self, se):
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=3500, user_w=1200, soc_pct=95))
        assert result.buffer_used_kw > 0


# ===========================================================================
# AC2 — Ample PV: no buffer needed
# ===========================================================================

class TestAC2AmplePV:
    """PV=8000 W, user=1200 W, SOC=100% → real surplus=6.8, buffer=0."""

    def test_real_surplus_kw(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=8000, user_w=1200, soc_pct=100))
        assert result.real_surplus_kw == pytest.approx(6.8)

    def test_buffer_used_zero(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=8000, user_w=1200, soc_pct=100))
        assert result.buffer_used_kw == pytest.approx(0.0)

    def test_reported_kw_equals_real(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=8000, user_w=1200, soc_pct=100))
        assert result.reported_kw == pytest.approx(6.8)

    def test_charging_state_active(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=8000, user_w=1200, soc_pct=100))
        assert result.charging_state == "ACTIVE"


# ===========================================================================
# AC3 — SOC exactly at floor: zero buffer available
# ===========================================================================

class TestAC3SocAtFloor:
    """SOC=50% == floor=50% → soc_headroom=0 → buffer_used=0."""

    def test_buffer_used_zero_when_soc_at_floor(self, se):
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=3500, user_w=1200, soc_pct=50))
        assert result.buffer_used_kw == pytest.approx(0.0)

    def test_reported_equals_real_when_above_threshold(self, se):
        """real surplus 4.5 kW ≥ threshold, no buffer needed → reported=4.5."""
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=5700, user_w=1200, soc_pct=50))
        assert result.real_surplus_kw == pytest.approx(4.5)
        assert result.reported_kw == pytest.approx(4.5)
        assert result.charging_state == "ACTIVE"

    def test_inactive_when_real_below_threshold_no_buffer(self, se):
        """real surplus 2.3 kW < threshold, SOC at floor → INACTIVE."""
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=3500, user_w=1200, soc_pct=50))
        assert result.reported_kw == pytest.approx(0.0)
        assert result.charging_state == "INACTIVE"


# ===========================================================================
# AC4 — Cannot meet threshold: INACTIVE
# ===========================================================================

class TestAC4CannotMeetThreshold:
    """real surplus < threshold AND SOC at floor → reported=0, INACTIVE."""

    def test_reported_zero(self, se):
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=1000, user_w=500, soc_pct=50))
        assert result.reported_kw == pytest.approx(0.0)

    def test_charging_state_inactive(self, se):
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=1000, user_w=500, soc_pct=50))
        assert result.charging_state == "INACTIVE"

    def test_buffer_used_zero_when_inactive(self, se):
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=1000, user_w=500, soc_pct=50))
        assert result.buffer_used_kw == pytest.approx(0.0)

    def test_negative_real_surplus_inactive(self, se):
        """Night scenario: PV=0, user=1200 → real=-1.2 → INACTIVE."""
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=0, user_w=1200, soc_pct=50))
        assert result.real_surplus_kw == pytest.approx(-1.2)
        assert result.reported_kw == pytest.approx(0.0)
        assert result.charging_state == "INACTIVE"


# ===========================================================================
# AC5 — soc_floor_active is populated
# ===========================================================================

class TestAC5SocFloorActive:
    """soc_floor_active must contain the floor returned by get_soc_floor."""

    def test_soc_floor_active_populated(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=3500, user_w=1200, soc_pct=95))
        # June seasonal target = 70; default rule uses seasonal_targets
        assert result.soc_floor_active == 70

    def test_soc_floor_active_is_int(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=3500, user_w=1200, soc_pct=95))
        assert isinstance(result.soc_floor_active, int)

    def test_soc_floor_active_matches_get_soc_floor(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        snap = _snap(se, pv_w=3500, user_w=1200, soc_pct=95)
        result = calc.calculate_surplus(snap)
        expected_floor = calc.get_soc_floor(snap)
        assert result.soc_floor_active == expected_floor


# ===========================================================================
# AC6 — Wallbox load included in surplus formula
# ===========================================================================

class TestAC6WallboxIncludedInLoad:
    """When ACTIVE, reason contains 'wallbox_included_in_load'."""

    def test_reason_when_active(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=8000, user_w=1200, soc_pct=100))
        assert result.reason == "wallbox_included_in_load"

    def test_reason_when_inactive(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=1000, user_w=500, soc_pct=50))
        assert result.reason == "surplus_below_threshold"


# ===========================================================================
# EvaluationResult field completeness
# ===========================================================================

class TestResultFields:
    """All 8 EvaluationResult fields must be set correctly in every call."""

    def test_all_fields_set_active(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        snap = _snap(se, pv_w=8000, user_w=1200, soc_pct=100.0)
        result = calc.calculate_surplus(snap)
        assert isinstance(result.reported_kw, float)
        assert isinstance(result.real_surplus_kw, float)
        assert isinstance(result.buffer_used_kw, float)
        assert isinstance(result.soc_percent, float)
        assert isinstance(result.soc_floor_active, int)
        assert isinstance(result.charging_state, str)
        assert isinstance(result.reason, str)
        assert isinstance(result.forecast_available, bool)

    def test_soc_percent_copied_through(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=8000, user_w=1200, soc_pct=87.5))
        assert result.soc_percent == pytest.approx(87.5)

    def test_forecast_available_true_when_forecast_set(self, se):
        fd = se.ForecastData(forecast_available=True)
        snap = _snap(se, pv_w=8000, user_w=1200, soc_pct=100, forecast=fd)
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(snap)
        assert result.forecast_available is True

    def test_forecast_available_false_when_no_forecast(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=8000, user_w=1200, soc_pct=100))
        assert result.forecast_available is False


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_hold_time_zero_no_division_error(self, se):
        """hold_time_minutes=0 must not raise ZeroDivisionError."""
        cfg = {**STANDARD_CONFIG, "hold_time_minutes": 0}
        calc = se.SurplusCalculator(cfg)
        result = calc.calculate_surplus(_snap(se, pv_w=3500, user_w=1200, soc_pct=95))
        assert isinstance(result, se.EvaluationResult)

    def test_power_to_user_zero(self, se):
        """power_to_user=0 → real surplus = full PV output."""
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=5000, user_w=0, soc_pct=80))
        assert result.real_surplus_kw == pytest.approx(5.0)

    def test_reported_kw_never_negative(self, se):
        """reported_kw must always be ≥ 0."""
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=0, user_w=5000, soc_pct=50))
        assert result.reported_kw >= 0.0

    def test_buffer_used_never_exceeds_gap(self, se):
        """buffer_used_kw must not exceed (threshold - real_surplus)."""
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        snap = _snap(se, pv_w=3500, user_w=1200, soc_pct=95)
        result = calc.calculate_surplus(snap)
        gap = max(0.0, STANDARD_CONFIG["wallbox_threshold_kw"] - result.real_surplus_kw)
        assert result.buffer_used_kw <= gap + 1e-9
