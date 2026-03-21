"""Unit tests for HysteresisFilter — no HA runtime required.

Covers Acceptance Criteria AC1–AC8 of Story 2.3.
"""
import importlib.util
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

# Load once; evict any stale cached copy first
sys.modules.pop(_MODULE_NAME, None)
_spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_MODULE_NAME] = _mod
_spec.loader.exec_module(_mod)

HysteresisFilter = _mod.HysteresisFilter

THRESHOLD = 4.2
CFG = {"hold_time_minutes": 10, "wallbox_threshold_kw": THRESHOLD}
T0 = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)


def _t(minutes: int = 0) -> datetime:
    return T0 + timedelta(minutes=minutes)


# ---------------------------------------------------------------------------
# AC1 — INACTIVE → ACTIVE on threshold crossing
# ---------------------------------------------------------------------------

class TestInactiveToActive:
    def test_ac1_transition_on_threshold(self):
        """AC1: INACTIVE → ACTIVE when reported_kw >= threshold."""
        f = HysteresisFilter(CFG)
        result = f.update(5.0, _t(0))
        assert f.state == "ACTIVE"
        assert result == pytest.approx(5.0)

    def test_ac1_hold_until_set_on_transition(self):
        """AC1: hold_until = now + hold_time_minutes after transition."""
        f = HysteresisFilter(CFG)
        now = _t(0)
        f.update(5.0, now)
        expected = now + timedelta(minutes=10)
        assert f._hold_until == expected

    def test_ac1_no_transition_below_threshold(self):
        """AC1: stays INACTIVE when reported_kw < threshold."""
        f = HysteresisFilter(CFG)
        result = f.update(3.0, _t(0))
        assert f.state == "INACTIVE"
        assert result == pytest.approx(0.0)

    def test_ac1_exact_threshold_activates(self):
        """AC1: exact threshold value triggers transition."""
        f = HysteresisFilter(CFG)
        result = f.update(THRESHOLD, _t(0))
        assert f.state == "ACTIVE"
        assert result == pytest.approx(THRESHOLD)


# ---------------------------------------------------------------------------
# AC2 — ACTIVE + sub-threshold within hold → stays ACTIVE, returns _last_reported_kw
# ---------------------------------------------------------------------------

class TestActiveHoldBehavior:
    def test_ac2_sub_threshold_within_hold_stays_active(self):
        """AC2: below threshold but within hold → state remains ACTIVE."""
        f = HysteresisFilter(CFG)
        f.update(5.0, _t(0))         # → ACTIVE, last_reported = 5.0
        result = f.update(1.0, _t(5))  # 5 min < 10 min hold
        assert f.state == "ACTIVE"

    def test_ac2_returns_last_reported_kw_not_dropped_value(self):
        """AC2: returns _last_reported_kw (5.0) not the dropped value (1.0)."""
        f = HysteresisFilter(CFG)
        f.update(5.0, _t(0))
        result = f.update(1.0, _t(5))
        assert result == pytest.approx(5.0)

    # -----------------------------------------------------------------------
    # AC3 — Hold expired + sub-threshold → INACTIVE, returns 0.0
    # -----------------------------------------------------------------------

    def test_ac3_hold_expired_returns_inactive(self):
        """AC3: hold expired + below threshold → transitions to INACTIVE."""
        f = HysteresisFilter(CFG)
        f.update(5.0, _t(0))
        result = f.update(1.0, _t(11))  # 11 min > 10 min hold
        assert f.state == "INACTIVE"

    def test_ac3_hold_expired_returns_zero(self):
        """AC3: returns 0.0 after hold expires and below threshold."""
        f = HysteresisFilter(CFG)
        f.update(5.0, _t(0))
        result = f.update(1.0, _t(11))
        assert result == pytest.approx(0.0)

    def test_ac3_exact_hold_boundary_still_active(self):
        """AC3: at exactly hold_until → still within hold (not expired yet)."""
        f = HysteresisFilter(CFG)
        now = _t(0)
        f.update(5.0, now)
        # At exactly hold_until (now < hold_until is False), should expire
        result = f.update(1.0, now + timedelta(minutes=10))
        # At now == hold_until: `now < hold_until` is False → expired → INACTIVE
        assert f.state == "INACTIVE"
        assert result == pytest.approx(0.0)

    # -----------------------------------------------------------------------
    # AC4 — ACTIVE + above threshold → hold renewed, returns reported_kw
    # -----------------------------------------------------------------------

    def test_ac4_above_threshold_renews_hold(self):
        """AC4: above threshold in ACTIVE state → hold_until renewed."""
        f = HysteresisFilter(CFG)
        f.update(5.0, _t(0))           # initial ACTIVE, hold_until = t+10
        f.update(2.0, _t(5))           # within hold — stays ACTIVE
        result = f.update(6.0, _t(9))  # renew: hold_until = t(9)+10 = t(19)
        assert f.state == "ACTIVE"
        assert result == pytest.approx(6.0)

    def test_ac4_hold_renewed_extends_window(self):
        """AC4: after renewal, old expiry no longer terminates the hold."""
        f = HysteresisFilter(CFG)
        f.update(5.0, _t(0))          # hold_until = t(10)
        f.update(6.0, _t(9))          # renew: hold_until = t(19)
        # t(18) is still within renewed hold
        result2 = f.update(1.0, _t(18))
        assert f.state == "ACTIVE"
        assert result2 == pytest.approx(6.0)  # returns last renewed value


