---
status: complete
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - growat-modbus/Homeassistant-Growatt-Local-Modbus/custom_components/growatt_local/sensor.py
  - growat-modbus/Homeassistant-Growatt-Local-Modbus/custom_components/growatt_local/__init__.py
  - marq24/ha-evcc/custom_components/evcc_intg/sensor.py
  - sensor.py
  - __init__.py
  - modbus_server.py
---

# sdm630-simulator - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for sdm630-simulator,
decomposing the requirements from the PRD and Architecture into implementable stories.
Implementation notes reference patterns from `growatt_local` and `evcc_intg` to reuse
proven HA integration patterns.

## Requirements Inventory

### Functional Requirements

- **FR1:** Surplus calculation engine — computes available PV surplus as difference
  of PV production minus household consumption (power_to_user), augmented by a
  configurable battery buffer based on current SOC.
- **FR2:** Time-based SOC strategy with 3 configurable time windows
  (before 11:00 → SOC floor 100%; before sunset−3h → SOC floor 50%;
  default → SOC floor 80%), defined in `configuration.yaml`.
- **FR3:** Weather/solar forecast integration (`weather.get_forecasts`,
  `forecast_solar` sensor entity) for proactive SOC-target and buffer-strategy
  adjustment.
- **FR4:** Stabilized Modbus signal via hysteresis — once charging is active,
  the reported surplus is held for a minimum of 10 minutes (configurable) to
  prevent wallbox start/stop cycling.
- **FR5:** Fail-safe mechanism — immediately reports 0 kW surplus when any
  critical sensor (`soc`, `power_to_grid`, `pv_production`) is `unavailable`
  or `unknown`, when stale data is detected, or when an unhandled exception
  occurs.
- **FR6:** Structured decision logging per evaluation cycle at DEBUG level
  (`SDM630 Eval: surplus=…kW buffer=…kW SOC=…% floor=…% state=… reported=…kW
  reason=… forecast=T/F`); fail-safe activations at WARNING level.
- **FR7:** YAML configuration for all entity IDs and all thresholds (SOC floor,
  wallbox threshold, hysteresis duration, evaluation interval) under
  `sdm630_sim:` in `configuration.yaml`.
- **FR8:** Staleness detection — if a sensor's last-changed timestamp has not
  updated for more than 60 seconds (configurable), the fail-safe is triggered.
- **FR9:** Seasonal SOC target at sunset — the system determines a month-based
  sunset SOC target: 100% (Nov–Jan), 90% (Feb, Oct), 80% (Mar, Sep), 70%
  (Apr–Aug). This target is configurable per month via `seasonal_targets:` in
  YAML and overrides the static `soc_floor` on the `default:` time-window rule
  so that the evening protection floor adapts to the season.
- **FR10:** Wallbox power accounting (architectural contract): the Growatt SPH
  inverter's `power_to_user` entity includes wallbox power draw in total
  household consumption. The surplus formula (`pv_production − power_to_user`)
  implicitly accounts for active EV charging — no separate adjustment required.
- **FR11:** Sensor range validation — before use in calculations, validate
  SOC ∈ [0, 100]% and power values within configurable bounds. Out-of-range
  values trigger the fail-safe with a descriptive reason string.

### NonFunctional Requirements

- **NFR1:** Evaluation interval configurable (default: 15 s) to balance
  responsiveness and CPU load.
- **NFR2:** All I/O and HA service calls fully async (`async/await`) — no
  blocking operations in the HA event loop.
- **NFR3:** SOC hard floor of 50% must never be violated under any circumstance
  (algorithm error, sensor failure, or edge case).
- **NFR4:** `SurplusCalculator` must not import any HA-specific objects — only
  Python stdlib and dataclasses — enabling unit tests without a running HA
  instance.
- **NFR5:** `surplus_engine.py` must be testable with `pytest` + `pytest-asyncio`.
- **NFR6:** Naming conventions: `CamelCase` classes, `snake_case` methods/functions,
  `UPPER_SNAKE_CASE` constants, `_LOGGER = logging.getLogger(__name__)` in every
  module, dual-import guard (`if __package__:`) in all modules.
- **NFR7:** Runtime: Python 3.12+, pymodbus ≥ 3.11.1.

### Additional Requirements

- **Arch-1:** Brownfield integration — no starter template; extend the existing
  codebase (`sensor.py`, `__init__.py`).
- **Arch-2:** New module `surplus_engine.py` containing `SurplusEngine`
  (orchestrator), `SurplusCalculator` (pure logic), `ForecastConsumer`
  (HA service calls), `HysteresisFilter` (state machine), `SensorSnapshot`
  (dataclass), and `EvaluationResult` (dataclass).
- **Arch-3:** `EvaluationResult` fields: `reported_kw`, `real_surplus_kw`,
  `buffer_used_kw`, `soc_percent`, `soc_floor_active`, `charging_state`,
  `reason`, `forecast_available`.
- **Arch-4:** Entity validation at startup in `async_added_to_hass()` — missing
  optional entity → WARNING + degraded mode; missing SOC entity → ERROR + FAILSAFE.
- **Arch-5:** `sensor.py` modified to instantiate `SurplusEngine`, subscribe to
  state-change events, run the async evaluation loop, and write
  `EvaluationResult` to the Modbus register.
- **Arch-6:** `__init__.py` modified for new YAML config parsing and entity ID
  validation.
- **Arch-7:** `manifest.json` updated: `pymodbus>=3.11.1`.
- **Arch-8:** Files unchanged: `modbus_server.py`, `registers.py`,
  `sdm630_input_registers.py`, `sdm630_holding_registers.py`.
- **Arch-9:** New test infrastructure: `tests/test_surplus_calculator.py`,
  `tests/test_hysteresis_filter.py`, `tests/conftest.py`.
