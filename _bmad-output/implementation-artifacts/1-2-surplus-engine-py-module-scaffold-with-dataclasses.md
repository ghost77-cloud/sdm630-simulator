# Story 1.2: `surplus_engine.py` Module Scaffold with Dataclasses

Status: ready-for-dev

## Story

As a developer (Ghost),
I want the `surplus_engine.py` module created with all class and dataclass
skeletons including the canonical `SensorSnapshot` and `EvaluationResult` dataclasses,
so that the full module structure is in place ready for logic implementation
in subsequent stories — and importable without errors in plain Python tests.

## Acceptance Criteria

1. **Given** `surplus_engine.py` is created in the component directory
   **When** imported in plain Python (no HA runtime)
   **Then** no `ImportError` or `ModuleNotFoundError` occurs
   **And** the module exposes exactly these top-level names:
   `SurplusEngine`, `SurplusCalculator`, `ForecastConsumer`, `HysteresisFilter`,
   `SensorSnapshot`, `EvaluationResult`, `ForecastData`

2. **Given** `SurplusCalculator` class definition
   **When** its import list is inspected
   **Then** it imports ONLY from Python stdlib (`datetime`, `math`) and `dataclasses` —
   zero HA-specific imports

3. **Given** `EvaluationResult` dataclass
   **When** instantiated with all fields
   **Then** it contains exactly: `reported_kw: float`, `real_surplus_kw: float`,
   `buffer_used_kw: float`, `soc_percent: float`, `soc_floor_active: int`,
   `charging_state: str`, `reason: str`, `forecast_available: bool`

4. **Given** `ForecastData` dataclass (stub — fully implemented in Epic 3)
   **When** instantiated with defaults
   **Then** it contains: `forecast_available: bool = False`,
   `cloud_coverage_avg: float = 50.0`,
   `solar_forecast_kwh_today: float | None = None`

5. **Given** `SensorSnapshot` dataclass
   **When** instantiated
   **Then** it contains at minimum: `soc_percent: float`, `power_to_grid_w: float`,
   `pv_production_w: float`, `power_to_user_w: float`, `timestamp: datetime`,
   `sunset_time: datetime | None`, `sunrise_time: datetime | None`,
   `forecast: ForecastData | None = None`
   **Note:** `sun.sun` is always present in HA; `None` defaults are for unit-test safety only

6. **Given** module-level declarations
   **Then** `_LOGGER = logging.getLogger(__name__)` is defined
   **And** `if __package__:` dual-import guard is present
   **And** `SOC_HARD_FLOOR: int = 50` is defined as a module-level constant

7. **Given** `SurplusEngine`, `ForecastConsumer`, `HysteresisFilter` skeletons
   **Then** each method body contains `raise NotImplementedError` or `pass`
   **EXCEPTION:** `SurplusEngine.evaluate_cycle(snapshot)` must return a valid
   default `EvaluationResult` — never raise:
   `EvaluationResult(reported_kw=0.0, real_surplus_kw=0.0, buffer_used_kw=0.0,`
   `soc_percent=0.0, soc_floor_active=50, charging_state="INACTIVE",`
   `reason="engine_not_yet_implemented", forecast_available=False)`
   so that Story 1.3's evaluation loop runs without crashing during Epic 1

## Tasks / Subtasks

