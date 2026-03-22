# Story 2.2: Surplus Calculation with Battery Buffer

Status: done

## Story

As the surplus engine,
I want `SurplusCalculator.calculate_surplus(snapshot)` to compute the real
surplus and the battery-buffer-augmented reported surplus,
So that the wallbox receives a stable signal that meets its 4.2 kW threshold
even during brief PV dips, provided the battery has capacity above the SOC floor.

## Acceptance Criteria

**AC1 — Buffer fills gap to threshold**

Given `snapshot`: PV=3500 W, power_to_user=1200 W, SOC=95%, SOC floor=50%,
wallbox_threshold=4200 W\
When `calculate_surplus(snapshot)` is called\
Then `result.real_surplus_kw` = 2.3\
And `result.buffer_used_kw` > 0 (buffer fills the 1.9 kW gap)\
And `result.reported_kw` = 4.2 (exactly at threshold)\
And `result.charging_state` = `"ACTIVE"`

**AC2 — Ample PV: no buffer needed**

Given `snapshot`: PV=8000 W, power_to_user=1200 W, SOC=100%\
When `calculate_surplus(snapshot)` is called\
Then `result.real_surplus_kw` = 6.8\
And `result.buffer_used_kw` = 0.0\
And `result.reported_kw` = 6.8

**AC3 — SOC exactly at floor: zero buffer available**

Given `snapshot.soc_percent` equals the SOC floor exactly\
When `calculate_surplus(snapshot)` is called\
Then `result.buffer_used_kw` = 0.0\
And `result.reported_kw` = `result.real_surplus_kw` when real surplus ≥ threshold\
Or `result.reported_kw` = 0.0 and `charging_state` = `"INACTIVE"` when real
surplus < threshold (see AC4)

**AC4 — Cannot meet threshold: INACTIVE**

Given real surplus < wallbox_threshold AND SOC at floor (no buffer available)\
When `calculate_surplus(snapshot)` is called\
Then `result.reported_kw` = 0.0\
And `result.charging_state` = `"INACTIVE"`

**AC5 — soc_floor_active is populated**

Given `result.soc_floor_active` field\
Then it contains the integer SOC floor returned by `get_soc_floor(snapshot)` (e.g.
50, 80, or 100)

**AC6 — Wallbox load included in surplus formula**

Given the wallbox is actively charging the EV\
When `calculate_surplus(snapshot)` runs\
Then `snapshot.power_to_user_w` from the Growatt SPH already includes wallbox
draw in total household consumption\
And surplus formula `pv_production_w − power_to_user_w` implicitly accounts for
EV load — no separate adjustment applied\
And `result.reason` contains `"wallbox_included_in_load"` when
`charging_state == "ACTIVE"`

## Tasks / Subtasks

