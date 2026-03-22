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
    """When ACTIVE, reason starts with 'wallbox_included_in_load'."""

    def test_reason_when_active(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=8000, user_w=1200, soc_pct=100))
        assert result.reason == "wallbox_included_in_load|forecast_unavailable"

    def test_reason_when_inactive(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=1000, user_w=500, soc_pct=50))
        assert result.reason == "surplus_below_threshold|forecast_unavailable"


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


# ===========================================================================
# Story 3.2 — Forecast-Driven SOC Target Adjustment
# ===========================================================================

# Config for forecast tests: midday window active (before=sunset-3h), March=80, Dec=100
MARCH_CONFIG: dict = {
    "wallbox_threshold_kw": 4.2,
    "hold_time_minutes": 10,
    "max_discharge_kw": 10.0,
    "battery_capacity_kwh": 10.0,
    "seasonal_targets": {3: 80, 12: 100},
    "time_strategy": [
        {"before": "sunrise+2h", "soc_floor": 100},
        {"before": "sunset-3h", "soc_floor": 50},
        {"default": True, "soc_floor": 80},
    ],
}


def _forecast_snap(
    se,
    *,
    cloud_avg: float,
    hour: int,
    month: int = 3,
    soc: float = 80.0,
    forecast_available: bool = True,
    solar_remaining=None,
    pv: float = 5000.0,
    load: float = 1200.0,
):
    """Build a SensorSnapshot with a ForecastData for forecast tests."""
    ts = datetime(2026, month, 21, hour, 0, 0)
    # sunrise well before hour; sunset well after: midday window active when hour<17
    sunrise = datetime(2026, month, 21, 6, 0, 0)
    sunset = datetime(2026, month, 21, 20, 0, 0)
    fd = se.ForecastData(
        forecast_available=forecast_available,
        cloud_coverage_avg=cloud_avg,
        solar_forecast_kwh_remaining=solar_remaining,
    )
    return se.SensorSnapshot(
        soc_percent=soc,
        power_to_grid_w=0.0,
        pv_production_w=pv,
        power_to_user_w=load,
        timestamp=ts,
        sunset_time=sunset,
        sunrise_time=sunrise,
        forecast=fd,
    )


