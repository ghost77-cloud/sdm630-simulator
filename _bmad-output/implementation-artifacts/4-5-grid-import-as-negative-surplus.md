# Story 4.5: Grid Import as Negative Surplus Contribution

Status: done

## Story

As the surplus engine,
I want to subtract AC grid import power from the surplus calculation,
so that when household spikes cause the wallbox to draw from the grid,
the reported surplus immediately drops (or goes negative), and the
hysteresis filter deactivates or withholds charging — preventing
unintended grid consumption.

## Acceptance Criteria

**AC1 — Zero grid import: behaviour unchanged**

Given `power_from_grid_w = 0.0` (entity not configured or sensor reads 0)\
When `SurplusCalculator.calculate_surplus()` runs\
Then `real_surplus_kw` equals `(pv_production_w - power_to_user_w) / 1000`\
And existing tests remain green without any modification

**AC2 — Positive grid import reduces surplus**

Given `pv_production_w = 5000`, `power_to_user_w = 1000`, `power_from_grid_w = 500`\
When `calculate_surplus()` runs\
Then `real_surplus_kw == (5000 - 1000 - 500) / 1000 == 3.5`\
And `buffer_used_kw` and `augmented_kw` are recalculated from the reduced base

**AC3 — Grid import exceeds PV–load margin → surplus negative or zero**

Given `pv_production_w = 1000`, `power_to_user_w = 800`, `power_from_grid_w = 400`\
When `calculate_surplus()` runs\
Then `real_surplus_kw == (1000 - 800 - 400) / 1000 == -0.2`\
And `augmented_kw` is capped to 0 by the existing `max(0, …)` mechanism\
And `charging_state == "INACTIVE"` (threshold not met)\
And no FAILSAFE is triggered (grid import is a legitimate operating condition)

**AC4 — Entity `power_from_grid` is optional**

Given `power_from_grid` is absent from `entities:` in `configuration.yaml`\
When the component initialises\
Then `CACHE_KEY_POWER_FROM_GRID` is never subscribed\
And `SensorSnapshot.power_from_grid_w` defaults to `0.0`\
And behaviour is identical to Story 2.2 baseline\
And no WARNING or ERROR is logged about the missing entity

**AC5 — Entity `power_from_grid` is configured: state-changes are subscribed**

Given `power_from_grid: sensor.sph10000_ac_to_user_total` is in `configuration.yaml`\
When the component initialises\
Then the entity is added to `_entity_to_cache_key` with key `CACHE_KEY_POWER_FROM_GRID`\
And state-change events update the sensor cache\
And each evaluation tick uses the latest cached value

**AC6 — Log output includes grid-import when non-zero**

Given `power_from_grid_w > 0` during an evaluation cycle\
When the structured decision log (`_LOGGER.debug`) emits\
Then the log line includes `grid_import=<value>kW`\
So that daytime grid-draw events are visible in HA logs

## Tasks / Subtasks

- [x] Task 1 — Add `CACHE_KEY_POWER_FROM_GRID` constant and `SensorSnapshot` field (AC1, AC4)
  - [x] 1.1 Add `CACHE_KEY_POWER_FROM_GRID = "power_from_grid_w"` after `CACHE_KEY_BATTERY_DISCHARGE`
        in `surplus_engine.py`
  - [x] 1.2 Add `power_from_grid_w: float = 0.0` as optional field to `SensorSnapshot` dataclass
        (keep it after `power_to_user_w`; default ensures backward compat)

- [x] Task 2 — Update surplus formula (AC2, AC3)
  - [x] 2.1 In `SurplusCalculator.calculate_surplus()` change the `real_surplus_kw` line to:
        `real_surplus_kw = (snapshot.pv_production_w - snapshot.power_to_user_w - snapshot.power_from_grid_w) / 1000.0`
  - [x] 2.2 Update the `_LOGGER.debug` structured log line to include
        `grid_import=%.2fkW` (AC6); add `snapshot.power_from_grid_w / 1000` as matching arg

