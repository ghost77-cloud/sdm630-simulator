# Story 1.3: Integration Wiring in `sensor.py` and Evaluation Loop

Status: ready-for-dev

## Story

As a developer (Ghost),
I want `sensor.py` to instantiate `SurplusEngine`, subscribe to entity state
changes, run the async evaluation loop via `async_track_time_interval`, and
write `EvaluationResult.reported_kw` to the Modbus register,
so that the engine is connected to the existing HA lifecycle and Modbus
infrastructure without altering any of the unchanged modules.

## Acceptance Criteria

**AC1 — SurplusEngine instantiation and state-change subscriptions**

Given `SDM630SimSensor.async_added_to_hass()` runs
When called by HA during platform setup
Then a `SurplusEngine` instance is created with the parsed config dict
And `async_track_state_change_event(hass, entity_ids, _handle_state_change)` is
called for all numeric sensor entity IDs from `config[CONF_ENTITIES]`
And each subscription is cleaned up via `self.async_on_remove(unsub)` (prevents
memory leaks on HA reload — pattern from `growatt_local`)
And `async_track_time_interval(hass, self._evaluation_tick, interval)` starts
the evaluation loop (integrates with HA's event loop shutdown — not
`asyncio.create_task`)
And the interval timer subscription is also cleaned up via `self.async_on_remove`

**AC2 — State-change handler: cache update**

Given a state-change event fires for a tracked entity
When `_handle_state_change(event)` is called
Then the new state is extracted via `event.data.get("new_state")`
And if `state.state` is `STATE_UNAVAILABLE` or `STATE_UNKNOWN`, the cache entry
is NOT updated — it remains invalid/absent
And if the value is a valid numeric string, `float(state.state)` is stored in
`self._sensor_cache` keyed by the corresponding `CACHE_KEY_*` constant
And NO Modbus register write happens in `_handle_state_change` (Modbus is
written only in `_evaluation_tick`)

**AC3 — Evaluation tick: SensorSnapshot assembly and engine call**

Given `_evaluation_tick` fires at each configured interval
When `SurplusEngine.evaluate_cycle(snapshot)` is called (stub)
Then the returned `EvaluationResult` is used to call
`input_data_block.set_float(TOTAL_POWER, result.reported_kw)`
And no blocking I/O occurs in the event loop
And the stub `evaluate_cycle()` returns the default `EvaluationResult` from
Story 1.2 — it never raises `NotImplementedError`

**AC4 — SensorSnapshot: sun.sun solar boundary times**

Given `_evaluation_tick` assembles the `SensorSnapshot`
When building snapshot fields before calling `evaluate_cycle`
Then both solar boundary times are read from `hass.states.get("sun.sun")`:
`snapshot.sunset_time` from attribute `"next_setting"` and
`snapshot.sunrise_time` from attribute `"next_rising"`, each parsed as a
timezone-aware `datetime` via `dt_util.parse_datetime`
And `sun.sun` is a built-in HA integration — both attributes normally resolve to
valid `datetime` objects
And as defensive coding: if `sun.sun` state is unavailable or either attribute is
absent, the corresponding snapshot field is set to `None` — no FAILSAFE is
triggered solely because `sun.sun` is temporarily missing

**AC5 — Startup INFO log**

Given component startup completes (first tick fires)
When the first evaluation tick fires
Then an INFO log entry confirms startup:
`"SDM630 SurplusEngine started. Interval=%ds, entities=%d configured"`

**AC6 — Lifecycle cleanup**

Given HA stops or the component is reloaded
When all `async_on_remove` callbacks fire
Then `async_track_time_interval` unsubscribes cleanly
And `async_track_state_change_event` unsubscribes cleanly

## Tasks / Subtasks

