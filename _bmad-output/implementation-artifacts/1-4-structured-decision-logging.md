# Story 1.4: Structured Decision Logging

Status: ready-for-dev

## Story

As a developer (Ghost),
I want every evaluation cycle to emit a structured DEBUG log entry and every
fail-safe activation to emit a WARNING,
so that I can trace surplus decisions during tuning and detect fail-safe
activations in production without any additional tooling.

## Acceptance Criteria

**AC1 — Per-cycle DEBUG log (exact format)**

Given a completed evaluation cycle produces an `EvaluationResult`\
When the result is written to the Modbus register\
Then `_LOGGER.debug(...)` is called with this exact format:

```text
"SDM630 Eval: surplus=%.2fkW buffer=%.2fkW SOC=%d%% floor=%d%% state=%s reported=%.2fkW reason=%s forecast=%s"
```

using `result` fields as positional arguments in this order:
`result.real_surplus_kw, result.buffer_used_kw, result.soc_percent,`
`result.soc_floor_active, result.charging_state, result.reported_kw,`
`result.reason, result.forecast_available`

**AC2 — Fail-safe WARNING log (exact format)**

Given a fail-safe is triggered (i.e. `result.charging_state == "FAILSAFE"`)\
When `_LOGGER.warning(...)` is called\
Then the message matches exactly:

```text
"SDM630 FAIL-SAFE: %s. Reporting 0 kW."
```

with `result.reason` as the single positional argument

**AC3 — Silent at INFO log level**

Given HA log level is set to `INFO` (not `DEBUG`)\
When the system operates in normal non-fail-safe mode\
Then no per-cycle log entries appear in the HA log\
(The DEBUG call is there; it just produces no output at INFO level — no
special branching needed.)

**AC4 — Startup INFO confirmation**

Given component startup completes successfully\
When `async_added_to_hass()` finishes setting up the engine and the evaluation
loop\
Then exactly one `INFO` log entry is emitted:

```text
"SDM630 SurplusEngine started. Interval=%ds, entities=%d configured"
```

with `config["evaluation_interval"]` and the count of entity IDs from
`config["entities"]` as arguments

## Tasks / Subtasks

- [ ] Task 1: Add DEBUG decision log call in `_evaluation_tick` (AC1, AC3)
  - [ ] After `await engine.evaluate_cycle(snapshot)` returns `result`
  - [ ] Add `_LOGGER.debug("SDM630 Eval: surplus=%.2fkW ...")` with exact
        format string and positional args in the correct order
  - [ ] Do NOT add an `if _LOGGER.isEnabledFor(logging.DEBUG):` guard —
        the `%`-style lazy formatting already avoids string interpolation cost
- [ ] Task 2: Add WARNING log on fail-safe path (AC2)
  - [ ] Detect `result.charging_state == "FAILSAFE"` inside `_evaluation_tick`
  - [ ] Call `_LOGGER.warning("SDM630 FAIL-SAFE: %s. Reporting 0 kW.", result.reason)`
  - [ ] This call is in addition to the DEBUG call — both are emitted for
        a FAILSAFE result (DEBUG gives full context; WARNING signals the event)
- [ ] Task 3: Add startup INFO log in `async_added_to_hass` (AC4)
  - [ ] After the evaluation loop (`async_track_time_interval`) is started
  - [ ] Call `_LOGGER.info("SDM630 SurplusEngine started. Interval=%ds, entities=%d configured", ...)`
  - [ ] `entities=%d` = `len(config["entities"])` (count of entity ID strings)

## Dev Notes

### ⚠️ Prerequisite: Story 1.3 Must Be Implemented First

This story adds logging calls to code that **Story 1.3 creates**. Specifically:

- `_evaluation_tick(self, now)` — created in Story 1.3; logging is added here
- `async_added_to_hass()` — extended in Story 1.3 to start evaluation loop;
  startup INFO log appended at end of that method

**Do not implement Story 1.4 in isolation.** The dev agent must implement it
immediately after or together with Story 1.3.

### Exact Log Placement in `_evaluation_tick`

After Story 1.3, `_evaluation_tick` will look roughly like:

```python
async def _evaluation_tick(self, now):
    snapshot = self._build_snapshot()
    result = await self._engine.evaluate_cycle(snapshot)
    input_data_block.set_float(TOTAL_POWER, result.reported_kw)
    self._attr_native_value = result.reported_kw
    self.async_write_ha_state()
```

Story 1.4 extends it to:

```python
async def _evaluation_tick(self, now):
    snapshot = self._build_snapshot()
    result = await self._engine.evaluate_cycle(snapshot)

    # Story 1.4: structured decision log
    _LOGGER.debug(
        "SDM630 Eval: surplus=%.2fkW buffer=%.2fkW SOC=%d%% floor=%d%% "
        "state=%s reported=%.2fkW reason=%s forecast=%s",
        result.real_surplus_kw, result.buffer_used_kw, result.soc_percent,
        result.soc_floor_active, result.charging_state, result.reported_kw,
        result.reason, result.forecast_available,
    )
    if result.charging_state == "FAILSAFE":
        _LOGGER.warning("SDM630 FAIL-SAFE: %s. Reporting 0 kW.", result.reason)

    input_data_block.set_float(TOTAL_POWER, result.reported_kw)
    self._attr_native_value = result.reported_kw
    self.async_write_ha_state()
```

