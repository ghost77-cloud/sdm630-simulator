# Story 7.2: Implement 5-Minute Warning Binary Sensor

Status: done

## Story

As Ghost,
I want a `binary_sensor.sdm_wallbox_poll_warning` that turns `on` automatically when
no wallbox poll is received for more than 5 minutes,
so that I notice without actively checking — the Lovelace card changes appearance.

## Acceptance Criteria

### AC1: No warning before threshold (299 s)

**Given** the last Modbus poll was received 299 seconds ago
**When** the warning evaluation runs
**Then** `binary_sensor.sdm_wallbox_poll_warning` is `off` (no warning)

### AC2: Warning at exact threshold (300 s)

**Given** the last Modbus poll was received exactly 300 seconds ago
**When** the warning evaluation runs
**Then** `binary_sensor.sdm_wallbox_poll_warning` is `on` (NFR6 strict `>=` boundary)

### AC3: Warning clears when new poll arrives

**Given** `binary_sensor.sdm_wallbox_poll_warning` is `on` (wallbox was silent)
**When** a new Modbus poll is received
**Then** the binary sensor transitions to `off` within the next warning evaluation
interval (FR7)

### AC4: No spurious warning on clean startup

**Given** the warning evaluation timer fires
**When** `sensor.sdm_wallbox_last_poll` has never been set (clean startup, no poll yet)
**Then** `binary_sensor.sdm_wallbox_poll_warning` is `off`

### AC5: Independent updates (FR9)

**Given** `sensor.sdm_wallbox_last_poll` updates and `sensor.sdm_raw_surplus` updates
simultaneously
**When** both are observed in HA Developer Tools
**Then** both can update independently and neither blocks the other

## Tasks / Subtasks

