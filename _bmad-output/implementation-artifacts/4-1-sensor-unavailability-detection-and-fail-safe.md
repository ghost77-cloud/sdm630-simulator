# Story 4.1: Sensor Unavailability Detection and Fail-Safe

Status: ready-for-dev

## Story

As the surplus engine,
I want `SurplusEngine` to detect `STATE_UNAVAILABLE` and `STATE_UNKNOWN` sensor
states and immediately switch to fail-safe mode reporting 0 kW,
so that the battery is never drained due to the engine operating on missing or
invalid data.

## Acceptance Criteria

**AC1 — Unavailable/unknown sensor marks cache entry invalid**

Given `sensor.sph10000_storage_soc` (e.g.) reports `STATE_UNAVAILABLE`\
When `_handle_state_change(event)` processes the update\
Then the cache entry for `CACHE_KEY_SOC` is updated with `is_valid=False`
(NOT left absent — the tuple entry must exist so `_evaluation_tick` can detect it)\
And the old float value in the tuple is preserved (or `0.0` if no prior value)

**AC2 — Evaluation tick detects invalid cache entry and triggers FAILSAFE**

Given sensor cache contains an entry with `is_valid=False` for any critical key
(`CACHE_KEY_SOC`, `CACHE_KEY_POWER_TO_GRID`, `CACHE_KEY_PV_PRODUCTION`,
`CACHE_KEY_POWER_TO_USER`)\
When `_evaluation_tick` runs `_check_cache_validity()`\
Then `HysteresisFilter.force_failsafe("<entity_id> = unavailable")` is called\
And `EvaluationResult.reported_kw` = 0.0\
And `EvaluationResult.charging_state` = `"FAILSAFE"`\
And `_LOGGER.warning("SDM630 FAIL-SAFE: %s. Reporting 0 kW.", reason)` is emitted\
And `input_data_block.set_float(TOTAL_POWER, 0.0)` is called

**AC3 — STATE_UNKNOWN handled identically to STATE_UNAVAILABLE**

Given any of `power_to_grid`, `pv_production`, or `power_to_user` reports
`STATE_UNKNOWN`\
When `_handle_state_change` processes the event\
Then the corresponding cache entry is set `is_valid=False`\
And on next `_evaluation_tick`, FAILSAFE is triggered with the specific entity
name in the reason string (e.g., `"sensor.sph10000_pac_to_grid_total = unknown"`)

**AC4 — Non-numeric state (ValueError) triggers FAILSAFE**

Given a sensor returns a non-numeric, non-unavailable/unknown string (e.g.,
`"error"` or `""` or `"n/a"`)\
When `float(state.state)` raises `ValueError` in `_handle_state_change`\
Then the cache entry is set `is_valid=False` with
reason `"<entity_id>: non-numeric value"`\
And FAILSAFE is triggered on the next `_evaluation_tick`

**AC5 — Recovery: valid value resumes normal evaluation**

Given all sensors were in FAILSAFE state\
When each affected sensor emits a valid numeric state-change event\
Then the corresponding cache entry is updated with `is_valid=True` and the
new float value\
And once ALL required cache entries are `is_valid=True`, `_check_cache_validity()`
passes\
And `HysteresisFilter.resume()` is called (state → `INACTIVE`)\
And on the next `_evaluation_tick`, a normal `EvaluationResult` is produced
with `charging_state != "FAILSAFE"`\
And `_LOGGER.info("SDM630 recovered from FAILSAFE. Resuming normal evaluation.")`
is emitted exactly once (not on every tick)

**AC6 — Cache format: full tuple from this story onward**

