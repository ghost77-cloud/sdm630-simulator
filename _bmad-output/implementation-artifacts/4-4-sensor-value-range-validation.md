# Story 4.4: Sensor Value Range Validation

Status: done

## Story

As the surplus engine,
I want `SurplusEngine` to validate sensor values are within plausible ranges
before passing them to `SurplusCalculator`,
so that out-of-range data (e.g., SOC=150%, negative PV production) triggers
the fail-safe rather than silently corrupting surplus calculations.

## Acceptance Criteria

**AC1 — SOC out of range → FAILSAFE**

Given the SOC sensor reports a value outside [0, 100] (e.g., 105)\
When `_evaluation_tick` calls `_validate_cache()` before building `SensorSnapshot`\
Then `HysteresisFilter.force_failsafe(reason)` is called\
And `_LOGGER.warning("SDM630 FAIL-SAFE: %s. Reporting 0 kW.", reason)` emits\
And `reason = "sensor.<entity_id>: value 105 out of range [0, 100]"`\
And `EvaluationResult.reported_kw = 0.0`, `charging_state = "FAILSAFE"`

**AC2 — Power sensor out of range → FAILSAFE**

Given a power sensor (`pv_production`, `power_to_user`, `power_to_grid`) reports
a value outside its configured valid range (default: [−30000, 30000] W)\
When `_validate_cache()` runs\
Then FAILSAFE is triggered with `reason = "sensor.<entity_id>: value <X> out of range [<min>, <max>]"`\
And the exact entity ID is included in `reason`

**AC3 — In-range values: no FAILSAFE**

Given all cache values are within their configured valid ranges\
When `_validate_cache()` runs\
Then `None` is returned (no failure)\
And no FAILSAFE is triggered\
And values are passed to `SurplusCalculator` unchanged

**AC4 — Default ranges applied when CONF_SENSOR_RANGES not in config**

Given `sensor_ranges` is not configured in `configuration.yaml`\
When `_validate_cache()` runs\
Then default ranges are used: SOC ∈ [0, 100], power values ∈ [−30000, 30000] W\
And the defaults are sourced from the `DEFAULTS` dict (not hardcoded inline)\
And no WARNING or ERROR is logged about missing config

**AC5 — Custom ranges applied when CONF_SENSOR_RANGES is configured**

Given `sensor_ranges: { soc: [10, 100], power_w: [-20000, 20000] }` is in YAML\
When `_validate_cache()` runs\
And a power sensor reports 25000 W (within default range but outside custom range)\
Then FAILSAFE is triggered with `reason` referencing the sensor entity ID and the
custom range `[-20000, 20000]`

**AC6 — Recovery path is standard**

Given sensors recover and return in-range values\
When the next valid state-change event arrives and the cache entry is updated\
And the next `_evaluation_tick` calls `_validate_cache()` and returns `None`\
Then `HysteresisFilter.resume()` is called (same path as Story 4.1 recovery)\
And normal evaluation resumes

**AC7 — Skip validation for invalid cache entries (no double-trigger)**

Given a cache entry is already marked `valid = False` (Story 4.1 scenario)\
When `_validate_cache()` encounters this entry\
Then range validation is skipped for that entry\
And Story 4.1 handles the unavailable/invalid case (no duplicate FAILSAFE)

**AC8 — Boundary values: inclusive range check**

Given `CACHE_KEY_SOC` value = 0 (exactly at lower bound)\
When `_validate_cache()` runs\
Then no FAILSAFE is triggered (0 is valid: range check is inclusive `min <= value <= max`)

Given `CACHE_KEY_SOC` value = 100 (exactly at upper bound)\
When `_validate_cache()` runs\
Then no FAILSAFE is triggered (100 is valid: inclusive upper bound)

Given `CACHE_KEY_SOC` value = 100.01 (just above upper bound)\
When `_validate_cache()` runs\
Then FAILSAFE is triggered

## Tasks / Subtasks

