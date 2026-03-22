# Story 5.2: `HysteresisFilter` State Machine Tests

Status: done

## Story

As a developer (Ghost),
I want a pytest test suite for `HysteresisFilter` covering all state transitions
and boundary conditions,
so that hysteresis correctness is verifiable in isolation and regressions are
caught automatically without a running HA instance.

## Acceptance Criteria

**AC1 — INACTIVE → ACTIVE on threshold met**

Given `HysteresisFilter` is in `INACTIVE` state\
And `reported_kw >= wallbox_threshold_kw` (default: 4.2)\
When `update(reported_kw, now)` is called\
Then state transitions to `ACTIVE`\
And `hold_until` is set to `now + timedelta(minutes=hold_time_minutes)`\
And the method returns the passed `reported_kw` unchanged

Test name: `test_inactive_to_active_on_threshold_met`

**AC2 — ACTIVE holds during hold period when kW drops below threshold**

Given `HysteresisFilter` is in `ACTIVE` state\
And `_last_reported_kw` was set when state became ACTIVE (e.g., 5.0 kW)\
And `reported_kw` has dropped below `wallbox_threshold_kw`\
When `update(reported_kw, now)` is called before `hold_until` expires\
Then state remains `ACTIVE`\
And the method returns `_last_reported_kw` (the value from when ACTIVE was first
entered — NOT the dropped value)

Test name: `test_active_holds_during_hold_period`

**AC3 — ACTIVE → INACTIVE after hold expires with kW still below threshold**

Given `HysteresisFilter` is in `ACTIVE` state\
And `hold_until` has passed (`now > hold_until`)\
And `reported_kw` is still below `wallbox_threshold_kw`\
When `update(reported_kw, now)` is called\
Then state transitions to `INACTIVE`\
And `hold_until` is cleared\
And the method returns `0.0`

Test name: `test_active_to_inactive_after_hold_expires`

**AC4 — `force_failsafe()` transitions any state to FAILSAFE**

Given `force_failsafe(reason: str)` is called\
When called from `INACTIVE`, `ACTIVE`, or `FAILSAFE`\
Then state transitions to (or remains at) `FAILSAFE` in all cases\
And `hold_until` is `None`\
And `_last_reported_kw` is `0.0`

Test name: `test_force_failsafe_from_any_state`\
Note: run from all three states to ensure coverage

**AC5 — `resume()` transitions FAILSAFE → INACTIVE (never directly to ACTIVE)**

Given `HysteresisFilter` is in `FAILSAFE` state\
When `resume()` is called\
Then state transitions to `INACTIVE`\
And `hold_until` remains `None`\
And the immediate next `update()` call with kW below threshold returns `0.0`\
And the immediate next `update()` call with kW >= threshold transitions to `ACTIVE`
(fresh evaluation — no hysteresis carry-over)

Test name: `test_failsafe_resume_goes_to_inactive`

**AC6 — Hold timer boundary: ACTIVE at exactly `hold_until`**

Given `HysteresisFilter` is in `ACTIVE` state\
And `reported_kw` is below threshold\
When `update(reported_kw, now)` is called with `now == hold_until` exactly\
Then state remains `ACTIVE`\
And the method returns `_last_reported_kw` (still within hold)

Test name: `test_hold_timer_boundary_at_exactly_hold_duration`

> ⚠️ **IMPLEMENTATION DISCREPANCY (critical):** The reference skeleton in Story 2.3
> uses `now < self._hold_until`, which makes the boundary at `now == hold_until` expire.
> But **this AC requires** the hold to still be active at `now == hold_until`, meaning
> the correct comparison is `now <= self._hold_until`. The implementation MUST use `<=`
> here — fix the reference skeleton accordingly before writing tests. See Dev Notes below.

**AC7 — Hold timer boundary: INACTIVE one second past `hold_until`**

Given `HysteresisFilter` is in `ACTIVE` state\
And `reported_kw` is below threshold\
When `update(reported_kw, now)` is called with `now == hold_until + timedelta(seconds=1)`\
Then state transitions to `INACTIVE`\
And the method returns `0.0`

