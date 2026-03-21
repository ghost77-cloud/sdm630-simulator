# Story 3.1: Forecast Data Fetching and Parsing

Status: ready-for-dev

## Story

As the surplus engine,
I want `ForecastConsumer.get_forecast(hass)` to asynchronously fetch weather
forecast and solar production forecast data from HA,
so that the engine has predictive data available each evaluation cycle to make
smarter SOC decisions.

## Acceptance Criteria

**AC1 — Weather forecast fetched and cloud coverage averaged**

Given `weather:` entity is configured in `entities:` block and the entity is available\
When `ForecastConsumer.get_forecast(hass)` is awaited\
Then `await hass.services.async_call("weather", "get_forecasts",`
`{"entity_id": config_entities["weather"], "type": "hourly"},`
`blocking=True, return_response=True)` is executed\
And the hourly `cloud_coverage` values for the **next 6 entries** in the
forecast list are extracted\
And entries missing `cloud_coverage` are skipped (no error, just excluded from avg)\
And the values are averaged into a single `cloud_coverage_avg: float` (0–100)\
And `result.forecast_available` is set to `True`

**AC2 — Solar forecast entity state read**

Given `forecast_solar:` entity is configured and its HA state is a numeric string\
When `get_forecast(hass)` is awaited\
Then `hass.states.get(config_entities["forecast_solar"]).state` is read\
And `float(state)` is stored as `result.solar_forecast_kwh_today`\
And `forecast_available` remains `True` if weather fetch also succeeded

**AC3 — Error/unavailable handled gracefully**

Given either forecast entity is `unavailable`, the `async_call` raises an
exception, the response dict is malformed, or `float()` conversion fails\
When `get_forecast(hass)` is awaited\
Then the exception is caught — **not propagated**\
And the method returns `ForecastData(forecast_available=False,`
`cloud_coverage_avg=50.0, solar_forecast_kwh_today=None)` (conservative defaults)\
And `_LOGGER.warning("Forecast unavailable: %s. Using conservative defaults.", reason)`
is emitted once

**AC4 — Weather entity not configured: silent no-op**

Given `weather:` key is absent from the `entities:` config block (optional entity)\
When `get_forecast(hass)` is called\
Then the method returns `ForecastData()` (all defaults) immediately\
And **no** WARNING is logged — this is the expected degraded mode

**AC5 — Partial configuration: only one source available**

Given only `forecast_solar:` is configured (no `weather:` entity)\
When `get_forecast(hass)` is awaited\
Then `solar_forecast_kwh_today` is populated from the entity state\
And `cloud_coverage_avg` retains the neutral default (50.0)\
And `forecast_available` is set to `True` (partial data is still useful)

**AC6 — Result flows into SensorSnapshot.forecast**

Given `ForecastConsumer.get_forecast(hass)` returns a `ForecastData` instance\
When `SurplusEngine._evaluation_tick` builds the `SensorSnapshot`\
Then `snapshot.forecast = await self._forecast_consumer.get_forecast(hass)` is the
exact assignment\
And `SurplusCalculator` accesses only `ForecastData` fields (no `hass` reference
in `SurplusCalculator` — HA-free purity is preserved)

## Tasks / Subtasks