Given this story is implemented (and supersedes Story 1.3's simple float cache)\
When `_handle_state_change` stores a value\
Then the value is stored as
`self._sensor_cache[cache_key] = (float_value, new_state.last_changed, True)`\
When STATE_UNAVAILABLE/STATE_UNKNOWN is detected\
Then stored as `self._sensor_cache[cache_key] = (last_known_value, now_utc, False)`\
where `last_known_value` is the previously stored float if available, else `0.0`\
And `now_utc` is `dt_util.utcnow()`

**AC7 — Warn-once anti-spam for repeated FAILSAFE ticks**

Given the engine is in FAILSAFE state across multiple `_evaluation_tick` calls\
When FAILSAFE persists across repeated ticks\
Then the `_LOGGER.warning` for the same reason is emitted on the FIRST detection
only\
And subsequent ticks while still in FAILSAFE log at DEBUG level (not WARNING),
to prevent log spam (track with `self._failsafe_reason_logged: str | None`)

## Tasks / Subtasks

- [ ] Task 1: Upgrade cache format from float to tuple (AC: #6) — supersedes Story 1.3 cache
  - [ ] In `SDM630SimSensor.__init__`, initialize
    `self._sensor_cache: dict[str, tuple[float, datetime, bool]] = {}`
  - [ ] Add `self._failsafe_reason_logged: str | None = None` for warn-once anti-spam (AC: #7)
  - [ ] In `_handle_state_change`: replace `float(new_state.state)` storage with tuple:
    `self._sensor_cache[cache_key] = (float(new_state.state), new_state.last_changed, True)`
  - [ ] In `_handle_state_change`: handle `STATE_UNAVAILABLE` / `STATE_UNKNOWN`:
    - [ ] Extract `last_val = self._sensor_cache.get(cache_key, (0.0, None, True))[0]`
    - [ ] `self._sensor_cache[cache_key] = (last_val, dt_util.utcnow(), False)`
    - [ ] Do NOT `return` — set cache first, then return (so evaluation_tick sees invalid entry)
  - [ ] In `_handle_state_change`: handle `ValueError` from `float()`:
    - [ ] `last_val = self._sensor_cache.get(cache_key, (0.0, None, True))[0]`
    - [ ] `self._sensor_cache[cache_key] = (last_val, dt_util.utcnow(), False)`
    - [ ] `_LOGGER.debug("Cache invalidated for %s: non-numeric value '%s'", entity_id, new_state.state)`
  - [ ] Update `_evaluation_tick`: extract float values using
    `self._sensor_cache.get(key, (0.0, None, False))[0]` (tuple index 0)

- [ ] Task 2: Implement `_check_cache_validity(self)` helper in `SDM630SimSensor` (AC: #1–#4)
  - [ ] Iterate over required cache keys:
    `[CACHE_KEY_SOC, CACHE_KEY_POWER_TO_GRID, CACHE_KEY_PV_PRODUCTION, CACHE_KEY_POWER_TO_USER]`
  - [ ] For each key, retrieve `entry = self._sensor_cache.get(key)`
  - [ ] If `entry is None`: treat as invalid (entity has never fired a state-change event yet — see AC6 in Story 4.2 for startup grace period)
    - [ ] Skip FAILSAFE on first tick if `entry is None` AND `self._first_tick` is True (AC: see startup note in Story 4.2)
    - [ ] For now: if entry is None and NOT first_tick → trigger FAILSAFE with reason `"<key>: no data received"`
  - [ ] If `entry` exists but `is_valid == False` (index 2):
    - [ ] Look up entity_id from reverse mapping `CACHE_KEY_TO_ENTITY_ID` (build from config)
    - [ ] Build reason string: `f"{entity_id} = unavailable"` or `f"{entity_id}: non-numeric value"`
    - [ ] Return `(False, reason)` immediately on first invalid entry found
  - [ ] If all entries valid: return `(True, "")`

- [ ] Task 3: Wire `_check_cache_validity` into `_evaluation_tick` (AC: #2, #5)
  - [ ] Add to start of `_evaluation_tick`, BEFORE `SensorSnapshot` assembly:
    ```python
    cache_valid, reason = self._check_cache_validity()
    if not cache_valid:
        self._engine.hysteresis_filter.force_failsafe(reason)
        result = EvaluationResult(
            reported_kw=0.0,
            real_surplus_kw=0.0,
            buffer_used_kw=0.0,
            soc_percent=self._sensor_cache.get(CACHE_KEY_SOC, (0.0,))[0],
            soc_floor_active=50,
            charging_state="FAILSAFE",
            reason=reason,
            forecast_available=False,
        )
        self._write_result(result)
        # Log warn-once
        if self._failsafe_reason_logged != reason:
            _LOGGER.warning("SDM630 FAIL-SAFE: %s. Reporting 0 kW.", reason)
            self._failsafe_reason_logged = reason
        else:
            _LOGGER.debug("SDM630 FAIL-SAFE (ongoing): %s", reason)
        return
    ```
  - [ ] Implement `_write_result(result)` helper (DRY — used by both FAILSAFE path and normal path):
    ```python
    def _write_result(self, result: EvaluationResult) -> None:
        input_data_block.set_float(TOTAL_POWER, result.reported_kw)
        self._attr_native_value = result.reported_kw
        self.async_write_ha_state()
    ```
  - [ ] After the validity check PASSES (normal path), check if engine was previously in FAILSAFE:
    ```python
    if self._failsafe_reason_logged is not None:
        self._engine.hysteresis_filter.resume()
        _LOGGER.info("SDM630 recovered from FAILSAFE. Resuming normal evaluation.")
        self._failsafe_reason_logged = None
    ```
  - [ ] Then proceed with normal `SensorSnapshot` assembly and `evaluate_cycle()` call

- [ ] Task 4: Add `CACHE_KEY_TO_ENTITY_ID` reverse-lookup helper (AC: #2, #3)
  - [ ] Build in `async_added_to_hass()` from `self._config[CONF_ENTITIES]`:
    ```python
    self._entity_to_cache_key = {
        config_entities["soc"]:            CACHE_KEY_SOC,
        config_entities["power_to_grid"]:  CACHE_KEY_POWER_TO_GRID,
        config_entities["pv_production"]:  CACHE_KEY_PV_PRODUCTION,
        config_entities["power_to_user"]:  CACHE_KEY_POWER_TO_USER,
    }
    self._cache_key_to_entity = {v: k for k, v in self._entity_to_cache_key.items()}
    ```
  - [ ] Use `self._cache_key_to_entity.get(cache_key, cache_key)` in reason string
    construction inside `_check_cache_validity`
  - [ ] Use `self._entity_to_cache_key.get(entity_id)` in `_handle_state_change` instead
    of a hardcoded `ENTITY_TO_CACHE_KEY` dict (entity IDs come from YAML config)

- [ ] Task 5: Add required imports to `sensor.py` (AC: all)
  - [ ] `from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN`
    (add to existing const import if already there from Story 1.3)
  - [ ] `from homeassistant.util import dt as dt_util`
  - [ ] `from .surplus_engine import EvaluationResult`
    (needed to construct EvaluationResult in FAILSAFE path directly)
  - [ ] Verify `CACHE_KEY_SOC`, `CACHE_KEY_POWER_TO_GRID`, `CACHE_KEY_PV_PRODUCTION`,
    `CACHE_KEY_POWER_TO_USER` are imported from `.surplus_engine`

## Dev Notes

### Cache Format Upgrade — Important Note on Story 1.3

Story 1.3 defined `self._sensor_cache` as a plain `dict` storing `float` values.
**This story upgrades that format** to a 3-tuple:
`(float_value, last_changed: datetime, is_valid: bool)`.

If implementing stories sequentially (1.3 before 4.1), the developer will need
to update all cache read/write sites in `sensor.py` when implementing this story.
**Recommended approach:** Implement the 3-tuple format already in Story 1.3 to
avoid a refactor here. Story 4.2 (staleness) then uses the `last_changed` field
that is already in place.

### Module to Modify

Only `sensor.py` changes in this story. `surplus_engine.py` already provides
`HysteresisFilter.force_failsafe(reason)` and `HysteresisFilter.resume()` from
Story 2.3. `EvaluationResult` dataclass from Story 1.2.

**Unchanged files (DO NOT TOUCH):**
`modbus_server.py`, `registers.py`, `sdm630_input_registers.py`,
`sdm630_holding_registers.py`, `__init__.py`

### `HysteresisFilter` Access

`SurplusEngine` must expose `hysteresis_filter` attribute for direct access from
`SDM630SimSensor._evaluation_tick`. The FAILSAFE path bypasses `evaluate_cycle()`
and calls `force_failsafe` directly on the filter.

**Access pattern** (add to `SurplusEngine` if not already present):

```python
class SurplusEngine:
    def __init__(self, config: dict):
        self._config = config
        self._calculator = SurplusCalculator(config)
        self._forecast_consumer = ForecastConsumer(config)
        self.hysteresis_filter = HysteresisFilter(config)  # public attr
```

Verify this attribute name is consistent with Story 2.3 implementation.

### `STATE_UNAVAILABLE` / `STATE_UNKNOWN` Pattern — growatt_local Reference

From `growatt_local/sensor.py` (`async_added_to_hass` restore logic):

```python
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
...
if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
    return
```

This story **extends** that pattern: instead of `return` (ignore), we mark the
cache entry invalid and let the evaluation tick detect it.

### marq24/ha-evcc State Pattern Reference

The `evcc_intg` integration uses a coordinator-based `DataUpdateCoordinator`
rather than per-sensor event subscriptions. The relevant pattern for our approach
is the state staleness check using `State.last_changed` — see Story 4.2's
implementation note. For unavailability specifically, the simpler
`STATE_UNAVAILABLE` / `STATE_UNKNOWN` guard is the canonical pattern used in
`growatt_local` and documented in HA developer docs.

### Log Format Reference

```python
# Fail-safe activation (WARNING — first time only for a given reason):
_LOGGER.warning("SDM630 FAIL-SAFE: %s. Reporting 0 kW.", reason)

# Fail-safe ongoing (DEBUG — every tick while FAILSAFE persists):
_LOGGER.debug("SDM630 FAIL-SAFE (ongoing): %s", reason)

# Recovery (INFO — exactly once when all sensors are healthy again):
_LOGGER.info("SDM630 recovered from FAILSAFE. Resuming normal evaluation.")

# Full decision log (from Story 1.4 — also emitted on FAILSAFE path):
_LOGGER.debug(
    "SDM630 Eval: surplus=%.2fkW buffer=%.2fkW SOC=%d%% floor=%d%% "
    "state=%s reported=%.2fkW reason=%s forecast=%s",
    result.real_surplus_kw, result.buffer_used_kw, result.soc_percent,
    result.soc_floor_active, result.charging_state, result.reported_kw,
    result.reason, result.forecast_available,
)
```

### CONFUSING NAME ALERT: `CONF_ENTITIES`

In `__init__.py` (Story 1.1), the entities sub-dict is stored under config key
`"entities"`. The constant is defined as:

```python
CONF_ENTITIES = "entities"
```

The entity IDs inside are: `"soc"`, `"power_to_grid"`, `"pv_production"`,
`"power_to_user"`, `"sun"`, `"weather"`, `"forecast_solar"`.

Only the first four are numeric sensors → only these go into `_entity_to_cache_key`.
`"sun"`, `"weather"`, `"forecast_solar"` are NOT tracked via `_handle_state_change`.

### Startup Behavior

On cold start, the sensor cache is empty. The first
`stale_threshold_seconds` seconds (default 60s) act as a startup grace period
(implemented fully in Story 4.2). For this story, the practical behavior is:

- If entity fires a valid state-change before first `_evaluation_tick`: cache entry
  exists and is valid → normal evaluation.
- If entity fires STATE_UNAVAILABLE before first tick: cache entry exists with
  `is_valid=False` → FAILSAFE. This is correct behavior (entity is already
  reporting a problem).
- If entity has NOT fired any event at all before first tick:
  `entry is None` → treat as `is_valid=False` → FAILSAFE after first tick
  (Story 4.2 introduces the proper startup grace period via `timestamp=None` check).

### Prerequisites (must be done before this story)

| Story | What it provides |
|---|---|
| 1.1 | Config dict with `CONF_ENTITIES` entity IDs |
| 1.2 | `surplus_engine.py` with `HysteresisFilter`, `EvaluationResult`, `SurplusEngine` |
| 1.3 | `SDM630SimSensor` wired to `SurplusEngine`, `_sensor_cache`, `_evaluation_tick` |
| 1.4 | Decision log format (`_LOGGER.debug("SDM630 Eval: ...")`) |
| 2.3 | `HysteresisFilter.force_failsafe(reason)` and `HysteresisFilter.resume()` implemented |

Stories 2.1, 2.2, 3.1, 3.2 are not required for this story.

### EvaluationResult FAILSAFE Construction

When FAILSAFE is triggered before `evaluate_cycle()` is called, build
`EvaluationResult` directly in the FAILSAFE block (not via `evaluate_cycle`):

```python
from .surplus_engine import EvaluationResult

result = EvaluationResult(
    reported_kw=0.0,
    real_surplus_kw=0.0,
    buffer_used_kw=0.0,
    soc_percent=self._sensor_cache.get(CACHE_KEY_SOC, (0.0,))[0],
    soc_floor_active=50,            # SOC_HARD_FLOOR constant
    charging_state="FAILSAFE",
    reason=reason,
    forecast_available=False,
)
```

### Project Structure Notes

- Only `sensor.py` (in `custom_components/sdm630_simulator/`) is modified
- The cache upgrade supersedes Story 1.3's simple float dict
- No new files created; no test files needed (HA-dependent code; covered by
  integration behavior, not unit tests)
- Naming of `_check_cache_validity`, `_write_result`, `_failsafe_reason_logged`,
  `_entity_to_cache_key`, `_cache_key_to_entity` must be consistent across this
  story and Story 4.2

### References

- Epics: [_bmad-output/planning-artifacts/epics.md](_bmad-output/planning-artifacts/epics.md) — Epic 4, Story 4.1
- Architecture: [_bmad-output/planning-artifacts/architecture.md](_bmad-output/planning-artifacts/architecture.md) — Decision 2 (Fail-Safe Strategy), Sensor Cache Keys, Logging Patterns
- Story 1.3 (cache wiring): [_bmad-output/implementation-artifacts/1-3-integration-wiring-in-sensor-py-and-evaluation-loop.md](_bmad-output/implementation-artifacts/1-3-integration-wiring-in-sensor-py-and-evaluation-loop.md)
- Story 2.3 (HysteresisFilter): [_bmad-output/implementation-artifacts/2-3-hysteresis-filter-state-machine.md](_bmad-output/implementation-artifacts/2-3-hysteresis-filter-state-machine.md)
- Story 4.2 (staleness): [_bmad-output/implementation-artifacts/4-2-staleness-detection.md](_bmad-output/implementation-artifacts/4-2-staleness-detection.md) — builds on cache format from this story
- HA docs pattern: `STATE_UNAVAILABLE` / `STATE_UNKNOWN` from `homeassistant.const`
- growatt_local reference: `growat-modbus/Homeassistant-Growatt-Local-Modbus/custom_components/growatt_local/sensor.py`
- Existing sensor.py: [sensor.py](sensor.py)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (via GitHub Copilot — SM agent, CS workflow)

### Debug Log References

### Completion Notes List

### File List