- [x] Task 3 — Wire entity role in `sensor.py` (AC4, AC5)
  - [x] 3.1 Import `CACHE_KEY_POWER_FROM_GRID` from `surplus_engine` alongside existing imports
  - [x] 3.2 Add `"power_from_grid": CACHE_KEY_POWER_FROM_GRID` to `ENTITY_ROLE_TO_CACHE_KEY`
  - [x] 3.3 Add `power_from_grid_w = self._sensor_cache.get(CACHE_KEY_POWER_FROM_GRID, (0.0, None, False))[0]`
        to `SensorSnapshot(...)` construction in `_evaluation_tick`

- [x] Task 4 — Register optional entity in `__init__.py` (AC4, AC5)
  - [x] 4.1 Add `CONF_POWER_FROM_GRID = "power_from_grid"  # optional` constant (after `CONF_POWER_TO_USER`)
  - [x] 4.2 Add `vol.Optional(CONF_POWER_FROM_GRID): cv.entity_id,` to `ENTITIES_SCHEMA`
  - [x] 4.3 Add `CONF_POWER_FROM_GRID` to the `for optional_key in (...)` warning loop

- [x] Task 5 — Tests (AC1, AC2, AC3, AC4)
  - [x] 5.1 Add `power_from_grid_w` kwarg to the `_snap()` helper in
        `tests/test_surplus_calculator.py` with default `0.0` (keeps all existing tests unchanged, satisfies AC1)
  - [x] 5.2 Add `TestAC_GridImport` class with three test methods:
        - `test_grid_import_zero_unchanged` — verifies AC1 numeric parity
        - `test_grid_import_reduces_surplus` — verifies AC2 (500 W import → 3.5 kW surplus)
        - `test_grid_import_forces_inactive` — verifies AC3 (400 W import + SOC at floor → INACTIVE, no FAILSAFE)

- [x] Task 6 — Update README (AC4, AC5)
  - [x] 6.1 Add `power_from_grid` to the optional entities table in `README.md` with description
        *"AC grid import (W) — subtracts from surplus; optional, defaults to 0"*

## Dev Notes

### Exact code locations

| File | Location | Change |
|---|---|---|
| `surplus_engine.py` | line ~27 (after `CACHE_KEY_BATTERY_DISCHARGE`) | new constant |
| `surplus_engine.py` | `SensorSnapshot` dataclass (~line 48) | new field `power_from_grid_w: float = 0.0` |
| `surplus_engine.py` | `calculate_surplus()` line ~233 | extend formula |
| `surplus_engine.py` | `calculate_surplus()` debug log (~line 240) | add `grid_import` arg |
| `sensor.py` | `ENTITY_ROLE_TO_CACHE_KEY` dict (~line 48) | new entry |
| `sensor.py` | import block (~line 33) | add `CACHE_KEY_POWER_FROM_GRID` |
| `sensor.py` | `SensorSnapshot(...)` construction (~line 516) | new field |
| `__init__.py` | line ~39 | new `CONF_POWER_FROM_GRID` constant |
| `__init__.py` | `ENTITIES_SCHEMA` (~line 93) | new `vol.Optional` entry |
| `__init__.py` | optional_key warning loop (~line 216) | add to tuple |
| `tests/test_surplus_calculator.py` | `_snap()` helper (~line 74) | add kwarg |
| `tests/test_surplus_calculator.py` | end of file | new `TestAC_GridImport` class |
| `README.md` | optional entities table | add row |

### Key invariants to preserve

- `power_from_grid_w` defaults to `0.0` — **no existing test may be modified**;
  all AC1 tests pass without touching them
- `power_from_grid_w` is purely a reduction of the available surplus; it must
  **not** trigger FAILSAFE by itself (grid import is a normal operating condition)
- The `buffer_used_kw` calculation already runs *after* `real_surplus_kw` is
  determined — the battery buffer will naturally compensate the reduced base,
  capped by `buffer_kw_max`
- Sensor cache pattern: `(value, timestamp, valid)` tuple — always read index 0;
  default `(0.0, None, False)` matches existing cache reads in sensor.py
- `ENTITY_ROLE_TO_CACHE_KEY` is the single source of truth for which entity roles
  get subscribed; adding the key there is sufficient for full wiring (see
  `sensor.py` lines 280–294)

### Algebraic note

Current effective surplus formula (with your sensor config):

```
surplus = output_power - (output_power - ac_to_grid) ≡ ac_to_grid
```

After this story, when `power_from_grid` is configured as `sensor.sph10000_ac_to_user_total`
(the Growatt register for AC drawn from grid to house):

