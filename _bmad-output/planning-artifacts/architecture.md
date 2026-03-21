---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
workflowType: architecture
lastStep: 8
status: complete
completedAt: '2026-03-21'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/product-brief-sdm630-simulator-2026-03-15.md
  - AGENTS.md
  - sensor.py
  - modbus_server.py
  - registers.py
  - sdm630_input_registers.py
  - sdm630_holding_registers.py
  - growat-modbus/Homeassistant-Growatt-Local-Modbus/custom_components/growatt_local/sensor.py
  - growat-modbus/Homeassistant-Growatt-Local-Modbus/custom_components/growatt_local/__init__.py
  - marq24/ha-evcc/custom_components/evcc_intg/sensor.py
workflowType: architecture
project_name: sdm630-simulator
user_name: Ghost
date: 2026-03-21
---

# Architecture Decision Document — sdm630-simulator

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

**Project:** sdm630-simulator — Intelligent Energy Broker  
**Type:** IoT / Home Assistant Custom Component (Brownfield)  
**Date:** 2026-03-21

### Functional Requirements

| # | Capability | Priority |
|---|---|---|
| FR-1 | Surplus-Calculation Engine (SOC + Power-to-Grid + PV → kW) | Must-Have |
| FR-2 | Time-based SOC strategy: 3 time windows with dynamic SOC floors | Must-Have |
| FR-3 | Weather/Solar forecast integration (`forecast_solar`, `weather.get_forecasts`) | Must-Have |
| FR-4 | Stabilized Modbus signal with hysteresis (min. 10 min. hold time) | Must-Have |
| FR-5 | Fail-safe: on missing/stale data → report 0 kW | Must-Have |
| FR-6 | Decision logging (DEBUG/INFO/WARNING) | Must-Have |
| FR-7 | YAML config for entity mappings and thresholds | Must-Have |
| FR-8 | Staleness detection: sensor timestamp unchanged > 60s → fail-safe | Should-Have |

### Non-Functional Requirements

- **Real-time**: Evaluation cycle 10–30 seconds (configurable)
- **Async**: Full `async/await` integration — no blocking I/O in HA event loop
- **Reliability**: Hard SOC floor 50% never violated under any circumstances
- **Brownfield**: Integration into existing `sensor.py` and `modbus_server.py`
- **Configuration**: All thresholds (SOC floors, time windows, seasonal targets) via `configuration.yaml`
- **Scale**: Single-user, no multi-tenancy, no cloud

### Key Architectural Challenges

1. **Three data sources → one scalar output**: SOC (real-time), Forecast (predictive), Time strategy (rule-based) → single kW value
2. **HA Entity State Machine**: Growatt entities can be `unknown`/`unavailable`/stale — all cases must be handled gracefully
3. **Brownfield integration**: Existing `SDM630SimSensor._handle_state_change()` is the entry point — new logic must integrate cleanly
4. **Staleness vs. unavailability**: A sensor showing its last known value (stale) is more dangerous than `unavailable` — must distinguish
5. **Forecast service calls**: `weather.get_forecasts` is a HA service call (async, returns coroutine) — pattern differs from entity state reads

### Complexity Assessment

- **Project Complexity:** High
- **Primary Technical Domain:** IoT / HA Custom Component / Modbus
- **Cross-cutting Concerns:** Fail-safe logic, decision logging, configuration validation, SOC protection
## Implementation Patterns & Consistency Rules

### Naming Conventions

| Scope | Convention | Example |
|---|---|---|
| Classes | `CamelCase` | `SurplusEngine`, `HysteresisFilter`, `ForecastConsumer` |
| Functions/Methods | `snake_case` | `calculate_surplus()`, `get_soc_floor()` |
| Constants | `UPPER_SNAKE_CASE` | `SOC_HARD_FLOOR`, `WALLBOX_THRESHOLD_KW` |
| Logger | `logging.getLogger(__name__)` as `_LOGGER` | every module |
| Dual-import guard | `if __package__:` | all modules |

### Module Internal Structure

```
surplus_engine.py
  class SurplusEngine         ← Orchestrator; instantiated by sensor.py
  class SurplusCalculator     ← Pure logic only: SOC strategy + surplus math
  class ForecastConsumer      ← HA service calls (weather.get_forecasts, forecast_solar)
  class HysteresisFilter      ← ACTIVE/INACTIVE state machine
  @dataclass SensorSnapshot   ← Immutable snapshot of all inputs per cycle
  @dataclass EvaluationResult ← Immutable result per evaluation cycle
```

**Non-negotiable rule:** `SurplusCalculator` MUST NOT import any HA-specific object — only Python stdlib and `dataclasses`. This enables unit testing without HA.