- **Arch-10:** YAML config schema includes `entities:` block, `time_strategy:`
  list, and global threshold parameters.

### UX Design Requirements

N/A — pure Modbus backend; no UI component.

### FR Coverage Map

| Requirement | Epic | Stories |
|---|---|---|
| FR1 Surplus Calculation Engine | Epic 1 | 1.2, 1.3 |
| FR2 SOC Time-Window Strategy | Epic 2 | 2.1, 2.2 |
| FR3 Forecast Integration | Epic 3 | 3.1, 3.2 |
| FR4 Hysteresis / Signal Stabilization | Epic 2 | 2.3 |
| FR5 Fail-Safe | Epic 4 | 4.1, 4.2 |
| FR6 Decision Logging | Epic 1 | 1.4 |
| FR7 YAML Configuration | Epic 1 | 1.1 |
| FR8 Staleness Detection | Epic 4 | 4.2 |
| FR9 Seasonal SOC Target at Sunset | Epic 2 | 2.1 |
| FR10 Wallbox Power Accounting (arch contract) | Epic 2 | 2.2 |
| FR11 Sensor Range Validation | Epic 4 | 4.4 |
| NFR4/5 Unit Test Infrastructure | Epic 5 | 5.1, 5.2 |

## Epic List

- **Epic 1:** Foundation — Configuration, Module Scaffold, and Logging
- **Epic 2:** Core Surplus Logic — SOC Strategy, Buffer Math, and Hysteresis
- **Epic 3:** Forecast Integration — Weather and Solar Forecast Consumption
- **Epic 4:** Fail-Safe and Reliability — Sensor Monitoring and Fault Handling
- **Epic 5:** Test Infrastructure — Unit Tests for Pure Logic Components

---

## Epic 1: Foundation — Configuration, Module Scaffold, and Logging

Establish the structural foundation for the intelligent surplus engine: YAML
configuration schema, the new `surplus_engine.py` module with all class
skeletons and dataclasses, integration wiring in `sensor.py` and `__init__.py`,
and the structured decision-logging infrastructure. All subsequent epics build
on top of this foundation.

After this epic: HA starts cleanly, the new YAML config is parsed, all module
skeletons exist, and the evaluation loop runs (logging `state=INACTIVE
reason=engine_not_yet_implemented` each cycle) without crashing. The existing
Modbus server and all existing sensor functionality are fully preserved.

### Story 1.1: YAML Configuration Schema and Parsing

As a developer (Ghost),
I want a structured YAML configuration schema under `sdm630_sim:` with entity
IDs, thresholds, and time-strategy entries,
So that all parameters are externalized and configurable without code changes.

**Acceptance Criteria:**

**Given** `configuration.yaml` contains a valid `sdm630_sim:` block with
`entities:`, `time_strategy:`, and global threshold keys\
**When** Home Assistant loads the component via `async_setup`\
**Then** all entity IDs and threshold values are parsed into a config dict\
**And** missing optional entities (`weather`, `forecast_solar`) log a WARNING
and continue in degraded mode\
**And** missing required entity `soc` logs an ERROR and the engine enters
FAILSAFE mode

**Given** a `time_strategy:` list with `before:` entries and a `default:` entry\
**When** the config is parsed\
**Then** each entry is stored as a time-window rule with a `soc_floor` value\
**And** dynamic offset tokens (`"sunrise+Xh"` and `"sunset-Xh"`) are stored
as-is and resolved at evaluation time using `snapshot.sunrise_time` /
`snapshot.sunset_time` (not at parse time)\
**And** a plain `"HH:MM"` string is accepted as a static fallback time\
**And** the DEFAULTS `time_strategy` uses `"sunrise+2h"` as the morning
boundary so that the protective morning window adapts to the actual sunrise
each day (e.g., 07:30 in summer, 10:00 in winter in Central Europe)

**Given** `configuration.yaml` contains a `seasonal_targets:` dict\
**When** the config is parsed\
**Then** month keys (integers 1–12) are mapped to integer SOC target
percentages (0–100) and stored in `config["seasonal_targets"]`\
**And** missing month keys fall back to the `DEFAULTS` seasonal target for
that month

**Given** a config key is absent from `configuration.yaml`\
**When** `async_setup` runs\
**Then** the value from `DEFAULTS` dict is used without error\
**And** `DEFAULTS` defines at minimum: `evaluation_interval=15`,
`wallbox_threshold_kw=4.2`, `hold_time_minutes=10`, `soc_hard_floor=50`,
`stale_threshold_seconds=60`, `max_discharge_kw=10.0`,
`battery_capacity_kwh=10.0`, and
`seasonal_targets={1:100,2:90,3:80,4:70,5:70,6:70,7:70,8:70,9:80,10:90,11:100,12:100}`

**Implementation note:** Extend existing `async_setup` in `__init__.py` using
the same `vol.Schema` / `cv.` validation style as the existing codebase.
`time_strategy:` entries arrive as a list of dicts; validate each entry has
either a `before:` key (string) or is the `default:` entry, plus a numeric
`soc_floor` key. `seasonal_targets:` arrives as a dict with integer month
keys (1–12) and integer SOC percentage values; validate with
`{vol.Coerce(int): vol.All(int, vol.Range(min=0, max=100))}`. `max_discharge_kw`
and `battery_capacity_kwh` are scalar floats validated with `vol.Coerce(float)`.

### Story 1.2: `surplus_engine.py` Module Scaffold with Dataclasses

As a developer (Ghost),
I want the `surplus_engine.py` module created with all class and dataclass
skeletons including the canonical `SensorSnapshot` and `EvaluationResult`
dataclasses,
So that the full module structure is in place ready for logic implementation
in subsequent stories — and importable without errors in plain Python tests.