class TestForecastAdjustment:
    """Story 3.2 — _apply_forecast_adjustment (AC1–AC8)."""

    # ── AC1 — Sunny forecast: floor unchanged, reason=forecast_good ──────────

    def test_ac1_sunny_floor_unchanged(self, se):
        """cloud<20, hour<15, solar ok → floor from get_soc_floor, tag=forecast_good."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(se, cloud_avg=10.0, hour=10, month=3, soc=80.0)
        base = calc.get_soc_floor(snap)
        adj_floor, tag = calc._apply_forecast_adjustment(snap, base)
        assert adj_floor == base
        assert tag == "forecast_good"

    def test_ac1_reason_in_calculate_surplus(self, se):
        """calculate_surplus reason contains 'forecast_good' when sunny."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(se, cloud_avg=10.0, hour=10, month=3, soc=80.0)
        result = calc.calculate_surplus(snap)
        assert "forecast_good" in result.reason

    def test_ac1_forecast_available_true(self, se):
        """result.forecast_available=True when ForecastData.forecast_available=True."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(se, cloud_avg=10.0, hour=10, month=3, soc=80.0)
        result = calc.calculate_surplus(snap)
        assert result.forecast_available is True

    # ── AC2 — Overcast forecast: floor raised to seasonal target ─────────────

    def test_ac2_march_floor_raised_to_80(self, se):
        """cloud>70, hour>=13, March → floor == 80."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(se, cloud_avg=80.0, hour=14, month=3, soc=55.0)
        adj_floor, tag = calc._apply_forecast_adjustment(snap, 50)
        assert adj_floor == 80
        assert tag == "forecast_poor"

    def test_ac2_december_floor_raised_to_100(self, se):
        """cloud>70, hour>=13, December → floor = 100."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(se, cloud_avg=90.0, hour=15, month=12, soc=60.0)
        adj_floor, tag = calc._apply_forecast_adjustment(snap, 50)
        assert adj_floor == 100
        assert tag == "forecast_poor"

    def test_ac2_reason_in_calculate_surplus(self, se):
        """calculate_surplus reason contains 'forecast_poor' when overcast."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(se, cloud_avg=80.0, hour=14, month=3, soc=55.0)
        result = calc.calculate_surplus(snap)
        assert "forecast_poor" in result.reason

    def test_ac2_forecast_available_true(self, se):
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(se, cloud_avg=80.0, hour=14, month=3, soc=55.0)
        result = calc.calculate_surplus(snap)
        assert result.forecast_available is True

    # ── AC3 — Forecast unavailable: no change ────────────────────────────────

    def test_ac3_forecast_false_floor_unchanged(self, se):
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=80.0, hour=14, month=3, soc=55.0, forecast_available=False
        )
        base = 55
        adj_floor, tag = calc._apply_forecast_adjustment(snap, base)
        assert adj_floor == base
        assert tag == "forecast_unavailable"

    def test_ac3_forecast_none_floor_unchanged(self, se):
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = se.SensorSnapshot(
            soc_percent=55.0,
            power_to_grid_w=0.0,
            pv_production_w=5000.0,
            power_to_user_w=1200.0,
            timestamp=datetime(2026, 3, 21, 14, 0, 0),
            sunset_time=datetime(2026, 3, 21, 20, 0, 0),
            sunrise_time=datetime(2026, 3, 21, 6, 0, 0),
            forecast=None,
        )
        adj_floor, tag = calc._apply_forecast_adjustment(snap, 55)
        assert adj_floor == 55
        assert tag == "forecast_unavailable"

    def test_ac3_forecast_available_false_in_result(self, se):
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=80.0, hour=14, month=3, soc=55.0, forecast_available=False
        )
        result = calc.calculate_surplus(snap)
        assert result.forecast_available is False

    # ── AC6 — Boundary: exactly at thresholds → neutral path ─────────────────

    def test_ac6_cloud_exactly_20_not_sunny(self, se):
        """cloud_avg=20 (not strictly <20) → sunny fast-path NOT taken."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(se, cloud_avg=20.0, hour=10, month=3, soc=80.0)
        base = 50
        _, tag = calc._apply_forecast_adjustment(snap, base)
        assert tag != "forecast_good"

    def test_ac6_cloud_exactly_70_not_overcast(self, se):
        """cloud_avg=70 (not strictly >70) → overcast fast-path NOT taken."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(se, cloud_avg=70.0, hour=13, month=3, soc=80.0)
        base = 50
        adj_floor, tag = calc._apply_forecast_adjustment(snap, base)
        assert tag not in ("forecast_poor", "forecast_solar_low")
        assert adj_floor == base

    # ── AC7 — Hard floor guarantee: adjusted floor never below SOC_HARD_FLOOR ─

    def test_ac7_seasonal_target_below_hard_floor_clamped(self, se):
        """seasonal_target=30 → clamped to SOC_HARD_FLOOR (50)."""
        cfg = {**MARCH_CONFIG, "seasonal_targets": {3: 30}}
        calc = se.SurplusCalculator(cfg)
        snap = _forecast_snap(se, cloud_avg=80.0, hour=14, month=3, soc=55.0)
        adj_floor, _ = calc._apply_forecast_adjustment(snap, 50)
        assert adj_floor >= se.SOC_HARD_FLOOR

    # ── AC8 — Low solar remaining: floor raised independent of cloud coverage ─

    def test_ac8_solar_low_raises_floor(self, se):
        """solar_remaining=1.5 < 2.0, hour>=12 → floor raised, tag=forecast_solar_low."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=50.0, hour=14, month=3, soc=55.0, solar_remaining=1.5
        )
        adj_floor, tag = calc._apply_forecast_adjustment(snap, 50)
        assert adj_floor >= 80
        assert tag == "forecast_solar_low"

    def test_ac8_solar_above_threshold_neutral(self, se):
        """solar_remaining=5.0 ≥ 2.0 → neutral path, floor unchanged."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=50.0, hour=14, month=3, soc=55.0, solar_remaining=5.0
        )
        base = 50
        adj_floor, tag = calc._apply_forecast_adjustment(snap, base)
        assert adj_floor == base
        assert tag == "forecast_neutral"

    def test_ac8_solar_none_cloud_neutral(self, se):
        """solar_remaining=None, cloud=50 (neutral) → neutral path."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=50.0, hour=14, month=3, soc=55.0, solar_remaining=None
        )
        base = 50
        adj_floor, tag = calc._apply_forecast_adjustment(snap, base)
        assert adj_floor == base
        assert tag == "forecast_neutral"

    def test_ac8_solar_low_before_noon_not_triggered(self, se):
        """solar_remaining=0.5 but hour=10 (<12) → not triggered (too early)."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=50.0, hour=10, month=3, soc=55.0, solar_remaining=0.5
        )
        base = 50
        adj_floor, tag = calc._apply_forecast_adjustment(snap, base)
        assert tag not in ("forecast_solar_low", "forecast_poor")
        assert adj_floor == base

    def test_ac8_reason_in_calculate_surplus(self, se):
        """calculate_surplus reason contains 'forecast_solar_low' when solar low."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=50.0, hour=14, month=3, soc=55.0, solar_remaining=1.5
        )
        result = calc.calculate_surplus(snap)
        assert "forecast_solar_low" in result.reason

    # ── CR Patch: boundary tests (hour=12 solar, hour=15 sunny, hour=12 cloud,
    #    solar=threshold, cross-path, custom threshold, NaN, caplog) ───────────

    def test_ac8_hour_exactly_12_triggers_solar_low(self, se):
        """hour=12 (>= 12) with solar below threshold → forecast_solar_low."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=50.0, hour=12, month=3, soc=55.0, solar_remaining=1.0
        )
        _, tag = calc._apply_forecast_adjustment(snap, 50)
        assert tag == "forecast_solar_low"

    def test_ac8_hour_11_does_not_trigger_solar_low(self, se):
        """hour=11 (< 12) with solar below threshold → NOT solar_low."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=50.0, hour=11, month=3, soc=55.0, solar_remaining=0.5
        )
        _, tag = calc._apply_forecast_adjustment(snap, 50)
        assert tag != "forecast_solar_low"

    def test_ac6_hour_15_not_sunny(self, se):
        """cloud<20: hour=15 (NOT < 15) → sunny fast-path NOT taken."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(se, cloud_avg=10.0, hour=15, month=3, soc=80.0)
        _, tag = calc._apply_forecast_adjustment(snap, 50)
        assert tag != "forecast_good"

    def test_ac6_hour_12_cloud_above_70_not_overcast(self, se):
        """cloud>70: hour=12 (NOT >= 13) → overcast path NOT taken."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(se, cloud_avg=80.0, hour=12, month=3, soc=80.0)
        _, tag = calc._apply_forecast_adjustment(snap, 50)
        assert tag != "forecast_poor"

    def test_ac8_solar_exactly_at_threshold_not_triggered(self, se):
        """solar_remaining=2.0 (== threshold, not < threshold) → NOT solar_low."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=50.0, hour=14, month=3, soc=55.0, solar_remaining=2.0
        )
        _, tag = calc._apply_forecast_adjustment(snap, 50)
        assert tag != "forecast_solar_low"

    def test_cross_path_sunny_cloud_but_solar_low(self, se):
        """cloud<20, hour=13 (in [12,14]), solar_remaining low → forecast_solar_low."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=10.0, hour=13, month=3, soc=55.0, solar_remaining=0.5
        )
        adj_floor, tag = calc._apply_forecast_adjustment(snap, 50)
        assert tag == "forecast_solar_low"
        assert adj_floor >= 80

    def test_ac8_custom_threshold_config(self, se):
        """Custom solar_remaining_threshold_kwh=5.0 → solar=3.0 triggers solar_low."""
        cfg = {**MARCH_CONFIG, "solar_remaining_threshold_kwh": 5.0}
        calc = se.SurplusCalculator(cfg)
        snap = _forecast_snap(
            se, cloud_avg=50.0, hour=14, month=3, soc=55.0, solar_remaining=3.0
        )
        adj_floor, tag = calc._apply_forecast_adjustment(snap, 50)
        assert tag == "forecast_solar_low"
        assert adj_floor >= 80

    def test_nan_cloud_treated_as_neutral(self, se):
        """NaN cloud_coverage_avg → sanitised to 50.0 (neutral)."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=float("nan"), hour=14, month=3, soc=80.0
        )
        _, tag = calc._apply_forecast_adjustment(snap, 50)
        assert tag == "forecast_neutral"

    def test_nan_solar_remaining_treated_as_none(self, se):
        """NaN solar_forecast_kwh_remaining → sanitised to None (neutral)."""
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=50.0, hour=14, month=3, soc=80.0,
            solar_remaining=float("nan"),
        )
        _, tag = calc._apply_forecast_adjustment(snap, 50)
        # NaN → None, cloud=50 neutral → forecast_neutral
        assert tag == "forecast_neutral"

    def test_ac3_no_warning_logged(self, se, caplog):
        """AC3: forecast unavailable → no WARNING logged."""
        import logging
        calc = se.SurplusCalculator(MARCH_CONFIG)
        snap = _forecast_snap(
            se, cloud_avg=80.0, hour=14, month=3, soc=55.0, forecast_available=False
        )
        with caplog.at_level(logging.WARNING):
            calc.calculate_surplus(snap)
        assert not any(
            r.levelno >= logging.WARNING for r in caplog.records
        ), f"Unexpected WARNING records: {[r.message for r in caplog.records if r.levelno >= logging.WARNING]}"


