# Story 7.1: Add Last-Poll Timestamp Sensor and Modbus Hook

Status: ready-for-dev

## Story

As Ghost,
I want to see `sensor.sdm_wallbox_last_poll` updated every time the wallbox polls the
Modbus server,
so that I can verify the wallbox is actively communicating without opening a network
trace.

## Acceptance Criteria

### AC1: Sensor updated on FC04 poll

**Given** the Modbus TCP server is running and the wallbox issues a function-code-04
read request
**When** the request is received by `modbus_server.py`
**Then** `sensor.sdm_wallbox_last_poll` is updated with the current UTC datetime within
500 ms (NFR1)
**And** the Modbus response to the wallbox is correct and unaffected by the sensor update

### AC2: Non-blocking poll callback

**Given** a callback function is registered on the `SDM630DataBlock` for poll events
**When** the poll notification fires
**Then** the callback is non-blocking (no `await`, no I/O in the synchronous callback
path)

### AC3: Restore state after HA restart

**Given** HA has been restarted and the wallbox has not yet polled
**When** `SDM630WallboxLastPollSensor.async_added_to_hass` completes
**Then** the sensor displays the last persisted datetime value (not `unknown`)

### AC4: Fail-silent on callback error

**Given** an exception occurs in the sensor update callback
**When** the Modbus poll event fires
**Then** the exception is caught and logged via `_LOGGER.warning()`, and the Modbus
server continues responding normally (NFR4, NFR5)

## Tasks / Subtasks

