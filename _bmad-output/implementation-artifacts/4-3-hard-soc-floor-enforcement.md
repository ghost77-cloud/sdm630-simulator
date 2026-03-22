# Story 4.3: Hard SOC Floor Enforcement

Status: done

## Story

As the surplus engine,
I want the `SOC_HARD_FLOOR` constant (50%) to be enforced as an absolute
non-overridable constraint in `SurplusCalculator`,
So that the battery is protected regardless of algorithm state, config errors,
or edge cases in the time-window logic.

## Acceptance Criteria

**AC1 — Buffer capped near hard floor**

Given `snapshot.soc_percent` = 51 and the calculated buffer would consume more
than the 1% headroom above the hard floor\
When `calculate_surplus(snapshot)` runs\
Then `buffer_used_kw` is capped so the resulting SOC draw does not push below
50%\
And `result.buffer_used_kw` reflects the capped value (not the uncapped
theoretical value)

**AC2 — SOC exactly at hard floor: zero buffer**

Given `snapshot.soc_percent` = 50 (exactly at hard floor)\
When `calculate_surplus(snapshot)` runs\
Then `result.buffer_used_kw` = 0.0 (zero buffer — floor reached)\
And `result.reported_kw` = `result.real_surplus_kw` (pure PV surplus only)

**AC3 — SOC below hard floor: FAILSAFE**

Given `snapshot.soc_percent` < 50 (should not occur in normal operation, but
must be handled defensively)\
When `calculate_surplus(snapshot)` runs\
Then a FAILSAFE `EvaluationResult` is returned:
`reported_kw=0.0`, `charging_state="FAILSAFE"`, `reason="SOC below hard floor"`\
And no exception is raised (degrade gracefully)

**AC4 — Misconfigured soc_floor clamped with one-time warning**

Given `get_soc_floor()` in any time-window rule returns a value below 50
(misconfiguration)\
When `SurplusCalculator` applies the floor\
Then it silently clamps to 50\
And logs a one-time `_LOGGER.warning("Configured soc_floor %d%% below
SOC_HARD_FLOOR 50%%. Clamping.", configured_value)` (emitted at most once per
`SurplusCalculator` instance lifetime)

## Tasks / Subtasks