# ===========================================================================
# Story 4.3 — Hard SOC Floor Enforcement
# ===========================================================================

class TestHardSocFloorEnforcement:
    """AC1–AC4 for Story 4.3: SOC_HARD_FLOOR = 50% absolute protection."""

    # ── AC3 — SOC below hard floor: FAILSAFE ─────────────────────────────────

    def test_soc_below_hard_floor_returns_failsafe(self, se):
        """AC3: SOC=48 < 50 → charging_state=FAILSAFE, reported_kw=0, no exception."""
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=8000, user_w=500, soc_pct=48))
        assert result.charging_state == "FAILSAFE"
        assert result.reported_kw == pytest.approx(0.0)
        assert result.reason == "SOC below hard floor"
        assert result.real_surplus_kw == pytest.approx(0.0)
        assert result.buffer_used_kw == pytest.approx(0.0)
        assert result.soc_floor_active == 50
        assert result.forecast_available is False

    def test_soc_far_below_hard_floor_returns_failsafe(self, se):
        """AC3 edge: SOC=0 → FAILSAFE, no exception."""
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        result = calc.calculate_surplus(_snap(se, pv_w=8000, user_w=0, soc_pct=0))
        assert result.charging_state == "FAILSAFE"
        assert result.reported_kw == pytest.approx(0.0)

    # ── AC2 — SOC exactly at hard floor: zero buffer ──────────────────────────

    def test_soc_at_hard_floor_zero_buffer(self, se):
        """AC2: SOC=50 == floor=50 → buffer_used_kw=0, reported_kw = real surplus."""
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        # PV=8000W, user=500W → real_surplus = 7.5 kW ≥ threshold → ACTIVE
        result = calc.calculate_surplus(_snap(se, pv_w=8000, user_w=500, soc_pct=50))
        assert result.buffer_used_kw == pytest.approx(0.0)
        assert result.real_surplus_kw == pytest.approx(7.5)
        assert result.reported_kw == pytest.approx(result.real_surplus_kw)
        assert result.charging_state == "ACTIVE"

    # ── AC1 — SOC near floor: buffer capped by headroom formula ──────────────

    def test_soc_near_floor_buffer_capped(self, se):
        """AC1: SOC=51, battery=10kWh, hold=10min → buffer_kw_max ≈ 0.6 kW caps the draw.

        Proof: headroom=1%, buffer_energy=0.1 kWh, buffer_kw_max=min(10, 0.1/(10/60))=0.6 kW
        Use threshold=2.9 so gap=0.6 exactly → buffer fills to cap → ACTIVE.
        """
        cfg = {
            "wallbox_threshold_kw": 2.9,  # reachable: real_surplus(2.3)+buffer(0.6)=2.9
            "max_discharge_kw": 10.0,
            "battery_capacity_kwh": 10.0,
            "hold_time_minutes": 10,
            "time_strategy": [{"default": True, "soc_floor": 50}],
        }
        calc = se.SurplusCalculator(cfg)
        # real_surplus = (2500 - 200) / 1000 = 2.3 kW; gap = 2.9 - 2.3 = 0.6 kW
        # buffer_kw_max = min(10, 0.1/(10/60)) = 0.6 kW (headroom-limited)
        # buffer_used = min(0.6, 0.6) = 0.6 kW; augmented = 2.9 → ACTIVE
        result = calc.calculate_surplus(_snap(se, pv_w=2500, user_w=200, soc_pct=51))
        assert result.charging_state == "ACTIVE"
        assert result.buffer_used_kw == pytest.approx(0.6, abs=1e-6)
        assert result.soc_floor_active == 50

    # ── AC4 — Misconfigured soc_floor clamped with one-time warning ───────────

    def test_misconfigured_floor_clamped_and_warned_once(self, se, caplog):
        """AC4: time_strategy soc_floor=30 → clamped to 50, warning emitted once."""
        import logging
        cfg = {
            "wallbox_threshold_kw": 4.2,
            "max_discharge_kw": 10.0,
            "battery_capacity_kwh": 10.0,
            "hold_time_minutes": 10,
            "time_strategy": [{"before": "23:59", "soc_floor": 30}],
        }
        calc = se.SurplusCalculator(cfg)
        snap = _snap(se, pv_w=5000, user_w=500, soc_pct=70)
        with caplog.at_level(logging.WARNING):
            floor1 = calc.get_soc_floor(snap)
            floor2 = calc.get_soc_floor(snap)
        # Floor must be clamped to 50 in both calls
        assert floor1 == 50
        assert floor2 == 50
        # Warning must be emitted exactly once (one-time guard)
        clamp_warnings = [
            r for r in caplog.records
            if "Clamping" in r.message and r.levelno == logging.WARNING
        ]
        assert len(clamp_warnings) == 1


