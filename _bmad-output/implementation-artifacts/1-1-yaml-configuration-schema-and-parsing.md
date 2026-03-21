# Story 1.1: YAML Configuration Schema and Parsing

Status: ready-for-dev

## Story

As a developer (Ghost),
I want a structured YAML configuration schema under `sdm630_sim:` with entity
IDs, thresholds, and time-strategy entries,
So that all parameters are externalized and configurable without code changes.

## Acceptance Criteria

**AC1 — Basic config loading with defaults**

Given `configuration.yaml` contains a valid `sdm630_sim:` block with
`entities:`, `time_strategy:`, and global threshold keys\
When Home Assistant loads the component via `async_setup`\
Then all entity IDs and threshold values are parsed into a config dict\
And missing optional entities (`weather`, `forecast_solar`) log a WARNING and
continue in degraded mode\
And missing required entity `soc` logs an ERROR and the engine enters FAILSAFE
mode

**AC2 — time_strategy parsing**

Given a `time_strategy:` list with `before:` entries and a `default:` entry\
When the config is parsed\
Then each entry is stored as a time-window rule with a `soc_floor` value\
And dynamic offset tokens (`"sunrise+Xh"` and `"sunset-Xh"`) are stored as-is
and resolved at evaluation time (not at parse time)\
And a plain `"HH:MM"` string is accepted as a static fallback time\
And the DEFAULTS `time_strategy` uses `"sunrise+2h"` as the morning boundary

**AC3 — seasonal_targets parsing**

Given `configuration.yaml` contains a `seasonal_targets:` dict\
When the config is parsed\
Then month keys (integers 1–12) are mapped to integer SOC target percentages
(0–100) and stored in `config["seasonal_targets"]`\
And missing month keys fall back to the `DEFAULTS` seasonal target for that
month

**AC4 — DEFAULTS fallback**

Given a config key is absent from `configuration.yaml`\
When `async_setup` runs\
Then the value from `DEFAULTS` dict is used without error\
And `DEFAULTS` defines at minimum:
- `evaluation_interval = 15`
- `wallbox_threshold_kw = 4.2`
- `hold_time_minutes = 10`
- `soc_hard_floor = 50`
- `stale_threshold_seconds = 60`
- `max_discharge_kw = 10.0`
- `battery_capacity_kwh = 10.0`
- `seasonal_targets = {1:100, 2:90, 3:80, 4:70, 5:70, 6:70, 7:70, 8:70, 9:80, 10:90, 11:100, 12:100}`

## Tasks / Subtasks