- [x] Task 1: Implement `SurplusCalculator.calculate_surplus(snapshot)` (AC: #1–#6)
  - [x] Call `soc_floor = self.get_soc_floor(snapshot)` — **requires Story 2.1 done first**
  - [x] Compute `real_surplus_kw = (pv_production_w - power_to_user_w) / 1000.0`
  - [x] Compute `soc_headroom = max(0.0, soc_percent - soc_floor)`
  - [x] Compute `buffer_energy_kwh = soc_headroom * battery_capacity_kwh / 100.0`
  - [x] Compute `buffer_kw_max = min(max_discharge_kw, buffer_energy_kwh / (hold_time_minutes / 60.0))`
  - [x] Compute `buffer_used_kw = min(buffer_kw_max, max(0.0, wallbox_threshold_kw - real_surplus_kw))`
  - [x] Compute `augmented_kw = real_surplus_kw + buffer_used_kw`
  - [x] If `augmented_kw >= wallbox_threshold_kw`: ACTIVE, `reported = augmented_kw`, `reason = "wallbox_included_in_load"`
  - [x] Else: INACTIVE, `reported = 0.0`, `buffer_used_kw = 0.0`, `reason = "surplus_below_threshold"`
  - [x] Return fully populated `EvaluationResult`
- [x] Task 2: Verify AC1 numeric precision (unit test)
  - [x] Assert `real_surplus_kw == pytest.approx(2.3)`
  - [x] Assert `buffer_used_kw == pytest.approx(1.9)`
  - [x] Assert `reported_kw == pytest.approx(4.2)`
- [x] Task 3: Verify AC2, AC3, AC4 cases in unit tests

## Dev Notes

### ⚠️ Story Dependency: 2.1 MUST Be Done First

`calculate_surplus` calls `self.get_soc_floor(snapshot)` on line 1. Until Story
2.1 implements that method, calling `calculate_surplus` raises `NotImplementedError`.
**Implement Story 2.1 before or alongside this story.**

### Exact Calculation Formula

```python
def calculate_surplus(self, snapshot: SensorSnapshot) -> EvaluationResult:
    soc_floor = self.get_soc_floor(snapshot)  # Story 2.1

    real_surplus_kw = (snapshot.pv_production_w - snapshot.power_to_user_w) / 1000.0

    battery_capacity_kwh = self.config.get("battery_capacity_kwh", 10.0)
    max_discharge_kw     = self.config.get("max_discharge_kw", 10.0)
    hold_time_minutes    = self.config.get("hold_time_minutes", 10)
    wallbox_threshold_kw = self.config.get("wallbox_threshold_kw", 4.2)

    soc_headroom       = max(0.0, snapshot.soc_percent - soc_floor)
    buffer_energy_kwh  = soc_headroom * battery_capacity_kwh / 100.0
    buffer_kw_max      = min(max_discharge_kw,
                             buffer_energy_kwh / (hold_time_minutes / 60.0))
    buffer_used_kw     = min(buffer_kw_max,
                             max(0.0, wallbox_threshold_kw - real_surplus_kw))
    augmented_kw       = real_surplus_kw + buffer_used_kw

    forecast_available = (
        snapshot.forecast.forecast_available if snapshot.forecast else False
    )

    if augmented_kw >= wallbox_threshold_kw:
        return EvaluationResult(
            reported_kw      = augmented_kw,
            real_surplus_kw  = real_surplus_kw,
            buffer_used_kw   = buffer_used_kw,
            soc_percent      = snapshot.soc_percent,
            soc_floor_active = soc_floor,
            charging_state   = "ACTIVE",
            reason           = "wallbox_included_in_load",
            forecast_available = forecast_available,
        )
    return EvaluationResult(
        reported_kw      = 0.0,
        real_surplus_kw  = real_surplus_kw,
        buffer_used_kw   = 0.0,
        soc_percent      = snapshot.soc_percent,
        soc_floor_active = soc_floor,
        charging_state   = "INACTIVE",
        reason           = "surplus_below_threshold",
        forecast_available = forecast_available,
    )
```

### Numeric Walkthrough — AC1 Verification

| Step | Formula | Value |
|------|---------|-------|
| real_surplus_kw | (3500 − 1200) / 1000 | **2.3 kW** |
| soc_headroom | 95 − 50 | 45% |
| buffer_energy_kwh | 45 × 10 / 100 | 4.5 kWh |
| buffer_kw_max | min(10.0, 4.5 / (10/60)) = min(10, 27) | **10.0 kW** |
| buffer_used_kw | min(10.0, max(0, 4.2 − 2.3)) = min(10, 1.9) | **1.9 kW** |
| augmented_kw | 2.3 + 1.9 | **4.2 kW** |
| reported_kw | 4.2 ≥ 4.2 → ACTIVE → 4.2 | **4.2 kW ✓** |

### Config Keys Used

All read via `self.config.get(key, default)` — never access raw without default:

| Config Key | Default | Unit | Source |
|------------|---------|------|--------|
| `wallbox_threshold_kw` | 4.2 | kW | DEFAULTS in `__init__.py` |
| `max_discharge_kw` | 10.0 | kW | DEFAULTS in `__init__.py` |
| `battery_capacity_kwh` | 10.0 | kWh | DEFAULTS in `__init__.py` |
| `hold_time_minutes` | 10 | min | DEFAULTS in `__init__.py` |
| `soc_hard_floor` | 50 | % | Used by `get_soc_floor` (Story 2.1) |

### EvaluationResult — All 8 Fields Required

No field has a default — all must be explicitly set:

```python
@dataclass
class EvaluationResult:
    reported_kw: float        # kW written to Modbus (0.0 when INACTIVE)
    real_surplus_kw: float    # PV − user_load in kW (can be negative)
    buffer_used_kw: float     # Battery buffer actually consumed (0 when INACTIVE)
    soc_percent: float        # snapshot.soc_percent (copied through)
    soc_floor_active: int     # Floor from get_soc_floor() (50, 80, or 100)
    charging_state: str       # "ACTIVE" | "INACTIVE" | "FAILSAFE"
    reason: str               # one-liner for log
    forecast_available: bool  # from snapshot.forecast
```

### Inspiration: marq24/ha-evcc Threshold Clamping Pattern

evcc's power offer to the EVSE always clamps to the EVSE minimum current to
avoid partial-charge oscillation. The equivalent here: `augmented_kw` is the
actual computed value; when ACTIVE, report it as-is (never below threshold since
`augmented >= threshold` by construction). When the buffer can't fill the gap,
report 0 instead of a sub-threshold value — this prevents the Growatt THOR from
cycling its contactor.

### Regression Protection

Only file to modify: `surplus_engine.py` — `SurplusCalculator.calculate_surplus`.

**Do not touch:**
- `sensor.py`, `modbus_server.py`, `registers.py`, `__init__.py`
- `sdm630_input_registers.py`, `sdm630_holding_registers.py`
- `SurplusEngine.evaluate_cycle` (still returns stub — Story 1.3 wires it up)
- `HysteresisFilter` (Story 2.3)
- `ForecastConsumer` (Story 3.1)

### Edge Cases

| Case | Expected behaviour |
|------|--------------------|
| `pv_production_w = 0` (night) | real_surplus negative, reported = 0.0 INACTIVE |
| `soc_percent > 100` (sensor glitch) | soc_headroom = min(soc - floor, 100) — clamp in `get_soc_floor` (Story 2.1) |
| `power_to_user_w = 0` | real_surplus = full PV output in kW |
| `hold_time_minutes = 0` | Division by zero — guard: `max(hold_time_minutes, 1)` |

### Unit Test Skeleton (no HA dependency)

```python
from datetime import datetime
from surplus_engine import SurplusCalculator, SensorSnapshot, ForecastData

def make_snap(pv_w, user_w, soc_pct, soc_floor=50):
    snap = SensorSnapshot(
        soc_percent=soc_pct,
        power_to_grid_w=0.0,
        pv_production_w=pv_w,
        power_to_user_w=user_w,
        timestamp=datetime.now(),
        sunset_time=None,
        sunrise_time=None,
    )
    return snap

def test_ac1_buffer_fills_gap():
    cfg = {
        "wallbox_threshold_kw": 4.2,
        "max_discharge_kw": 10.0,
        "battery_capacity_kwh": 10.0,
        "hold_time_minutes": 10,
        # time_strategy: single default rule with soc_floor=50
        "time_strategy": [{"default": True, "soc_floor": 50}],
    }
    calc = SurplusCalculator(cfg)
    snap = make_snap(pv_w=3500, user_w=1200, soc_pct=95)
    result = calc.calculate_surplus(snap)
    assert result.real_surplus_kw == pytest.approx(2.3)
    assert result.buffer_used_kw == pytest.approx(1.9)
    assert result.reported_kw == pytest.approx(4.2)
    assert result.charging_state == "ACTIVE"
    assert result.soc_floor_active == 50

def test_ac2_no_buffer_needed():
    ...  # PV=8000, user=1200, SOC=100 → reported=6.8, buffer=0

def test_ac4_inactive_soc_at_floor():
    ...  # PV=1000, user=500, SOC=50 → reported=0.0, INACTIVE
```

### Logging Patterns (from architecture.md)

```python
_LOGGER.debug(
    "SDM630 Eval: surplus=%.2fkW buffer=%.2fkW SOC=%d%% floor=%d%% "
    "state=%s reported=%.2fkW reason=%s forecast=%s",
    result.real_surplus_kw, result.buffer_used_kw, result.soc_percent,
    result.soc_floor_active, result.charging_state, result.reported_kw,
    result.reason, result.forecast_available
)
```

### Project Structure Notes

Only one method body to implement in one file:

| Action | File | Detail |
|--------|------|--------|
| MODIFY | `surplus_engine.py` | Implement `SurplusCalculator.calculate_surplus` |

No new files. No other modifications.

### References

- Story 2.2 AC — [Source: `_bmad-output/planning-artifacts/epics.md#Story-2.2`]
- Buffer math implementation note — [Source: `_bmad-output/planning-artifacts/epics.md#Story-2.2`]
- EvaluationResult fields — [Source: `_bmad-output/planning-artifacts/architecture.md#EvaluationResult-Structure`]
- Config keys and defaults — [Source: `_bmad-output/planning-artifacts/architecture.md#Configuration-Defaults`]
- Logging format — [Source: `_bmad-output/planning-artifacts/architecture.md#Logging-Patterns`]
- SurplusCalculator scaffold — [Source: `_bmad-output/implementation-artifacts/1-2-surplus-engine-py-module-scaffold-with-dataclasses.md`]
- Threshold clamping pattern — [Source: `marq24/ha-evcc` EVSE minimum current enforcement]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- `soc_floor_active` test initially expected 50 but June seasonal target = 70; test corrected
- `soc_percent=100` (int) fails `isinstance(x, float)` — test corrected to pass `100.0`
- guard `max(hold_time_minutes, 1)` prevents ZeroDivisionError for edge case hold_time=0

### Completion Notes List

- Task 1: Implemented `SurplusCalculator.calculate_surplus` in `surplus_engine.py`
  - Formula follows exact spec: real_surplus → soc_headroom → buffer_energy → buffer_kw_max → buffer_used
  - `hold_time_minutes` guarded with `max(..., 1)` to prevent ZeroDivisionError (edge case)
  - ACTIVE path: `reported = augmented_kw`, `reason = "wallbox_included_in_load"`
  - INACTIVE path: `reported = 0.0`, `buffer_used_kw = 0.0`, `reason = "surplus_below_threshold"`
  - Both paths log via `_LOGGER.debug` at evaluation time
- Task 2: AC1 numeric precision verified (`real=2.3, buffer=1.9, reported=4.2`)
- Task 3: AC2 (no buffer), AC3 (SOC at floor), AC4 (INACTIVE), AC5 (floor populated), AC6 (reason)
  covered in `tests/test_surplus_calculator.py` — 33 new tests, all pass
- Updated `tests/test_surplus_engine.py`: replaced stale `NotImplementedError` test with
  `test_surplus_calculator_calculate_surplus_returns_result`
- Full suite: 220 passed, 0 failed (2026-03-21)
- **Code Review (2026-03-21):** 0 production bugs found. Fixed 3 test-precision
  issues: AC1/AC3/AC4 tests used `STANDARD_CONFIG` with seasonal_targets
  (floor=70 for June) instead of spec-required floor=50. Added `FLOOR_50_CONFIG`,
  new `test_soc_floor_active_is_50` assertion. Suite: 221 passed, 0 failed.

### File List

- `surplus_engine.py` — implemented `SurplusCalculator.calculate_surplus`
- `tests/test_surplus_calculator.py` — new Story 2.2 test file (33 tests)
- `tests/test_surplus_engine.py` — updated stale scaffold test for `calculate_surplus`
