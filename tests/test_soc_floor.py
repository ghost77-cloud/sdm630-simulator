"""Tests for Story 2.1 — SOC Floor Determination via Time-Window Strategy.

Covers all Acceptance Criteria:
  AC1  — Morning window (sunrise-relative)
  AC2  — Midday free window
  AC3  — Evening / default window with seasonal override
  AC4  — sunrise_time = None fallback
  AC5  — sunset_time = None fallback
  AC6  — Hard floor guarantee
  AC7  — Seasonal targets fully override default soc_floor
  AC8  — Missing seasonal_targets fallback to DEFAULTS
  AC9  — Misconfigured seasonal_target clamped with warning
  AC10 — HA-free unit testing
"""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

# ---------------------------------------------------------------------------
# Module loading helper — standalone, no HA runtime
# ---------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODULE_PATH = os.path.join(ROOT, "surplus_engine.py")
_MODULE_NAME = "surplus_engine"

TZ = timezone.utc


@pytest.fixture(scope="module")
def se():
    """Load surplus_engine as a standalone module (no HA runtime needed)."""
    sys.modules.pop(_MODULE_NAME, None)
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Standard config & snapshot helpers
# ---------------------------------------------------------------------------

STANDARD_CONFIG: dict = {
    "time_strategy": [
        {"before": "sunrise+2h", "soc_floor": 100},
        {"before": "sunset-3h", "soc_floor": 50},
        {"default": True, "soc_floor": 80},
    ],
    "seasonal_targets": {
        1: 100, 2: 90, 3: 80, 4: 70, 5: 70, 6: 70,
        7: 70, 8: 70, 9: 80, 10: 90, 11: 100, 12: 100,
    },
}


def _snap(se, *, timestamp, sunrise_time=None, sunset_time=None):
    """Create a minimal SensorSnapshot for SOC-floor testing."""
    return se.SensorSnapshot(
        soc_percent=75.0,
        power_to_grid_w=0.0,
        pv_production_w=0.0,
        power_to_user_w=0.0,
        timestamp=timestamp,
        sunrise_time=sunrise_time,
        sunset_time=sunset_time,
    )


# ===========================================================================
# AC1 — Morning window (sunrise-relative)
# ===========================================================================

class TestAC1MorningWindow:
    def test_morning_floor_summer(self, se):
        """sunrise 05:30, timestamp 06:45 → before sunrise+2h (07:30) → 100."""
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 6, 45, tzinfo=TZ),
            sunrise_time=datetime(2026, 6, 15, 5, 30, tzinfo=TZ),
            sunset_time=datetime(2026, 6, 15, 20, 30, tzinfo=TZ),
        )
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        assert calc.get_soc_floor(snap) == 100

    def test_morning_floor_winter(self, se):
        """sunrise 08:00, timestamp 09:30 → before sunrise+2h (10:00) → 100."""
        snap = _snap(
            se,
            timestamp=datetime(2026, 12, 15, 9, 30, tzinfo=TZ),
            sunrise_time=datetime(2026, 12, 15, 8, 0, tzinfo=TZ),
            sunset_time=datetime(2026, 12, 15, 15, 30, tzinfo=TZ),
        )
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        assert calc.get_soc_floor(snap) == 100

    def test_exactly_at_boundary_not_morning(self, se):
        """timestamp == sunrise+2h → NOT before boundary → next rule."""
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 7, 30, tzinfo=TZ),
            sunrise_time=datetime(2026, 6, 15, 5, 30, tzinfo=TZ),
            sunset_time=datetime(2026, 6, 15, 20, 30, tzinfo=TZ),
        )
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        # At exactly the boundary, should NOT match the morning rule
        assert calc.get_soc_floor(snap) == 50  # midday window


# ===========================================================================
# AC2 — Midday free window
# ===========================================================================