- [ ] Create `surplus_engine.py` in component directory (AC: #1, #6)
  - [ ] Add module docstring and `if __package__:` guard at top
  - [ ] Add `_LOGGER` and `SOC_HARD_FLOOR = 50` module-level constants
- [ ] Define `ForecastData` dataclass (AC: #4)
  - [ ] `forecast_available: bool = False`
  - [ ] `cloud_coverage_avg: float = 50.0`
  - [ ] `solar_forecast_kwh_today: float | None = None`
- [ ] Define `SensorSnapshot` dataclass (AC: #5)
  - [ ] All required fields with correct types
  - [ ] `forecast: ForecastData | None = None` as last field with default
- [ ] Define `EvaluationResult` dataclass (AC: #3)
  - [ ] All 8 fields with exact types matching AC
- [ ] Define `SurplusCalculator` class — stdlib only (AC: #2)
  - [ ] Imports: `datetime`, `math`, `dataclasses` only — NO HA imports
  - [ ] `__init__(self, config: dict) -> None: pass` — stores config for Epic 2 access
  - [ ] `get_soc_floor(self, snapshot: SensorSnapshot) -> int: raise NotImplementedError`
  - [ ] `calculate_surplus(self, snapshot: SensorSnapshot) -> EvaluationResult: raise NotImplementedError`
- [ ] Define `HysteresisFilter` class skeleton (AC: #7)
  - [ ] `__init__(self, hold_time_minutes: int) -> None: pass`
  - [ ] `update(self, reported_kw: float, now: datetime) -> float: raise NotImplementedError`
  - [ ] `force_failsafe(self, reason: str) -> None: raise NotImplementedError`
  - [ ] `resume(self) -> None: raise NotImplementedError`
- [ ] Define `ForecastConsumer` class skeleton (AC: #7)
  - [ ] `__init__(self, config: dict) -> None: pass`
  - [ ] `async def get_forecast(self, hass) -> ForecastData: raise NotImplementedError`
- [ ] Define `SurplusEngine` orchestrator class (AC: #1, #7)
  - [ ] `__init__(self, config: dict) -> None` → store `self.config = config` (not just `pass`)
  - [ ] `async def evaluate_cycle(self, snapshot: SensorSnapshot) -> EvaluationResult` → returns default
    `EvaluationResult` (NOT raise) — **must be `async def`** to avoid signature regression in Story 3
- [ ] Verify module imports cleanly in plain Python (no HA runtime) (AC: #1)

## Dev Notes

### File Location

- **Create:** `custom_components/sdm630_simulator/surplus_engine.py`
- Do NOT place anywhere else — same directory as `sensor.py`, `__init__.py`, etc.

### Module Structure (exact required layout)

```python
# surplus_engine.py
from __future__ import annotations
import logging
import math
from dataclasses import dataclass
from datetime import datetime

if __package__:
    pass  # HA-specific imports go here (none in this story)

_LOGGER = logging.getLogger(__name__)

SOC_HARD_FLOOR: int = 50

# --- Dataclasses ---
@dataclass
class ForecastData: ...

@dataclass
class SensorSnapshot: ...

@dataclass
class EvaluationResult: ...

# --- Pure logic (stdlib only, no HA) ---
class SurplusCalculator:
    def __init__(self, config: dict) -> None: ...
    def get_soc_floor(self, snapshot: SensorSnapshot) -> int: ...       # Story 2.1
    def calculate_surplus(self, snapshot: SensorSnapshot) -> EvaluationResult: ...  # Story 2.2

# --- HA-aware classes ---
class HysteresisFilter:
    def __init__(self, hold_time_minutes: int) -> None: ...
    def update(self, reported_kw: float, now: datetime) -> float: ...   # Story 2.3
    def force_failsafe(self, reason: str) -> None: ...
    def resume(self) -> None: ...

class ForecastConsumer:
    def __init__(self, config: dict) -> None: ...
    async def get_forecast(self, hass) -> ForecastData: ...             # Story 3.1

class SurplusEngine:                                                     # Orchestrator
    def __init__(self, config: dict) -> None: ...
    async def evaluate_cycle(self, snapshot: SensorSnapshot) -> EvaluationResult: ...
```

### Dual-Import Guard Pattern

The existing codebase uses `if __package__:` to guard HA-specific imports. Example from pattern in codebase:

```python
if __package__:
    from homeassistant.core import HomeAssistant
    # ... other HA imports for Story 1.3 onward
```

For this story, no HA imports are needed — the guard block can be empty or omitted.
`SurplusCalculator` **must** have zero HA-related imports, even behind the guard.

### Exact Field Specifications

#### `EvaluationResult` (all fields required, no defaults allowed)

```python
@dataclass
class EvaluationResult:
    reported_kw: float
    real_surplus_kw: float
    buffer_used_kw: float
    soc_percent: float
    soc_floor_active: int
    charging_state: str       # "ACTIVE" | "INACTIVE" | "FAILSAFE"
    reason: str               # human-readable one-liner for log
    forecast_available: bool
```

#### `ForecastData` (all fields have defaults — safe to instantiate as `ForecastData()`)

```python
@dataclass
class ForecastData:
    forecast_available: bool = False
    cloud_coverage_avg: float = 50.0
    solar_forecast_kwh_today: float | None = None
```

#### `SensorSnapshot` (fields with defaults must come after fields without)

```python
@dataclass
class SensorSnapshot:
    soc_percent: float
    power_to_grid_w: float
    pv_production_w: float
    power_to_user_w: float
    timestamp: datetime
    sunset_time: datetime | None
    sunrise_time: datetime | None
    forecast: ForecastData | None = None
```

### `evaluate_cycle` — MUST be `async def` (prevents Story 3 regression)

`ForecastConsumer.get_forecast(hass)` is async (Story 3.1). When integrated into
`SurplusEngine.evaluate_cycle`, the method must `await` it. Defining `evaluate_cycle`
as sync now forces a signature change AND a Story 1.3 update in Story 3 — a regression.
**Define it as `async def` from the start.** Story 1.3 will call `await engine.evaluate_cycle(snapshot)`.

```python
async def evaluate_cycle(self, snapshot: SensorSnapshot) -> EvaluationResult:
    return EvaluationResult(
        reported_kw=0.0,
        real_surplus_kw=0.0,
        buffer_used_kw=0.0,
        soc_percent=0.0,
        soc_floor_active=50,
        charging_state="INACTIVE",
        reason="engine_not_yet_implemented",
        forecast_available=False,
    )
```

### `SurplusEngine.__init__` Signature

Story 1.3 calls `SurplusEngine(config)`. In Stories 2+, `self.config` is accessed directly.
Must store — not just `pass`:

```python
def __init__(self, config: dict) -> None:
    self.config = config
```

### `SurplusCalculator` Constructor and Method Stubs

`SurplusCalculator` needs `config` for time_strategy (Story 2.1) and wallbox thresholds
(Story 2.2). Define stubs now so Story 2 can extend without touching the constructor:

```python
class SurplusCalculator:
    def __init__(self, config: dict) -> None:
        self.config = config

    def get_soc_floor(self, snapshot: SensorSnapshot) -> int:
        raise NotImplementedError

    def calculate_surplus(self, snapshot: SensorSnapshot) -> EvaluationResult:
        raise NotImplementedError
```

### `HysteresisFilter` Constructor and Method Stubs

Story 2.3 implements the ACTIVE/INACTIVE/FAILSAFE state machine. Define the full
method surface now so Story 2.3 only fills in the bodies:

```python
class HysteresisFilter:
    def __init__(self, hold_time_minutes: int) -> None:
        pass

    def update(self, reported_kw: float, now: datetime) -> float:
        raise NotImplementedError

    def force_failsafe(self, reason: str) -> None:
        raise NotImplementedError

    def resume(self) -> None:
        raise NotImplementedError
```

### `ForecastConsumer` Constructor and Method Stub

Story 3.1 implements `get_forecast(hass)`. The `hass` object is passed per-call to avoid
storing it at construction (keeps the class HA-lifecycle-independent at startup):

```python
class ForecastConsumer:
    def __init__(self, config: dict) -> None:
        self.config = config

    async def get_forecast(self, hass) -> ForecastData:
        raise NotImplementedError
```

### Naming Conventions (from AGENTS.md)

| Scope | Convention | Example |
|---|---|---|
| Classes | `CamelCase` | `SurplusEngine`, `HysteresisFilter` |
| Functions | `snake_case` | `evaluate_cycle()`, `fetch_forecast()` |
| Constants | `UPPER_SNAKE_CASE` | `SOC_HARD_FLOOR` |
| Logger | `logging.getLogger(__name__)` as `_LOGGER` | module level |

### Python Version & Typing

- Python 3.12 (current HA requirement)
- Use `float | None` syntax (PEP 604 union types — no `Optional[float]`)
- `from __future__ import annotations` at top enables forward references cleanly

### What NOT to Implement in This Story

- No actual surplus calculation logic (Epic 2)
- No hysteresis state transitions (Epic 2)
- No forecast fetching (Epic 3)
- No HA service calls or `hass` references anywhere in this story
- No integration with `sensor.py` (Story 1.3)
- No config parsing (Story 1.1)

### Regression Risk

- Zero changes to existing files: `sensor.py`, `__init__.py`, `modbus_server.py`,
  `registers.py`, `sdm630_input_registers.py`, `sdm630_holding_registers.py`
- This story creates only one new file: `surplus_engine.py`

### Project Structure Notes

```
custom_components/sdm630_simulator/
├── __init__.py                      (unchanged)
├── sensor.py                        (unchanged)
├── surplus_engine.py                ← CREATE THIS (this story)
├── modbus_server.py                 (unchanged)
├── registers.py                     (unchanged)
├── sdm630_input_registers.py        (unchanged)
├── sdm630_holding_registers.py      (unchanged)
└── manifest.json                    (unchanged)
```

### References

- Class/dataclass specifications: [Source: `_bmad-output/planning-artifacts/architecture.md` — Module Internal Structure, EvaluationResult Structure]
- Story AC: [Source: `_bmad-output/planning-artifacts/epics.md` — Story 1.2]
- Dual-import guard pattern: [Source: `sensor.py`, `__init__.py` — existing codebase convention]
- Naming conventions: [Source: `AGENTS.md` — Code Style section]
- Python 3.12 requirement: [Source: `_bmad-output/planning-artifacts/architecture.md` — Technology Versions]

## Dev Agent Record

### Agent Model Used

_to be filled by dev agent_

### Debug Log References

### Completion Notes List

### File List
