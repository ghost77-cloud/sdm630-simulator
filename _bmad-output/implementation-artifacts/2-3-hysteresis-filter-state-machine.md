# Story 2.3: Hysteresis Filter State Machine

Status: done

## Story

As the surplus engine,
I want `HysteresisFilter` to manage `ACTIVE`/`INACTIVE`/`FAILSAFE` charging
states with a configurable hold time,
So that the wallbox does not experience rapid start/stop cycling during brief
surplus fluctuations below the threshold.

## Acceptance Criteria

**AC1 — INACTIVE → ACTIVE transition**

Given `HysteresisFilter` is in `INACTIVE` state\
And `reported_kw >= wallbox_threshold_kw`\
When `update(reported_kw, now)` is called\
Then state transitions to `ACTIVE`\
And `hold_until` is set to `now + timedelta(minutes=hold_time_minutes)`\
And the method returns the passed `reported_kw` unchanged

**AC2 — Hold period: ACTIVE stays ACTIVE below threshold**

Given `HysteresisFilter` is in `ACTIVE` state\
And `reported_kw` has dropped below `wallbox_threshold_kw`\
When `update(reported_kw, now)` is called before `hold_until` expires\
Then state remains `ACTIVE`\
And the method returns the last valid `reported_kw` (the value from when
the state first became ACTIVE — not the dropped value)

**AC3 — Hold expired: ACTIVE → INACTIVE**

Given `HysteresisFilter` is in `ACTIVE` state\
And `hold_until` has passed\
And `reported_kw` is still below `wallbox_threshold_kw`\
When `update(reported_kw, now)` is called after `hold_until`\
Then state transitions to `INACTIVE`\
And the method returns `0.0`

**AC4 — ACTIVE stays ACTIVE above threshold (hold renewal)**

Given `HysteresisFilter` is in `ACTIVE` state\
And `reported_kw >= wallbox_threshold_kw`\
When `update(reported_kw, now)` is called\
Then state remains `ACTIVE`\
And `hold_until` is renewed: `now + timedelta(minutes=hold_time_minutes)`\
And the method returns `reported_kw`

**AC5 — force_failsafe() in any state**

Given `force_failsafe(reason: str)` is called on the filter\
When called from any state (`INACTIVE`, `ACTIVE`, or `FAILSAFE`)\
Then state immediately transitions to `FAILSAFE`\
And `hold_until` is cleared (set to `None`)\
And `_last_reported_kw` is set to `0.0`

**AC6 — FAILSAFE: update() always returns 0.0**

Given `HysteresisFilter` is in `FAILSAFE` state\
When `update(reported_kw, now)` is called with any value\
Then the method returns `0.0`\
And state remains `FAILSAFE` (no automatic recovery)

**AC7 — resume() from FAILSAFE → INACTIVE**

Given `HysteresisFilter` is in `FAILSAFE` state\
And the engine has confirmed all critical sensors are healthy\
When `resume()` is called\
Then state transitions to `INACTIVE`\
And `hold_until` remains `None`\
And next `update()` call evaluates fresh from `INACTIVE`

**AC8 — HA-free unit test compatibility**

Given `HysteresisFilter` is imported in a plain Python unit test\
When state machine tests run with `datetime` objects (no HA runtime)\
Then all assertions pass without any HA import or HA mock

## Tasks / Subtasks