**Acceptance Criteria:**

**Given** `surplus_engine.py` is created in the component directory\
**When** imported in plain Python (no HA runtime)\
**Then** no `ImportError` or `ModuleNotFoundError` occurs\
**And** the module contains exactly these top-level names:
`SurplusEngine`, `SurplusCalculator`, `ForecastConsumer`, `HysteresisFilter`,
`SensorSnapshot`, `EvaluationResult`, `ForecastData`

**Given** `SurplusCalculator` class definition\
**When** its import list is inspected\
**Then** it imports ONLY from Python stdlib (`datetime`, `math`) and
`dataclasses` — zero HA-specific imports

**Given** `EvaluationResult` dataclass\
**When** instantiated with all fields\
**Then** it contains: `reported_kw: float`, `real_surplus_kw: float`,
`buffer_used_kw: float`, `soc_percent: float`, `soc_floor_active: int`,
`charging_state: str`, `reason: str`, `forecast_available: bool`

**Given** `ForecastData` dataclass (stub — fully implemented in Epic 3)\
**When** instantiated with defaults\
**Then** it contains: `forecast_available: bool = False`,
`cloud_coverage_avg: float = 50.0`,
`solar_forecast_kwh_today: float | None = None`

**Given** `SensorSnapshot` dataclass\
**When** instantiated\
**Then** it contains at minimum: `soc_percent: float`, `power_to_grid_w: float`,
`pv_production_w: float`, `power_to_user_w: float`, `timestamp: datetime`,
`sunset_time: datetime | None`, `sunrise_time: datetime | None`,
`forecast: ForecastData | None = None`\
**And** note: `sun.sun` is a built-in HA integration always present; `None`
defaults are kept for defensive unit-test construction only

**Given** module-level declarations\
**Then** `_LOGGER = logging.getLogger(__name__)` is defined\
**And** `if __package__:` dual-import guard is present\
**And** `SOC_HARD_FLOOR: int = 50` is defined as a module-level constant

**Given** `SurplusEngine`, `ForecastConsumer`, `HysteresisFilter` skeletons\
**Then** each method body contains `raise NotImplementedError` or `pass`
(to be filled in subsequent epics)\
**And** the EXCEPTION is `SurplusEngine.evaluate_cycle(snapshot)` — this
method must return a default `EvaluationResult` rather than raising:
`EvaluationResult(reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,`
`soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",`
`reason="engine_not_yet_implemented", forecast_available=False)`
so that Story 1.3's evaluation loop runs without crashing during Epic 1

### Story 1.3: Integration Wiring in `sensor.py` and Evaluation Loop

As a developer (Ghost),
I want `sensor.py` to instantiate `SurplusEngine`, subscribe to entity
state changes, run the async evaluation loop via `async_track_time_interval`,
and write `EvaluationResult.reported_kw` to the Modbus register,
So that the engine is connected to the existing HA lifecycle and Modbus
infrastructure without altering any of the unchanged modules.

**Acceptance Criteria:**