# ===========================================================================
# Story 5.1 — AC2: Required 11 test functions (standalone, using se + conftest)
# ===========================================================================

from datetime import datetime, timezone  # noqa: E402 (after class definitions)


def test_normal_sunny_day(se, make_snapshot, base_config):
    """PV=8000W, user=1200W, SOC=100% → real_surplus=6.8, buffer=0, ACTIVE."""
    snapshot = make_snapshot(soc_percent=100.0, pv_production_w=8000.0, power_to_user_w=1200.0)
    calc = se.SurplusCalculator(base_config)
    result = calc.calculate_surplus(snapshot)
    assert result.real_surplus_kw == pytest.approx(6.8)
    assert result.buffer_used_kw == pytest.approx(0.0)
    assert result.reported_kw == pytest.approx(6.8)
    assert result.charging_state == "ACTIVE"


def test_cloudy_buffer_fills_gap(se, make_snapshot, base_config):
    """PV=3500W, user=1200W, SOC=95%, floor=50 (midday) → buffer fills 1.9 kW gap → ACTIVE."""
    snapshot = make_snapshot(soc_percent=95.0, pv_production_w=3500.0, power_to_user_w=1200.0)
    calc = se.SurplusCalculator(base_config)
    result = calc.calculate_surplus(snapshot)
    assert result.real_surplus_kw == pytest.approx(2.3)
    assert result.buffer_used_kw == pytest.approx(1.9)
    assert result.reported_kw == pytest.approx(4.2)
    assert result.charging_state == "ACTIVE"


