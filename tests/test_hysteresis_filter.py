"""Unit tests for HysteresisFilter — no HA runtime required.

Run: python -m pytest tests/test_hysteresis_filter.py -v
"""
import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

# ---------------------------------------------------------------------------
# Module loading — standalone, no HA runtime required
# ---------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODULE_PATH = os.path.join(ROOT, "surplus_engine.py")
_MODULE_NAME = "surplus_engine"

sys.modules.pop(_MODULE_NAME, None)
_spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_MODULE_NAME] = _mod
_spec.loader.exec_module(_mod)

HysteresisFilter = _mod.HysteresisFilter

# ---------------------------------------------------------------------------
# Fixtures / Helpers
# ---------------------------------------------------------------------------

THRESHOLD = 4.2
CFG = {"hold_time_minutes": 10, "wallbox_threshold_kw": THRESHOLD}
T0 = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
HOLD_MINUTES = CFG["hold_time_minutes"]


def _t(minutes: float = 0, seconds: float = 0) -> datetime:
    """Return T0 + offset for readable timestamp construction."""
    return T0 + timedelta(minutes=minutes, seconds=seconds)


@pytest.fixture
def hf() -> HysteresisFilter:
    """Fresh HysteresisFilter in INACTIVE state."""
    return HysteresisFilter(CFG)


@pytest.fixture
def hf_active(hf: HysteresisFilter) -> HysteresisFilter:
    """HysteresisFilter already transitioned to ACTIVE at T0 with 5.0 kW."""
    hf.update(5.0, _t(0))
    assert hf.state == "ACTIVE"
    return hf


@pytest.fixture
def hf_failsafe(hf: HysteresisFilter) -> HysteresisFilter:
    """HysteresisFilter in FAILSAFE state."""
    hf.force_failsafe("test setup")
    assert hf.state == "FAILSAFE"
    return hf


# ---------------------------------------------------------------------------
# AC1 — INACTIVE → ACTIVE on threshold met
# ---------------------------------------------------------------------------

class TestInactiveToActive:

    def test_inactive_to_active_on_threshold_met(self, hf: HysteresisFilter) -> None:
        result = hf.update(5.0, _t(0))
        assert hf.state == "ACTIVE"
        assert hf._hold_until == _t(0) + timedelta(minutes=HOLD_MINUTES)
        assert result == pytest.approx(5.0)

    def test_inactive_stays_inactive_below_threshold(self, hf: HysteresisFilter) -> None:
        result = hf.update(3.0, _t(0))
        assert hf.state == "INACTIVE"
        assert result == pytest.approx(0.0)

    def test_inactive_transitions_at_exact_threshold(self, hf: HysteresisFilter) -> None:
        """Boundary: kW == threshold should activate (>=, not >)."""
        result = hf.update(THRESHOLD, _t(0))
        assert hf.state == "ACTIVE"
        assert result == pytest.approx(THRESHOLD)

    def test_returns_zero_when_inactive(self, hf: HysteresisFilter) -> None:
        """AC8: update() returns 0.0 in INACTIVE state when kW below threshold."""
        result = hf.update(1.0, _t(0))
        assert result == pytest.approx(0.0)
        assert hf.state == "INACTIVE"


# ---------------------------------------------------------------------------
# AC2, AC3, AC6, AC7 — ACTIVE hold behaviour and transitions
# ---------------------------------------------------------------------------

class TestActiveHoldBehavior:

    def test_active_holds_during_hold_period(self, hf_active: HysteresisFilter) -> None:
        """AC2: Sub-threshold within hold → stays ACTIVE, returns _last_reported_kw."""
        # Drop below threshold before hold expires
        result = hf_active.update(2.0, _t(5))  # 5 min < 10 min hold
        assert hf_active.state == "ACTIVE"
        assert result == pytest.approx(5.0)  # _last_reported_kw = 5.0 from fixture

    def test_active_to_inactive_after_hold_expires(self, hf_active: HysteresisFilter) -> None:
        """AC3: Sub-threshold after hold expires → INACTIVE, returns 0.0, hold cleared."""
        result = hf_active.update(2.0, _t(HOLD_MINUTES, seconds=1))  # 1s after hold
        assert hf_active.state == "INACTIVE"
        assert hf_active._hold_until is None
        assert result == pytest.approx(0.0)

    def test_active_above_threshold_renews_hold(self, hf_active: HysteresisFilter) -> None:
        """Being above threshold while ACTIVE should renew hold_until."""
        # Advance to near end of hold, then renew
        hf_active.update(6.0, _t(9))          # still above threshold at +9 min
        # Now at +15 min (beyond original hold_until at +10 min, but hold was renewed at +9 min)
        result = hf_active.update(2.0, _t(15))  # within renewed hold (+9+10 = +19 min)
        assert hf_active.state == "ACTIVE"
        assert result == pytest.approx(6.0)  # returns last valid kW after renewal

    def test_hold_timer_boundary_at_exactly_hold_duration(
        self, hf_active: HysteresisFilter
    ) -> None:
        """AC6: At exactly hold_until, state is STILL ACTIVE (<=, not <)."""
        result = hf_active.update(2.0, _t(HOLD_MINUTES))  # now == hold_until
        assert hf_active.state == "ACTIVE", (
            "Hold should still be active at now == hold_until (inclusive boundary)"
        )
        assert result == pytest.approx(5.0)

    def test_hold_timer_boundary_one_second_past(
        self, hf_active: HysteresisFilter
    ) -> None:
        """AC7: One second past hold_until, state transitions to INACTIVE."""
        result = hf_active.update(2.0, _t(HOLD_MINUTES, seconds=1))
        assert hf_active.state == "INACTIVE"
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# AC4, AC5 — FAILSAFE transitions
# ---------------------------------------------------------------------------

