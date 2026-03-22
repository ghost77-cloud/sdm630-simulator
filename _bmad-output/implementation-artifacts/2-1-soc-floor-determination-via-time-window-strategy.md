# Story 2.1: SOC Floor Determination via Time-Window Strategy

Status: done

## Story

As the surplus engine,
I want `SurplusCalculator.get_soc_floor(snapshot)` to return the applicable
SOC floor for the current time using the configured `time_strategy:` rules,
so that battery protection adapts automatically to time of day without any
manual intervention.

## Acceptance Criteria

**AC1 — Morning window (sunrise-relative)**

Given `snapshot.sunrise_time` = 05:30 and `snapshot.timestamp` is 06:45
(before `sunrise_time + 2h = 07:30`)\
When `SurplusCalculator.get_soc_floor(snapshot)` is called\
Then it returns 100 (the `soc_floor` from the `before: "sunrise+2h"` rule)\
And winter sunrise at 08:00 shifts the boundary to 10:00 — same rule applies

**AC2 — Midday free window**

Given `snapshot.timestamp` is past `sunrise_time + 2h` and before
`sunset_time − 3h`\
When `get_soc_floor(snapshot)` is called\
Then it returns 50 (the free midday window floor)

**AC3 — Evening / default window with seasonal override**

Given `snapshot.timestamp` is within 3 hours of sunset or later\
When `get_soc_floor(snapshot)` is called\
Then it returns `config["seasonal_targets"][snapshot.timestamp.month]`
(e.g. 80 in March, 100 in December)\
And this overrides the static `soc_floor` on the `default:` YAML entry

**AC4 — sunrise_time = None fallback**

Given `snapshot.sunrise_time` is `None` (sun.sun temporarily unavailable)\
When `get_soc_floor(snapshot)` is called and the morning rule uses
`"sunrise+Xh"`\
Then the morning `before:` boundary cannot be resolved, the rule is skipped\
And the `default:` seasonal target for the current month is applied directly

**AC5 — sunset_time = None fallback**

Given `snapshot.sunset_time` is `None`\
When the `"sunset-3h"` token cannot be resolved\
Then the rule is treated as not yet triggered (rule skipped)\
And the `default:` seasonal target is applied

**AC6 — Hard floor guarantee**

Given the time-strategy rules are evaluated\
Then `SOC_HARD_FLOOR` (50) acts as an absolute lower bound —
`get_soc_floor()` never returns a value below 50

**AC7 — Seasonal targets fully override default soc_floor**

Given current month is November (month 11)\
When `get_soc_floor(snapshot)` evaluates the `default:` time-window rule\
Then the returned floor equals `config["seasonal_targets"][11]` (default: 100)\
And this overrides the static `soc_floor` value on the `default:` YAML entry

**AC8 — Missing seasonal_targets fallback to DEFAULTS**

Given `seasonal_targets` is absent from or incomplete in YAML config\
When `get_soc_floor(snapshot)` resolves the `default:` rule\
Then the `DEFAULTS` seasonal target for the current month is used\
And no exception is raised

**AC9 — Misconfigured seasonal_target clamped with warning**

Given `seasonal_targets[month]` yields a value below `SOC_HARD_FLOOR`\
When `get_soc_floor(snapshot)` applies the seasonal target\
Then the result is clamped to `SOC_HARD_FLOOR` (50)\
And `_LOGGER.warning("Configured seasonal_target month=%d value=%d below
SOC_HARD_FLOOR. Clamping.", month, value)` is emitted once

**AC10 — HA-free unit testing**

Given `SurplusCalculator` is imported in a plain Python unit test\
When the test runs with mock `SensorSnapshot` objects\
Then all assertions pass without any HA runtime dependency

## Tasks / Subtasks