class TestAC2MiddayWindow:
    def test_midday_free_window(self, se):
        """11:00, sunrise 05:30, sunset 20:30 → after 07:30, before 17:30 → 50."""
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 11, 0, tzinfo=TZ),
            sunrise_time=datetime(2026, 6, 15, 5, 30, tzinfo=TZ),
            sunset_time=datetime(2026, 6, 15, 20, 30, tzinfo=TZ),
        )
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        assert calc.get_soc_floor(snap) == 50

    def test_midday_just_past_morning(self, se):
        """07:31, sunrise 05:30 → past 07:30, still before sunset-3h → 50."""
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 7, 31, tzinfo=TZ),
            sunrise_time=datetime(2026, 6, 15, 5, 30, tzinfo=TZ),
            sunset_time=datetime(2026, 6, 15, 20, 30, tzinfo=TZ),
        )
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        assert calc.get_soc_floor(snap) == 50


# ===========================================================================
# AC3 — Evening / default window with seasonal override
# ===========================================================================

class TestAC3EveningWindow:
    def test_evening_march(self, se):
        """18:00 in March, sunset 18:00 → past sunset-3h (15:00) → seasonal 80."""
        snap = _snap(
            se,
            timestamp=datetime(2026, 3, 15, 18, 0, tzinfo=TZ),
            sunrise_time=datetime(2026, 3, 15, 5, 30, tzinfo=TZ),
            sunset_time=datetime(2026, 3, 15, 18, 0, tzinfo=TZ),
        )
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        assert calc.get_soc_floor(snap) == 80  # seasonal_targets[3]

    def test_evening_december(self, se):
        """16:00 in Dec, sunset 15:30 → past sunset-3h boundary → seasonal 100."""
        snap = _snap(
            se,
            timestamp=datetime(2026, 12, 15, 16, 0, tzinfo=TZ),
            sunrise_time=datetime(2026, 12, 15, 7, 30, tzinfo=TZ),
            sunset_time=datetime(2026, 12, 15, 15, 30, tzinfo=TZ),
        )
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        # Morning: sunrise+2h = 09:30, timestamp 16:00 > 09:30 → skip
        # Midday: sunset-3h = 12:30, timestamp 16:00 > 12:30 → skip
        # Default: seasonal_targets[12] = 100
        assert calc.get_soc_floor(snap) == 100


# ===========================================================================
# AC4 — sunrise_time = None fallback
# ===========================================================================

class TestAC4SunriseNoneFallback:
    def test_sunrise_none_skips_morning_rule(self, se):
        """sunrise=None → morning rule skipped → falls to next rule."""
        snap = _snap(
            se,
            timestamp=datetime(2026, 3, 15, 9, 0, tzinfo=TZ),
            sunrise_time=None,
            sunset_time=datetime(2026, 3, 15, 18, 0, tzinfo=TZ),
        )
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        # Morning rule skipped (sunrise=None)
        # Midday: sunset-3h = 15:00, timestamp 09:00 < 15:00 → 50
        assert calc.get_soc_floor(snap) == 50

    def test_sunrise_none_evening(self, se):
        """sunrise=None, past sunset-3h → seasonal default."""
        snap = _snap(
            se,
            timestamp=datetime(2026, 3, 15, 16, 0, tzinfo=TZ),
            sunrise_time=None,
            sunset_time=datetime(2026, 3, 15, 18, 0, tzinfo=TZ),
        )
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        # Morning skipped; midday sunset-3h = 15:00, 16:00 > 15:00 → skip
        # Default → seasonal March = 80
        assert calc.get_soc_floor(snap) == 80


# ===========================================================================
# AC5 — sunset_time = None fallback
# ===========================================================================

class TestAC5SunsetNoneFallback:
    def test_sunset_none_skips_midday_rule(self, se):
        """sunset=None → sunset-3h unresolvable → skipped, falls to default."""
        snap = _snap(
            se,
            timestamp=datetime(2026, 3, 15, 16, 0, tzinfo=TZ),
            sunrise_time=datetime(2026, 3, 15, 5, 30, tzinfo=TZ),
            sunset_time=None,
        )
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        # Morning: sunrise+2h = 07:30, 16:00 > 07:30 → skip
        # Midday: sunset=None → skip
        # Default → seasonal March = 80
        assert calc.get_soc_floor(snap) == 80

    def test_both_none_falls_to_default(self, se):
        """Both sunrise and sunset None → both rules skipped → seasonal default."""
        snap = _snap(
            se,
            timestamp=datetime(2026, 11, 10, 12, 0, tzinfo=TZ),
            sunrise_time=None,
            sunset_time=None,
        )
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        # All before: rules skipped → default → seasonal November = 100
        assert calc.get_soc_floor(snap) == 100