- [ ] Task 1: Implement `ForecastConsumer.get_forecast(hass)` in `surplus_engine.py` (AC: #1–#5)
  - [ ] Read `entities = self._config.get("entities", {})` at top of method
  - [ ] Check `weather_entity = entities.get("weather")` — if `None`, return `ForecastData()` silently (AC: #4)
  - [ ] Wrap entire fetch in `try/except Exception as exc:` block (AC: #3)
  - [ ] Inside try: call `hass.services.async_call("weather", "get_forecasts",`
        `{"entity_id": weather_entity, "type": "hourly"},`
        `blocking=True, return_response=True)` — store result
  - [ ] Extract `raw_forecast = response[weather_entity]["forecast"][:6]`
  - [ ] Compute `cloud_values = [e["cloud_coverage"] for e in raw_forecast if "cloud_coverage" in e]`
  - [ ] Compute `cloud_coverage_avg = sum(cloud_values) / len(cloud_values) if cloud_values else 50.0`
  - [ ] Set `forecast_available = True`
  - [ ] Check `solar_entity = entities.get("forecast_solar")` — if not `None`, read
        `hass.states.get(solar_entity)` and parse `float(state.state)` into
        `solar_forecast_kwh_today`; wrap this sub-call in its own try/except
        (solar failure should not block weather result — AC: #5)
  - [ ] Return `ForecastData(forecast_available=True, cloud_coverage_avg=cloud_coverage_avg,`
        `solar_forecast_kwh_today=solar_forecast_kwh_today)`
  - [ ] In except block: log WARNING with `str(exc)` as `reason`; return `ForecastData()` (AC: #3)

- [ ] Task 2: Wire `get_forecast` call into `SurplusEngine._evaluation_tick` in `surplus_engine.py` (AC: #6)
  - [ ] Add `self._forecast_consumer = ForecastConsumer(self._config)` in `SurplusEngine.__init__`
        (if not already created in Story 1.3 — verify before adding)
  - [ ] In `_evaluation_tick` (or `evaluate_cycle`), before building `SensorSnapshot`:
        call `forecast_data = await self._forecast_consumer.get_forecast(hass)` and pass it to
        `SensorSnapshot(... forecast=forecast_data)`
  - [ ] Confirm `SurplusEngine.evaluate_cycle` passes `snapshot` (with populated `.forecast`)
        into `SurplusCalculator.calculate_surplus(snapshot)` — no other change needed there

- [ ] Task 3: Verify `ForecastConsumer.__init__` stores `self._config = config` (already in Story 1.2 scaffold)
  - [ ] Confirm no new dataclass fields need to be added to `ForecastData` (all three fields were
        defined in Story 1.2 — no changes to dataclass)

- [ ] Task 4: Manual smoke-test confirmation (no formal test infra for HA service calls)
  - [ ] Confirm no regression in evaluation loop by enabling verbose logging and checking
        debug log format includes `forecast=True` or `forecast=False` correctly

## Dev Notes

### ⚠️ Story Dependencies

- **Stories 1.1–1.4 must be done** — provides: config dict structure, `ForecastData` dataclass,
  `ForecastConsumer` skeleton, `SurplusEngine._evaluation_tick`, `SensorSnapshot.forecast` field
- **Stories 2.1–2.3 ideally done** — `calculate_surplus` will consume `snapshot.forecast` in Story 3.2;
  this story only populates it (no logic change to `SurplusCalculator` required here)

### Only File to Modify

`surplus_engine.py` — only `ForecastConsumer.get_forecast` implementation + wiring in
`SurplusEngine.__init__` / `evaluate_cycle`.

**Do NOT touch:**
- `sensor.py`, `__init__.py`, `modbus_server.py`, `registers.py`
- `sdm630_input_registers.py`, `sdm630_holding_registers.py`
- `SurplusCalculator` methods (no changes needed in this story)
- `HysteresisFilter`
- `ForecastData` dataclass definition (already correct from Story 1.2)

### HA Service Call Pattern

```python
async def get_forecast(self, hass) -> ForecastData:
    entities = self._config.get("entities", {})
    weather_entity = entities.get("weather")

    # AC4: weather not configured → silent no-op
    if not weather_entity:
        return ForecastData()

    try:
        response = await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": weather_entity, "type": "hourly"},
            blocking=True,
            return_response=True,
        )
        raw_forecast = response[weather_entity]["forecast"][:6]
        cloud_values = [
            e["cloud_coverage"] for e in raw_forecast if "cloud_coverage" in e
        ]
        cloud_coverage_avg = sum(cloud_values) / len(cloud_values) if cloud_values else 50.0

        solar_forecast_kwh_today: float | None = None
        solar_entity = entities.get("forecast_solar")
        if solar_entity:
            try:
                state = hass.states.get(solar_entity)
                if state and state.state not in ("unavailable", "unknown"):
                    solar_forecast_kwh_today = float(state.state)
            except (ValueError, AttributeError):
                pass  # solar failure is non-critical — cloud_coverage already fetched

        return ForecastData(
            forecast_available=True,
            cloud_coverage_avg=cloud_coverage_avg,
            solar_forecast_kwh_today=solar_forecast_kwh_today,
        )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Forecast unavailable: %s. Using conservative defaults.", exc)
        return ForecastData()
```

### HA `weather.get_forecasts` Response Structure

Available from HA 2023.7+. The response dict from `return_response=True` is:

```python
{
    "weather.openweathermap": {
        "forecast": [
            {"datetime": "2026-03-21T14:00:00+00:00", "cloud_coverage": 45, ...},
            {"datetime": "2026-03-21T15:00:00+00:00", "cloud_coverage": 80, ...},
            # ... up to 48 hourly entries
        ]
    }
}
```

The service call uses `"type": "hourly"` to request hourly granularity. Only the
first 6 entries (next 6 hours) are consumed for `cloud_coverage_avg`. Entries without
the `cloud_coverage` key (not all providers include it) are silently skipped.

### Inspiration: marq24/ha-evcc Service Call Pattern

From [marq24/ha-evcc/custom_components/evcc_intg/service.py](marq24/ha-evcc/custom_components/evcc_intg/service.py):

```python
# evcc_intg uses blocking=False for fire-and-forget writes, but the pattern for
# return_response=True (introduced HA 2023.7) is identical — await the call directly.
resp = await self._coordinator.async_write_plan(...)
if call.return_response:
    return {"success": "true", "response": resp}
```

The key pattern: wrap with try/except, use `return_response=True` for reads,
`blocking=True` to ensure the service completes before reading the response.

From [marq24/ha-evcc/custom_components/evcc_intg/\_\_init\_\_.py](marq24/ha-evcc/custom_components/evcc_intg/__init__.py) line 16:

```python
from homeassistant.helpers.event import async_track_time_interval, async_call_later
```

The evaluation loop already uses `async_track_time_interval` (wired in Story 1.3) —
the forecast fetch slots naturally into the `_evaluation_tick` coroutine without
any additional scheduling complexity.

### ForecastData Dataclass (from Story 1.2 — no changes)

```python
@dataclass
class ForecastData:
    forecast_available: bool = False
    cloud_coverage_avg: float = 50.0          # 0–100; 50 = neutral/unknown
    solar_forecast_kwh_today: float | None = None
```

`ForecastData()` with no arguments is a valid "no forecast" sentinel — all defaults
are conservative (50% cloud coverage = don't raise or lower SOC floor; Story 3.2 defines
the threshold logic). No changes to this dataclass are needed.

### Config Entity Key Access Pattern

From Story 1.1, the config dict is structured as:

```python
config = {
    "entities": {
        "soc": "sensor.sph10000_storage_soc",
        "power_to_grid": "sensor.sph10000_pac_to_grid_total",
        "pv_production": "sensor.sph10000_input_power",
        "power_to_user": "sensor.sph10000_pac_to_user_total",
        "weather": "weather.openweathermap",       # optional — may be absent
        "forecast_solar": "sensor.forecast_solar_energy_today",  # optional
    },
    # ... thresholds, time_strategy, seasonal_targets
}
```

Access pattern used throughout codebase: `config.get("entities", {}).get("weather")`.
If `CONF_ENTITIES` and `CONF_WEATHER` string constants are defined in `__init__.py`
(Story 1.1 tasks), use those instead of raw strings for consistency.

### SurplusEngine Wiring Checkpoint

Before Story 3.1 work, confirm in `surplus_engine.py` that `SurplusEngine`:

1. Has a `ForecastConsumer` instance attribute (e.g., `self._forecast_consumer`)
2. `evaluate_cycle`/`_evaluation_tick` builds `SensorSnapshot` with
   `forecast=await self._forecast_consumer.get_forecast(hass)`
3. `SurplusCalculator.calculate_surplus(snapshot)` already reads
   `snapshot.forecast.forecast_available` (added in Story 2.2) — no changes needed

If `self._forecast_consumer` was NOT created in Story 1.3 scaffolding, add it in
`SurplusEngine.__init__` now.

### Logging Format Compliance

The evaluation cycle debug log (from Story 1.4) already includes `forecast=%s`:

```python
_LOGGER.debug(
    "SDM630 Eval: surplus=%.2fkW buffer=%.2fkW SOC=%d%% floor=%d%% "
    "state=%s reported=%.2fkW reason=%s forecast=%s",
    result.real_surplus_kw, result.buffer_used_kw, result.soc_percent,
    result.soc_floor_active, result.charging_state, result.reported_kw,
    result.reason, result.forecast_available
)
```

No changes needed to the logging calls — `result.forecast_available` will now be
`True` when forecast is available.

### Regression Protection

After implementing, verify the following remain unchanged:
- Evaluation loop continues if forecast fails (no exception propagation)
- `EvaluationResult.forecast_available` is correctly populated from `ForecastData`
- Existing Modbus register writes (`input_data_block.set_float(TOTAL_POWER, ...)`) unaffected
- `SurplusCalculator` still has zero HA imports

### Project Structure Notes

- **Modify only:** `surplus_engine.py`
- **Component directory:** same folder as `sensor.py`, `__init__.py` (not in a sub-package)
- No new files, no new constants in `__init__.py` required beyond what Story 1.1 established
- `manifest.json` already updated to `pymodbus>=3.11.1` in Story 1.x — no change needed

### References

- Epics story 3.1 definition: [_bmad-output/planning-artifacts/epics.md](_bmad-output/planning-artifacts/epics.md)
- Architecture — ForecastConsumer role: [_bmad-output/planning-artifacts/architecture.md](_bmad-output/planning-artifacts/architecture.md)
- `ForecastData` scaffold: [_bmad-output/implementation-artifacts/1-2-surplus-engine-py-module-scaffold-with-dataclasses.md](_bmad-output/implementation-artifacts/1-2-surplus-engine-py-module-scaffold-with-dataclasses.md)
- `SurplusEngine._evaluation_tick` wiring: [_bmad-output/implementation-artifacts/1-3-integration-wiring-in-sensor-py-and-evaluation-loop.md](_bmad-output/implementation-artifacts/1-3-integration-wiring-in-sensor-py-and-evaluation-loop.md)
- `calculate_surplus` consuming `snapshot.forecast`: [_bmad-output/implementation-artifacts/2-2-surplus-calculation-with-battery-buffer.md](_bmad-output/implementation-artifacts/2-2-surplus-calculation-with-battery-buffer.md)
- evcc_intg service call pattern: [marq24/ha-evcc/custom_components/evcc_intg/service.py](marq24/ha-evcc/custom_components/evcc_intg/service.py)
- HA weather.get_forecasts response structure: [Source: architecture.md#Story 3.1 implementation note]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

### File List