### Sensor Cache Keys (canonical, never change)

```python
CACHE_KEY_SOC              = "soc_percent"
CACHE_KEY_POWER_TO_GRID    = "power_to_grid_w"
CACHE_KEY_PV_PRODUCTION    = "pv_production_w"
CACHE_KEY_POWER_TO_USER    = "power_to_user_w"
CACHE_KEY_BATTERY_DISCHARGE = "battery_discharge_w"
```

### EvaluationResult Structure (always fully populated)

```python
@dataclass
class EvaluationResult:
    reported_kw: float        # Value written to Modbus register
    real_surplus_kw: float    # Actual surplus without battery buffer
    buffer_used_kw: float     # Battery buffer contribution
    soc_percent: float        # Current SOC at evaluation time
    soc_floor_active: int     # Which SOC floor rule applied
    charging_state: str       # "ACTIVE" | "INACTIVE" | "FAILSAFE"
    reason: str               # Human-readable one-liner for log
    forecast_available: bool
```

### Logging Patterns (mandatory formats)

**Decision log (DEBUG):**

```python
_LOGGER.debug(
    "SDM630 Eval: surplus=%.2fkW buffer=%.2fkW SOC=%d%% floor=%d%% "
    "state=%s reported=%.2fkW reason=%s forecast=%s",
    result.real_surplus_kw, result.buffer_used_kw, result.soc_percent,
    result.soc_floor_active, result.charging_state, result.reported_kw,
    result.reason, result.forecast_available
)
```

**Fail-safe (WARNING):**

```python
_LOGGER.warning("SDM630 FAIL-SAFE: %s. Reporting 0 kW.", reason)
```

### Configuration Defaults (never propagate None)

```python
DEFAULTS = {
    "evaluation_interval": 15,       # seconds
    "wallbox_threshold_kw": 4.2,     # reported minimum to keep wallbox charging
    "wallbox_min_kw": 4.1,           # wallbox's own minimum to start charging
    "hold_time_minutes": 10,          # hysteresis hold duration
    "soc_hard_floor": 50,            # absolute battery protection floor (%)
    "stale_threshold_seconds": 60,   # sensor staleness detection threshold
}
```

### Entity Validation Rules

- All entity IDs validated in `async_added_to_hass()` at startup
- Missing non-critical entity → WARNING, degraded mode (no forecast)
- Missing SOC entity → ERROR, FAILSAFE mode until entity becomes available
- Never crash on missing entity — always degrade gracefully

## Project Structure & Boundaries

### Technology Versions

| Component | Version | Source |
|---|---|---|
| Python | 3.12 | Current HA requirement (2024+) |
| pymodbus | >=3.11.1 | Aligned with growatt_local manifest.json |
| Home Assistant | 2024.x+ | Runtime platform |

**Note:** AGENTS.md previously stated `Python 3.9+` and `pymodbus>=3.9.2`. Both updated to align with the Growatt Local Modbus reference implementation (`pymodbus>=3.11.1`) and current HA runtime (Python 3.12).

### Requirements-to-Component Mapping

| Requirement | Component | File |
|---|---|---|
| FR-1 Surplus Calculation Engine | `SurplusCalculator` | `surplus_engine.py` |
| FR-2 SOC Time-Window Strategy | `SurplusCalculator` | `surplus_engine.py` |
| FR-3 Forecast Integration | `ForecastConsumer` | `surplus_engine.py` |
| FR-4 Hysteresis / Signal Stabilization | `HysteresisFilter` | `surplus_engine.py` |
| FR-5 Fail-Safe | `SurplusEngine` (orchestrator) | `surplus_engine.py` |
| FR-6 Decision Logging | All modules via `_LOGGER` | all `.py` files |
| FR-7 YAML Configuration | Config parsing + entity setup | `__init__.py`, `sensor.py` |
| FR-8 Staleness Detection | `SurplusEngine._sensor_cache` | `surplus_engine.py` |

### Complete Project File Structure