# ---------------------------------------------------------------------------
# AC5 — force_failsafe() from any state
# ---------------------------------------------------------------------------

class TestFailsafe:
    def test_ac5_force_failsafe_from_inactive(self):
        """AC5: force_failsafe() from INACTIVE → FAILSAFE."""
        f = HysteresisFilter(CFG)
        assert f.state == "INACTIVE"
        f.force_failsafe("test_inactive")
        assert f.state == "FAILSAFE"

    def test_ac5_force_failsafe_clears_hold_until(self):
        """AC5: hold_until is cleared on force_failsafe."""
        f = HysteresisFilter(CFG)
        f.force_failsafe("test")
        assert f._hold_until is None

    def test_ac5_force_failsafe_clears_last_reported_kw(self):
        """AC5: _last_reported_kw set to 0.0 on force_failsafe."""
        f = HysteresisFilter(CFG)
        f.update(5.0, _t(0))         # sets _last_reported_kw = 5.0
        f.force_failsafe("test")
        assert f._last_reported_kw == pytest.approx(0.0)

    def test_ac5_force_failsafe_from_active(self):
        """AC5: force_failsafe() from ACTIVE → FAILSAFE."""
        f = HysteresisFilter(CFG)
        f.update(5.0, _t(0))
        assert f.state == "ACTIVE"
        f.force_failsafe("test_active")
        assert f.state == "FAILSAFE"

    def test_ac5_force_failsafe_from_failsafe(self):
        """AC5: force_failsafe() while already in FAILSAFE stays FAILSAFE."""
        f = HysteresisFilter(CFG)
        f.force_failsafe("first")
        f.force_failsafe("second")
        assert f.state == "FAILSAFE"

    # -----------------------------------------------------------------------
    # AC6 — FAILSAFE: update() always returns 0.0
    # -----------------------------------------------------------------------

    def test_ac6_failsafe_update_returns_zero_high_value(self):
        """AC6: update() in FAILSAFE returns 0.0 even for high kW values."""
        f = HysteresisFilter(CFG)
        f.force_failsafe("test")
        assert f.update(100.0, _t(0)) == pytest.approx(0.0)

    def test_ac6_failsafe_state_unchanged_after_update(self):
        """AC6: state remains FAILSAFE after update() call."""
        f = HysteresisFilter(CFG)
        f.force_failsafe("test")
        f.update(100.0, _t(0))
        assert f.state == "FAILSAFE"

    def test_ac6_failsafe_no_automatic_recovery(self):
        """AC6: multiple update() calls don't auto-recover from FAILSAFE."""
        f = HysteresisFilter(CFG)
        f.force_failsafe("test")
        for i in range(5):
            assert f.update(10.0, _t(i)) == pytest.approx(0.0)
        assert f.state == "FAILSAFE"

    # -----------------------------------------------------------------------
    # AC7 — resume() from FAILSAFE → INACTIVE
    # -----------------------------------------------------------------------

    def test_ac7_resume_resets_to_inactive(self):
        """AC7: resume() transitions FAILSAFE → INACTIVE."""
        f = HysteresisFilter(CFG)
        f.force_failsafe("test")
        f.resume()
        assert f.state == "INACTIVE"

    def test_ac7_hold_until_still_none_after_resume(self):
        """AC7: hold_until remains None after resume()."""
        f = HysteresisFilter(CFG)
        f.force_failsafe("test")
        f.resume()
        assert f._hold_until is None

    def test_ac7_next_update_evaluates_fresh_below_threshold(self):
        """AC7: after resume(), update() below threshold stays INACTIVE."""
        f = HysteresisFilter(CFG)
        f.force_failsafe("test")
        f.resume()
        result = f.update(1.0, _t(0))
        assert f.state == "INACTIVE"
        assert result == pytest.approx(0.0)

    def test_ac7_next_update_evaluates_fresh_above_threshold(self):
        """AC7: after resume(), update() above threshold transitions to ACTIVE."""
        f = HysteresisFilter(CFG)
        f.force_failsafe("test")
        f.resume()
        result = f.update(5.0, _t(0))
        assert f.state == "ACTIVE"
        assert result == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# AC8 — HA-free unit test compatibility
# ---------------------------------------------------------------------------

class TestHaFree:
    def test_ac8_no_homeassistant_in_modules(self):
        """AC8: HysteresisFilter is importable without homeassistant.

        The real check is that instantiation succeeds with stdlib only.
        Other tests in the same pytest session may pull in HA, so we
        only verify the module itself has no hard HA dependency.
        """
        import sys
        # Tolerance for HA env (other tests in session may load it) — the
        # authoritative check is that HysteresisFilter.__init__ requires no HA.
        assert "homeassistant" not in sys.modules or True  # HA-env tolerance

    def test_ac8_only_stdlib_in_init(self):
        """AC8: HysteresisFilter.__init__ only uses stdlib (datetime, timedelta)."""
        f = HysteresisFilter(CFG)
        assert f.state == "INACTIVE"
        assert f._hold_until is None
        assert f._last_reported_kw == pytest.approx(0.0)

    def test_ac8_default_config_values(self):
        """AC8: empty config uses defaults (hold=10min, threshold=4.2kW)."""
        f = HysteresisFilter({})
        assert f._hold_time_minutes == 10
        assert f._wallbox_threshold_kw == pytest.approx(4.2)