- [x] Add `import re` at module top of `surplus_engine.py` (AC: #1–#6)
- [x] Implement `SurplusCalculator._resolve_time_token(token, snapshot) -> datetime | None` (AC: #1–#6)
  - [x] Parse `"sunrise+Xh"` / `"sunset-Xh"` pattern via regex
  - [x] Return `None` when snapshot solar field is `None`
  - [x] Parse plain `"HH:MM"` as a timezone-aware `datetime` on the same date as `snapshot.timestamp`
  - [x] Log WARNING and return `None` for unrecognised token formats
- [x] Implement `SurplusCalculator.get_soc_floor(snapshot) -> int` (AC: #1–#9)
  - [x] Iterate `time_strategy` rules top-to-bottom
  - [x] For each `before:` rule: call `_resolve_time_token`; if `None`, skip rule
  - [x] Return rule `soc_floor` (clamped to `SOC_HARD_FLOOR`) when `snapshot.timestamp < boundary`
  - [x] For `default:` rule: resolve seasonal target from config with DEFAULTS fallback
  - [x] Clamp + warn when seasonal target < `SOC_HARD_FLOOR`
  - [x] Final fallback: return `SOC_HARD_FLOOR` (defensive, should not occur with valid config)

## Dev Notes

### File to Modify

**Only `surplus_engine.py` is changed in this story.**

```
custom_components/sdm630_simulator/
├── surplus_engine.py   ← MODIFY: implement get_soc_floor + _resolve_time_token
└── (all other files unchanged)
```

### Existing Scaffold State (from Story 1.2)

`surplus_engine.py` already exists with:

```python
class SurplusCalculator:
    def __init__(self, config: dict) -> None:
        self.config = config

    def get_soc_floor(self, snapshot: SensorSnapshot) -> int:
        raise NotImplementedError   # ← replace this body

    def calculate_surplus(self, snapshot: SensorSnapshot) -> EvaluationResult:
        raise NotImplementedError   # ← leave untouched (Story 2.2)
```

`DEFAULTS` dict is defined in `__init__.py` (Story 1.1). Import it at the top
of `surplus_engine.py` behind the `if __package__:` guard so unit tests do not
need HA:

```python
if __package__:
    from . import DEFAULTS   # access to defaults dict
```

For unit tests provide the DEFAULTS dict directly in the test config.

### Token Resolution — `_resolve_time_token`

```python
import re

def _resolve_time_token(
    self, token: str, snapshot: "SensorSnapshot"
) -> "datetime | None":
    # "sunrise+2h" or "sunset-3h"
    m = re.match(r"^(sunrise|sunset)([+-])(\d+(?:\.\d+)?)h$", token)
    if m:
        base_name, sign, hours = m.group(1), m.group(2), float(m.group(3))
        base = snapshot.sunrise_time if base_name == "sunrise" else snapshot.sunset_time
        if base is None:
            return None
        delta = timedelta(hours=hours)
        return base + delta if sign == "+" else base - delta
    # Plain "HH:MM" static time
    try:
        t = datetime.strptime(token, "%H:%M").time()
        ts = snapshot.timestamp
        return ts.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    except ValueError:
        _LOGGER.warning("SDM630: Cannot parse time token '%s'", token)
        return None
```

**Timezone note:** `snapshot.timestamp`, `snapshot.sunrise_time`, and
`snapshot.sunset_time` are all timezone-aware datetimes sourced from HA
(usually UTC or local TZ). Token resolution produces timezone-aware results
because `base + timedelta` preserves timezone, and `ts.replace(...)` preserves
the tz of `snapshot.timestamp`. No explicit tz conversion needed.

### `get_soc_floor` Implementation

```python
def get_soc_floor(self, snapshot: SensorSnapshot) -> int:
    if __package__:
        from . import DEFAULTS as _DEFAULTS
    else:
        _DEFAULTS = {}  # unit tests supply full config directly

    time_strategy = self.config.get("time_strategy", _DEFAULTS.get("time_strategy", []))
    default_seasonal = _DEFAULTS.get("seasonal_targets", {})
    seasonal_targets = {**default_seasonal, **self.config.get("seasonal_targets", {})}
    month = snapshot.timestamp.month

    for rule in time_strategy:
        if "before" in rule:
            boundary = self._resolve_time_token(rule["before"], snapshot)
            if boundary is None:
                continue  # token unresolvable — skip, try next rule
            if snapshot.timestamp < boundary:
                floor = max(int(rule["soc_floor"]), SOC_HARD_FLOOR)
                return floor
        elif rule.get("default"):
            floor = int(seasonal_targets.get(month, SOC_HARD_FLOOR))
            if floor < SOC_HARD_FLOOR:
                _LOGGER.warning(
                    "Configured seasonal_target month=%d value=%d below "
                    "SOC_HARD_FLOOR. Clamping.",
                    month, floor,
                )
                floor = SOC_HARD_FLOOR
            return floor

    # Defensive fallback — should not occur with well-formed config
    return SOC_HARD_FLOOR
```

### DEFAULTS Handling Pattern

`DEFAULTS` is defined in `__init__.py` (Story 1.1). The canonical DEFAULTS
`time_strategy` and `seasonal_targets` are:

```python
# From __init__.py
DEFAULTS = {
    "time_strategy": [
        {"before": "sunrise+2h", "soc_floor": 100},   # morning protection
        {"before": "sunset-3h",  "soc_floor": 50},    # free midday window
        {"default": True,        "soc_floor": 80},    # evening — overridden by seasonal
    ],
    "seasonal_targets": {
        1: 100, 2: 90, 3: 80, 4: 70, 5: 70, 6: 70,
        7: 70, 8: 70, 9: 80, 10: 90, 11: 100, 12: 100,
    },
    # ... other defaults
}
```

**Unit test pattern** — supply config directly, no HA needed:

```python
config = {
    "time_strategy": [
        {"before": "sunrise+2h", "soc_floor": 100},
        {"before": "sunset-3h",  "soc_floor": 50},
        {"default": True,        "soc_floor": 80},
    ],
    "seasonal_targets": {
        1: 100, 2: 90, 3: 80, 4: 70, 5: 70, 6: 70,
        7: 70, 8: 70, 9: 80, 10: 90, 11: 100, 12: 100,
    },
}
calc = SurplusCalculator(config)
```

### `SensorSnapshot` Fields Used in This Story

```python
@dataclass
class SensorSnapshot:
    soc_percent: float
    power_to_grid_w: float
    pv_production_w: float
    power_to_user_w: float
    timestamp: datetime           # ← used: current evaluation time (tz-aware)
    sunset_time: datetime | None  # ← used: from sun.sun next_setting
    sunrise_time: datetime | None # ← used: from sun.sun next_rising
    forecast: ForecastData | None = None
```

`sunrise_time` and `sunset_time` come from `sun.sun` entity attributes
`next_rising` / `next_setting`. In `SurplusEngine._evaluation_tick` (Story 1.3):

```python
sun_state = hass.states.get(config["entities"].get("sun", "sun.sun"))
snapshot = SensorSnapshot(
    ...
    sunset_time=sun_state.attributes.get("next_setting"),   # datetime or None
    sunrise_time=sun_state.attributes.get("next_rising"),   # datetime or None
)
```

### Required Import Addition

Add `import re` to the top of `surplus_engine.py` (it is stdlib — safe to add
without guard). The full import block becomes:

```python
from __future__ import annotations
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
```

Note: `timedelta` is already needed for token resolution — ensure it is
imported (it was in the Story 1.2 scaffold already if used, otherwise add it).

### What NOT to Change in This Story

- `calculate_surplus()` — leave as `raise NotImplementedError` (Story 2.2)
- `HysteresisFilter` — untouched (Story 2.3)
- `ForecastConsumer` — untouched (Epic 3)
- `SurplusEngine.evaluate_cycle()` — default stub from Story 1.2 remains
- `sensor.py`, `__init__.py`, `modbus_server.py`, `registers.py`,
  `sdm630_input_registers.py`, `sdm630_holding_registers.py` — all unchanged

### Inspiration: ha-evcc Pattern (marq24/ha-evcc)

ha-evcc achieves a clean two-layer architecture:

- `pyevcc_ha/` — pure Python domain layer, no HA imports, fully testable
- `sensor.py` / `select.py` / etc. — thin HA adapters

This mirrors our architecture: `SurplusCalculator` is the pure domain layer
(stdlib-only, no HA), `SurplusEngine` in the same file is the HA-aware
orchestrator. Keep `_resolve_time_token` and `get_soc_floor` completely
HA-free — they receive `SensorSnapshot` (a plain dataclass) and operate on
plain `datetime` objects. No `hass`, no `state`, no HA helpers here.

### Logging Standards (mandatory from architecture)

- `_LOGGER` is already defined at module level: `_LOGGER = logging.getLogger(__name__)`
- Warning for misconfigured seasonal target:
  ```python
  _LOGGER.warning(
      "Configured seasonal_target month=%d value=%d below SOC_HARD_FLOOR. Clamping.",
      month, floor,
  )
  ```
- Warning for unparseable token:
  ```python
  _LOGGER.warning("SDM630: Cannot parse time token '%s'", token)
  ```
- No INFO/DEBUG logging required in this story's logic (decision-level logging
  happens in `SurplusEngine`, not `SurplusCalculator`)

### Unit Test Guidance (for Epic 5 reference)

Suggested test cases (verify correct rule selection):

| Test name | `timestamp` | `sunrise_time` | `sunset_time` | Expected floor |
|---|---|---|---|---|
| `test_morning_floor_summer` | 07:00 | 05:30 | 20:30 | 100 (before 07:30) |
| `test_morning_floor_winter` | 09:30 | 08:00 | 15:30 | 100 (before 10:00) |
| `test_midday_free_window` | 11:00 | 05:30 | 20:30 | 50 (past 07:30, before 17:30) |
| `test_evening_march` | 18:00 | 05:30 | 18:00 | 80 (seasonal March) |
| `test_evening_december` | 16:00 | 07:30 | 15:30 | 100 (seasonal December) |
| `test_sunrise_none_fallback` | 09:00 | None | 18:00 | seasonal default |
| `test_sunset_none_fallback` | 16:00 | 05:30 | None | seasonal default |
| `test_hard_floor_enforced` | any | any | any | never < 50 |

All tests use `SurplusCalculator(config)` with plain Python — no HA runtime.

### Project Structure Notes

Alignment with unified project structure:

```
custom_components/sdm630_simulator/
├── __init__.py                    (unchanged — provides DEFAULTS)
├── sensor.py                      (unchanged)
├── surplus_engine.py              ← MODIFY THIS FILE ONLY
├── modbus_server.py               (unchanged)
├── registers.py                   (unchanged)
├── sdm630_input_registers.py      (unchanged)
└── sdm630_holding_registers.py    (unchanged)
```

### References

- Story acceptance criteria: [Source: `_bmad-output/planning-artifacts/epics.md` — Story 2.1]
- Token resolution design: [Source: `_bmad-output/planning-artifacts/epics.md` — Story 2.1 implementation note]
- DEFAULTS dict: [Source: `_bmad-output/implementation-artifacts/1-1-yaml-configuration-schema-and-parsing.md` — Full DEFAULTS Dict]
- Architecture Decision 3 (SOC time-window): [Source: `_bmad-output/planning-artifacts/architecture.md` — Decision 3]
- SurplusCalculator scaffold: [Source: `_bmad-output/implementation-artifacts/1-2-surplus-engine-py-module-scaffold-with-dataclasses.md`]
- HA-free layer pattern: [Source: marq24/ha-evcc `custom_components/evcc_intg/pyevcc_ha/` — pure domain layer]
- Python 3.12, naming conventions: [Source: `_bmad-output/planning-artifacts/architecture.md` — Technology Versions, Naming Conventions]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (Dev Agent — Amelia)

### Debug Log References

- Existing test `test_surplus_calculator_get_soc_floor_raises` updated to `test_surplus_calculator_get_soc_floor_returns_int` since `get_soc_floor` no longer raises `NotImplementedError`

### Completion Notes List

- Implemented `_resolve_time_token()`: parses `sunrise+Xh`, `sunset-Xh`, plain `HH:MM` tokens; returns `None` for unresolvable/invalid tokens with WARNING log
- Implemented `get_soc_floor()`: iterates time_strategy rules top-to-bottom, resolves seasonal targets with DEFAULTS fallback, clamps to SOC_HARD_FLOOR with warning
- Added `import re` and `timedelta` to imports
- Added `from . import DEFAULTS` behind `if __package__:` guard
- 27 new unit tests covering AC1–AC10 plus `_resolve_time_token` edge cases
- All 191 tests pass (0 regressions)

### Change Log

- 2026-03-21: Story 2.1 implemented — `get_soc_floor` + `_resolve_time_token` in surplus_engine.py, tests in test_soc_floor.py
- 2026-03-21: Code review passed (approved). P-01 note: `ForecastData.solar_forecast_kwh_today` renamed to `solar_forecast_kwh_remaining` (out-of-scope but correct; Story 3.1 artefact already references new name). D-01–D-03 deferred to future stories.

### File List

- surplus_engine.py (modified — added `re`, `timedelta` imports, `DEFAULTS` import, `_resolve_time_token`, `get_soc_floor` implementation)
- tests/test_soc_floor.py (new — 27 unit tests for AC1–AC10)
- tests/test_surplus_engine.py (modified — updated skeleton test for `get_soc_floor`)