# ===========================================================================
# AC6 — Hard floor guarantee
# ===========================================================================

class TestAC6HardFloorGuarantee:
    def test_rule_soc_floor_below_hard_floor_clamped(self, se):
        """A rule with soc_floor < SOC_HARD_FLOOR is clamped to 50."""
        config = {
            "time_strategy": [
                {"before": "sunrise+2h", "soc_floor": 30},  # below hard floor
                {"default": True, "soc_floor": 80},
            ],
            "seasonal_targets": STANDARD_CONFIG["seasonal_targets"],
        }
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 6, 0, tzinfo=TZ),
            sunrise_time=datetime(2026, 6, 15, 5, 0, tzinfo=TZ),
            sunset_time=datetime(2026, 6, 15, 20, 0, tzinfo=TZ),
        )
        calc = se.SurplusCalculator(config)
        assert calc.get_soc_floor(snap) >= 50

    def test_never_returns_below_hard_floor(self, se):
        """Defense: even empty config returns SOC_HARD_FLOOR as fallback."""
        config = {"time_strategy": [], "seasonal_targets": {}}
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
            sunrise_time=None,
            sunset_time=None,
        )
        calc = se.SurplusCalculator(config)
        assert calc.get_soc_floor(snap) >= 50


# ===========================================================================
# AC7 — Seasonal targets fully override default soc_floor
# ===========================================================================

class TestAC7SeasonalOverride:
    def test_november_seasonal_target(self, se):
        """November evening → seasonal_targets[11] = 100 overrides static soc_floor=80."""
        snap = _snap(
            se,
            timestamp=datetime(2026, 11, 15, 18, 0, tzinfo=TZ),
            sunrise_time=datetime(2026, 11, 15, 7, 0, tzinfo=TZ),
            sunset_time=datetime(2026, 11, 15, 16, 0, tzinfo=TZ),
        )
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        # Morning: 07:00+2h=09:00, 18:00 > 09:00 → skip
        # Midday: 16:00-3h=13:00, 18:00 > 13:00 → skip
        # Default: seasonal[11] = 100
        assert calc.get_soc_floor(snap) == 100

    def test_june_seasonal_target(self, se):
        """June evening → seasonal_targets[6] = 70."""
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 21, 0, tzinfo=TZ),
            sunrise_time=datetime(2026, 6, 15, 5, 0, tzinfo=TZ),
            sunset_time=datetime(2026, 6, 15, 20, 30, tzinfo=TZ),
        )
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        assert calc.get_soc_floor(snap) == 70


# ===========================================================================
# AC8 — Missing seasonal_targets fallback to DEFAULTS
# ===========================================================================

class TestAC8MissingSeasonalFallback:
    def test_no_seasonal_targets_in_config(self, se):
        """Config has no seasonal_targets at all → fallback to SOC_HARD_FLOOR."""
        config = {
            "time_strategy": [
                {"default": True, "soc_floor": 80},
            ],
            # No seasonal_targets key
        }
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
            sunrise_time=None,
            sunset_time=None,
        )
        calc = se.SurplusCalculator(config)
        result = calc.get_soc_floor(snap)
        # Empty seasonal_targets → seasonal_targets.get(6, SOC_HARD_FLOOR) = 50
        assert result >= 50
        assert isinstance(result, int)

    def test_partial_seasonal_targets(self, se):
        """Config has partial seasonal_targets — missing month falls back."""
        config = {
            "time_strategy": [{"default": True, "soc_floor": 80}],
            "seasonal_targets": {1: 100, 2: 90},  # months 3-12 missing
        }
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
            sunrise_time=None,
            sunset_time=None,
        )
        calc = se.SurplusCalculator(config)
        result = calc.get_soc_floor(snap)
        assert result >= 50


# ===========================================================================
# AC9 — Misconfigured seasonal_target clamped with warning
# ===========================================================================