```
custom_components/sdm630_simulator/
├── __init__.py                      # HA entry: async_setup, config parse, entity ID validation
├── sensor.py                        # MODIFIED: SDM630SimSensor
│                                    #   - Instantiates SurplusEngine
│                                    #   - State-change handlers → update sensor cache
│                                    #   - Starts evaluation loop (asyncio task)
│                                    #   - Writes EvaluationResult → input_data_block
├── surplus_engine.py                # NEW: Intelligence layer
│   ├── SurplusEngine                #   Orchestrator (HA-aware)
│   ├── SurplusCalculator            #   Pure logic (HA-free, unit-testable)
│   ├── ForecastConsumer             #   HA service calls
│   ├── HysteresisFilter             #   ACTIVE/INACTIVE state machine
│   ├── SensorSnapshot (dataclass)   #   Immutable per-cycle input snapshot
│   └── EvaluationResult (dataclass) #   Immutable per-cycle output
├── modbus_server.py                 # UNCHANGED: Modbus TCP server + SDM630DataBlock
├── registers.py                     # UNCHANGED: SDM630Register, SDM630Registers
├── sdm630_input_registers.py        # UNCHANGED: 51 input registers
├── sdm630_holding_registers.py      # UNCHANGED: 11 holding registers
├── manifest.json                    # Updated: pymodbus>=3.11.1
AGENTS.md                            # Updated: Python 3.12, pymodbus>=3.11.1

tests/
├── test_surplus_calculator.py       # Unit tests — no HA dependency
├── test_hysteresis_filter.py        # Unit tests for state machine
└── conftest.py                      # pytest fixtures
```

### Component Boundary Diagram

```
┌───────────────────────────────────────────┐
│  Home Assistant Platform Layer            │
│  sensor.py: SDM630SimSensor               │
│  - HA lifecycle (async_added_to_hass)     │
│  - State change subscriptions             │
│  - asyncio evaluation loop (15s default)  │
│  - Writes to Modbus register              │
└──────────────┬────────────────────────────┘
               │ calls evaluate_cycle()
               ▼
┌───────────────────────────────────────────┐
│  Domain Layer (HA-free)                   │
│  surplus_engine.py: SurplusEngine         │
│  ┌─────────────────┐ ┌─────────────────┐  │
│  │ SurplusCalc.    │ │ ForecastConsumer│  │
│  │ - SOC strategy  │ │ - weather svc   │  │
│  │ - buffer math   │ │ - solar forecast│  │
│  └─────────────────┘ └─────────────────┘  │
│  ┌───────────────────────────────────┐    │
│  │ HysteresisFilter                  │    │
│  │ - ACTIVE / INACTIVE state machine │    │
│  └───────────────────────────────────┘    │
└──────────────┬────────────────────────────┘
               │ returns float (kW)
               ▼
┌───────────────────────────────────────────┐
│  Modbus Layer (unchanged)                 │
│  modbus_server.py: SDM630DataBlock        │
│  input_data_block.set_float(TOTAL_POWER) │
└──────────────┬────────────────────────────┘
               │ Modbus TCP :5020
               ▼
         Growatt THOR Wallbox
```

### Configuration Schema (`configuration.yaml`)

```yaml
sdm630_sim:
  name: "SDM630 Simulator"             # optional
  evaluation_interval: 15              # seconds, default: 15
  wallbox_threshold_kw: 4.2            # reported surplus floor, default: 4.2
  hold_time_minutes: 10                # hysteresis hold duration, default: 10
  soc_hard_floor: 50                   # absolute battery protection, default: 50

  entities:
    soc:            sensor.sph10000_storage_soc
    power_to_grid:  sensor.sph10000_pac_to_grid_total
    pv_production:  sensor.sph10000_input_power
    power_to_user:  sensor.sph10000_pac_to_user_total
    sun:            sun.sun                              # for sunset-relative times
    weather:        weather.openweathermap               # optional
    forecast_solar: sensor.forecast_solar_energy_today   # optional

  time_strategy:
    - before: "11:00"
      soc_floor: 100
    - before: "sunset-3h"
      soc_floor: 50
    - default:
      soc_floor: 80
```

## Architecture Validation

### Coherence Validation

| Check | Result |
|---|---|
| Technology compatibility (Python 3.12 + pymodbus 3.11.1 + HA async) | ✅ Pass |
| Pattern consistency (Hybrid Cache+Loop ↔ ForecastConsumer) | ✅ Pass |
| Structure alignment (surplus_engine.py fully self-contained) | ✅ Pass |
| No contradictory decisions | ✅ Pass |

### Requirements Coverage

| Requirement | Covered by | Status |
|---|---|---|
| FR-1 Surplus Engine | `SurplusCalculator` | ✅ |
| FR-2 SOC Time-Window Strategy | `SurplusCalculator` + YAML config | ✅ |
| FR-3 Forecast Integration | `ForecastConsumer` | ✅ |
| FR-4 Hysteresis / Signal Stabilization | `HysteresisFilter` | ✅ |
| FR-5 Fail-Safe (0 kW on error) | `SurplusEngine` orchestrator | ✅ |
| FR-6 Decision Logging | `_LOGGER` + `EvaluationResult.reason` | ✅ |
| FR-7 YAML Configuration | `__init__.py` + config schema | ✅ |
| FR-8 Staleness Detection | `_sensor_cache` with timestamp tracking | ✅ |
| NFR: Async / no blocking I/O | asyncio evaluation loop | ✅ |
| NFR: SOC 50% hard floor | `soc_hard_floor` in all code paths | ✅ |
| NFR: HA lifecycle handling | `async_added_to_hass()` + entity validation | ✅ |
| NFR: Fail-safe on data loss | Layered fail-safe strategy | ✅ |