class TestFailsafeAndResume:

    def test_force_failsafe_from_any_state(self, hf: HysteresisFilter) -> None:
        """AC4: force_failsafe() must work from INACTIVE, ACTIVE, and FAILSAFE."""
        # From INACTIVE
        hf.force_failsafe("sensor unavailable")
        assert hf.state == "FAILSAFE"

        # From ACTIVE (new instance)
        hf2 = HysteresisFilter(CFG)
        hf2.update(5.0, _t(0))
        assert hf2.state == "ACTIVE"
        hf2.force_failsafe("active then failsafe")
        assert hf2.state == "FAILSAFE"

        # From FAILSAFE (already in it — calling again is idempotent)
        hf3 = HysteresisFilter(CFG)
        hf3.force_failsafe("first")
        hf3.force_failsafe("second")
        assert hf3.state == "FAILSAFE"

    def test_force_failsafe_clears_hold_and_last_kw(self, hf_active: HysteresisFilter) -> None:
        """force_failsafe() clears hold_until and sets _last_reported_kw = 0.0."""
        hf_active.force_failsafe("test")
        assert hf_active._hold_until is None
        assert hf_active._last_reported_kw == pytest.approx(0.0)

    def test_failsafe_update_always_returns_zero(self, hf_failsafe: HysteresisFilter) -> None:
        """FAILSAFE: update() returns 0.0 for any input, state stays FAILSAFE."""
        for kw in (0.0, 3.0, 5.0, 100.0):
            result = hf_failsafe.update(kw, _t(0))
            assert result == pytest.approx(0.0)
            assert hf_failsafe.state == "FAILSAFE"

    def test_failsafe_resume_goes_to_inactive(self, hf_failsafe: HysteresisFilter) -> None:
        """AC5: resume() transitions FAILSAFE → INACTIVE, hold_until stays None."""
        hf_failsafe.resume()
        assert hf_failsafe.state == "INACTIVE"
        assert hf_failsafe._hold_until is None

    def test_after_resume_below_threshold_returns_zero(
        self, hf_failsafe: HysteresisFilter
    ) -> None:
        """After resume, update below threshold returns 0.0 and stays INACTIVE."""
        hf_failsafe.resume()
        result = hf_failsafe.update(2.0, _t(0))
        assert hf_failsafe.state == "INACTIVE"
        assert result == pytest.approx(0.0)

    def test_after_resume_above_threshold_activates(
        self, hf_failsafe: HysteresisFilter
    ) -> None:
        """After resume, update above threshold can activate normally (fresh eval)."""
        hf_failsafe.resume()
        result = hf_failsafe.update(5.0, _t(0))
        assert hf_failsafe.state == "ACTIVE"
        assert result == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# AC9 — HA-freedom verification
# ---------------------------------------------------------------------------

class TestHAFreedom:

    def test_no_homeassistant_import(self) -> None:
        """AC9: surplus_engine does not require real homeassistant package.

        conftest.py installs lightweight stubs (types.ModuleType, no __version__)
        for other tests. Those stubs are acceptable — real HA is not.
        """
        ha_mods = [k for k in sys.modules if k.startswith("homeassistant")]
        if ha_mods:
            # Stubs installed by conftest have no __version__; real HA does
            real_ha = hasattr(sys.modules.get("homeassistant"), "__version__")
            assert not real_ha, (
                f"Real homeassistant package imported: {ha_mods}. "
                "HysteresisFilter must remain HA-free."
            )