- [ ] Extend `sensor.py`: constructor accepts `config` dict (AC: #1)
  - [ ] `__init__(self, name, hass, config)` — store `self._config = config`
  - [ ] Initialize `self._sensor_cache: dict = {}`
  - [ ] Initialize `self._engine: SurplusEngine | None = None`
  - [ ] Initialize `self._first_tick: bool = True` (for startup log)
- [ ] Implement `async_added_to_hass()` wiring (AC: #1)
  - [ ] Create `SurplusEngine(self._config)` and assign to `self._engine`
  - [ ] Build `entity_ids` list from `config[CONF_ENTITIES]` for numeric
    sensors (soc, power_to_grid, pv_production, power_to_user — exclude sun,
    weather, forecast_solar which are NOT numeric state subscriptions)
  - [ ] Subscribe to state changes: `async_track_state_change_event` → `async_on_remove`
  - [ ] Start evaluation loop: `async_track_time_interval` → `async_on_remove`
- [ ] Implement `_handle_state_change(event)` (AC: #2)
  - [ ] Extract `new_state = event.data.get("new_state")`
  - [ ] Guard: if `new_state is None` return
  - [ ] Guard: if `new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)` return
  - [ ] Identify entity_id → cache key using `ENTITY_TO_CACHE_KEY` mapping dict
  - [ ] Store `float(new_state.state)` in `self._sensor_cache[cache_key]`
  - [ ] Handle `ValueError`/`TypeError` with `_LOGGER.debug`
- [ ] Implement `async def _evaluation_tick(self, now)` (AC: #3, #4, #5)
  - [ ] Emit startup INFO log on first tick, then set `self._first_tick = False`
  - [ ] Read numeric values from `self._sensor_cache` with `.get()` and `0.0` defaults
  - [ ] Read `sun.sun` state via `hass.states.get("sun.sun")` and parse times
  - [ ] Build `SensorSnapshot(...)` with all fields
  - [ ] `result = await self._engine.evaluate_cycle(snapshot)`
  - [ ] `input_data_block.set_float(TOTAL_POWER, result.reported_kw)`
  - [ ] `self._attr_native_value = result.reported_kw` + `self.async_write_ha_state()`
- [ ] Update `async_setup_platform` to pass config to sensor (AC: #1)
  - [ ] `SDM630SimSensor(name, hass, config)` — add config argument
  - [ ] `start_modbus_server()` call stays unchanged
- [ ] Add imports to `sensor.py` (AC: #1, #4)
  - [ ] `from homeassistant.helpers.event import async_track_time_interval`
    (already has `async_track_state_change_event`)
  - [ ] `from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN`
  - [ ] `from homeassistant import util as dt_util` OR
    `from homeassistant.util import dt as dt_util`
  - [ ] `from datetime import timedelta` (already present)
  - [ ] `from .surplus_engine import SurplusEngine, SensorSnapshot`

## Dev Notes

### Critical: What Changes vs. What Stays Unchanged

**Modified file: `sensor.py`** — extend only, no structural rewrites.

**Unchanged files (DO NOT TOUCH):**
`modbus_server.py`, `registers.py`, `sdm630_input_registers.py`,
`sdm630_holding_registers.py`, `__init__.py` (config parsing is Story 1.1's
domain).

**Prerequisite files (must exist from prior stories):**
- `surplus_engine.py` (Story 1.2) — must be importable
- `__init__.py` with config dict passed through platform setup (Story 1.1)

### Current `sensor.py` State (Before This Story)

The existing `sensor.py` has:

- `async_track_state_change_event` already imported ✅
- `self.async_on_remove()` pattern already used ✅
- `input_data_block.set_float(TOTAL_POWER, ...)` pattern already present ✅
- `self.hass` stored in constructor ✅
- **PROBLEM:** Hardcoded entity list `["sensor.sph10000_ac_to_grid_total",
  "sensor.sph10000_output_power"]` — must be replaced with dynamic entities
  from config
- **PROBLEM:** `_handle_state_change` currently writes directly to Modbus —
  must be changed to cache-only update; Modbus write moves to `_evaluation_tick`
- **MISSING:** `async_track_time_interval` import
- **MISSING:** `dt_util` import for `sun.sun` time parsing
- **MISSING:** `SurplusEngine` import and instantiation

### Entity-to-Cache-Key Mapping

Define a module-level dict (or compute in `async_added_to_hass`) that maps
config entity role keys to CACHE_KEY constants from `surplus_engine.py`:

```python
# In sensor.py (or as a module constant)
ENTITY_ROLE_TO_CACHE_KEY = {
    "soc":           CACHE_KEY_SOC,            # "soc_percent"
    "power_to_grid": CACHE_KEY_POWER_TO_GRID,  # "power_to_grid_w"
    "pv_production": CACHE_KEY_PV_PRODUCTION,  # "pv_production_w"
    "power_to_user": CACHE_KEY_POWER_TO_USER,  # "power_to_user_w"
}
```

Entities `sun`, `weather`, `forecast_solar` are excluded from state-change
subscriptions — they are handled differently (`sun.sun` is read directly in
`_evaluation_tick`; `weather`/`forecast_solar` are consumed by `ForecastConsumer`
in Epic 3).

### Import `CACHE_KEY_*` from `surplus_engine.py`

Story 1.2 defines these constants in `surplus_engine.py`:

```python
CACHE_KEY_SOC              = "soc_percent"
CACHE_KEY_POWER_TO_GRID    = "power_to_grid_w"
CACHE_KEY_PV_PRODUCTION    = "pv_production_w"
CACHE_KEY_POWER_TO_USER    = "power_to_user_w"
CACHE_KEY_BATTERY_DISCHARGE = "battery_discharge_w"
```

Import them into `sensor.py`:

```python
from .surplus_engine import (
    SurplusEngine,
    SensorSnapshot,
    CACHE_KEY_SOC,
    CACHE_KEY_POWER_TO_GRID,
    CACHE_KEY_PV_PRODUCTION,
    CACHE_KEY_POWER_TO_USER,
)
```

### Evaluation Tick: Full Implementation Pattern

```python
async def _evaluation_tick(self, now) -> None:
    """Called by async_track_time_interval at each evaluation cycle."""
    if self._first_tick:
        entities = self._config.get(CONF_ENTITIES, {})
        _LOGGER.info(
            "SDM630 SurplusEngine started. Interval=%ds, entities=%d configured",
            self._config.get("evaluation_interval", 15),
            len(entities),
        )
        self._first_tick = False

    # Read sun.sun for solar boundary times (defensive — never triggers FAILSAFE)
    sunset_time = None
    sunrise_time = None
    sun_state = self.hass.states.get("sun.sun")
    if sun_state and sun_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        raw_setting = sun_state.attributes.get("next_setting")
        raw_rising  = sun_state.attributes.get("next_rising")
        if raw_setting:
            sunset_time  = dt_util.parse_datetime(raw_setting)
        if raw_rising:
            sunrise_time = dt_util.parse_datetime(raw_rising)

    snapshot = SensorSnapshot(
        soc_percent     = self._sensor_cache.get(CACHE_KEY_SOC, 0.0),
        power_to_grid_w = self._sensor_cache.get(CACHE_KEY_POWER_TO_GRID, 0.0),
        pv_production_w = self._sensor_cache.get(CACHE_KEY_PV_PRODUCTION, 0.0),
        power_to_user_w = self._sensor_cache.get(CACHE_KEY_POWER_TO_USER, 0.0),
        timestamp       = now,
        sunset_time     = sunset_time,
        sunrise_time    = sunrise_time,
    )

    result = await self._engine.evaluate_cycle(snapshot)
    input_data_block.set_float(TOTAL_POWER, result.reported_kw)
    self._attr_native_value = result.reported_kw
    self.async_write_ha_state()
```

### State-Change Handler: Cache-Only Pattern

```python
@callback
def _handle_state_change(self, event) -> None:
    new_state = event.data.get("new_state")
    if new_state is None:
        return
    if new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return
    entity_id = new_state.entity_id
    # Look up which role this entity plays
    for role, eid in self._config.get(CONF_ENTITIES, {}).items():
        if eid == entity_id and role in ENTITY_ROLE_TO_CACHE_KEY:
            try:
                self._sensor_cache[ENTITY_ROLE_TO_CACHE_KEY[role]] = float(new_state.state)
            except (ValueError, TypeError) as exc:
                _LOGGER.debug("Cannot parse state for %s: %s", entity_id, exc)
            break
```

### `async_added_to_hass` Wiring Pattern

```python
async def async_added_to_hass(self) -> None:
    await super().async_added_to_hass()
    self._engine = SurplusEngine(self._config)

    # Collect numeric entity IDs to subscribe to
    entities_cfg = self._config.get(CONF_ENTITIES, {})
    numeric_entity_ids = [
        entity_id
        for role, entity_id in entities_cfg.items()
        if role in ENTITY_ROLE_TO_CACHE_KEY
    ]

    # Subscribe to state changes
    if numeric_entity_ids:
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, numeric_entity_ids, self._handle_state_change
            )
        )

    # Start evaluation loop
    interval = timedelta(seconds=self._config.get("evaluation_interval", 15))
    self.async_on_remove(
        async_track_time_interval(self.hass, self._evaluation_tick, interval)
    )
```

### `async_setup_platform` Change

```python
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    name = config.get(CONF_NAME, DEFAULT_NAME)
    hass.loop.create_task(start_modbus_server())   # unchanged
    sensor = SDM630SimSensor(name, hass, config)   # add config argument
    async_add_entities([sensor])
```

### `dt_util` Import Note

```python
from homeassistant.util import dt as dt_util
```

`dt_util.parse_datetime(string)` returns a timezone-aware `datetime` or `None`
if the string is malformed. Use it — do NOT use `datetime.fromisoformat()` which
lacks timezone awareness for all HA datetime strings.

### Epic 1 End State (After All 4 Stories Complete)

After Story 1.3, the system logs each tick:
`state=INACTIVE reason=engine_not_yet_implemented reported=0.00kW`

This is correct behavior — the stub engine returns the default `EvaluationResult`.
Story 1.4 adds the DEBUG log formatting; the actual surplus logic is Epic 2.

### Regression Prevention

- `start_modbus_server()` stays in `async_setup_platform` — do NOT move it
- `TOTAL_POWER` register address is imported from `sdm630_input_registers` — do
  NOT inline the address value
- `input_data_block` is imported from `.modbus_server` — do NOT re-import or
  re-instantiate
- The existing Modbus TCP server on port 5020 is completely unaffected

### Project Structure Notes

```
custom_components/sdm630_simulator/
├── __init__.py                (Story 1.1: config parsing — DO NOT MODIFY)
├── sensor.py                  ← MODIFY THIS (this story)
├── surplus_engine.py          (Story 1.2: must exist — DO NOT MODIFY)
├── modbus_server.py           (UNCHANGED)
├── registers.py               (UNCHANGED)
├── sdm630_input_registers.py  (UNCHANGED)
├── sdm630_holding_registers.py (UNCHANGED)
└── manifest.json              (UNCHANGED)
```

### References

- Story AC and user story: [Source: `_bmad-output/planning-artifacts/epics.md` — Story 1.3]
- Data flow architecture: [Source: `_bmad-output/planning-artifacts/architecture.md` — Decision 1: Hybrid Cache+Loop, Component Boundary Diagram]
- Cache key constants: [Source: `_bmad-output/planning-artifacts/architecture.md` — Sensor Cache Keys]
- Logging patterns: [Source: `_bmad-output/planning-artifacts/architecture.md` — Logging Patterns]
- DEFAULTS dict: [Source: `_bmad-output/planning-artifacts/architecture.md` — Configuration Defaults]
- Entity config schema: [Source: `_bmad-output/planning-artifacts/architecture.md` — Configuration Schema]
- `async_on_remove` pattern: [Source: existing `sensor.py` — already used]
- `async_track_state_change_event` pattern: [Source: existing `sensor.py` — already used]
- `async_track_time_interval`: [Source: `_bmad-output/planning-artifacts/epics.md` — Story 1.3 implementation note]
- `SurplusEngine(config)` constructor: [Source: `_bmad-output/implementation-artifacts/1-2-surplus-engine-py-module-scaffold-with-dataclasses.md` — SurplusEngine.__init__ Signature]
- `evaluate_cycle` must be `async def`: [Source: `_bmad-output/implementation-artifacts/1-2-surplus-engine-py-module-scaffold-with-dataclasses.md` — evaluate_cycle MUST be async def]
- Python 3.12, pymodbus >=3.11.1: [Source: `_bmad-output/planning-artifacts/architecture.md` — Technology Versions]

## Dev Agent Record

### Agent Model Used

_to be filled by dev agent_

### Debug Log References

### Completion Notes List

### File List