def test_soc_at_hard_floor_no_buffer(se, make_snapshot, base_config):
    """PV=2000W, user=1000W, SOC=50% → soc_headroom=0 → buffer=0, INACTIVE."""
    snapshot = make_snapshot(soc_percent=50.0, pv_production_w=2000.0, power_to_user_w=1000.0)
    calc = se.SurplusCalculator(base_config)
    result = calc.calculate_surplus(snapshot)
    assert result.buffer_used_kw == pytest.approx(0.0)
    assert result.reported_kw == pytest.approx(0.0)
    assert result.charging_state == "INACTIVE"


def test_soc_below_hard_floor_failsafe(se, make_snapshot, base_config):
    """SOC=48% < SOC_HARD_FLOOR (50) → FAILSAFE guard fires immediately."""
    snapshot = make_snapshot(soc_percent=48.0, pv_production_w=8000.0, power_to_user_w=1200.0)
    calc = se.SurplusCalculator(base_config)
    result = calc.calculate_surplus(snapshot)
    assert result.reported_kw == pytest.approx(0.0)
    assert result.charging_state == "FAILSAFE"
    assert "hard floor" in result.reason.lower()
    assert result.buffer_used_kw == pytest.approx(0.0)


def test_time_window_morning_floor_100(se, make_snapshot, base_config):
    """timestamp=09:00 (before 11:00) → first rule matches → floor=100."""
    snapshot = make_snapshot(timestamp=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc))
    calc = se.SurplusCalculator(base_config)
    assert calc.get_soc_floor(snapshot) == 100