```
surplus = output_power - home_consumption - ac_from_grid
```

This is the fully correct AC-side energy balance.

### Test pattern (from existing story 2.2 tests)

```python
def _snap(se, *, pv_w, user_w, soc_pct, power_from_grid_w=0.0, forecast=None):
    return se.SensorSnapshot(
        soc_percent=soc_pct,
        power_to_grid_w=0.0,
        pv_production_w=pv_w,
        power_to_user_w=user_w,
        power_from_grid_w=power_from_grid_w,
        timestamp=NOW,
        sunset_time=None,
        sunrise_time=None,
        forecast=forecast,
    )

class TestAC_GridImport:
    def test_grid_import_zero_unchanged(self, se):
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        r = calc.calculate_surplus(_snap(se, pv_w=5000, user_w=1000, soc_pct=90))
        assert r.real_surplus_kw == pytest.approx(4.0)

    def test_grid_import_reduces_surplus(self, se):
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        r = calc.calculate_surplus(
            _snap(se, pv_w=5000, user_w=1000, soc_pct=90, power_from_grid_w=500)
        )
        assert r.real_surplus_kw == pytest.approx(3.5)

    def test_grid_import_forces_inactive(self, se):
        calc = se.SurplusCalculator(FLOOR_50_CONFIG)
        r = calc.calculate_surplus(
            _snap(se, pv_w=1000, user_w=800, soc_pct=90, power_from_grid_w=400)
        )
        assert r.real_surplus_kw == pytest.approx(-0.2)
        assert r.charging_state == "INACTIVE"
        assert r.charging_state != "FAILSAFE"
```

### Project Structure Notes

- Follows the `optional entity → cache key → snapshot field → formula` pattern
  established by `power_to_user` / `CACHE_KEY_POWER_TO_USER` in Story 1.3
- No new files needed — all changes are in-place extensions of existing modules
- `CACHE_KEY_BATTERY_DISCHARGE` exists in surplus_engine.py but is not yet
  used in the formula; do not wire it in this story

### References

- Surplus formula: [surplus_engine.py](../../surplus_engine.py#L233)
- SensorSnapshot dataclass: [surplus_engine.py](../../surplus_engine.py#L44)
- ENTITY_ROLE_TO_CACHE_KEY: [sensor.py](../../sensor.py#L46)
- SensorSnapshot construction: [sensor.py](../../sensor.py#L516)
- ENTITIES_SCHEMA: [\_\_init\_\_.py](../../__init__.py#L93)
- Optional entity warning loop: [\_\_init\_\_.py](../../__init__.py#L216)
- Test helper pattern: [tests/test_surplus_calculator.py](../../tests/test_surplus_calculator.py#L74)
- Story 2.2 (baseline surplus logic): [2-2-surplus-calculation-with-battery-buffer.md](2-2-surplus-calculation-with-battery-buffer.md)
- Story 4.4 (range validation pattern, optional cache handling): [4-4-sensor-value-range-validation.md](4-4-sensor-value-range-validation.md)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (party mode — Ghost session 2026-03-25)

### Debug Log References

AC3 test required SOC=50 (at floor) to ensure buffer_kw_max=0; with SOC=90 the
battery buffer fills the gap to threshold and charging_state becomes ACTIVE —
correct behaviour, wrong test assumption. Fixed in test.

### Completion Notes List

- All 388 tests pass (285 pre-existing + 3 new)
- `power_from_grid_w` defaults to `0.0` — zero behavioural change when entity not configured
- Both ACTIVE and INACTIVE debug log lines updated with `grid_import=%.2fkW`
- AC3 note: grid import alone does not force INACTIVE if SOC headroom provides buffer;
  the test correctly uses SOC=50 (at floor) to verify the formula without buffer interference

### File List

- `surplus_engine.py` — constant, SensorSnapshot field, formula, debug logs
- `sensor.py` — import, ENTITY_ROLE_TO_CACHE_KEY, SensorSnapshot construction
- `__init__.py` — CONF_POWER_FROM_GRID constant, ENTITIES_SCHEMA, optional warning loop
- `tests/test_surplus_calculator.py` — _snap() helper, TestAC_GridImport class
- `README.md` — power_from_grid optional entity documented