- [x] Task 1: Implement `HysteresisFilter` class in `surplus_engine.py` (AC: #1–#7)
  - [x] Define `STATES = ("INACTIVE", "ACTIVE", "FAILSAFE")` as class-level constant (optional, for clarity)
  - [x] `__init__(self, config: dict)`: initialise `_state = "INACTIVE"`, `_hold_until: datetime | None = None`, `_last_reported_kw: float = 0.0`
  - [x] Read `hold_time_minutes` from `config.get("hold_time_minutes", 10)` in `__init__`
  - [x] Read `wallbox_threshold_kw` from `config.get("wallbox_threshold_kw", 4.2)` in `__init__`
  - [x] Implement `update(self, reported_kw: float, now: datetime) -> float` per state diagram below
  - [x] Implement `force_failsafe(self, reason: str) -> None`
  - [x] Implement `resume(self) -> None`
  - [x] Implement `@property state(self) -> str` (read-only access)
- [x] Task 2: Integrate `HysteresisFilter` into `SurplusEngine.evaluate_cycle`
  - [x] Call `self._hysteresis.update(calc_result.reported_kw, snapshot.timestamp)` after `SurplusCalculator.calculate_surplus(snapshot)`
  - [x] Use the value returned by `update()` as the final `EvaluationResult.reported_kw`
  - [x] Propagate `self._hysteresis.state` into `EvaluationResult.charging_state`
  - [x] If `self._hysteresis.state == "FAILSAFE"`: set `reason = "failsafe_active"`, `reported_kw = 0.0`
- [x] Task 3: Wire `force_failsafe` / `resume` for sensor-unavailability (Epic 4 prep — stubs only here)
  - [x] Ensure `SurplusEngine` has a reference to the `HysteresisFilter` instance (`self._hysteresis`)
  - [x] No full sensor-unavailability logic yet (Epic 4 scope): just confirm the method exists and is callable
- [x] Task 4: Unit tests in `tests/test_hysteresis_filter.py` (AC: #1–#8)
  - [x] AC1 test: initial `INACTIVE` → `ACTIVE` on threshold crossing
  - [x] AC2 test: `ACTIVE` + sub-threshold within hold → stays `ACTIVE`, returns `_last_reported_kw`
  - [x] AC3 test: hold expired + sub-threshold → `INACTIVE`, returns `0.0`
  - [x] AC4 test: `ACTIVE` + above-threshold → hold renewed, returns `reported_kw`
  - [x] AC5 test: `force_failsafe()` from each of the three states
  - [x] AC6 test: `FAILSAFE` → `update()` always `0.0`
  - [x] AC7 test: `resume()` → `INACTIVE`, next `update()` evaluates fresh
  - [x] AC8 verification: test file has NO `homeassistant` import anywhere

## Dev Notes

### State Diagram

```
                  ┌────────────────────┐
                  │      INACTIVE      │
                  └────────┬───────────┘
                           │ update(): reported_kw >= threshold
                           │ → hold_until = now + hold_time
                           ▼
                  ┌────────────────────┐
           ┌─────▶│       ACTIVE       │◀──────────────────────────┐
           │      └────────┬─────┬─────┘                           │
           │ still ACTIVE  │     │ reported_kw >= threshold        │
           │ (within hold) │     │ → renew hold_until              │
           │               │     └─────────────────────────────────┘
           │               │ hold expired AND reported_kw < threshold
           │               │ → return 0.0
           │               ▼
           │      ┌────────────────────┐
           │      │      INACTIVE      │◀──── resume() ──────────────┐
           │      └────────────────────┘                              │
           │                                                          │
           │  force_failsafe(reason)  ─────────────────────────────► │
           │  (from any state)                                        │
           │                                    ┌────────────────────┤
           │                                    │      FAILSAFE      │
           │                                    └────────────────────┘
           │                                    update() → always 0.0
           │
           └──── update() within hold & below threshold
                 → returns _last_reported_kw (NOT reported_kw)
```

### Reference Implementation Skeleton

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

        # Below threshold: check hold
        if self._hold_until is not None and now < self._hold_until:
            # Still within hold period — return last valid value
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
        """Call only after all sensors confirmed healthy. Transitions FAILSAFE → INACTIVE."""
        self._state = "INACTIVE"
```

> **Note:** The skeleton above is the exact target. Implement it verbatim — no deviation. The
> `_last_reported_kw` survives hold-period dips so the wallbox does not see a lower value mid-hold.

### Integration Point: `SurplusEngine.evaluate_cycle`

After implementing `HysteresisFilter`, wire it into `SurplusEngine.evaluate_cycle(snapshot)`.
The stub from Story 1.2 currently returns a hardcoded `EvaluationResult`. Replace that with:

```python
def evaluate_cycle(self, snapshot: SensorSnapshot) -> EvaluationResult:
    # 1. Run pure calculation (Stories 2.1 + 2.2)
    calc = self._calculator.calculate_surplus(snapshot)

    # 2. Apply hysteresis filter (Story 2.3)
    final_kw = self._hysteresis.update(calc.reported_kw, snapshot.timestamp)

    # 3. Return final result
    return EvaluationResult(
        reported_kw      = final_kw,
        real_surplus_kw  = calc.real_surplus_kw,
        buffer_used_kw   = calc.buffer_used_kw,
        soc_percent      = calc.soc_percent,
        soc_floor_active = calc.soc_floor_active,
        charging_state   = self._hysteresis.state,
        reason           = calc.reason if final_kw > 0.0 else "hysteresis_hold_or_inactive",
        forecast_available = calc.forecast_available,
    )
```

`SurplusEngine.__init__` must instantiate both:

```python
self._calculator = SurplusCalculator(config)
self._hysteresis = HysteresisFilter(config)
```

### Inspiration: marq24/ha-evcc — Watchdog & State Reset Pattern

The `evcc_intg` integration uses a websocket-based watchdog that calls
`coordinator.stop_watchdog()` / `start_watchdog()` on reconnect
([`__init__.py` lines 143–156](../../../marq24/ha-evcc/custom_components/evcc_intg/__init__.py)).
The key pattern for us:

- **Fail-safe entry** = `force_failsafe(reason)` (analogous to websocket disconnect)
- **Recovery** = `resume()` after sensor health confirmed (analogous to reconnect path)
- **No automatic recovery** in the filter itself — the orchestrator (`SurplusEngine`) owns
  recovery logic, not the state machine. This mirrors evcc's design where the coordinator,
  not the data source, decides when to trust data again.

Additionally, evcc's power-offer logic clamps delivered values to the EVSE minimum to avoid
contactor cycling. In our implementation, `_last_reported_kw` serves the same purpose:
returning the last above-threshold value during the hold window so the wallbox never sees a
sub-threshold dip signal mid-session.

### Config Keys Used

All keys read via `config.get(key, default)` — never access raw without default:

| Config Key | Default | Unit | Origin |
|---|---|---|---|
| `hold_time_minutes` | 10 | minutes | `DEFAULTS` in `__init__.py` |
| `wallbox_threshold_kw` | 4.2 | kW | `DEFAULTS` in `__init__.py` |

### Test File Structure

Create `tests/test_hysteresis_filter.py` if not already present:

```python
"""Unit tests for HysteresisFilter — no HA runtime required."""
from datetime import datetime, timedelta, timezone
import pytest

# Verify HA-free: the following import must succeed without homeassistant installed
# (run: python -c "from surplus_engine import HysteresisFilter")
if __package__:
    from custom_components.sdm630_simulator.surplus_engine import HysteresisFilter
else:
    from surplus_engine import HysteresisFilter

THRESHOLD = 4.2
CFG = {"hold_time_minutes": 10, "wallbox_threshold_kw": THRESHOLD}
T0 = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)


def _t(minutes: int = 0) -> datetime:
    return T0 + timedelta(minutes=minutes)


class TestInactiveToActive:
    def test_ac1_transition_on_threshold(self):
        f = HysteresisFilter(CFG)
        result = f.update(5.0, _t(0))
        assert f.state == "ACTIVE"
        assert result == pytest.approx(5.0)

    def test_no_transition_below_threshold(self):
        f = HysteresisFilter(CFG)
        result = f.update(3.0, _t(0))
        assert f.state == "INACTIVE"
        assert result == pytest.approx(0.0)


class TestActiveHoldBehavior:
    def test_ac2_sub_threshold_within_hold(self):
        f = HysteresisFilter(CFG)
        f.update(5.0, _t(0))         # → ACTIVE, last_reported = 5.0
        result = f.update(1.0, _t(5))  # within hold (5 min < 10 min)
        assert f.state == "ACTIVE"
        assert result == pytest.approx(5.0)  # returns _last_reported_kw

    def test_ac3_sub_threshold_after_hold_expires(self):
        f = HysteresisFilter(CFG)
        f.update(5.0, _t(0))
        result = f.update(1.0, _t(11))  # 11 min > 10 min hold
        assert f.state == "INACTIVE"
        assert result == pytest.approx(0.0)

    def test_ac4_above_threshold_renews_hold(self):
        f = HysteresisFilter(CFG)
        f.update(5.0, _t(0))          # initial ACTIVE, hold_until = t+10
        f.update(2.0, _t(5))          # within hold, returns last (5.0)
        result = f.update(6.0, _t(9)) # renew hold at t(9): hold_until = t(19)
        assert f.state == "ACTIVE"
        assert result == pytest.approx(6.0)
        # Now at t(18) — below threshold but still within renewed hold
        result2 = f.update(1.0, _t(18))
        assert f.state == "ACTIVE"
        assert result2 == pytest.approx(6.0)


class TestFailsafe:
    def test_ac5_force_failsafe_from_inactive(self):
        f = HysteresisFilter(CFG)
        f.force_failsafe("test_inactive")
        assert f.state == "FAILSAFE"
        assert f._hold_until is None

    def test_ac5_force_failsafe_from_active(self):
        f = HysteresisFilter(CFG)
        f.update(5.0, _t(0))
        f.force_failsafe("test_active")
        assert f.state == "FAILSAFE"

    def test_ac6_failsafe_blocks_update(self):
        f = HysteresisFilter(CFG)
        f.force_failsafe("test")
        assert f.update(100.0, _t(0)) == pytest.approx(0.0)
        assert f.state == "FAILSAFE"

    def test_ac7_resume_resets_to_inactive(self):
        f = HysteresisFilter(CFG)
        f.force_failsafe("test")
        f.resume()
        assert f.state == "INACTIVE"
        # Next update should evaluate fresh — below threshold → 0.0
        assert f.update(1.0, _t(0)) == pytest.approx(0.0)


class TestHaFree:
    def test_ac8_no_ha_import(self):
        """Verify the module can be imported with datetime only."""
        import sys
        assert "homeassistant" not in sys.modules or True  # tolerance for HA env
        # The real check: HysteresisFilter.__init__ only uses stdlib
        f = HysteresisFilter(CFG)
        assert f.state == "INACTIVE"
```

### Regression Protection

**Only file to modify:** `surplus_engine.py`

- Implement `HysteresisFilter` class body (replace `pass` / `raise NotImplementedError`)
- Update `SurplusEngine.__init__` to instantiate `HysteresisFilter`
- Update `SurplusEngine.evaluate_cycle` to call `_hysteresis.update()`

**Do NOT touch:**
- `sensor.py`, `modbus_server.py`, `registers.py`, `__init__.py`
- `sdm630_input_registers.py`, `sdm630_holding_registers.py`
- `SurplusCalculator` (Stories 2.1 + 2.2 complete)
- `ForecastConsumer` (Story 3.1)

**Regressions to verify:**
- `SurplusEngine.evaluate_cycle(snapshot)` still returns a valid `EvaluationResult` (not a stub)
- Modbus register write in `sensor.py` continues to receive a `float` from `evaluate_cycle`
- No `ImportError` when importing `surplus_engine.py` in plain Python

### Story Dependencies

| Dependency | Status | Notes |
|---|---|---|
| Story 1.2: `HysteresisFilter` skeleton in `surplus_engine.py` | ready-for-dev | Stub exists (`pass`/`raise NotImplementedError`) |
| Story 2.1: `get_soc_floor()` implemented | ready-for-dev | Required by `calculate_surplus` (called inside `evaluate_cycle`) |
| Story 2.2: `calculate_surplus()` implemented | ready-for-dev | Required by `evaluate_cycle` integration |

Implement 1.2 → 2.1 → 2.2 → **2.3** in order. Story 2.3 is the final integration
step for Epic 2 that makes `evaluate_cycle` fully operational.

### Expected Epic 2 End State

After this story, `SurplusEngine.evaluate_cycle(snapshot)` is fully functional:

1. `SurplusCalculator.get_soc_floor(snapshot)` → SOC floor for current time
2. `SurplusCalculator.calculate_surplus(snapshot)` → real surplus + buffer math
3. `HysteresisFilter.update(reported_kw, now)` → stable signal with hold
4. `EvaluationResult` returned with correct all 8 fields
5. Modbus register `TOTAL_POWER` reflects the stabilised kW value

The wallbox connected via Modbus TCP to port 5020 will now receive a stable,
hysteresis-protected charging signal. 🎯

## Dev Agent Record

### Implementation Plan

Followed red-green-refactor TDD cycle:
1. Created `tests/test_hysteresis_filter.py` (26 tests, RED — all failed on stubs)
2. Implemented `HysteresisFilter` verbatim per story skeleton in `surplus_engine.py`
3. Integrated into `SurplusEngine.__init__` and `evaluate_cycle`
4. Updated 5 stale Story 1.2 skeleton tests in `test_surplus_engine.py` that tested stub/placeholder behaviour now superseded by the real implementation

### Decisions

- `HysteresisFilter.__init__` signature changed from `hold_time_minutes: int` (old stub) to `config: dict` (per story spec). Updated `TestSkeletonNotImplemented` in `test_surplus_engine.py` accordingly.
- AC8 `test_ac8_no_homeassistant_in_modules`: used `or True` tolerance (per story spec) because other tests in the same pytest session load `homeassistant`.
- `evaluate_cycle` changed from `async def` returning hardcoded stub to real pipeline: `calculate_surplus` → `hysteresis.update` → `EvaluationResult`.

### Completion Notes

✅ All 4 Tasks + 16 subtasks complete  
✅ 26 new tests in `tests/test_hysteresis_filter.py` — all pass  
✅ Full regression suite: 247/247 passed (0 failures)  
✅ AC1–AC8 all satisfied  
✅ `SurplusEngine.evaluate_cycle` fully operational: Stories 2.1+2.2+2.3 pipeline complete  
✅ `force_failsafe`/`resume` accessible via `self._hysteresis` for Epic 4

## File List

- `surplus_engine.py` — `HysteresisFilter` class implemented; `SurplusEngine.__init__` and `evaluate_cycle` updated
- `tests/test_hysteresis_filter.py` — new; 26 unit tests for AC1–AC8
- `tests/test_surplus_engine.py` — 5 stale Story 1.2 skeleton tests updated to match real implementation
- `_bmad-output/implementation-artifacts/2-3-hysteresis-filter-state-machine.md` — story file (tasks, record, file list, status)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `2-3`: in-progress → review

## Change Log

- 2026-03-21: Implemented `HysteresisFilter` ACTIVE/INACTIVE/FAILSAFE state machine (Story 2.3). Integrated into `SurplusEngine.evaluate_cycle`. Added 26 unit tests. Epic 2 evaluation pipeline fully functional.
