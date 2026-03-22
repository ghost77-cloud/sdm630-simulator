# Story 6.1: Add Raw and Reported Surplus Sensor Entities

Status: done

## Story

As Ghost,
I want to see `sensor.sdm_raw_surplus` and `sensor.sdm_reported_surplus` on my HA
dashboard with live values,
so that I can verify the entire surplus computation chain at a glance without opening
logs.

## Acceptance Criteria (BDD)

### AC1: Sensors present after first evaluation cycle

**Given** the HA component is running and `SurplusEngine` has completed at least one
evaluation cycle
**When** Ghost opens HA Developer Tools → States
**Then** `sensor.sdm_raw_surplus` is present with a numeric value in W matching
`EvaluationResult.real_surplus_kw × 1000`
**And** `sensor.sdm_reported_surplus` is present with a numeric value in W matching
`EvaluationResult.reported_kw × 1000`

### AC2: Non-blocking update on evaluation callback

**Given** `SurplusEngine` completes an evaluation cycle
**When** the evaluation callback fires
**Then** both sensors update within the same HA event loop tick (non-blocking, no
await in the callback path)
**And** `_LOGGER.debug` records the new values at DEBUG level

### AC3: Restore state after HA restart

**Given** HA has been restarted
**When** the `SDM630RawSurplusSensor` and `SDM630ReportedSurplusSensor` entities are
added to hass
**Then** `async_get_last_sensor_data()` is called on both
**And** each sensor displays the last persisted value (not `unknown`) until the next
evaluation cycle provides a fresh value

### AC4: Fail-silent on error

**Given** an error occurs while updating the sensor state (e.g., entity not yet
registered)
**When** the evaluation callback fires
**Then** the exception is caught, logged via `_LOGGER.warning()`, and neither
`SurplusEngine` nor the Modbus server crashes

## Tasks / Subtasks