- [x] Task 1: Add `sensor_ranges` to `DEFAULTS` in `surplus_engine.py` (AC: #4)
  - [x] Add to `DEFAULTS` dict:
    ```python
    "sensor_ranges": {
        "soc": (0, 100),
        "power_w": (-30000, 30000),
    }
    ```
  - [x] Do NOT hardcode range values anywhere except `DEFAULTS`

- [x] Task 2: Implement `SurplusEngine._validate_cache(self) -> str | None` (AC: #1–#8)
  - [x] Read ranges from `self._config.get("sensor_ranges", DEFAULTS["sensor_ranges"])`
  - [x] Build check list mapping each cache key to its range key:
    ```python
    checks = [
        (CACHE_KEY_SOC,             "soc"),
        (CACHE_KEY_POWER_TO_GRID,   "power_w"),
        (CACHE_KEY_PV_PRODUCTION,   "power_w"),
        (CACHE_KEY_POWER_TO_USER,   "power_w"),
    ]
    ```
  - [x] For each `(cache_key, range_key)` in checks:
    - [x] Fetch `entry = self._sensor_cache.get(cache_key)`
    - [x] If `entry is None` or `not entry.valid`: `continue` (defer to Story 4.1)
    - [x] Resolve `(min_val, max_val) = ranges[range_key]`
    - [x] If `not (min_val <= entry.value <= max_val)`:
      - [x] Resolve `entity_id` from `self._entity_map.get(cache_key, cache_key)`
      - [x] Return `f"{entity_id}: value {entry.value} out of range [{min_val}, {max_val}]"`
  - [x] Return `None` if all checks pass

- [x] Task 3: Wire `_validate_cache()` into `_evaluation_tick` (AC: #1, #2, #6)
  - [x] At the start of `_evaluation_tick`, after the Story 4.1 unavailability check and
    before building `SensorSnapshot`, insert:
    ```python
    range_fail = self._validate_cache()
    if range_fail:
        self._hysteresis.force_failsafe(range_fail)
        _LOGGER.warning("SDM630 FAIL-SAFE: %s. Reporting 0 kW.", range_fail)
        return self._build_failsafe_result(range_fail)
    ```
  - [x] Confirm `HysteresisFilter.resume()` is called in the successful-validation path
    (same surrounding logic as Story 4.1 recovery — share the same `resume()` call site)

- [x] Task 4: YAML config support for custom ranges (AC: #5)
  - [x] In `__init__.py` config parsing, add optional `sensor_ranges:` key:
    ```python
    "sensor_ranges": config.get("sensor_ranges", DEFAULTS["sensor_ranges"])
    ```
  - [x] Document the optional YAML key in a code comment (no external doc changes needed)
  - [x] Validate that both `soc` and `power_w` sub-keys are present; log WARNING and fall
    back to defaults if either is missing (defensive: user may supply partial config)

- [x] Task 5: Unit tests (no HA dependency) (AC: #1–#8)
  - [x] Test AC1: cache SOC=105 → `_validate_cache()` returns reason containing `"out of range [0, 100]"`
  - [x] Test AC2: cache `pv_production_w=35000` → reason contains entity ID and `"[-30000, 30000]"`
  - [x] Test AC3: all cache values in range → returns `None`
  - [x] Test AC4: config without `sensor_ranges` key → defaults applied correctly
  - [x] Test AC5: custom range `power_w: [-20000, 20000]`, value=25000 → FAILSAFE triggered
  - [x] Test AC6: after recovery, `_validate_cache()` returns `None` on next tick
  - [x] Test AC7: `valid=False` cache entry is skipped (no exception, no double-trigger)
  - [x] Test AC8 boundaries: SOC=0 → no fail; SOC=100 → no fail; SOC=100.01 → fail
  - [x] Confirm test file has NO `homeassistant` import

## Dev Notes

### ⚠️ Story Dependencies

| Prerequisite Story | Why Required |
|---|---|
| **Story 2.3** | `HysteresisFilter.force_failsafe()` and `resume()` must exist |
| **Story 4.1** | Establishes `_sensor_cache` entry structure (`valid` flag), `_entity_map`, and the `force_failsafe` / `resume` wiring in `_evaluation_tick`. Story 4.4 extends the same guard stack. |
| **Story 1.3** | `_evaluation_tick` evaluation loop exists |

### Files to Modify

Only `surplus_engine.py` is changed (plus tests):

```
custom_components/sdm630_simulator/
├── surplus_engine.py          ← MODIFY: add _validate_cache(), extend DEFAULTS,
│                                         wire into _evaluation_tick
├── __init__.py                ← MODIFY: parse optional sensor_ranges YAML key
└── tests/
    └── test_surplus_calculator.py   ← ADD: range validation tests (or new file
        or test_surplus_engine.py         test_surplus_engine.py if preferred)
```

Files that remain **unchanged**: `sensor.py`, `modbus_server.py`, `registers.py`,
`sdm630_input_registers.py`, `sdm630_holding_registers.py`.

### Architecture Pattern: Per-Entity Range Descriptors (marq24/ha-evcc Inspiration)

The `marq24/ha-evcc` integration uses `native_min_value` / `native_max_value` fields
on `ExtNumberEntityDescriptionStub` dataclasses (see
`marq24/ha-evcc/custom_components/evcc_intg/const.py` lines 109–113) to declare
per-entity bounds declaratively alongside entity metadata. The same principle
applies here via `CONF_SENSOR_RANGES`: bounds are declared in one central dict
(keyed by sensor type, not raw entity ID) and consumed by validation logic.
This allows future extension (e.g., per-entity overrides) without changing the
validation logic.

```python
# marq24/ha-evcc pattern (declarative, per-entity):
#   native_max_value=200, native_min_value=0   (const.py L360–361)

# Our pattern (declarative, per-sensor-type — same principle):
DEFAULTS = {
    ...
    "sensor_ranges": {
        "soc": (0, 100),        # SOC % — always 0–100
        "power_w": (-30000, 30000),  # W — bidirectional (grid export = negative)
    },
}
```

### Validation Placement in `_evaluation_tick`

The order within `_evaluation_tick` MUST be preserved to avoid conflicts with
existing guard layers:

```
1. Cache unavailability check  ← Story 4.1 (valid flag)
2. Staleness check             ← Story 4.2 (timestamp age)
3. _validate_cache()           ← Story 4.4 (range check)  ← INSERT HERE
4. Build SensorSnapshot
5. SurplusCalculator.calculate_surplus(snapshot)
6. HysteresisFilter.update()
7. Write result to Modbus register
```

Placing range validation after unavailability/staleness checks (step 3) avoids
double-triggering FAILSAFE on entries already marked invalid.

### Cache Entry Structure (from Story 4.1)

```python
@dataclass
class CacheEntry:
    value: float
    timestamp: datetime | None
    valid: bool          # False for unavailable/unknown states
```

The `valid` flag short-circuits range checks — if `valid` is `False`, the entry
is skipped in `_validate_cache()` (see AC7 and Task 2).

### Entity Map Pattern (from Story 4.1)

```python
# self._entity_map: dict[str, str]
# Maps cache key → HA entity_id for human-readable log messages
# e.g., CACHE_KEY_SOC → "sensor.sph10000_storage_soc"
```

Use `self._entity_map.get(cache_key, cache_key)` as fallback — graceful if the map
is not fully populated on startup.

### DEFAULTS Structure (extend existing dict in surplus_engine.py)

```python
DEFAULTS = {
    "evaluation_interval": 15,
    "wallbox_threshold_kw": 4.2,
    "wallbox_min_kw": 4.1,
    "hold_time_minutes": 10,
    "soc_hard_floor": 50,
    "stale_threshold_seconds": 60,
    # ADD in this story:
    "sensor_ranges": {
        "soc": (0, 100),
        "power_w": (-30000, 30000),
    },
}
```

### YAML Configuration (optional, for advanced users)

```yaml
sdm630_sim:
  sensor_ranges:
    soc: [0, 100]          # SOC percent — never changes in practice
    power_w: [-30000, 30000]  # Watt — adjust for smaller/larger inverters
```

This pattern mirrors the `native_min_value`/`native_max_value` concept from
`marq24/ha-evcc` but applied at the configuration layer rather than entity
descriptor layer, consistent with our YAML-first config approach.

### NFR17 Alignment

NFR17 states the system must never write invalid IEEE 754 floats (NaN, Infinity)
to Modbus registers. Range validation in this story provides additional protection:
extreme out-of-range values that could result from sensor malfunction or bit errors
(e.g., SOC=-32768 from a faulty Modbus read) are caught here before reaching
`SurplusCalculator` and before `struct.pack('>f')` in `modbus_server.py`.

### References

- Story requirements: [_bmad-output/planning-artifacts/epics.md](_bmad-output/planning-artifacts/epics.md) — Epic 4, Story 4.4 (line 802)
- FR26: [_bmad-output/planning-artifacts/prd.md](_bmad-output/planning-artifacts/prd.md#L366) — Fail-Safe & Error Handling
- NFR18: [_bmad-output/planning-artifacts/prd.md](_bmad-output/planning-artifacts/prd.md#L424) — Data Integrity
- Architecture cache keys + DEFAULTS: [_bmad-output/planning-artifacts/architecture.md](_bmad-output/planning-artifacts/architecture.md) — Sensor Cache Keys section
- HysteresisFilter API: [_bmad-output/implementation-artifacts/2-3-hysteresis-filter-state-machine.md](_bmad-output/implementation-artifacts/2-3-hysteresis-filter-state-machine.md) — Tasks/Subtasks
- Story 4.1 unavailability pattern: [_bmad-output/implementation-artifacts/4-1-sensor-unavailability-detection-and-fail-safe.md](_bmad-output/implementation-artifacts/4-1-sensor-unavailability-detection-and-fail-safe.md) — Dev Notes (guard stack order)
- marq24/ha-evcc range pattern: [marq24/ha-evcc/custom_components/evcc_intg/const.py](marq24/ha-evcc/custom_components/evcc_intg/const.py#L109) — `native_min_value`/`native_max_value`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6 (GitHub Copilot)

### Debug Log References

_None — implementation proceeded without issues._

### Completion Notes List

- **Task 1 + 4**: `DEFAULTS["sensor_ranges"]` added to `__init__.py` with `(0,100)` / `(-30000,30000)`. New constant `CONF_SENSOR_RANGES`. `SENSOR_RANGES_SCHEMA` validates optional sub-keys. `async_setup` parses the key with per-sub-key fallback + WARNING on partial config.
- **Task 2**: `_validate_cache()` added to `SDM630SimSensor` in `sensor.py`. Uses tuple-based cache entries `(value, timestamp, valid)` — `entry[0]` for value, `entry[2]` for valid flag. `DEFAULTS` imported from package.
- **Task 3**: Range check inserted in `_evaluation_tick` after the staleness/validity guard block, before the recovery/snapshot section. On failure: `force_failsafe`, warning log, FAILSAFE `EvaluationResult`, return. Recovery (`resume()`) call site unchanged — it now serves as recovery from all three guard layers (staleness, validity, range).
- **Task 5**: `tests/test_range_validation.py` — 23 tests, 0 HA imports, all AC1–AC8 covered plus a meta-test verifying no `homeassistant` import in the file.
- **Full suite**: 395 tests pass, 0 regressions.

### File List

- `__init__.py` — Added `CONF_SENSOR_RANGES`, `sensor_ranges` in `DEFAULTS`, `SENSOR_RANGES_SCHEMA`, schema entry, `async_setup` parsing with sub-key validation
- `sensor.py` — Added `DEFAULTS` import; added `_validate_cache()` method; wired into `_evaluation_tick`
- `tests/test_range_validation.py` — New file: 23 unit tests for AC1–AC8
- `_bmad-output/implementation-artifacts/4-4-sensor-value-range-validation.md` — Story updated (tasks, status, record)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — Status updated to `review`