**Given** `SDM630SimSensor.async_added_to_hass()` runs\
**When** called by HA during platform setup\
**Then** a `SurplusEngine` instance is created with the parsed config dict\
**And** `async_track_state_change_event(hass, entity_ids, _handle_state_change)`
is called for all entity IDs from `config[CONF_ENTITIES]`\
**And** each subscription is cleaned up via `self.async_on_remove(unsub)`
(pattern from `growatt_local` — prevents memory leaks on HA reload)\
**And** `async_track_time_interval(hass, self._evaluation_tick, interval)`
starts the evaluation loop (cleaner than `asyncio.create_task` — integrates
with HA's event loop shutdown)

**Given** a state-change event fires for a tracked entity\
**When** `_handle_state_change(event)` is called\
**Then** the new state value is extracted via
`event.data.get("new_state")`\
**And** the raw string state is validated: if `state.state` is `STATE_UNAVAILABLE`
or `STATE_UNKNOWN`, the cache entry is marked invalid (not updated with a float)\
**And** if valid numeric, `float(state.state)` is stored in the sensor value
cache dict keyed by `CACHE_KEY_*` constants

**Given** `_evaluation_tick` fires at each configured interval\
**When** `SurplusEngine.evaluate_cycle(snapshot)` is called (stub)\
**Then** the returned `EvaluationResult` is used to call
`input_data_block.set_float(TOTAL_POWER, result.reported_kw)`\
**And** no blocking I/O occurs in the event loop\
**And** the stub `evaluate_cycle()` returns the default `EvaluationResult`
specified in Story 1.2 — it never raises `NotImplementedError`

**Given** `_evaluation_tick` assembles the `SensorSnapshot`\
**When** building snapshot fields before calling `evaluate_cycle`\
**Then** both solar boundary times are read from `hass.states.get("sun.sun")`:
`snapshot.sunset_time` from attribute `"next_setting"` and
`snapshot.sunrise_time` from attribute `"next_rising"`, each parsed as a
timezone-aware `datetime` via `dt_util.parse_datetime`\
**And** `sun.sun` is a built-in HA integration and is always present during
normal operation — both attributes resolve to valid `datetime` objects\
**And** as defensive coding: if `sun.sun` state is unavailable or either
attribute is absent (e.g., during an unusual HA startup edge case), the
corresponding snapshot field is set to `None`; the time-window logic then
falls back to the seasonal target without a dynamic offset\
**And** no FAILSAFE is triggered solely because `sun.sun` is temporarily
missing — it is not a critical energy sensor

**Given** HA stops or the component is reloaded\
**When** all `async_on_remove` callbacks fire\
**Then** `async_track_time_interval` unsubscribes cleanly\
**And** `async_track_state_change_event` unsubscribes cleanly

**Implementation note:** Import `async_track_state_change_event` and
`async_track_time_interval` from `homeassistant.helpers.event`. Both return
unsubscribe callables suitable for `self.async_on_remove()`.

### Story 1.4: Structured Decision Logging

As a developer (Ghost),
I want every evaluation cycle to emit a structured DEBUG log entry and every
fail-safe activation to emit a WARNING,
So that I can trace surplus decisions during tuning and detect fail-safe
activations in production without any additional tooling.

**Acceptance Criteria:**

**Given** a completed evaluation cycle produces an `EvaluationResult`\
**When** the result is written to the Modbus register\
**Then** `_LOGGER.debug(...)` is called with this exact format:\
`"SDM630 Eval: surplus=%.2fkW buffer=%.2fkW SOC=%d%% floor=%d%% state=%s`
`reported=%.2fkW reason=%s forecast=%s"`\
using `result` fields as positional arguments

**Given** a fail-safe is triggered\
**When** `_LOGGER.warning(...)` is called\
**Then** the message matches: `"SDM630 FAIL-SAFE: %s. Reporting 0 kW."` with
the reason string as argument

**Given** HA log level is set to `INFO` (not `DEBUG`)\
**When** the system operates in normal non-fail-safe mode\
**Then** no per-cycle entries appear in the HA log

**Given** component startup completes successfully\
**When** the first evaluation tick fires\
**Then** an `INFO` log entry confirms startup:
`"SDM630 SurplusEngine started. Interval=%ds, entities=%d configured"`

---

## Epic 2: Core Surplus Logic — SOC Strategy, Buffer Math, and Hysteresis

Implement the pure surplus calculation logic inside `SurplusCalculator` and the
`HysteresisFilter` state machine. This epic converts the stubs from Epic 1
into working logic and delivers the core value of the project.

After this epic: On a sunny day with clouds, the simulator automatically uses
battery buffer to fill the gap below 4.2 kW, the wallbox gets a stable signal,
and SOC protection enforces the time-window strategy. `EvaluationResult`
contains correct values and the Modbus register reflects the computed surplus.
SOC floor of 50% is enforced unconditionally.

### Story 2.1: SOC Floor Determination via Time-Window Strategy

As the surplus engine,
I want `SurplusCalculator.get_soc_floor(snapshot)` to return the applicable
SOC floor for the current time using the configured `time_strategy:` rules,
So that battery protection adapts automatically to time of day without any
manual intervention.

**Acceptance Criteria:**

**Given** `snapshot.sunrise_time` = 05:30 and `snapshot.timestamp` is 06:45
(before `sunrise_time + 2h = 07:30`)\
**When** `SurplusCalculator.get_soc_floor(snapshot)` is called\
**Then** it returns the `soc_floor` from the `before: "sunrise+2h"` rule
(default: 100) — morning protection is active regardless of clock hour

**Given** `snapshot.sunrise_time` = 08:00 and `snapshot.timestamp` is 09:30
(before `sunrise_time + 2h = 10:00`)\
**When** `get_soc_floor(snapshot)` is called\
**Then** it returns 100 — same rule, winter sunrise shifts the boundary later

**Given** `snapshot.timestamp` is past `sunrise_time + 2h` and before
`sunset_time − 3h`\
**When** `get_soc_floor(snapshot)` is called\
**Then** it returns 50 (the free midday window floor)

**Given** `snapshot.timestamp` is within 3 hours of sunset or later\
**When** `get_soc_floor(snapshot)` is called\
**Then** it returns the seasonal SOC target for the current month from
`config["seasonal_targets"][snapshot.timestamp.month]` (e.g., 80 in March,
100 in December) overriding the static `soc_floor` on the `default:` entry

**Given** `snapshot.sunrise_time` is `None` (sun.sun temporarily unavailable)\
**When** `get_soc_floor(snapshot)` is called and the morning rule uses a
`"sunrise+Xh"` token\
**Then** the morning `before:` boundary cannot be resolved\
**And** the rule is skipped — the `default:` seasonal target is applied
directly (conservative fallback — the battery stays protected)

**Given** `snapshot.sunset_time` is `None`\
**When** the `"sunset-3h"` token cannot be resolved\
**Then** the rule is treated as not yet triggered and the `default:` seasonal
target is applied for the current month

**Given** the time-strategy rules are evaluated\
**Then** the `SOC_HARD_FLOOR` constant (50) acts as an absolute lower bound —
`get_soc_floor()` never returns a value below 50

**Given** current month is November (month 11)\
**When** `get_soc_floor(snapshot)` evaluates the `default:` time-window rule\
**Then** the returned floor equals `config["seasonal_targets"][11]` (default: 100)\
**And** this overrides the static `soc_floor` value on the `default:` YAML entry

**Given** `seasonal_targets` is absent from or incomplete in YAML config\
**When** `get_soc_floor(snapshot)` resolves the `default:` rule\
**Then** the `DEFAULTS` seasonal target for the current month is used\
**And** no exception is raised

**Given** `seasonal_targets[month]` would yield a value below `SOC_HARD_FLOOR`
due to misconfiguration\
**When** `get_soc_floor(snapshot)` applies the seasonal target\
**Then** the result is clamped to `SOC_HARD_FLOOR` (50) and a one-time
`_LOGGER.warning("Configured seasonal_target month=%d value=%d below
SOC_HARD_FLOOR. Clamping.")` is emitted

**Given** `SurplusCalculator` is imported in a plain Python unit test\
**When** the test runs with mock `SensorSnapshot` objects\
**Then** all assertions pass without any HA runtime dependency

**Implementation note:** Both solar boundary times come from the built-in
`sun.sun` integration, read in `SurplusEngine._evaluation_tick` and passed
into `SurplusCalculator` via `SensorSnapshot`:
- `snapshot.sunset_time` ← `sun.sun` attribute `next_setting`
- `snapshot.sunrise_time` ← `sun.sun` attribute `next_rising`

Token resolution in `get_soc_floor`:
- `"sunrise+2h"` → `snapshot.sunrise_time + timedelta(hours=2)`
- `"sunset-3h"` → `snapshot.sunset_time - timedelta(hours=3)`
- Plain `"HH:MM"` → parsed as a static `time` relative to today

If a token cannot be resolved because the snapshot field is `None`,
the rule is skipped and the `default:` entry is applied — this is a
defensive edge case; in practice `sun.sun` is always present in HA.
`async_track_sunset` from `homeassistant.helpers.event` (used in
`growatt_local`) can additionally notify on solar events, but the
primary determination is snapshot-based for simplicity.

### Story 2.2: Surplus Calculation with Battery Buffer

As the surplus engine,
I want `SurplusCalculator.calculate_surplus(snapshot)` to compute the real
surplus and the battery-buffer-augmented reported surplus,
So that the wallbox receives a stable signal that meets its 4.1 kW minimum
threshold even during brief PV dips, provided the battery has capacity above
the SOC floor.

**Acceptance Criteria:**

**Given** `snapshot`: PV=3500 W, power_to_user=1200 W, SOC=95%,
SOC floor=50%, wallbox_threshold=4200 W\
**When** `calculate_surplus(snapshot)` is called\
**Then** `result.real_surplus_kw` = 2.3\
**And** `result.buffer_used_kw` > 0 (buffer fills the gap)\
**And** `result.reported_kw` = 4.2 (minimum threshold applied)\
**And** `result.charging_state` = `"ACTIVE"` (threshold met after buffer)

**Given** `snapshot`: PV=8000 W, power_to_user=1200 W, SOC=100%\
**When** `calculate_surplus(snapshot)` is called\
**Then** `result.real_surplus_kw` = 6.8\
**And** `result.buffer_used_kw` = 0.0 (no buffer needed)\
**And** `result.reported_kw` = 6.8

**Given** `snapshot.soc_percent` equals the SOC floor exactly\
**When** `calculate_surplus(snapshot)` is called\
**Then** `result.buffer_used_kw` = 0.0 (no buffer available at floor)\
**And** `result.reported_kw` = `result.real_surplus_kw` (no augmentation)

**Given** real surplus < wallbox_threshold AND SOC at floor\
**When** `calculate_surplus(snapshot)` is called\
**Then** `result.reported_kw` = 0.0 (cannot meet threshold — report nothing)\
**And** `result.charging_state` = `"INACTIVE"`

**Given** `result.soc_floor_active` field\
**Then** it contains the integer SOC floor value that was applied (e.g. 50, 80,
or 100) for logging

**Given** the wallbox is actively charging the EV\
**When** `calculate_surplus(snapshot)` runs\
**Then** `snapshot.power_to_user_w` from the Growatt SPH integration already
includes the wallbox power draw in total household consumption\
**And** the surplus formula `pv_production_w − power_to_user_w` implicitly
accounts for EV charging load — no separate adjustment is applied\
**And** `result.reason` contains `"wallbox_included_in_load"` when
`charging_state == "ACTIVE"`

**Implementation note:** Real surplus = `pv_production_w - power_to_user_w`
(both in W, convert to kW for output). Buffer available is computed in two
steps to keep units consistent:
`buffer_energy_kwh = (soc_percent - soc_floor) * battery_capacity_kwh / 100`
(kWh stored above the SOC floor);
`buffer_kw = min(max_discharge_kw, buffer_energy_kwh / (hold_time_minutes / 60))`
(maximum kW deliverable for the full hold period without exhausting the buffer).
`max_discharge_kw` (default: 10.0) and `battery_capacity_kwh` (default: 10.0)
are config-driven constants in `configuration.yaml`.

### Story 2.3: Hysteresis Filter State Machine

As the surplus engine,
I want `HysteresisFilter` to manage ACTIVE/INACTIVE/FAILSAFE charging states
with a configurable hold time,
So that the wallbox does not experience rapid start/stop cycling during brief
surplus fluctuations below the threshold.

**Acceptance Criteria:**

**Given** `HysteresisFilter` is in `INACTIVE` state and
`reported_kw ≥ wallbox_threshold_kw`\
**When** `update(reported_kw, now)` is called\
**Then** state transitions to `ACTIVE`\
**And** `hold_until` is set to `now + timedelta(minutes=hold_time_minutes)`\
**And** the method returns the passed `reported_kw`

**Given** `HysteresisFilter` is in `ACTIVE` state and
`reported_kw` drops below `wallbox_threshold_kw`\
**When** `update(reported_kw, now)` is called within the hold period\
**Then** state remains `ACTIVE`\
**And** the method returns the last valid `reported_kw` (not the dropped value)

**Given** hold period has expired and `reported_kw` is still below threshold\
**When** `update(reported_kw, now)` is called after `hold_until`\
**Then** state transitions to `INACTIVE`\
**And** method returns `0.0`

**Given** `force_failsafe(reason)` is called on the filter\
**When** called in any state\
**Then** state immediately transitions to `FAILSAFE`\
**And** next `update()` call returns `0.0` regardless of input\
**And** `hold_until` is cleared

**Given** `FAILSAFE` state and `resume()` is called\
**When** the engine has confirmed sensors are healthy again\
**Then** state transitions to `INACTIVE` (never directly to `ACTIVE`)\
**And** next cycle evaluates fresh

**Given** `HysteresisFilter` is imported in a plain Python unit test with
`datetime` objects as timestamps\
**When** state machine tests run\
**Then** all assertions pass without any HA import

---

## Epic 3: Forecast Integration — Weather and Solar Forecast Consumption

Implement `ForecastConsumer` to fetch weather forecast and `forecast_solar`
data from HA services, and integrate forecast signals into SOC target adjustment
within `SurplusCalculator`.

After this epic: On an overcast afternoon with poor tomorrow forecast, the engine
automatically raises the effective SOC floor earlier to preserve battery for the
household. On a sunny day with good forecast, it allows more buffer usage for EV
charging.

### Story 3.1: Forecast Data Fetching and Parsing

As the surplus engine,
I want `ForecastConsumer.get_forecast(hass)` to asynchronously fetch weather
forecast and solar production forecast data from HA,
So that the engine has predictive data available each evaluation cycle to make
smarter SOC decisions.

**Acceptance Criteria:**

**Given** `weather:` entity is configured and available\
**When** `ForecastConsumer.get_forecast(hass)` is awaited\
**Then** `await hass.services.async_call("weather", "get_forecasts",`
`{"entity_id": config[CONF_WEATHER], "type": "hourly"},`
`blocking=True, return_response=True)` is executed\
**And** the hourly `cloud_coverage` values for the next 6 hours are extracted
and averaged into a single `cloud_coverage_avg: float` (0–100)\
**And** `forecast_available` is set to `True`

**Given** `forecast_solar:` entity is configured and available\
**When** `get_forecast(hass)` is awaited\
**Then** `hass.states.get(config[CONF_FORECAST_SOLAR]).state` is read\
**And** the value is stored as `solar_forecast_kwh_today: float`\
**And** `forecast_available` remains `True` (both sources combined)

**Given** either forecast entity is `unavailable`, the service call raises an
exception, or the response is malformed\
**When** `get_forecast(hass)` is awaited\
**Then** the method catches the exception (no propagation)\
**And** returns a `ForecastData` dataclass with `forecast_available=False`,
`cloud_coverage_avg=50.0` (neutral default), `solar_forecast_kwh_today=None`\
**And** `_LOGGER.warning("Forecast unavailable: %s. Using conservative
defaults.", reason)` is emitted

**Given** `weather:` is not configured in YAML (absent from entities block)\
**When** `get_forecast(hass)` is called\
**Then** returns `ForecastData(forecast_available=False, ...)` silently —
no WARNING (expected degraded mode)

**Implementation note:** `hass.services.async_call` with `return_response=True`
is available from HA 2023.7+. The response dict structure for
`weather.get_forecasts` is
`{entity_id: {"forecast": [{"cloud_coverage": N, "datetime": "...", ...}]}}`.
This is the same service-call pattern used in `evcc_intg` (see
`await hass.services.async_call(DOMAIN, SERVICE, data, blocking=True,
return_response=True)`). Add `ForecastData` as a new `@dataclass` at the top
of `surplus_engine.py`.

### Story 3.2: Forecast-Driven SOC Target Adjustment

As the surplus engine,
I want `SurplusCalculator.calculate_surplus(snapshot)` to raise the effective
SOC floor when forecast indicates poor upcoming solar production,
So that the household battery is better protected on days when PV output will
be insufficient to recharge it.

**Acceptance Criteria:**

**Given** `snapshot.forecast.cloud_coverage_avg < 20` (sunny forecast) and
current time is before 15:00\
**When** `calculate_surplus(snapshot)` is called\
**Then** the effective SOC floor equals the time-window default (not raised)\
**And** `result.reason` contains `"forecast_good"`

**Given** `snapshot.forecast.cloud_coverage_avg > 70` (overcast forecast) and
current time is past 13:00\
**When** `calculate_surplus(snapshot)` is called\
**Then** the effective SOC floor is raised to exactly 80% (matching the
`default:` seasonal target for the current month, which equals 80 for months
where the seasonal target is 80; in winter months this floor may be higher)
regardless of whether the `before: "sunset-3h"` window has been reached\
**And** `result.reason` contains `"forecast_poor"`

**Given** `snapshot.forecast.forecast_available == False`\
**When** `calculate_surplus(snapshot)` is called\
**Then** the time-window SOC floor is used unchanged (conservative, no adjustment)\
**And** `result.forecast_available` = `False`

**Given** `ForecastConsumer.get_forecast(hass)` is called in `SurplusEngine`\
**Then** the result is passed into `SurplusCalculator` via `SensorSnapshot.forecast`\
**And** the `SurplusCalculator` accesses only `ForecastData` fields (no `hass`
reference — maintains HA-free purity of the calculator)

---

## Epic 4: Fail-Safe and Reliability — Sensor Monitoring and Fault Handling

Implement all fault-detection and fail-safe mechanisms: unavailable sensor
detection, staleness monitoring, hard SOC floor enforcement, and automatic
recovery. These safeguards ensure the battery is never at risk regardless of
software bugs, sensor failures, or network issues.

After this epic: Journey 5 (Inverter offline) works correctly. If the Growatt
integration loses connection, `STATE_UNAVAILABLE` is detected immediately,
`0 kW` is reported to the wallbox, and a WARNING is logged. When the inverter
reconnects, normal operation resumes automatically.

### Story 4.1: Sensor Unavailability Detection and Fail-Safe

As the surplus engine,
I want `SurplusEngine` to detect `STATE_UNAVAILABLE` and `STATE_UNKNOWN` sensor
states and immediately switch to fail-safe mode reporting 0 kW,
So that the battery is never drained due to the engine operating on missing or
invalid data.

**Acceptance Criteria:**

**Given** `sensor.sph10000_storage_soc` reports `STATE_UNAVAILABLE`\
**When** `_handle_state_change(event)` processes the update\
**Then** the cache entry for `CACHE_KEY_SOC` is marked invalid\
**And** on the next `_evaluation_tick`, `SurplusEngine` detects the invalid
cache entry\
**And** `HysteresisFilter.force_failsafe("sensor.sph10000_storage_soc =
unavailable")` is called\
**And** `EvaluationResult.reported_kw` = 0.0\
**And** `EvaluationResult.charging_state` = `"FAILSAFE"`\
**And** `_LOGGER.warning("SDM630 FAIL-SAFE: %s. Reporting 0 kW.", reason)` emits

**Given** any of `power_to_grid`, `pv_production`, or `power_to_user` entities
reports `STATE_UNKNOWN`\
**When** the evaluation cycle runs\
**Then** FAILSAFE is triggered with the specific entity name in the reason string

**Given** a sensor returns a non-numeric state string (not unavailable/unknown,
but e.g. `"error"` or `""` )\
**When** `float(state.state)` raises `ValueError`\
**Then** FAILSAFE is triggered with reason `"<entity_id>: non-numeric value"`

**Given** sensors recover and return valid numeric states\
**When** the cache is populated with valid values on the next state-change event\
**Then** `HysteresisFilter.resume()` is called\
**And** the next evaluation cycle produces a normal `EvaluationResult` with
`charging_state != "FAILSAFE"`\
**And** `_LOGGER.info("SDM630 recovered from FAILSAFE. Resuming normal
evaluation.")` emits

**Implementation note:** Use the constants `STATE_UNAVAILABLE` and
`STATE_UNKNOWN` from `homeassistant.const` (same pattern as `growatt_local`
`async_added_to_hass` restore logic:
`if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN): return`).
The sensor cache dict maps `CACHE_KEY_*` → `(float_value, timestamp, is_valid)`
tuples to support both unavailability detection (this story) and staleness
detection (Story 4.2).

### Story 4.2: Staleness Detection

As the surplus engine,
I want the engine to detect sensors that stopped updating (showing a frozen
last-known value) and trigger fail-safe when staleness exceeds the configured
threshold,
So that a frozen sensor reading (more dangerous than `unavailable` because it
looks normal) does not silently cause incorrect surplus calculations.

**Acceptance Criteria:**

**Given** `CACHE_KEY_SOC` was last updated more than `stale_threshold_seconds`
(default 60) seconds ago\
**When** `_evaluation_tick` runs a staleness check\
**Then** FAILSAFE is triggered\
**And** `_LOGGER.warning("SDM630 FAIL-SAFE: %s stale for %ds. Reporting 0 kW.",
entity_id, elapsed_seconds)` emits

**Given** a sensor resumes emitting state-change events after a stale period\
**When** `_handle_state_change` processes a new valid value\
**Then** the cache entry's timestamp is refreshed\
**And** on the next evaluation tick, staleness check passes\
**And** normal evaluation resumes

**Given** `stale_threshold_seconds` = 60\
**When** a sensor's last update was exactly 60 seconds ago\
**Then** FAILSAFE is NOT triggered (boundary: strictly `> 60` seconds triggers)

**Given** HA starts up and entities have not yet emitted any state-change events\
**When** the first `_evaluation_tick` fires within the first
`stale_threshold_seconds` seconds\
**Then** staleness check is skipped for cache entries with `timestamp = None`
(startup grace period — no false FAILSAFE on cold start)\
**And** after `stale_threshold_seconds` without any update, FAILSAFE triggers
normally (the startup grace period equals `stale_threshold_seconds` — changing
the config value affects both, there is no separate hardcoded grace period)

**Implementation note:** Cache each sensor value as
`(value: float, last_changed: datetime, is_valid: bool)`. The `last_changed`
is updated from `new_state.last_changed` (HA `State` object attribute) when
`_handle_state_change` fires — this is the same field checked in `evcc_intg`'s
stale-value pattern. HA's `State.last_changed` is a timezone-aware `datetime`;
compare against `dt_util.utcnow()` from `homeassistant.util.dt`.

### Story 4.3: Hard SOC Floor Enforcement

As the surplus engine,
I want the `SOC_HARD_FLOOR` constant (50%) to be enforced as an absolute
non-overridable constraint in `SurplusCalculator`,
So that the battery is protected regardless of algorithm state, config errors,
or edge cases in the time-window logic.

**Acceptance Criteria:**

**Given** `snapshot.soc_percent` = 51 and the calculated buffer would consume
more than 1% of battery capacity\
**When** `calculate_surplus(snapshot)` runs\
**Then** `buffer_used_kw` is capped so the resulting SOC draw does not push
below 50%\
**And** `result.buffer_used_kw` reflects the capped value (not the uncapped
theoretical value)

**Given** `snapshot.soc_percent` = 50 (exactly at hard floor)\
**When** `calculate_surplus(snapshot)` runs\
**Then** `result.buffer_used_kw` = 0.0 (zero buffer — floor reached)\
**And** reported surplus = real surplus only

**Given** `snapshot.soc_percent` < 50 (should not occur, but must be handled)\
**When** `calculate_surplus(snapshot)` runs\
**Then** FAILSAFE result is returned: `reported_kw=0.0`,
`charging_state="FAILSAFE"`, `reason="SOC below hard floor"`\
**And** no exception is raised (degrade gracefully)

**Given** `get_soc_floor()` in any time-window rule returns a value below 50
(misconfiguration)\
**When** `SurplusCalculator` applies the floor\
**Then** it silently clamps to 50 and logs a one-time
`_LOGGER.warning("Configured soc_floor %d% below SOC_HARD_FLOOR 50%. Clamping.")`

### Story 4.4: Sensor Value Range Validation

As the surplus engine,
I want `SurplusEngine` to validate sensor values are within plausible ranges
before passing them to `SurplusCalculator`,
So that out-of-range data (e.g., SOC=150%, negative PV production) triggers
the fail-safe rather than silently corrupting surplus calculations.

**Acceptance Criteria:**

**Given** the SOC sensor reports a value outside [0, 100] (e.g., 105)\
**When** `_evaluation_tick` validates cache values\
**Then** FAILSAFE is triggered\
**And** `_LOGGER.warning("SDM630 FAIL-SAFE: %s. Reporting 0 kW.", reason)`
emits with `reason = "sensor.<entity_id>: value 105 out of range [0, 100]"`

**Given** a power sensor (`pv_production`, `power_to_user`, `power_to_grid`)
reports a value outside its configured valid range\
**When** validation runs\
**Then** FAILSAFE is triggered with reason
`"sensor.<entity_id>: value <X> out of range [<min>, <max>]"`

**Given** sensor value passes range validation\
**When** validation completes\
**Then** no FAILSAFE is triggered and the value is passed to
`SurplusCalculator` unchanged

**Given** `CONF_SENSOR_RANGES` is not configured in YAML\
**When** range validation runs\
**Then** default ranges are used: SOC ∈ [0, 100], power values ∈ [−30000, 30000] W\
**And** the defaults are defined in the `DEFAULTS` dict

**Given** sensors recover and return in-range values\
**When** next valid state-change event arrives\
**Then** FAILSAFE clears normally (same `HysteresisFilter.resume()` path as
unavailability recovery in Story 4.1)

**Implementation note:** Implement range checks in a `_validate_cache(cache)`
method in `SurplusEngine`, called at the start of `_evaluation_tick` before
building `SensorSnapshot`. This keeps `SurplusCalculator` HA-free (no
validation logic moves into the pure module).

---

## Epic 5: Test Infrastructure — Unit Tests for Pure Logic Components

Create the pytest test suite for all HA-independent logic. `SurplusCalculator`
and `HysteresisFilter` are pure Python — they can be tested without a running
HA instance, in CI, or locally with just `pip install pytest pytest-asyncio`.

After this epic: `python -m pytest tests/ -v` exits with code 0, providing
confidence that core surplus logic is correct before deploying to a live HA
instance.

### Story 5.1: Test Infrastructure Setup and `SurplusCalculator` Tests

As a developer (Ghost),
I want a pytest test suite for `SurplusCalculator` covering all logic paths
including all SOC strategy time windows, buffer math, and forecast adjustments,
So that surplus calculation correctness is verifiable in isolation and
regressions are caught automatically when parameters change.

**Acceptance Criteria:**

**Given** `tests/conftest.py` with shared `SensorSnapshot` and `ForecastData`
fixtures\
**When** `pytest tests/` runs\
**Then** fixtures are available to all test modules without import errors\
**And** no `homeassistant` package is imported (verified by checking
`sys.modules` in conftest teardown)

**Given** `tests/test_surplus_calculator.py`\
**When** all tests run with `pytest tests/test_surplus_calculator.py -v`\
**Then** the following scenarios are covered and pass:

- `test_normal_sunny_day`: real_surplus > threshold, no buffer, reported = real
- `test_cloudy_buffer_fills_gap`: real < threshold, buffer fills to 4.2 kW
- `test_soc_at_hard_floor_no_buffer`: SOC=50, buffer_used=0.0
- `test_soc_below_hard_floor_failsafe`: SOC=48, charging_state=FAILSAFE
- `test_time_window_morning_floor_100`: before 11:00, floor=100
- `test_time_window_free_window_floor_50`: 11:00–sunset-3h, floor=50
- `test_time_window_evening_floor_80`: after sunset-3h, floor=80
- `test_time_window_no_sunset_uses_default`: sunset_time=None, floor=default
- `test_forecast_good_floor_unchanged`: cloud_coverage=10, floor not raised
- `test_forecast_poor_floor_raised`: cloud_coverage=85 after 13:00, floor raised
- `test_forecast_unavailable_conservative`: forecast_available=False, floor=default

**Given** all tests pass\
**When** run with `python -m pytest tests/ -v`\
**Then** exit code = 0

### Story 5.2: `HysteresisFilter` State Machine Tests

As a developer (Ghost),
I want a pytest test suite for `HysteresisFilter` covering all state
transitions and boundary conditions,
So that hysteresis correctness is verifiable in isolation and regressions are
caught automatically without a running HA instance.

**Acceptance Criteria:**

**Given** `tests/test_hysteresis_filter.py`\
**When** all tests run with `pytest tests/test_hysteresis_filter.py -v`\
**Then** the following state transitions are covered and pass:

- `test_inactive_to_active_on_threshold_met`: INACTIVE → ACTIVE when kW ≥
  threshold
- `test_active_holds_during_hold_period`: ACTIVE stays ACTIVE when kW drops
  but hold timer not expired
- `test_active_to_inactive_after_hold_expires`: ACTIVE → INACTIVE when hold
  timer expires and kW still below threshold
- `test_force_failsafe_from_any_state`: any state → FAILSAFE on
  `force_failsafe()`
- `test_failsafe_resume_goes_to_inactive`: FAILSAFE → INACTIVE (not ACTIVE) on
  `resume()`
- `test_hold_timer_boundary_at_exactly_hold_duration`: still ACTIVE at
  `now == hold_until`
- `test_hold_timer_boundary_one_second_past`: INACTIVE at
  `now == hold_until + 1s`
- `test_returns_zero_when_inactive`: `update()` returns 0.0 in INACTIVE state
  when kW below threshold

**Given** `HysteresisFilter` is imported in a plain Python test\
**When** the test runs without a Home Assistant instance\
**Then** all state machine tests pass with exit code 0