- [ ] Task 1: Add `SDM630WallboxLastPollSensor` class to `sensor.py` (AC: #1, #2, #3, #4)
  - [ ] 1.1 Add class extending `RestoreSensor`
  - [ ] 1.2 Set `_attr_should_poll = False`
  - [ ] 1.3 Set `_attr_device_class = SensorDeviceClass.TIMESTAMP`
  - [ ] 1.4 Set `_attr_unique_id = "sdm_wallbox_last_poll"`
  - [ ] 1.5 Set `_attr_name = "SDM Wallbox Last Poll"`
  - [ ] 1.6 Implement `async_added_to_hass` restoring last `datetime` via `async_get_last_sensor_data()`
  - [ ] 1.7 Add `on_poll` method decorated with `@callback`, recording `dt_util.utcnow()` and calling `async_write_ha_state()`
  - [ ] 1.8 Wrap `on_poll` body in `try/except`, logging failures via `_LOGGER.warning()`
- [ ] Task 2: Add poll-callback mechanism to `SDM630DataBlock` in `modbus_server.py` (AC: #1, #2, #4)
  - [ ] 2.1 Add `self._poll_callback: Callable | None = None` to `__init__`
  - [ ] 2.2 Add `set_poll_callback(cb: Callable) -> None` public method
  - [ ] 2.3 Override `getValues(address, count)` — call `super().getValues(...)` first, then invoke `self._poll_callback()` if set, return the super result
  - [ ] 2.4 Wrap `_poll_callback` invocation in `try/except`, logging via `_LOGGER.warning()`
  - [ ] 2.5 Add `Callable` to imports (`from typing import Callable`)
- [ ] Task 3: Wire sensor and callback in `async_setup_platform` in `sensor.py` (AC: #1, #3)
  - [ ] 3.1 Instantiate `SDM630WallboxLastPollSensor` in `async_setup_platform`
  - [ ] 3.2 Register the callback: `input_data_block.set_poll_callback(wallbox_last_poll_sensor.on_poll)`
  - [ ] 3.3 Pass `wallbox_last_poll_sensor` to `async_add_entities` together with existing sensors

## Dev Notes

### Critical Architecture Constraints

1. **File boundaries**: Changes touch exactly two files:
   - `sensor.py` — new `SDM630WallboxLastPollSensor` class + wiring in `async_setup_platform`
   - `modbus_server.py` — poll-callback slot in `SDM630DataBlock` (`getValues` override + `set_poll_callback`)
2. **`surplus_engine.py`, `registers.py`, `sdm630_input_registers.py`, `sdm630_holding_registers.py` are NOT modified.**
3. **Callback must be non-blocking**: `on_poll` runs in the HA event loop (wired via `@callback`). No `await`, no blocking I/O.
4. **Fail-silent pattern**: Any exception in `on_poll` or the `_poll_callback` wrapper in `SDM630DataBlock` must be caught and logged — never crash the server.
5. **`getValues` override timing**: Call `super().getValues(...)` first to assemble the Modbus response, then invoke the callback. The wallbox must receive the correct response regardless of any callback failure.
6. **`RestoreSensor` for datetime**: `_attr_native_value` must be a `datetime` object (or `None`). The `SensorDeviceClass.TIMESTAMP` class requires `datetime`. On restore, cast the native_value from `SensorExtraStoredData` back to `datetime` if it is a string.

### Dependency Note — Story 6-1

Story 6-1 (`SDM630RawSurplusSensor`, `SDM630ReportedSurplusSensor`) is currently
**ready-for-dev** and not yet implemented. Story 7-1 is independent: it only adds
`SDM630WallboxLastPollSensor` and touches `modbus_server.py`. Coordination point:

- `async_setup_platform` wiring in Task 3 updates the existing `async_add_entities`
  call. If 6-1 is implemented first, extend the entities list to include
  `wallbox_last_poll_sensor` alongside the surplus sensors. If 7-1 is implemented first,
  add it to the current single-entity list.

### RestoreSensor Pattern for Timestamp

```python
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.util import dt as dt_util

class SDM630WallboxLastPollSensor(RestoreSensor):
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self) -> None:
        self._attr_name = "SDM Wallbox Last Poll"
        self._attr_unique_id = "sdm_wallbox_last_poll"
        self._attr_native_value = None  # datetime | None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data and last_data.native_value is not None:
            # native_value may be a datetime or an ISO string depending on HA version
            val = last_data.native_value
            if isinstance(val, str):
                val = dt_util.parse_datetime(val)
            self._attr_native_value = val

    @callback
    def on_poll(self) -> None:
        """Called by Modbus poll hook — runs in HA event loop, must be non-blocking."""
        try:
            self._attr_native_value = dt_util.utcnow()
            self.async_write_ha_state()
            _LOGGER.debug("SDM Wallbox last poll updated: %s", self._attr_native_value)
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Failed to update sdm_wallbox_last_poll sensor", exc_info=True)
```

### Poll-Callback Slot in `SDM630DataBlock`

```python
from typing import Callable

class SDM630DataBlock(ModbusSparseDataBlock):
    def __init__(self, registers: SDM630Registers):
        super().__init__()
        self.registers = registers
        self._poll_callback: Callable | None = None  # NEW
        self._float_map_to_regs()

    def set_poll_callback(self, cb: Callable) -> None:
        """Register a callback invoked on every Modbus read (getValues)."""
        self._poll_callback = cb

    def getValues(self, address, count=1):
        """Override to fire poll callback after assembling Modbus response."""
        values = super().getValues(address, count)
        if self._poll_callback is not None:
            try:
                self._poll_callback()
            except Exception:  # noqa: BLE001
                _LOGGER.warning("SDM630DataBlock poll callback failed", exc_info=True)
        return values
```

### Wiring in `async_setup_platform`

```python
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    name = config.get(CONF_NAME, DEFAULT_NAME)
    hass.loop.create_task(start_modbus_server())

    wallbox_last_poll_sensor = SDM630WallboxLastPollSensor()
    input_data_block.set_poll_callback(wallbox_last_poll_sensor.on_poll)

    sensor = SDM630SimSensor(name, hass, config)
    async_add_entities([sensor, wallbox_last_poll_sensor])
```

> Note: When story 6-1 is also implemented, extend the list:
> `async_add_entities([sensor, raw_surplus_sensor, reported_surplus_sensor, wallbox_last_poll_sensor])`

### Existing Code Patterns to Follow

- **`SDM630SimSensor`** in `sensor.py`: reference for `_attr_should_poll = False`,
  `@callback` decorator, `async_write_ha_state()`.
- **`SDM630DataBlock.setValues`** in `modbus_server.py`: demonstrates the existing
  `try/except` guard pattern and `super()` delegation. `getValues` follows the same
  shape.
- **`_LOGGER`**: `logging.getLogger(__name__)` already declared at module level in both
  files — do not redeclare.
- **`input_data_block`**: already imported in `sensor.py` from `.modbus_server`.
- **`dt_util`**: already imported in `sensor.py` as `from homeassistant.util import dt as dt_util`.

### Imports Required

In `sensor.py` — add to the `homeassistant.components.sensor` import:

```python
from homeassistant.components.sensor import (
    RestoreSensor,     # ADD
    SensorDeviceClass,  # ADD
    SensorEntity,      # already present
)
```

In `modbus_server.py` — add:

```python
from typing import Callable  # ADD
```

### Naming Conventions

| Item | Convention | Value |
|------|-----------|-------|
| Class | `CamelCase` | `SDM630WallboxLastPollSensor` |
| Entity ID (auto) | HA-generated | `sensor.sdm_wallbox_last_poll` |
| Unique ID | `snake_case` | `sdm_wallbox_last_poll` |
| Method `set_poll_callback` | `snake_case` | matches existing `set_float`, `get_float` naming |
| Constant (story 7-2) | `UPPER_SNAKE_CASE` | `WALLBOX_POLL_WARNING_THRESHOLD = 300` (NOT in this story) |
| Logger | module-level `_LOGGER` | exists in both files |

### What NOT To Do

- **DO NOT** call the poll callback *before* `super().getValues(...)` — response must be correct regardless of callback outcome.
- **DO NOT** use `await` in `on_poll` or the `_poll_callback` invocation — both run synchronously.
- **DO NOT** modify `surplus_engine.py`, `registers.py`, or any register file.
- **DO NOT** add new dependencies — only `homeassistant` core, `pymodbus`, and Python stdlib.
- **DO NOT** create new files — all code goes into `sensor.py` and `modbus_server.py`.
- **DO NOT** add `_attr_state_class` to the timestamp sensor — `SensorDeviceClass.TIMESTAMP` does not use state classes.
- **DO NOT** implement the 5-minute warning binary sensor here — that is Story 7-2.

### Testing Approach

No automated unit tests required for this story (HA sensor entity requires full HA
harness). Manual verification:

1. Start Modbus TCP server (`python modbus_server.py`).
2. Send a FC04 read request from any Modbus client to port 5020.
3. Verify `sensor.sdm_wallbox_last_poll` in HA Developer Tools → States shows an
   ISO-8601 UTC timestamp refreshed on each poll.
4. Restart HA; confirm sensor shows last persisted timestamp (not `unknown`).
5. Confirm Modbus responses remain correct (register values unchanged).

### Project Structure Notes

- `sensor.py` is the HA sensor platform file — all HA entity classes live here.
- `modbus_server.py` contains `SDM630DataBlock` and the Modbus context — poll hook is
  the only change here.
- `input_data_block` is the global instance used by both files — wiring via
  `set_poll_callback` is intentional and matches the established pattern of
  `sensor.py` reading `input_data_block` from `modbus_server`.
- The `if __package__:` dual-import guard is already present in `modbus_server.py`.
  No changes required there.

### References

- Epic spec: [_bmad-output/planning-artifacts/epics-wallbox-dashboard-extension.md](../../_bmad-output/planning-artifacts/epics-wallbox-dashboard-extension.md) — Epic 2, Story 2.1
- Architecture: [_bmad-output/planning-artifacts/architecture.md](../../_bmad-output/planning-artifacts/architecture.md) — Naming Conventions, Sensor Cache Pattern
- AGENTS.md — file boundary and dual-import guard rules
- Prior pattern: [_bmad-output/implementation-artifacts/6-1-add-raw-and-reported-surplus-sensor-entities.md](6-1-add-raw-and-reported-surplus-sensor-entities.md) — `RestoreSensor` pattern reference

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

### File List