- [x] Task 1: Confirm/add `SOC_HARD_FLOOR` constant in `surplus_engine.py` (AC: #1–#4)
  - [x] Add module-level `SOC_HARD_FLOOR: int = 50` near the top of
        `surplus_engine.py`, below imports and above class definitions
  - [x] If a local copy already exists (e.g. read from `self.config["soc_hard_floor"]`),
        keep both: the constant is the non-overridable absolute; the config value is
        the operator-configured floor (must be ≥ `SOC_HARD_FLOOR`)
- [x] Task 2: Add `_hard_floor_warned` guard flag to `SurplusCalculator.__init__`
        (AC: #4)
  - [x] Add `self._hard_floor_warned: bool = False` to `__init__`
  - [x] This ensures the "clamping" warning fires once per instance, not every
        evaluation cycle
- [x] Task 3: Enforce hard floor at the top of `get_soc_floor(snapshot)` (AC: #4)
  - [ ] After resolving the applicable time-window rule and its `soc_floor` value,
        before returning:

        ```python
        if effective_floor < SOC_HARD_FLOOR:
            if not self._hard_floor_warned:
                _LOGGER.warning(
                    "Configured soc_floor %d%% below SOC_HARD_FLOOR 50%%. Clamping.",
                    effective_floor,
                )
                self._hard_floor_warned = True
            effective_floor = SOC_HARD_FLOOR
        return effective_floor
        ```

- [x] Task 4: Add FAILSAFE guard in `calculate_surplus(snapshot)` for
        `soc_percent < SOC_HARD_FLOOR` (AC: #3)
  - [ ] Insert as the **first check** in `calculate_surplus`, before any other
        computation:

        ```python
        if snapshot.soc_percent < SOC_HARD_FLOOR:
            _LOGGER.warning(
                "SDM630 FAIL-SAFE: SOC %.1f%% below hard floor %d%%. Reporting 0 kW.",
                snapshot.soc_percent, SOC_HARD_FLOOR,
            )
            return EvaluationResult(
                reported_kw=0.0,
                real_surplus_kw=0.0,
                buffer_used_kw=0.0,
                soc_percent=snapshot.soc_percent,
                soc_floor_active=SOC_HARD_FLOOR,
                charging_state="FAILSAFE",
                reason="SOC below hard floor",
                forecast_available=False,
            )
        ```

- [x] Task 5: Verify AC2 (SOC = 50) is handled by existing headroom formula (AC: #2)
  - [x] When SOC = 50 and `soc_floor` = 50: `soc_headroom = max(0.0, 50 - 50) = 0.0`,
        `buffer_energy_kwh = 0.0`, `buffer_kw_max = 0.0`, `buffer_used_kw = 0.0`
  - [x] This is correct by construction from Story 2.2 — no code change needed; add
        an inline comment confirming the invariant
- [x] Task 6: Verify AC1 (SOC = 51) existing headroom formula already caps correctly
        (AC: #1)
  - [x] Numeric check: `soc_headroom = 1%`, `battery_capacity_kwh = 10.0` →
        `buffer_energy_kwh = 0.1 kWh`, `buffer_kw_max = min(10, 0.1/(10/60)) = 0.6 kW`
  - [x] With `real_surplus = 3.0 kW` and `threshold = 4.2 kW`, gap = 1.2 kW;
        `buffer_used_kw = min(0.6, 1.2) = 0.6 kW` — not the full 1.2 kW; battery
        protected
  - [x] No code change needed; add inline comment confirming the hard-floor cap is
        implicit in the headroom formula
- [x] Task 7: Write unit-test cases for all ACs (AC: #1–#4)
  - [x] `test_soc_below_hard_floor_returns_failsafe` (AC3): SOC=48 → `charging_state="FAILSAFE"`, `reason="SOC below hard floor"`, `reported_kw=0.0`
  - [x] `test_soc_at_hard_floor_zero_buffer` (AC2): SOC=50, threshold=4.2, PV=8kW, load=0.5kW → `buffer_used_kw=0.0`, `reported_kw≈7.5`
  - [x] `test_soc_near_floor_buffer_capped` (AC1): SOC=51, `battery_capacity_kwh=10.0`, `hold_time_minutes=10` → `buffer_kw_max ≈ 0.6 kW`; uses `wallbox_threshold_kw=2.9` to achieve ACTIVE state
  - [x] `test_misconfigured_floor_clamped_and_warned_once` (AC4): configure `time_strategy` with `soc_floor=30`, call `get_soc_floor()` twice → warning emitted once, returned floor = 50

## Dev Notes

### Architecture: Where This Lives

Story 4.3 modifies exactly one class: `SurplusCalculator` in `surplus_engine.py`.

Per Arch-8, the following files are **UNCHANGED** and must not be touched:
`modbus_server.py`, `registers.py`, `sdm630_input_registers.py`,
`sdm630_holding_registers.py`.

`SurplusCalculator` must remain HA-free (NFR4) — only Python stdlib and
`dataclasses`. No `homeassistant.*` imports. This enables unit testing
without an HA instance.

### Existing Code to Understand Before Implementing

**Story 2.2 formula (already in `calculate_surplus`):**

```python
soc_floor = self.get_soc_floor(snapshot)               # Story 2.1
real_surplus_kw = (snapshot.pv_production_w - snapshot.power_to_user_w) / 1000.0
soc_headroom       = max(0.0, snapshot.soc_percent - soc_floor)
buffer_energy_kwh  = soc_headroom * battery_capacity_kwh / 100.0
buffer_kw_max      = min(max_discharge_kw,
                         buffer_energy_kwh / (hold_time_minutes / 60.0))
buffer_used_kw     = min(buffer_kw_max,
                         max(0.0, wallbox_threshold_kw - real_surplus_kw))
```

The `soc_headroom` formula from Story 2.2 already provides implicit hard-floor
capping when `get_soc_floor()` returns 50 correctly. Story 4.3 adds **explicit
defensive guards** on top:

1. Pre-condition guard at the top of `calculate_surplus` (SOC < 50 → FAILSAFE)
2. Post-floor-resolution clamping inside `get_soc_floor` (misconfigured floor → clamp + warn once)

**Story 2.1 — `get_soc_floor()` already specs this (AC6, AC9):**

AC6 of Story 2.1 states: `get_soc_floor()` never returns a value below 50.
AC9 of Story 2.1 states: misconfigured seasonal targets are clamped with warning.
Story 4.3 ADDITIONALLY enforces the same invariant for static `soc_floor` entries
in `time_strategy:` rules (not just seasonal targets). Both must be clamped.

### `SOC_HARD_FLOOR` Constant Positioning

Place `SOC_HARD_FLOOR` as a module-level constant in `surplus_engine.py`:

```python
# surplus_engine.py — module-level constants
SOC_HARD_FLOOR: int = 50  # % — absolute battery protection, never overridden
```

Do NOT read it from `self.config["soc_hard_floor"]` for the absolute guard in
`calculate_surplus`. The config value (`soc_hard_floor`) is used by Story 1.1 to
set the default — but the hard floor enforcement in `SurplusCalculator` always
uses the module constant `SOC_HARD_FLOOR`, making it impossible to accidentally
configure it away.

### FAILSAFE EvaluationResult Pattern (from Architecture)

Per architecture, `EvaluationResult` has **no defaults** — all 8 fields must be
explicitly provided:

```python
@dataclass
class EvaluationResult:
    reported_kw: float
    real_surplus_kw: float
    buffer_used_kw: float
    soc_percent: float
    soc_floor_active: int
    charging_state: str       # "ACTIVE" | "INACTIVE" | "FAILSAFE"
    reason: str
    forecast_available: bool
```

When returning a FAILSAFE result from `calculate_surplus`, use
`forecast_available=False` (no forecast relevance when hard floor is violated).

### Inspiration: marq24/ha-evcc Minimum SOC Pattern

evcc expresses the same concept with `VEHICLEMINSOC`
(`marq24/ha-evcc/custom_components/evcc_intg/pyevcc_ha/keys.py:441`) and
`BUFFERSOC` (`keys.py:174`): these are absolute minimums that the system enforces
regardless of user configuration or loadpoint state. The evcc `LIMITSOC` entity
in `number.py` uses `native_min_value=20` to enforce a UI-level floor — our
equivalent is the `SOC_HARD_FLOOR` module constant enforced in code, making the
floor truly non-negotiable (not just a UI hint).

Key pattern from evcc `number.py:114`: when a stored value (SOC-Limit=0) is
structurally invalid, fall back to the effective limit —
`value = self.coordinator.read_tag(Tag.EFFECTIVELIMITSOC, self.lp_idx)`.
Our equivalent: when `soc_floor` config < 50, silently promote to 50 and log
once.

### One-Time Warning Implementation

The `_hard_floor_warned` flag prevents log spam when the evaluation loop runs
every 15 seconds:

```python
class SurplusCalculator:
    def __init__(self, config: dict) -> None:
        self.config = config
        self._hard_floor_warned: bool = False

    def get_soc_floor(self, snapshot: "SensorSnapshot") -> int:
        # ... resolve time-window rule → effective_floor ...
        if effective_floor < SOC_HARD_FLOOR:
            if not self._hard_floor_warned:
                _LOGGER.warning(
                    "Configured soc_floor %d%% below SOC_HARD_FLOOR 50%%. Clamping.",
                    effective_floor,
                )
                self._hard_floor_warned = True
            effective_floor = SOC_HARD_FLOOR
        return effective_floor
```

### Numeric Walkthrough — AC1 Verification

| Step | Formula | Value |
|------|---------|-------|
| soc_percent | input | 51% |
| soc_floor | `get_soc_floor()` | 50 |
| soc_headroom | 51 − 50 | 1% |
| buffer_energy_kwh | 1 × 10.0 / 100 | 0.1 kWh |
| buffer_kw_max | min(10, 0.1 / (10/60)) = min(10, 0.6) | **0.6 kW** |
| buffer_used_kw | min(0.6, gap) | ≤ 0.6 kW (hard-floor protected) |

The 0.6 kW cap ensures the battery never loses more than 0.1 kWh in the 10-minute
hold window, keeping SOC at exactly 50%.

### Dependency: Stories 2.1 and 2.2 Must Be Implemented First

`get_soc_floor()` and `calculate_surplus()` are the host methods for this story's
changes. Both must exist (from Stories 2.1 and 2.2) before this story can be
implemented.

### Project Structure Notes

- Only file modified: `surplus_engine.py` — `SurplusCalculator` class
- Unit tests added to: `tests/test_surplus_calculator.py`
- No changes to: `sensor.py`, `__init__.py`, `modbus_server.py`, or any other
  module

### References

- Story 4.3 AC source: [_bmad-output/planning-artifacts/epics.md](../../_bmad-output/planning-artifacts/epics.md) — Story 4.3 section (lines 767–800)
- NFR3 (hard floor invariant): [_bmad-output/planning-artifacts/epics.md](../../_bmad-output/planning-artifacts/epics.md) line 75
- Architecture `EvaluationResult`: [_bmad-output/planning-artifacts/architecture.md](../../_bmad-output/planning-artifacts/architecture.md) — EvaluationResult Structure section
- Story 2.1 AC6, AC9 (floor clamping pre-spec): [_bmad-output/implementation-artifacts/2-1-soc-floor-determination-via-time-window-strategy.md](2-1-soc-floor-determination-via-time-window-strategy.md)
- Story 2.2 buffer formula: [_bmad-output/implementation-artifacts/2-2-surplus-calculation-with-battery-buffer.md](2-2-surplus-calculation-with-battery-buffer.md)
- evcc VEHICLEMINSOC pattern: `marq24/ha-evcc/custom_components/evcc_intg/pyevcc_ha/keys.py:441`
- evcc LIMITSOC fallback pattern: `marq24/ha-evcc/custom_components/evcc_intg/number.py:114`

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

- ✅ Task 1: `SOC_HARD_FLOOR: int = 50` already present from prior stories — confirmed, no addition needed.
- ✅ Task 2: Added `self._hard_floor_warned: bool = False` to `SurplusCalculator.__init__`.
- ✅ Task 3: Replaced silent `max()` clamp in `get_soc_floor()` "before" branch with explicit one-time `_LOGGER.warning` + `_hard_floor_warned` guard. Seasonal-target warning (separate path) left as-is from Story 2.1.
- ✅ Task 4: Inserted FAILSAFE early-return as first check in `calculate_surplus()` — returns `EvaluationResult(charging_state="FAILSAFE", reason="SOC below hard floor", ...)` when `soc_percent < SOC_HARD_FLOOR`.
- ✅ Tasks 5+6: Added inline comments in `calculate_surplus()` documenting AC2 (SOC=floor → headroom=0 → buffer=0 by construction) and AC1 (SOC=51 → headroom=1% → buffer_kw_max≈0.6 kW) invariants.
- ✅ Task 7: Added `TestHardSocFloorEnforcement` class (5 tests) to `tests/test_surplus_calculator.py`. AC1 test uses `wallbox_threshold_kw=2.9` to achieve ACTIVE state with headroom-limited buffer.
- 339 tests pass, 0 failures.
- ✅ Code Review P1 fix: Unified one-time warning guard (`_hard_floor_warned`) now also covers the "default" branch in `get_soc_floor()`. Warning message unified to `"Configured soc_floor %d%% below SOC_HARD_FLOOR 50%%. Clamping."`. Updated `test_low_seasonal_target_clamped` in `tests/test_soc_floor.py` to match new message format.

### File List

- `surplus_engine.py`
- `tests/test_surplus_calculator.py`
- `tests/test_soc_floor.py`