### Exact Startup INFO Log Placement in `async_added_to_hass`

After Story 1.3, `async_added_to_hass` ends with starting the evaluation loop:

```python
self.async_on_remove(
    async_track_time_interval(
        self.hass,
        self._evaluation_tick,
        timedelta(seconds=cfg["evaluation_interval"]),
    )
)
```

Story 1.4 adds the INFO call immediately after:

```python
_LOGGER.info(
    "SDM630 SurplusEngine started. Interval=%ds, entities=%d configured",
    cfg["evaluation_interval"],
    len(cfg["entities"]),
)
```

`cfg["entities"]` is a dict of entity-ID strings; `len()` gives the count of
configured sensor entities.

### Why Both DEBUG and WARNING for FAILSAFE?

The DEBUG call captures the full `EvaluationResult` fields (surplus, buffer,
SOC, floor, state, reported, reason, forecast). For a FAILSAFE result this
means `reported_kw=0.0`, `charging_state="FAILSAFE"`, and `reason` explains
why. The WARNING adds the same `reason` at a higher priority so operators
see fail-safe events without enabling DEBUG-level logging.

### `%`-Style Format Strings (not f-strings)

The existing codebase uses `%`-style format strings with the `logging` module:

```python
_LOGGER.debug("Updated sensor value to: %s from external sensor", new_value)
_LOGGER.error("Failed to start Modbus server: %s", str(e))
```

Story 1.4 **must** use the same `%`-style pattern. Do NOT use f-strings in
logging calls — they evaluate unconditionally, defeating lazy formatting.

### `double-%` for Literal `%` in Log Messages

```python
"SOC=%d%%"   → logs as "SOC=95%"
"floor=%d%%" → logs as "floor=50%"
```

### `forecast_available` Is a `bool` — Logs as `True`/`False`

The `%s` format on a Python `bool` renders as `"True"` or `"False"`, which is
the intended output. No conversion needed.

### File Modified

Only one file is modified by Story 1.4:

| Action | File | Change |
|--------|------|--------|
| MODIFY | `sensor.py` | Add DEBUG + WARNING calls in `_evaluation_tick`; add INFO call at end of `async_added_to_hass` |

**Zero changes to:** `__init__.py`, `surplus_engine.py`, `modbus_server.py`,
`registers.py`, `sdm630_input_registers.py`, `sdm630_holding_registers.py`,
`manifest.json`

### Regression Risk

This story is purely additive logging — no logic changes, no new imports, no
schema changes. The only regression risk is a typo in the format string or
wrong argument order that would cause a `TypeError` at runtime. The dev agent
must verify argument count matches format specifier count:

Format: `surplus=%.2f buffer=%.2f SOC=%d floor=%d state=%s reported=%.2f reason=%s forecast=%s`
→ 8 specifiers
→ 8 args: `real_surplus_kw, buffer_used_kw, soc_percent, soc_floor_active, charging_state, reported_kw, reason, forecast_available`

### Project Structure Notes

```text
custom_components/sdm630_simulator/
├── __init__.py         (unchanged)
├── sensor.py           ← MODIFY: add 3 log calls (2 in _evaluation_tick, 1 in async_added_to_hass)
├── surplus_engine.py   (unchanged — created in 1.2)
├── modbus_server.py    (unchanged)
├── registers.py        (unchanged)
├── sdm630_input_registers.py   (unchanged)
├── sdm630_holding_registers.py (unchanged)
└── manifest.json       (unchanged)
```

### Context from Previous Stories

**Story 1.1** established `DEFAULTS["evaluation_interval"] = 15` and
`config["entities"]` dict structure. These are the values used in the startup
INFO log.

**Story 1.2** defined `EvaluationResult` with all 8 fields. The DEBUG format
string references all of them: `real_surplus_kw`, `buffer_used_kw`,
`soc_percent`, `soc_floor_active`, `charging_state`, `reported_kw`, `reason`,
`forecast_available`.

**Story 1.3** wires up `sensor.py` with `SurplusEngine`, `_evaluation_tick`,
and `async_added_to_hass` expansion. Story 1.4 only adds log calls — no
structural changes to the patterns Story 1.3 establishes.

During Epic 1, `evaluate_cycle()` always returns the default stub result:
`charging_state="INACTIVE"`, `reason="engine_not_yet_implemented"`. So the
FAILSAFE WARNING path will not fire during Epic 1 — but it must be present
for Epic 2/4 to function correctly.

### References

- Mandatory log formats: [Source: `_bmad-output/planning-artifacts/architecture.md` — Logging Patterns]
- Story AC: [Source: `_bmad-output/planning-artifacts/epics.md` — Story 1.4]
- EvaluationResult fields: [Source: `_bmad-output/planning-artifacts/architecture.md` — EvaluationResult Structure]
- `%`-style logging convention: [Source: `sensor.py` — existing `_LOGGER` usage]
- Config entities/interval structure: [Source: `_bmad-output/implementation-artifacts/1-1-yaml-configuration-schema-and-parsing.md`]
- `_evaluation_tick` method: [Source: `_bmad-output/implementation-artifacts/1-3-integration-wiring-in-sensor-py-and-evaluation-loop.md` — to be created]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (SM story context engine)

### Debug Log References

### Completion Notes List

### File List