Test name: `test_hold_timer_boundary_one_second_past`

**AC8 — `update()` returns `0.0` in INACTIVE state when kW below threshold**

Given `HysteresisFilter` is in `INACTIVE` state\
And `reported_kw < wallbox_threshold_kw`\
When `update(reported_kw, now)` is called\
Then the method returns `0.0`\
And state remains `INACTIVE`

Test name: `test_returns_zero_when_inactive`

**AC9 — No HA import in test file**

Given `tests/test_hysteresis_filter.py` is run in a plain Python environment\
When the test module is imported (no `homeassistant` package installed)\
Then no `ImportError` occurs\
And `"homeassistant"` does NOT appear in `sys.modules` at test completion

Test name: `test_no_homeassistant_import`

## Tasks / Subtasks

- [x] Task 1: Fix boundary condition in `HysteresisFilter.update()` in `surplus_engine.py` (AC: #6, #7)
  - [x] Locate `if self._hold_until is not None and now < self._hold_until:` in ACTIVE branch
  - [x] Change `<` to `<=` so hold is still active at `now == hold_until`
  - [x] Verify AC7 still passes (INACTIVE at `hold_until + 1s`)
- [x] Task 2: Create `tests/` directory if not yet present (Story 5.1 dependency — do it here if 5.1 not done)
  - [x] Create `tests/__init__.py` (empty — makes `tests/` a package importable from a HA component path)
- [x] Task 3: Create `tests/conftest.py` if not present (normally Story 5.1 scope)
  - [x] If Story 5.1 is not yet done: create a minimal `conftest.py` with just the HysteresisFilter
    config fixture (`cfg_hysteresis`) to unblock this story
  - [x] If Story 5.1 is already done: use the existing `conftest.py` fixtures without modification
- [x] Task 4: Create `tests/test_hysteresis_filter.py` with all 9 ACs (AC: #1–#9)
  - [x] Module docstring: `"""Unit tests for HysteresisFilter — no HA runtime required."""`
  - [x] Dual-import guard using `if __package__:` pattern (consistent with project style)
  - [x] `THRESHOLD = 4.2`, `CFG = {"hold_time_minutes": 10, "wallbox_threshold_kw": THRESHOLD}`
  - [x] `T0` fixed UTC datetime, `_t(minutes)` helper function
  - [x] `class TestInactiveToActive:` → AC1 tests
  - [x] `class TestActiveHoldBehavior:` → AC2, AC3, AC4 (hold renewal), AC6, AC7
  - [x] `class TestFailsafeAndResume:` → AC4, AC5, FAILSAFE update-always-zero
  - [x] `class TestReturnValues:` → AC8 (zero in INACTIVE), return values from AC1/AC2/AC3
  - [x] `class TestHAFreedom:` → AC9 (no HA import)
  - [x] All test methods follow `test_<name>` naming from ACs above
- [x] Task 5: Run tests and verify all pass
  - [x] `python -m pytest tests/test_hysteresis_filter.py -v`
  - [x] Exit code 0
  - [x] Zero warnings about HA imports

## Dev Notes

### Critical: Boundary Condition Fix Required in `surplus_engine.py`

The reference implementation skeleton in Story 2.3 contains:

```python
# ACTIVE branch — below threshold, check hold
if self._hold_until is not None and now < self._hold_until:
    return self._last_reported_kw
```

This uses `<` (strict less-than). Story 5.2 AC6 explicitly requires that at
`now == hold_until` the hold is **still active**. Fix to `<=` before tests:

```python
if self._hold_until is not None and now <= self._hold_until:
    return self._last_reported_kw
```

This aligns with the "hold lasts at least N minutes" semantic and mirrors the
staleness detection boundary in Story 4.2 ("strictly `> 60s` triggers" = `>`,
not `>=`). Boundary semantics: inclusive hold expiry = `<=` comparison.

### Target Implementation (Correct Version)

The final `HysteresisFilter` should look exactly as in Story 2.3's skeleton,
with the single `<` → `<=` fix noted above:

```python
from datetime import datetime, timedelta

class HysteresisFilter:
    """ACTIVE/INACTIVE/FAILSAFE state machine for wallbox charge signal stabilisation.

    HA-free: only stdlib datetime — fully unit-testable without HA runtime.
    """

    def __init__(self, config: dict) -> None:
        self._state: str = "INACTIVE"
        self._hold_until: datetime | None = None
        self._last_reported_kw: float = 0.0
        self._hold_time_minutes: int = config.get("hold_time_minutes", 10)
        self._wallbox_threshold_kw: float = config.get("wallbox_threshold_kw", 4.2)

    @property
    def state(self) -> str:
        return self._state

    def update(self, reported_kw: float, now: datetime) -> float:
        if self._state == "FAILSAFE":
            return 0.0

        if self._state == "INACTIVE":
            if reported_kw >= self._wallbox_threshold_kw:
                self._state = "ACTIVE"
                self._hold_until = now + timedelta(minutes=self._hold_time_minutes)
                self._last_reported_kw = reported_kw
                return reported_kw
            return 0.0

        # ACTIVE branch
        if reported_kw >= self._wallbox_threshold_kw:
            # Renew hold
            self._hold_until = now + timedelta(minutes=self._hold_time_minutes)
            self._last_reported_kw = reported_kw
            return reported_kw

        # Below threshold: check hold (USE <= NOT <, per AC6)
        if self._hold_until is not None and now <= self._hold_until:
            return self._last_reported_kw

        # Hold expired
        self._state = "INACTIVE"
        self._hold_until = None
        return 0.0

    def force_failsafe(self, reason: str) -> None:
        self._state = "FAILSAFE"
        self._hold_until = None
        self._last_reported_kw = 0.0

    def resume(self) -> None:
        """Transitions FAILSAFE → INACTIVE. Call only after all sensors confirmed healthy."""
        self._state = "INACTIVE"
```

### Inspiration: marq24/ha-evcc Watchdog Pattern

Story 2.3 already documents the `evcc_intg` parallel: `force_failsafe` ↔ websocket
disconnect, `resume()` ↔ reconnect. Critically for testing: evcc's watchdog is
NOT tested in isolation — tests would require a websocket server. Our design is
deliberately HA-free so tests are simple, fast, and dependency-free. This design
choice (HA-free `SurplusCalculator` and `HysteresisFilter`) is the architectural
payoff from NFR4/NFR5 and Arch-2: we get reliable, lightweight unit tests.

### Test File: Complete Reference Implementation

```python
"""Unit tests for HysteresisFilter — no HA runtime required.

Run: python -m pytest tests/test_hysteresis_filter.py -v
"""
import sys
from datetime import datetime, timedelta, timezone

import pytest

# Dual-import guard — consistent with project style (AGENTS.md)
if __package__:
    from custom_components.sdm630_simulator.surplus_engine import HysteresisFilter
else:
    from surplus_engine import HysteresisFilter

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
        """AC3: Sub-threshold after hold expires → INACTIVE, returns 0.0."""
        result = hf_active.update(2.0, _t(HOLD_MINUTES, seconds=1))  # 1s after hold
        assert hf_active.state == "INACTIVE"
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
        """AC5: resume() transitions FAILSAFE → INACTIVE, never directly to ACTIVE."""
        hf_failsafe.resume()
        assert hf_failsafe.state == "INACTIVE"

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
        """AC9: No homeassistant package is imported during tests."""
        ha_modules = [k for k in sys.modules if k.startswith("homeassistant")]
        assert ha_modules == [], (
            f"HA modules unexpectedly imported: {ha_modules}. "
            "HysteresisFilter must remain HA-free."
        )
```

### Dependency on Story 5.1 (`conftest.py`)

Story 5.1 is responsible for creating `tests/conftest.py` with shared fixtures.
Since `HysteresisFilter` tests are fully self-contained (no `SensorSnapshot` or
`ForecastData` fixtures needed), this story does NOT depend on Story 5.1's
`conftest.py` fixtures. All fixtures are defined locally inside
`test_hysteresis_filter.py`.

**If Story 5.1 has not been done:** Only create `tests/__init__.py` (empty) and
`tests/conftest.py` (empty or minimal) as scaffolding so pytest can discover
the test file. No `SurplusCalculator` fixtures needed.

**If Story 5.1 has been done:** The existing `conftest.py` is already in place.
No modification to it is required for this story.

### Run Command

```bash
# From the project root (where surplus_engine.py lives):
python -m pytest tests/test_hysteresis_filter.py -v

# HA-free verification (no homeassistant package needed):
pip install pytest pytest-asyncio
python -m pytest tests/test_hysteresis_filter.py -v
```

### Project Structure Notes

- **Directory:** `tests/` at project root (sibling of `surplus_engine.py`)
- **File:** `tests/test_hysteresis_filter.py` (no `custom_components/` prefix —
  matches the standalone test pattern from architecture Arch-9)
- **Import guard:** `if __package__:` selects between HA-path and dev-path:
  - HA install: `from custom_components.sdm630_simulator.surplus_engine import HysteresisFilter`
  - Standalone: `from surplus_engine import HysteresisFilter`
- **No `surplus_engine.py` yet?** If Story 2.3 hasn't been implemented, you must
  implement `HysteresisFilter` in `surplus_engine.py` first (see skeleton above).
  Story 5.2 depends on the class existing — tests cannot pass against stubs.

### References

- `HysteresisFilter` spec: Story 2.3 dev notes — reference skeleton
  [Source: `_bmad-output/implementation-artifacts/2-3-hysteresis-filter-state-machine.md`]
- Boundary condition analysis: AC6/AC7 in this story — `<=` comparison required
- HA-free pattern: Architecture NFR4, Arch-2
  [Source: `_bmad-output/planning-artifacts/architecture.md`]
- Dual-import guard: AGENTS.md — "All modules support dual import: as HA package
  and standalone (`if __package__:` guard)"
  [Source: `AGENTS.md`]
- evcc watchdog pattern (fail-safe/resume conceptual model):
  [Source: `_bmad-output/implementation-artifacts/2-3-hysteresis-filter-state-machine.md#Inspiration`]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- Task 1: `surplus_engine.py` line 337 — changed `now < self._hold_until` to `now <= self._hold_until` (AC6 inclusive boundary)
- Task 3: `tests/__init__.py` and `tests/conftest.py` already present (Story 5.1 done)
- Task 4: Replaced existing `test_hysteresis_filter.py` (had stale boundary assertion expecting INACTIVE at `now == hold_until`) with reference implementation. Used `importlib.util` import pattern (project standard for test files) instead of `if __package__:` guard (not suitable for pytest context where `__package__ == 'tests'`). AC9 test adapted to tolerate conftest.py stubs while rejecting real HA.
- Task 5: 16 tests pass, full suite 396/396 — no regressions

### Completion Notes List

- Story 5.2 fully implemented: boundary fix + 16 AC tests (AC1–AC9) all green
- `surplus_engine.py`: `now < self._hold_until` → `now <= self._hold_until` in ACTIVE branch
- `tests/test_hysteresis_filter.py`: replaced with story reference implementation; 4 test classes (`TestInactiveToActive`, `TestActiveHoldBehavior`, `TestFailsafeAndResume`, `TestHAFreedom`), 16 tests
- Full regression suite: 396 passed, 0 failed (2026-03-22)

### File List

- `surplus_engine.py` — modified: `now < self._hold_until` → `now <= self._hold_until` (ACTIVE branch, AC6 boundary fix)
- `tests/test_hysteresis_filter.py` — replaced: full reference implementation with 16 tests covering AC1–AC9

## Change Log

- 2026-03-22: Story 5.2 implemented by Amelia (dev agent). Fixed boundary condition in `HysteresisFilter.update()`, replaced test file with reference implementation. 16 tests, 396/396 suite green.
- 2026-03-22: Code Review + Fix. Added missing assertions: AC1 `hold_until` check, AC3 `hold_until cleared`, AC5 `hold_until remains None`. 396/396 green. Status → done.