def test_time_window_free_window_floor_50(se, make_snapshot, base_config):
    """timestamp=12:30, sunset=18:00 → after 11:00, before 15:00=sunset-3h → floor=50."""
    snapshot = make_snapshot(
        timestamp=datetime(2026, 3, 15, 12, 30, tzinfo=timezone.utc),
        sunset_time=datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc),
    )
    calc = se.SurplusCalculator(base_config)
    assert calc.get_soc_floor(snapshot) == 50


def test_time_window_evening_floor_80(se, make_snapshot, base_config):
    """timestamp=16:00, sunset=18:00 → past 15:00=sunset-3h → default rule → seasonal[3]=80."""
    snapshot = make_snapshot(
        timestamp=datetime(2026, 3, 15, 16, 0, tzinfo=timezone.utc),
        sunset_time=datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc),
    )
    calc = se.SurplusCalculator(base_config)
    assert calc.get_soc_floor(snapshot) == 80


def test_time_window_no_sunset_uses_default(se, make_snapshot, base_config):
    """sunset_time=None → 'sunset-3h' token unresolvable → rule skipped → default → floor=80."""
    snapshot = make_snapshot(
        timestamp=datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
        sunset_time=None,  # explicit None — NOT the default 18:00
    )
    calc = se.SurplusCalculator(base_config)
    assert calc.get_soc_floor(snapshot) == 80


def test_forecast_good_floor_unchanged(se, make_snapshot, base_config):
    """cloud=10 (<20), hour=9 (<15) → forecast_good, floor stays 100 (morning window)."""
    snapshot = make_snapshot(
        timestamp=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
        pv_production_w=8000.0,
        soc_percent=80.0,
        forecast=se.ForecastData(forecast_available=True, cloud_coverage_avg=10.0),
    )
    calc = se.SurplusCalculator(base_config)
    result = calc.calculate_surplus(snapshot)
    assert result.forecast_available is True
    assert "forecast_good" in result.reason
    assert result.soc_floor_active == 100


def test_forecast_poor_floor_raised(se, make_snapshot, base_config):
    """cloud=85 (>70), hour=14 (>=13) → forecast_poor, floor raised 50→80 (seasonal[3])."""
    snapshot = make_snapshot(
        timestamp=datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc),
        sunset_time=datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc),
        pv_production_w=3500.0,
        soc_percent=80.0,
        forecast=se.ForecastData(forecast_available=True, cloud_coverage_avg=85.0),
    )
    calc = se.SurplusCalculator(base_config)
    result = calc.calculate_surplus(snapshot)
    assert result.forecast_available is True
    assert "forecast_poor" in result.reason
    assert result.soc_floor_active == 80  # raised from midday floor=50 to seasonal=80


def test_forecast_unavailable_conservative(se, make_snapshot, base_config):
    """ForecastData(forecast_available=False) → no crash, floor unchanged, no exception."""
    snapshot = make_snapshot(
        pv_production_w=8000.0,
        soc_percent=80.0,
        forecast=se.ForecastData(forecast_available=False),
    )
    calc = se.SurplusCalculator(base_config)
    result = calc.calculate_surplus(snapshot)
    assert result.forecast_available is False
    assert result.charging_state in ("ACTIVE", "INACTIVE")
    # Floor must not exceed base time-window value (midday=50, no forecast forcing)
    assert result.soc_floor_active == 50