- [ ] Task 1: Add imports and DEFAULTS constant to `__init__.py` (AC: #4)
  - [ ] Import `voluptuous as vol` and `homeassistant.helpers.config_validation as cv`
  - [ ] Import `logging`
  - [ ] Define `_LOGGER = logging.getLogger(__name__)`
  - [ ] Define `CONF_ENTITIES`, `CONF_TIME_STRATEGY`, `CONF_SEASONAL_TARGETS`,
        `CONF_EVALUATION_INTERVAL`, etc. string constants
  - [ ] Define `DEFAULTS` dict with all default values
- [ ] Task 2: Define voluptuous schema for entities sub-block (AC: #1)
  - [ ] Required: `soc` (`cv.entity_id`)
  - [ ] Required: `power_to_grid`, `pv_production`, `power_to_user` (`cv.entity_id`)
  - [ ] Optional: `weather`, `forecast_solar` (`vol.Optional(cv.entity_id)`)
- [ ] Task 3: Define voluptuous schema for time_strategy list (AC: #2)
  - [ ] Each entry: `vol.Optional("before"): str` (accepts `"HH:MM"`,
        `"sunset-Xh"`, `"sunrise+Xh"`) + `"soc_floor": vol.All(int, vol.Range(0,100))`
  - [ ] Or entry with `"default": True` + `"soc_floor"`
- [ ] Task 4: Define voluptuous schema for seasonal_targets (AC: #3)
  - [ ] `{vol.Coerce(int): vol.All(int, vol.Range(min=0, max=100))}`
- [ ] Task 5: Assemble `CONFIG_SCHEMA` and extend `async_setup` (AC: #1, #4)
  - [ ] Define `CONFIG_SCHEMA = vol.Schema({"sdm630_sim": COMPONENT_SCHEMA}, extra=vol.ALLOW_EXTRA)`
  - [ ] In `async_setup`: read `config.get("sdm630_sim", {})`, apply DEFAULTS,
        validate entities, store validated config in `hass.data[DOMAIN]`
  - [ ] Log WARNING for missing optional entities, ERROR + set failsafe for
        missing `soc`
  - [ ] Forward parsed config to sensor platform via `hass.helpers.discovery.load_platform`
        or `hass.async_create_task`
- [ ] Task 6: Update `manifest.json` — bump pymodbus requirement (Arch-7)
  - [ ] Change `"pymodbus>=3.9.2"` to `"pymodbus>=3.11.1"` in `requirements` list

## Dev Notes

### ⚠️ Config Key vs DOMAIN

**Critical:** The config key in `configuration.yaml` is `sdm630_sim:` (NOT
`sdm630_simulator:`). The folder/domain remain `sdm630_simulator`. Use the
literal string `"sdm630_sim"` in `CONFIG_SCHEMA`, NOT the `DOMAIN` variable.

```python
CONFIG_SCHEMA = vol.Schema(
    {"sdm630_sim": COMPONENT_SCHEMA},
    extra=vol.ALLOW_EXTRA,
)
```

In `configuration.yaml` the user writes:

```yaml
sdm630_sim:
  entities:
    soc: sensor.sph10000_storage_soc
    ...
```

### Existing Code State

- `__init__.py` is a 17-line placeholder. `async_setup` returns `True` only.
  No voluptuous, no constants, no logging — **all must be added**.
- `sensor.py` currently hard-codes entity IDs:
  `["sensor.sph10000_ac_to_grid_total", "sensor.sph10000_output_power"]`.
  **Story 1.1 must pass the parsed entity config forward** so that Story 1.3
  can replace those hard-coded IDs.
- No `const.py` exists — define all `CONF_*` constants inline in `__init__.py`
  for now (Epic 1 scope only).

### Dual-Import Guard

Preserve the existing standalone import guard in `__init__.py`:

```python
if __package__ is None:
    DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, DIR)
```

This enables `python __init__.py` to run without HA for quick smoke tests.

### time_strategy Validation Detail

`time_strategy:` entries arrive as a list of dicts. Each dict is either:

```python
# Time-bounded rule
{"before": "sunset-3h", "soc_floor": 50}

# Default rule (no "before" key)
{"default": True, "soc_floor": 80}
```

Validate each entry with a custom validator or `vol.Any`:

```python
TIME_ENTRY_SCHEMA = vol.Any(
    vol.Schema({"before": str, "soc_floor": vol.All(int, vol.Range(0, 100))}),
    vol.Schema({"default": True, "soc_floor": vol.All(int, vol.Range(0, 100))}),
)
TIME_STRATEGY_SCHEMA = [TIME_ENTRY_SCHEMA]
```

Do **not** parse/resolve `"sunrise+2h"` or `"sunset-3h"` strings — store
as-is. Resolution happens in Story 2 `SurplusCalculator` at evaluation time
using `snapshot.sunrise_time` / `snapshot.sunset_time`.

### seasonal_targets Validation

```python
SEASONAL_TARGETS_SCHEMA = vol.Schema(
    {vol.Coerce(int): vol.All(int, vol.Range(min=0, max=100))}
)
```

YAML delivers month keys as integers automatically. After validation, merge
with `DEFAULTS["seasonal_targets"]` so missing months fall back to defaults.

### Full DEFAULTS Dict

```python
DEFAULTS = {
    "evaluation_interval": 15,
    "wallbox_threshold_kw": 4.2,
    "wallbox_min_kw": 4.1,              # wallbox's own minimum to keep charging
    "hold_time_minutes": 10,
    "soc_hard_floor": 50,
    "stale_threshold_seconds": 60,
    "max_discharge_kw": 10.0,
    "battery_capacity_kwh": 10.0,
    "seasonal_targets": {
        1: 100, 2: 90, 3: 80, 4: 70, 5: 70, 6: 70,
        7: 70, 8: 70, 9: 80, 10: 90, 11: 100, 12: 100,
    },
    "time_strategy": [
        {"before": "sunrise+2h", "soc_floor": 100},  # morning protection
        {"before": "sunset-3h",  "soc_floor": 50},   # free midday window
        {"default": True,        "soc_floor": 80},   # evening/seasonal (overridden by seasonal_targets)
    ],
}
```

### Config Storage Pattern

Store the validated config in `hass.data` so Story 1.3 (`sensor.py`) can
read it:

```python
async def async_setup(hass, config):
    cfg = config.get("sdm630_sim", {})
    # ... apply defaults, validate ...
    hass.data[DOMAIN] = {"config": validated_cfg}
    # Forward to sensor platform
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform(
            hass, "sensor", DOMAIN, {}, config
        )
    )
    return True
```

`sensor.py` then reads `hass.data[DOMAIN]["config"]` in
`async_setup_platform` (implemented in Story 1.3 — for now sensor.py is
unchanged by this story).

### Entities Config Keys

Define these string constants (used by sensor.py in Story 1.3):

```python
CONF_ENTITIES       = "entities"
CONF_SOC            = "soc"              # required
CONF_POWER_TO_GRID  = "power_to_grid"   # required
CONF_PV_PRODUCTION  = "pv_production"   # required
CONF_POWER_TO_USER  = "power_to_user"   # required
CONF_WEATHER        = "weather"          # optional
CONF_FORECAST_SOLAR = "forecast_solar"  # optional
```

### Regression Protection

**Do not touch:** `sensor.py`, `modbus_server.py`, `registers.py`,
`sdm630_input_registers.py`, `sdm630_holding_registers.py`. This story is
`__init__.py`-only. The existing Modbus server and sensor continue to work
unchanged after this story.

### Reference: HA vol.Schema Pattern

Canonical HA pattern for YAML-configured integrations (older style):

```python
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({...})  # for platforms
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({...})}, extra=vol.ALLOW_EXTRA)
```

This story uses `"sdm630_sim"` as the schema key (not `DOMAIN`) due to the
naming discrepancy. See "Config Key vs DOMAIN" note above.

### Project Structure Notes

Files to create or modify in this story:

| Action | File | Note |
|--------|------|------|
| MODIFY | `__init__.py` | Add CONFIG_SCHEMA, DEFAULTS, constants, extended async_setup |
| MODIFY | `manifest.json` | Bump pymodbus from `>=3.9.2` to `>=3.11.1` (Arch-7, NFR7) |

No other files are modified. No new files are created.

### References

- Epic 1 Story 1.1 acceptance criteria — [Source: _bmad-output/planning-artifacts/epics.md#Story-1.1]
- Configuration schema example — [Source: _bmad-output/planning-artifacts/architecture.md#Configuration-Schema]
- time_strategy decision — [Source: _bmad-output/planning-artifacts/architecture.md#Decision-3]
- Existing `__init__.py` — [Source: __init__.py]
- Existing `sensor.py` (entity IDs to be replaced in 1.3) — [Source: sensor.py]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (SM story context engine)

### Debug Log References

### Completion Notes List

### File List