- [x] Task 1: Add `WALLBOX_POLL_WARNING_THRESHOLD` constant to `sensor.py` (AC: #1, #2)
  - [x] 1.1 Add `WALLBOX_POLL_WARNING_THRESHOLD: int = 300` at module level (after existing constants)
- [x] Task 2: Add `SDM630WallboxPollWarningSensor` class to `sensor.py` (AC: #1, #2, #3, #4, #5)
  - [x] 2.1 Add class extending `BinarySensorEntity`
  - [x] 2.2 Set `_attr_should_poll = False`
  - [x] 2.3 Set `_attr_device_class = BinarySensorDeviceClass.PROBLEM`
  - [x] 2.4 Set `_attr_unique_id = "sdm_wallbox_poll_warning"`
  - [x] 2.5 Set `_attr_name = "SDM Wallbox Poll Warning"`
  - [x] 2.6 Initialize `self._last_poll_dt: datetime | None = None` in `__init__`
  - [x] 2.7 Add `set_last_poll_dt(dt: datetime) -> None` method for the last-poll sensor to call
  - [x] 2.8 Add `_evaluate_warning(now) -> None` method (the interval callback): compute `is_on`, update `_attr_is_on`, call `async_write_ha_state()` — non-blocking
  - [x] 2.9 Implement `async_added_to_hass`: register `async_track_time_interval` with 60-second interval calling `_evaluate_warning`; unsubscribe on remove via `self.async_on_remove`
- [x] Task 3: Wire last-poll sensor → warning sensor in `async_setup_platform` (AC: #3)
  - [x] 3.1 Instantiate `SDM630WallboxPollWarningSensor` in `async_setup_platform`
  - [x] 3.2 Pass `poll_warning_sensor` reference to `SDM630WallboxLastPollSensor` so `on_poll` calls `poll_warning_sensor.set_last_poll_dt(dt_util.utcnow())`
  - [x] 3.3 Add `poll_warning_sensor` to `async_add_entities`
- [x] Task 4: Add required imports to `sensor.py` (AC: all)
  - [x] 4.1 Add `BinarySensorDeviceClass` and `BinarySensorEntity` imports
  - [x] 4.2 Add `datetime` to imports from `datetime` module

## Dev Notes

### Critical Architecture Constraints

1. **File boundary**: Only `sensor.py` is modified. `modbus_server.py`, `surplus_engine.py`,
   and register files are NOT touched.
2. **`BinarySensorEntity`** (not `RestoreSensor`): the warning state is always derivable
   from `_last_poll_dt` — no persistence needed. State is `False` on clean startup (AC4).
3. **Strict `>=` boundary**: `total_seconds() >= WALLBOX_POLL_WARNING_THRESHOLD` — not `>`.
   At exactly 300.0 s the state is `on` (AC2 / NFR6).
4. **Startup `None` guard**: if `_last_poll_dt is None`, result is `False` — no warning,
   no exception (AC4).
5. **Evaluation interval 60 s** (NFR2): use `async_track_time_interval`, not a busy loop.
6. **`set_last_poll_dt` called from `on_poll`**: runs inside the HA event loop
   (inherited from `SDM630WallboxLastPollSensor.on_poll` which is `@callback`).
   Must remain non-blocking.
7. **Warning clears on next tick** after new poll (AC3): `set_last_poll_dt` updates
   `_last_poll_dt`; the next 60-second tick will recompute and clear the state. Clearing
   happens within at most 60 seconds — within the documented contract.
8. **`async_on_remove`**: unsubscribe the time-interval listener to avoid leaked tasks
   when HA removes the entity.

### Dependency on Story 7-1

Story 7-2 **requires** that `SDM630WallboxLastPollSensor` (from Story 7-1) has been
implemented, because:

- `SDM630WallboxLastPollSensor.on_poll` must call
  `poll_warning_sensor.set_last_poll_dt(dt_util.utcnow())` in addition to updating its
  own state.
- The two sensors are cross-wired in `async_setup_platform`.

If Story 7-1 is not yet implemented, implement it first. If both are implemented
together in one batch, ensure the `on_poll` modification is part of the Task 3 wiring.

### Full Class Implementation

```python
from datetime import datetime
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.event import async_track_time_interval

WALLBOX_POLL_WARNING_THRESHOLD: int = 300  # seconds — module level constant


class SDM630WallboxPollWarningSensor(BinarySensorEntity):
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self) -> None:
        self._attr_name = "SDM Wallbox Poll Warning"
        self._attr_unique_id = "sdm_wallbox_poll_warning"
        self._attr_is_on = False
        self._last_poll_dt: datetime | None = None

    def set_last_poll_dt(self, dt: datetime) -> None:
        """Called by SDM630WallboxLastPollSensor.on_poll — non-blocking, no I/O."""
        self._last_poll_dt = dt

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._evaluate_warning,
                timedelta(seconds=60),
            )
        )

    @callback
    def _evaluate_warning(self, now) -> None:
        if self._last_poll_dt is None:
            is_on = False
        else:
            elapsed = (now - self._last_poll_dt).total_seconds()
            is_on = elapsed >= WALLBOX_POLL_WARNING_THRESHOLD
        if is_on != self._attr_is_on:
            self._attr_is_on = is_on
            self.async_write_ha_state()
            _LOGGER.debug(
                "SDM Wallbox poll warning → %s (elapsed=%s s)",
                "ON" if is_on else "OFF",
                None if self._last_poll_dt is None
                else int((now - self._last_poll_dt).total_seconds()),
            )
```

### Wiring in `async_setup_platform`

```python
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    name = config.get(CONF_NAME, DEFAULT_NAME)
    hass.loop.create_task(start_modbus_server())

    poll_warning_sensor = SDM630WallboxPollWarningSensor()
    wallbox_last_poll_sensor = SDM630WallboxLastPollSensor(
        poll_warning_sensor=poll_warning_sensor
    )
    input_data_block.set_poll_callback(wallbox_last_poll_sensor.on_poll)

    sensor = SDM630SimSensor(name, hass, config)
    async_add_entities([
        sensor,
        wallbox_last_poll_sensor,
        poll_warning_sensor,
    ])
```

Alternatively, if avoiding constructor injection, set the reference after construction:

```python
    poll_warning_sensor = SDM630WallboxPollWarningSensor()
    wallbox_last_poll_sensor = SDM630WallboxLastPollSensor()
    wallbox_last_poll_sensor.set_warning_sensor(poll_warning_sensor)
    input_data_block.set_poll_callback(wallbox_last_poll_sensor.on_poll)
```

Either approach is acceptable; choose the one that minimises changes to the 7-1
`SDM630WallboxLastPollSensor` class.

### Modified `SDM630WallboxLastPollSensor.on_poll` (Story 7-1 → 7-2 extension)

```python
@callback
def on_poll(self) -> None:
    try:
        now = dt_util.utcnow()
        self._attr_native_value = now
        self.async_write_ha_state()
        if self._poll_warning_sensor is not None:
            self._poll_warning_sensor.set_last_poll_dt(now)
        _LOGGER.debug("SDM Wallbox last poll updated: %s", now)
    except Exception:  # noqa: BLE001
        _LOGGER.warning("Failed to update sdm_wallbox_last_poll sensor", exc_info=True)
```

### Imports Required

Add to `sensor.py`:

```python
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
```

`datetime` is already available via `from datetime import timedelta` — extend to:

```python
from datetime import datetime, timedelta
```

`async_track_time_interval` is already imported at module level — no additional import
needed.

### Naming Conventions

| Item | Convention | Value |
|------|-----------|-------|
| Class | `CamelCase` | `SDM630WallboxPollWarningSensor` |
| Entity ID (auto) | HA-generated | `binary_sensor.sdm_wallbox_poll_warning` |
| Unique ID | `snake_case` | `sdm_wallbox_poll_warning` |
| Threshold constant | `UPPER_SNAKE_CASE` | `WALLBOX_POLL_WARNING_THRESHOLD` |
| Interval callback | `snake_case` | `_evaluate_warning` |
| Logger | module-level | `_LOGGER` (already exists) |

### What NOT To Do

- **DO NOT** use `await` in `_evaluate_warning` or `set_last_poll_dt` — both must be
  synchronous.
- **DO NOT** use `>` instead of `>=` for the threshold comparison — NFR6 requires that
  exactly 300 s triggers warning.
- **DO NOT** implement the Lovelace card here — that is Story 8-1.
- **DO NOT** modify `modbus_server.py` for this story — the poll hook was added in 7-1.
- **DO NOT** add new Python dependencies — only `homeassistant` core.
- **DO NOT** create new files — all code goes into `sensor.py`.
- **DO NOT** use `RestoreSensor` for the binary sensor — the warning state is always
  recomputed from `_last_poll_dt`; no persistence is needed.

### Testing Approach

No automated unit tests required (HA binary sensor entity requires full HA harness).
Manual verification:

1. Start HA with the component loaded.
2. Let the wallbox poll → confirm `binary_sensor.sdm_wallbox_poll_warning` is `off`.
3. Stop wallbox polls, wait 5 min → confirm sensor turns `on` within 60 s of the
   crossing the 300-second boundary.
4. Resume polls → confirm sensor turns `off` within 60 s (AC3).
5. Restart HA without any prior poll → confirm sensor starts `off` (AC4).

### Project Structure Notes

- All changes in `sensor.py` only.
- `WALLBOX_POLL_WARNING_THRESHOLD` is a module-level constant placed after existing
  module-level constants (`DEFAULT_NAME`, `SCAN_INTERVAL`, `ENTITY_ROLE_TO_CACHE_KEY`).
- `SDM630WallboxPollWarningSensor` is added after `SDM630WallboxLastPollSensor` in the
  file to preserve declaration order for cross-referencing.

### References

- Epic spec: [_bmad-output/planning-artifacts/epics-wallbox-dashboard-extension.md](../../_bmad-output/planning-artifacts/epics-wallbox-dashboard-extension.md) — Epic 2, Story 2.2
- Previous story: [_bmad-output/implementation-artifacts/7-1-add-last-poll-timestamp-sensor-and-modbus-hook.md](7-1-add-last-poll-timestamp-sensor-and-modbus-hook.md)
- Architecture: [_bmad-output/planning-artifacts/architecture.md](../../_bmad-output/planning-artifacts/architecture.md) — Naming Conventions
- AGENTS.md — file boundary rule, `_attr_should_poll = False`, `@callback` pattern

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- Updated three test fixtures (`test_sensor.py`, `test_range_validation.py`, `test_surplus_engine_staleness.py`) to stub `homeassistant.components.binary_sensor` — required because `sensor.py` now imports `BinarySensorEntity` and `BinarySensorDeviceClass`.
- Updated `TestSetupPlatform::test_setup_platform_passes_config_to_sensor` to assert 5 entities (was 4) and validate `SDM630WallboxPollWarningSensor` is the 5th entity.
- Used post-construction setter (`set_warning_sensor`) to wire `SDM630WallboxLastPollSensor` → `SDM630WallboxPollWarningSensor`, minimising changes to `SDM630WallboxLastPollSensor.__init__`.

### Completion Notes List

- All 363 tests pass.
- Only `sensor.py` modified (production code); three test fixtures updated for stub completeness.
- `_evaluate_warning` only calls `async_write_ha_state()` when state actually changes (optimisation over spec).
- Story 7-1 status was already `done` in its own file but showed `ready-for-dev` in sprint-status.yaml — corrected in sprint-status update.

### File List

- `sensor.py` — added imports, constant, `SDM630WallboxPollWarningSensor` class, wiring in `async_setup_platform`, `SDM630WallboxLastPollSensor` extension
- `tests/test_sensor.py` — binary_sensor stub + entity count assertion update
- `tests/test_range_validation.py` — binary_sensor stub
- `tests/test_surplus_engine_staleness.py` — binary_sensor stub