### Gap Analysis

| # | Gap | Severity | Resolution |
|---|---|---|---|
| L1 | Exact Growatt entity IDs for Ghost's setup not pinned in architecture | Medium | Configurable in `configuration.yaml` — not an architecture concern |
| L2 | Exact `forecast_solar` attribute name (today vs. tomorrow kWh) | Low | Resolved during `ForecastConsumer` implementation |
| L3 | Epics/Stories not yet created | Low | Next workflow step |
| L4 | `pytest` / `pytest-asyncio` not in `manifest.json` | Low | Dev-only dependencies; excluded from HA package |

**No critical gaps. Architecture is implementation-ready.**

### Decision 1: Data Flow & Trigger Model

**Decision:** Hybrid Pattern — Sensor Cache + Interval Evaluation Loop

- State-change handlers per Growatt sensor update only a local in-memory cache (`_sensor_cache: dict`)
- A separate `asyncio` evaluation loop (default 15s, configurable) reads cache + fetches forecast + calculates surplus → writes Modbus register
- Forecast is fetched once per evaluation cycle, not per sensor update

**Rationale:** Prevents excessive HA service calls for forecast on every sensor update; decouples input rate from output rate; aligns with PRD requirement for configurable 10–30s evaluation interval.

### Decision 2: Fail-Safe Strategy

**Decision:** Layered fail-safe with distinct handling per failure type:

| Condition | Action | Log Level |
|---|---|---|
| Entity state is `unavailable` or `unknown` | Report 0 kW immediately | WARNING |
| Stale sensor: critical sensor timestamp unchanged > 60s | Report 0 kW | WARNING (once per incident) |
| Forecast service unavailable | Continue with conservative seasonal defaults | INFO |
| Complete data loss / exception in evaluation | Report 0 kW | ERROR |

- "Critical sensors" for staleness check: SOC, Power-to-Grid (mandatory for surplus decisions)
- Forecast failure never triggers 0 kW — it degrades gracefully to conservative mode
- Log-spam prevention: repeated fail-safe events logged max once per minute

### Decision 3: SOC Time-Window Strategy

**Decision:** Configurable list of time-window rules evaluated top-to-bottom; first matching rule wins.

- Time references support absolute (`"11:00"`) and relative-to-sunset (`"sunset-3h"`) formats
- Sunset time sourced from `sun.sun` entity (`next_setting` attribute) — resolved at evaluation time
- Config format (YAML):

```yaml
sdm630_sim:
  time_strategy:
    - before: "11:00"
      soc_floor: 100
    - before: "sunset-3h"
      soc_floor: 50
    - default:
      soc_floor: 80
  soc_hard_floor: 50
```

- `soc_hard_floor: 50` is the absolute battery protection floor — overrides all other rules
- For MVP: sunset-relative time is supported from day one (uses `sun.sun`)

### Decision 4: Hysteresis / Signal Stabilization State Machine

**Decision:** Two-state machine: `INACTIVE` ↔ `ACTIVE`

```
INACTIVE → ACTIVE:  computed_surplus >= wallbox_threshold (4.2 kW default)
ACTIVE → INACTIVE:  SOC < soc_hard_floor
                    OR (hold_timer_expired AND real_surplus < wallbox_min_threshold)
```

- `hold_timer`: 10 minutes (configurable), reset on every evaluation that keeps `ACTIVE` valid
- While `ACTIVE`: report `max(computed_surplus, wallbox_threshold)` to stabilize signal
- While `INACTIVE`: report `real_surplus_to_grid` (or 0 if negative / SOC protection)

**Decision:** Option B — `surplus_engine.py` als eigenständiges Modul (Separation of Concerns)

**Rationale:** Minimaler Brownfield-Umbau, isolierbare Domänenlogik, AGENTS.md-konforme Modul-Trennung.

```
sensor.py               → SDM630SimSensor (Orchestration + HA lifecycle)
surplus_engine.py       → SurplusEngine (pure domain logic, testable)
  ├── SurplusCalculator   (SOC strategy + power flow calculation)
  ├── ForecastConsumer    (weather + solar forecast)
  └── HysteresisFilter    (signal stabilization)
modbus_server.py        → unverändert (Modbus TCP server + register store)
registers.py            → unverändert
sdm630_input_registers.py  → unverändert
sdm630_holding_registers.py → unverändert
```