- [x] Task 1: Create `SDM630RawSurplusSensor` class (AC: #1, #2, #3, #4)
  - [x] 1.1 Add class extending `RestoreSensor` in `sensor.py`
  - [x] 1.2 Set `_attr_should_poll = False`
  - [x] 1.3 Set `_attr_native_unit_of_measurement = "W"`
  - [x] 1.4 Set `_attr_device_class = SensorDeviceClass.POWER`
  - [x] 1.5 Set `_attr_unique_id = "sdm_raw_surplus"`
  - [x] 1.6 Implement `async_added_to_hass` with `async_get_last_sensor_data()`
- [x] Task 2: Create `SDM630ReportedSurplusSensor` class (AC: #1, #2, #3, #4)
  - [x] 2.1 Same structure as Task 1 but for reported surplus
  - [x] 2.2 Set `_attr_unique_id = "sdm_reported_surplus"`
- [x] Task 3: Wire sensors into `async_setup_platform` (AC: #1)
  - [x] 3.1 Instantiate both new sensors in `async_setup_platform`
  - [x] 3.2 Pass all three entities (existing + two new) to `async_add_entities`
- [x] Task 4: Add surplus sensor update to evaluation tick (AC: #1, #2, #4)
  - [x] 4.1 After `_write_result()` in `_evaluation_tick`, call update method on both surplus sensors
  - [x] 4.2 The update must be synchronous (`@callback` decorated), no `await`
  - [x] 4.3 Wrap update in try/except with `_LOGGER.warning()` on failure
  - [x] 4.4 Add `_LOGGER.debug` for new sensor values

## Dev Notes

### Critical Architecture Constraints

1. **File boundary**: Only `sensor.py` is modified. No changes to `surplus_engine.py`, `modbus_server.py`, `registers.py`, or register files.
2. **`EvaluationResult` already has both fields**: `real_surplus_kw` and `reported_kw` — read directly from the result, no engine changes needed.
3. **Conversion**: `EvaluationResult` stores values in kW; sensors display in W → multiply by 1000.
4. **Non-blocking**: The update callback from `_evaluation_tick` runs inside the HA event loop. The sensor update MUST be synchronous — use `@callback` decorator, no `await`, no I/O.
5. **Fail-silent**: Never propagate exceptions that could crash the Modbus server or `SurplusEngine`. Wrap in `try/except`.

### RestoreSensor Pattern

Use `homeassistant.components.sensor.RestoreSensor` (not `RestoreEntity` directly). This provides `async_get_last_sensor_data()` which returns `SensorExtraStoredData` with `native_value` and `native_unit_of_measurement`.

```python
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
)

class SDM630RawSurplusSensor(RestoreSensor):
    _attr_should_poll = False
    _attr_native_unit_of_measurement = "W"
    _attr_device_class = SensorDeviceClass.POWER

    def __init__(self) -> None:
        self._attr_name = "SDM Raw Surplus"
        self._attr_unique_id = "sdm_raw_surplus"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data and last_data.native_value is not None:
            self._attr_native_value = float(last_data.native_value)
```

### Existing Code Patterns to Follow

- **`SDM630SimSensor`** in `sensor.py` is the reference pattern: `_attr_should_poll = False`, `async_write_ha_state()`, `@callback` decorator
- **Logger**: `_LOGGER = logging.getLogger(__name__)` (already declared at module level)
- **`async_setup_platform`** currently creates a single `SDM630SimSensor` and calls `async_add_entities([sensor])` — extend to include the two new sensors
- **`_write_result()`** at the end of `_evaluation_tick` writes the Modbus register and updates HA state — surplus sensor update goes right after this call

### Where to Hook the Update

In `SDM630SimSensor._evaluation_tick()` method, after `self._write_result(result)` is called, add the surplus sensor updates. The `SDM630SimSensor` needs references to both surplus sensors (passed during `async_setup_platform`).

**Approach**: Store surplus sensor references on the `SDM630SimSensor` instance:

```python
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    name = config.get(CONF_NAME, DEFAULT_NAME)
    hass.loop.create_task(start_modbus_server())

    raw_surplus_sensor = SDM630RawSurplusSensor()
    reported_surplus_sensor = SDM630ReportedSurplusSensor()
    sensor = SDM630SimSensor(name, hass, config)
    sensor.set_surplus_sensors(raw_surplus_sensor, reported_surplus_sensor)

    async_add_entities([sensor, raw_surplus_sensor, reported_surplus_sensor])
```

In `_write_result()` or after it in `_evaluation_tick`:

```python
def _update_surplus_sensors(self, result: EvaluationResult) -> None:
    """Push surplus values to dashboard sensors — non-blocking, fail-silent."""
    try:
        if self._raw_surplus_sensor is not None:
            self._raw_surplus_sensor.update_value(result.real_surplus_kw * 1000)
        if self._reported_surplus_sensor is not None:
            self._reported_surplus_sensor.update_value(result.reported_kw * 1000)
    except Exception:
        _LOGGER.warning("Failed to update surplus sensors", exc_info=True)
```

On each sensor class:

```python
@callback
def update_value(self, value_w: float) -> None:
    self._attr_native_value = round(value_w, 1)
    self.async_write_ha_state()
```

### Imports Required

Add to the existing import block in `sensor.py`:

```python
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
)
```

Note: `SensorEntity` is already imported — just add `RestoreSensor` and `SensorDeviceClass`.

### Naming Conventions

| Item | Convention | Value |
|------|-----------|-------|
| Class | CamelCase | `SDM630RawSurplusSensor`, `SDM630ReportedSurplusSensor` |
| Entity ID | HA auto-generates from name | `sensor.sdm_raw_surplus`, `sensor.sdm_reported_surplus` |
| Unique ID | snake_case | `sdm_raw_surplus`, `sdm_reported_surplus` |
| Logger | module-level | `_LOGGER` (already exists) |

### What NOT To Do

- **DO NOT** modify `surplus_engine.py` — `EvaluationResult` already has both values
- **DO NOT** modify `modbus_server.py` — no Modbus changes needed for this story
- **DO NOT** add polling — sensors are event-driven (`_attr_should_poll = False`)
- **DO NOT** use `await` in the update callback — it must be synchronous
- **DO NOT** add new dependencies — only `homeassistant` core imports
- **DO NOT** create new files — all code goes into `sensor.py`

### Project Structure Notes

- All code changes are in `sensor.py` only
- The `if __package__:` dual-import guard pattern is already in place
- `async_setup_platform` is the HA sensor platform entry point
- Both surplus sensors appear as independent HA entities alongside the existing `SDM630SimSensor`

### Testing Approach

- No automated tests required for this story (HA sensor entities require full HA test harness)
- Manual verification: HA Developer Tools → States → check `sensor.sdm_raw_surplus` and `sensor.sdm_reported_surplus`
- Verify values match `EvaluationResult` fields (× 1000 for W conversion)
- Verify restore after HA restart: values persist, not `unknown`

### References

- [Source: epics-wallbox-dashboard-extension.md — Epic 1, Story 1.1]
- [Source: architecture.md — Implementation Patterns & Consistency Rules]
- [Source: architecture.md — EvaluationResult Structure]
- [Source: prd-wallbox-dashboard-extension.md — FR1, FR2, FR3, FR4]
- [Source: sensor.py — SDM630SimSensor pattern, _write_result(), _evaluation_tick()]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Completion Notes List

- Added `RestoreSensor`, `SensorDeviceClass` to `homeassistant.components.sensor` import
- `SDM630RawSurplusSensor` (extends `RestoreSensor`): `unique_id=sdm_raw_surplus`, `device_class=POWER`, `unit=W`, `should_poll=False`; `async_added_to_hass` restores last value; `@callback update_value()` writes rounded W value and calls `async_write_ha_state()`
- `SDM630ReportedSurplusSensor`: identical structure, `unique_id=sdm_reported_surplus`
- `SDM630SimSensor.__init__` extended with `_raw_surplus_sensor` and `_reported_surplus_sensor` (both `None`)
- `set_surplus_sensors()` stores both references on the `SDM630SimSensor` instance
- `_update_surplus_sensors()` called inside `_write_result()` — covers all three `_write_result` call sites (stale/failsafe, range-fail, success); wrapped in try/except with `_LOGGER.warning`; logs DEBUG with W values
- `async_setup_platform` creates both sensors, calls `set_surplus_sensors()`, passes all three to `async_add_entities()`
- Test stubs updated in `test_sensor.py`, `test_range_validation.py`, `test_surplus_engine_staleness.py`: added `_RestoreSensor`, `SensorDeviceClass` stubs to `ha_sensor_m`
- `test_setup_platform_passes_config_to_sensor` updated: expects 3 entities, verifies types for indices 1 and 2
- 363 tests pass, 0 failures

### Change Log

- 2026-03-22: Implemented Story 6-1 — added `SDM630RawSurplusSensor`, `SDM630ReportedSurplusSensor` to `sensor.py`; wired into `async_setup_platform`; hooked update into `_write_result()`; updated test stubs and setup-platform test
- 2026-03-22: Code Review fixes — guarded `float()` in `async_added_to_hass` with `try/except (ValueError, TypeError)`; moved `_LOGGER.debug` outside try-block in `_update_surplus_sensors` so it only fires on success

### File List

- `sensor.py` — Add `SDM630RawSurplusSensor`, `SDM630ReportedSurplusSensor`, wire into `async_setup_platform`, update from `_write_result()`
- `tests/test_sensor.py` — Add `RestoreSensor`/`SensorDeviceClass` stubs; update `test_setup_platform_passes_config_to_sensor` for 3 entities
- `tests/test_range_validation.py` — Add `RestoreSensor`/`SensorDeviceClass` stubs
- `tests/test_surplus_engine_staleness.py` — Add `RestoreSensor`/`SensorDeviceClass` stubs