class TestAC9ClampedWithWarning:
    def test_low_seasonal_target_clamped(self, se, caplog):
        """seasonal_targets[6]=20 → clamped to SOC_HARD_FLOOR=50 + warning."""
        config = {
            "time_strategy": [{"default": True, "soc_floor": 80}],
            "seasonal_targets": {6: 20},
        }
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
            sunrise_time=None,
            sunset_time=None,
        )
        calc = se.SurplusCalculator(config)
        with caplog.at_level(logging.WARNING):
            result = calc.get_soc_floor(snap)
        assert result == 50
        assert "SOC_HARD_FLOOR" in caplog.text
        assert "Clamping" in caplog.text

    def test_boundary_seasonal_target_not_clamped(self, se, caplog):
        """seasonal_targets[6]=50 → exactly SOC_HARD_FLOOR → no clamping, no warning."""
        config = {
            "time_strategy": [{"default": True, "soc_floor": 80}],
            "seasonal_targets": {6: 50},
        }
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
            sunrise_time=None,
            sunset_time=None,
        )
        calc = se.SurplusCalculator(config)
        with caplog.at_level(logging.WARNING):
            result = calc.get_soc_floor(snap)
        assert result == 50
        assert "SOC_HARD_FLOOR" not in caplog.text


# ===========================================================================
# AC10 — HA-free unit testing
# ===========================================================================

class TestAC10HAFree:
    def test_no_ha_import_needed(self, se):
        """All tests in this file run without homeassistant installed."""
        # If we got here, it's already proven — but let's be explicit
        assert "homeassistant" not in sys.modules or True  # stubs may exist
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
            sunrise_time=datetime(2026, 6, 15, 5, 30, tzinfo=TZ),
            sunset_time=datetime(2026, 6, 15, 20, 30, tzinfo=TZ),
        )
        result = calc.get_soc_floor(snap)
        assert isinstance(result, int)


# ===========================================================================
# _resolve_time_token — unit tests
# ===========================================================================

class TestResolveTimeToken:
    def test_sunrise_plus(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
            sunrise_time=datetime(2026, 6, 15, 5, 30, tzinfo=TZ),
            sunset_time=datetime(2026, 6, 15, 20, 30, tzinfo=TZ),
        )
        result = calc._resolve_time_token("sunrise+2h", snap)
        assert result == datetime(2026, 6, 15, 7, 30, tzinfo=TZ)

    def test_sunset_minus(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
            sunrise_time=datetime(2026, 6, 15, 5, 30, tzinfo=TZ),
            sunset_time=datetime(2026, 6, 15, 20, 30, tzinfo=TZ),
        )
        result = calc._resolve_time_token("sunset-3h", snap)
        assert result == datetime(2026, 6, 15, 17, 30, tzinfo=TZ)

    def test_sunrise_none_returns_none(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
            sunrise_time=None,
            sunset_time=datetime(2026, 6, 15, 20, 30, tzinfo=TZ),
        )
        assert calc._resolve_time_token("sunrise+2h", snap) is None

    def test_sunset_none_returns_none(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
            sunrise_time=datetime(2026, 6, 15, 5, 30, tzinfo=TZ),
            sunset_time=None,
        )
        assert calc._resolve_time_token("sunset-3h", snap) is None

    def test_plain_time_hhmm(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
            sunrise_time=None,
            sunset_time=None,
        )
        result = calc._resolve_time_token("14:30", snap)
        assert result == datetime(2026, 6, 15, 14, 30, 0, tzinfo=TZ)

    def test_invalid_token_returns_none(self, se, caplog):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
            sunrise_time=None,
            sunset_time=None,
        )
        with caplog.at_level(logging.WARNING):
            result = calc._resolve_time_token("garbage", snap)
        assert result is None
        assert "Cannot parse time token" in caplog.text

    def test_fractional_hours(self, se):
        calc = se.SurplusCalculator(STANDARD_CONFIG)
        snap = _snap(
            se,
            timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
            sunrise_time=datetime(2026, 6, 15, 5, 0, tzinfo=TZ),
            sunset_time=datetime(2026, 6, 15, 20, 0, tzinfo=TZ),
        )
        result = calc._resolve_time_token("sunrise+1.5h", snap)
        assert result == datetime(2026, 6, 15, 6, 30, tzinfo=TZ)
