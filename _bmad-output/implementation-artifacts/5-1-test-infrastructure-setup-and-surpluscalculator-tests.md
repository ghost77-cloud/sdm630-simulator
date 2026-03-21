# Story 5.1: Test Infrastructure Setup and `SurplusCalculator` Tests

Status: ready-for-dev

## Story

As a developer (Ghost),
I want a pytest test suite for `SurplusCalculator` covering all logic paths
including all SOC strategy time windows, buffer math, and forecast adjustments,
so that surplus calculation correctness is verifiable in isolation and
regressions are caught automatically when parameters change.

## Acceptance Criteria

**AC1 — conftest.py fixtures available without HA**

Given `tests/conftest.py` with shared `SensorSnapshot` and `ForecastData` fixtures\
When `pytest tests/` runs\
Then fixtures are available to all test modules without import errors\
And no `homeassistant` package is imported (verified by checking `sys.modules` in
conftest teardown)

**AC2 — All test_surplus_calculator.py scenarios pass**

Given `tests/test_surplus_calculator.py`\
When all tests run with `pytest tests/test_surplus_calculator.py -v`\
Then the following 11 scenarios are covered and all pass:

- `test_normal_sunny_day`
- `test_cloudy_buffer_fills_gap`
- `test_soc_at_hard_floor_no_buffer`
- `test_soc_below_hard_floor_failsafe`
- `test_time_window_morning_floor_100`
- `test_time_window_free_window_floor_50`
- `test_time_window_evening_floor_80`
- `test_time_window_no_sunset_uses_default`
- `test_forecast_good_floor_unchanged`
- `test_forecast_poor_floor_raised`
- `test_forecast_unavailable_conservative`

**AC3 — Exit code 0**

Given all tests pass\
When run with `python -m pytest tests/ -v`\
Then exit code = 0

## Tasks / Subtasks

- [ ] Task 1: Create `requirements-dev.txt` at repo root (AC: #1, #3)
  - [ ] Add `pytest>=8.0`
  - [ ] Add `pytest-asyncio>=0.23` (needed by story 5.2 — install now to avoid upgrades later)
- [ ] Task 2: Create `tests/` directory at repo root (AC: #1)
  - [ ] `tests/__init__.py` — empty file (makes `tests/` a proper Python package for pytest discovery)
- [ ] Task 3: Create `tests/conftest.py` (AC: #1)
  - [ ] Add `sys.path` insert so `surplus_engine` is importable without HA package (see Dev Notes)
  - [ ] Import `SensorSnapshot`, `ForecastData` from `surplus_engine` directly
  - [ ] Define `TEST_CONFIG` dict with all required keys (replaces `DEFAULTS` from `__init__.py`)
  - [ ] Define `@pytest.fixture` `base_config()` returning `TEST_CONFIG.copy()`
  - [ ] Define `@pytest.fixture` `make_snapshot()` factory returning a callable that creates
        `SensorSnapshot` with test-friendly defaults (see Dev Notes for exact defaults)
  - [ ] Define `@pytest.fixture(autouse=True, scope="session")` `assert_no_ha_import()`
        that registers a session-end finalizer checking `"homeassistant"` not in `sys.modules`
- [ ] Task 4: Create `tests/test_surplus_calculator.py` (AC: #2)
  - [ ] `test_normal_sunny_day` (AC: #2)
  - [ ] `test_cloudy_buffer_fills_gap` (AC: #2)
  - [ ] `test_soc_at_hard_floor_no_buffer` (AC: #2)
  - [ ] `test_soc_below_hard_floor_failsafe` (AC: #2)
  - [ ] `test_time_window_morning_floor_100` (AC: #2)
  - [ ] `test_time_window_free_window_floor_50` (AC: #2)
  - [ ] `test_time_window_evening_floor_80` (AC: #2)
  - [ ] `test_time_window_no_sunset_uses_default` (AC: #2)
  - [ ] `test_forecast_good_floor_unchanged` (AC: #2)
  - [ ] `test_forecast_poor_floor_raised` (AC: #2)
  - [ ] `test_forecast_unavailable_conservative` (AC: #2)
- [ ] Task 5: Verify full suite passes (AC: #3)
  - [ ] Run `python -m pytest tests/ -v` from repo root
  - [ ] Confirm exit code = 0 and all 11 tests reported as PASSED

## Dev Notes

### ⚠️ Story Dependencies — All Epic 1–4 Stories Must Be Done First

All implementation stories (1-1 through 4-4) must be **done** before this story is useful.
Specifically:

| Prerequisite | Why |
|---|---|
| Story 1.2 | `surplus_engine.py` must exist with class skeletons |
| Story 2.1 | `get_soc_floor()` and `_resolve_time_token()` must be implemented |
| Story 2.2 | `calculate_surplus()` base logic must be implemented |
| Story 3.2 | `_apply_forecast_adjustment()` must be wired into `calculate_surplus()` |
| Story 4.3 | Hard SOC floor guard (FAILSAFE on SOC < 50) in `calculate_surplus()` |

If any of the above are still raising `NotImplementedError`, the corresponding tests will fail
as expected — fix the implementation story first.

### File Locations

```
<repo-root>/
├── requirements-dev.txt              ← CREATE (pytest dev dependencies)
├── tests/
│   ├── __init__.py                   ← CREATE (empty)
│   ├── conftest.py                   ← CREATE (fixtures + sys.path + HA guard)
│   └── test_surplus_calculator.py   ← CREATE (11 test functions)
└── custom_components/
    └── sdm630_simulator/
        └── surplus_engine.py         ← READ ONLY (already implemented by Epics 1–4)
```

**Do NOT touch** any file under `custom_components/sdm630_simulator/` in this story.

### Import Strategy — HA-Free Access to `surplus_engine`

`SurplusCalculator` has a `if __package__:` guard that skips all HA-specific imports when the
module is imported outside of the HA package system. To trigger this, import `surplus_engine.py`
with `__package__ == ""` (i.e. a plain top-level import via `sys.path`):

```python
# tests/conftest.py — top of file, before any surplus_engine import
import sys
from pathlib import Path

# Insert the component directory directly so `import surplus_engine` works
# without any `homeassistant` package installed.
# Doing so sets __package__ to "" (falsy) ⟹ if __package__: guard skips HA imports.
_COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "sdm630_simulator"
if str(_COMPONENT_DIR) not in sys.path:
    sys.path.insert(0, str(_COMPONENT_DIR))

from surplus_engine import (   # noqa: E402
    SurplusCalculator,
    SensorSnapshot,
    EvaluationResult,
    ForecastData,
    SOC_HARD_FLOOR,
)
```

**Why NOT** `from custom_components.sdm630_simulator.surplus_engine import ...`:
- This sets `__package__ = "custom_components.sdm630_simulator"` (truthy)
- The `if __package__:` guard fires → tries `from . import DEFAULTS` → imports `__init__.py`
  which imports `homeassistant` → test fails with `ModuleNotFoundError`

### `TEST_CONFIG` — Replaces `DEFAULTS` from `__init__.py`

The tests never import `__init__.py`. All config values are provided directly:

```python
# tests/conftest.py

TEST_CONFIG: dict = {
    "evaluation_interval": 15,
    "wallbox_threshold_kw": 4.2,
    "wallbox_min_kw": 4.1,
    "hold_time_minutes": 10,
    "soc_hard_floor": 50,
    "stale_threshold_seconds": 60,
    "max_discharge_kw": 10.0,
    "battery_capacity_kwh": 10.0,
    "seasonal_targets": {
        1: 100, 2: 90, 3: 80, 4: 70, 5: 70, 6: 70,
        7: 70, 8: 70, 9: 80, 10: 90, 11: 100, 12: 100,
    },
    # Use static HH:MM times — avoids sunrise/sunset complexity in most tests.
    # Sunset-relative token "sunset-3h" is tested explicitly via snapshot.sunset_time.
    "time_strategy": [
        {"before": "11:00", "soc_floor": 100},
        {"before": "sunset-3h", "soc_floor": 50},
        {"default": True, "soc_floor": 80},
    ],
}
```

### `make_snapshot` Fixture — Factory Pattern

```python
# tests/conftest.py

import pytest
from datetime import datetime, timezone

@pytest.fixture
def make_snapshot():
    """Factory fixture: call make_snapshot(**overrides) to get a SensorSnapshot."""
    def _factory(
        soc_percent: float = 80.0,
        power_to_grid_w: float = 0.0,
        pv_production_w: float = 5000.0,
        power_to_user_w: float = 1200.0,
        timestamp: datetime | None = None,
        sunset_time: datetime | None = None,
        sunrise_time: datetime | None = None,
        forecast: ForecastData | None = None,
    ) -> SensorSnapshot:
        if timestamp is None:
            # Default: 12:30 on 2026-03-15 (March → seasonal_target=80, midday window)
            timestamp = datetime(2026, 3, 15, 12, 30, tzinfo=timezone.utc)
        if sunset_time is None:
            # Default: 18:00 same day → sunset-3h = 15:00
            sunset_time = datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc)
        if sunrise_time is None:
            # Default: 06:00 same day
            sunrise_time = datetime(2026, 3, 15, 6, 0, tzinfo=timezone.utc)
        return SensorSnapshot(
            soc_percent=soc_percent,
            power_to_grid_w=power_to_grid_w,
            pv_production_w=pv_production_w,
            power_to_user_w=power_to_user_w,
            timestamp=timestamp,
            sunset_time=sunset_time,
            sunrise_time=sunrise_time,
            forecast=forecast,
        )
    return _factory
```

### HA Import Guard in `conftest.py`

```python
# tests/conftest.py

@pytest.fixture(autouse=True, scope="session")
def assert_no_ha_import(request):
    """Fail the session if homeassistant was accidentally imported."""
    def _check():
        ha_modules = [k for k in sys.modules if k == "homeassistant" or k.startswith("homeassistant.")]
        assert not ha_modules, (
            f"homeassistant was imported during tests — purity violated!\n"
            f"Offending modules: {ha_modules}"
        )
    request.addfinalizer(_check)
```

### Test Implementations — Exact Setups

#### `test_normal_sunny_day`

```
PV=8000W, power_to_user=1200W, SOC=100%
real_surplus = (8000 - 1200) / 1000 = 6.8 kW
soc_headroom = 100 - 50 = 50% (floor=50 in midday window)
buffer_used = min(10.0, max(0, 4.2 - 6.8)) = min(10.0, 0) = 0.0
augmented = 6.8 ≥ 4.2 → ACTIVE
```

Assertions:
- `result.real_surplus_kw == pytest.approx(6.8)`
- `result.buffer_used_kw == pytest.approx(0.0)`
- `result.reported_kw == pytest.approx(6.8)`
- `result.charging_state == "ACTIVE"`

#### `test_cloudy_buffer_fills_gap`

```
PV=3500W, power_to_user=1200W, SOC=95%, floor=50 (midday, 12:30)
real_surplus = (3500 - 1200) / 1000 = 2.3 kW
soc_headroom = 95 - 50 = 45%
buffer_energy_kwh = 45 * 10.0 / 100 = 4.5 kWh
buffer_kw_max = min(10.0, 4.5 / (10/60)) = min(10.0, 27.0) = 10.0
buffer_used = min(10.0, max(0, 4.2 - 2.3)) = min(10.0, 1.9) = 1.9
augmented = 2.3 + 1.9 = 4.2 ≥ 4.2 → ACTIVE
```

Assertions:
- `result.real_surplus_kw == pytest.approx(2.3)`
- `result.buffer_used_kw == pytest.approx(1.9)`
- `result.reported_kw == pytest.approx(4.2)`
- `result.charging_state == "ACTIVE"`

#### `test_soc_at_hard_floor_no_buffer`

```
PV=2000W, power_to_user=1000W, SOC=50% (exactly at hard floor)
real_surplus = (2000 - 1000) / 1000 = 1.0 kW
soc_headroom = max(0.0, 50 - 50) = 0.0
buffer_used = 0.0
augmented = 1.0 < 4.2 → INACTIVE
```

Assertions:
- `result.buffer_used_kw == pytest.approx(0.0)`
- `result.reported_kw == pytest.approx(0.0)`
- `result.charging_state == "INACTIVE"`

#### `test_soc_below_hard_floor_failsafe`

```
SOC=48% < SOC_HARD_FLOOR (50)
→ calculate_surplus() first check fires FAILSAFE guard (Story 4.3 AC3)
→ returns immediately without any further computation
```

Assertions:
- `result.reported_kw == pytest.approx(0.0)`
- `result.charging_state == "FAILSAFE"`
- `"hard floor" in result.reason.lower()` (reason contains "SOC below hard floor")
- `result.buffer_used_kw == pytest.approx(0.0)`

#### `test_time_window_morning_floor_100`

Tests `get_soc_floor()` directly. No need to call `calculate_surplus`.

```
timestamp = 09:00 (before 11:00 → first rule matches)
Expected: floor = 100
```

```python
snapshot = make_snapshot(timestamp=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc))
calc = SurplusCalculator(config)
assert calc.get_soc_floor(snapshot) == 100
```

#### `test_time_window_free_window_floor_50`

```
timestamp = 12:30 (after 11:00, before 15:00 = sunset-3h where sunset=18:00)
Expected: floor = 50
```

```python
snapshot = make_snapshot(
    timestamp=datetime(2026, 3, 15, 12, 30, tzinfo=timezone.utc),
    sunset_time=datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc),
)
assert calc.get_soc_floor(snapshot) == 50
```

#### `test_time_window_evening_floor_80`

```
timestamp = 16:00 (after 15:00 = sunset-3h where sunset=18:00)
default rule fires → seasonal_targets[3] = 80
Expected: floor = 80
```

```python
snapshot = make_snapshot(
    timestamp=datetime(2026, 3, 15, 16, 0, tzinfo=timezone.utc),
    sunset_time=datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc),
)
assert calc.get_soc_floor(snapshot) == 80
```

#### `test_time_window_no_sunset_uses_default`

```
sunset_time = None → "sunset-3h" token cannot be resolved → rule skipped
Falls through to default → seasonal_targets[3] = 80
timestamp = 13:00 (past 11:00, so morning rule also doesn't match)
Expected: floor = 80
```

```python
snapshot = make_snapshot(
    timestamp=datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc),
    sunset_time=None,
)
assert calc.get_soc_floor(snapshot) == 80
```

#### `test_forecast_good_floor_unchanged`

```
cloud_coverage_avg = 10 (< 20 threshold), hour = 10 (< 15)
_apply_forecast_adjustment returns (base_floor, "forecast_good")
floor unchanged from time-window result (= 100 at 09:00)
```

Use timestamp=09:00 so morning rule gives floor=100. Pass `ForecastData(forecast_available=True, cloud_coverage_avg=10.0)`.

Assertions on `calculate_surplus` result:
- `result.forecast_available == True`
- `"forecast_good" in result.reason`
- `result.soc_floor_active == 100`

#### `test_forecast_poor_floor_raised`

```
cloud_coverage_avg = 85 (> 70 threshold), hour = 14 (≥ 13)
month = 3 (March), seasonal_targets[3] = 80
base_floor from time-window at 14:00 mid-day = 50
adjusted_floor = max(50, 80) = 80
```

Use timestamp=14:00 (past 11:00, before sunset-3h=15:00 so midday window floor=50),
`ForecastData(forecast_available=True, cloud_coverage_avg=85.0)`.

Assertions:
- `result.forecast_available == True`
- `"forecast_poor" in result.reason`
- `result.soc_floor_active == 80`  (raised from 50 to 80)

#### `test_forecast_unavailable_conservative`

```
ForecastData(forecast_available=False) → _apply_forecast_adjustment returns (base_floor, "forecast_unavailable")
Floor unchanged; no exception raised
```

Assertions:
- `result.forecast_available == False`
- `result.charging_state in ("ACTIVE", "INACTIVE")` (no crash)
- floor not raised above base time-window value

### `marq24/ha-evcc` Architecture Inspiration

The ha-evcc project keeps all interaction with the EVCC API inside `pyevcc_ha/EvccApiBridge` and
passes plain Python objects to the HA sensor layer — the HA layer never calls the network directly.
This mirrors our architecture exactly: `ForecastConsumer` (HA-aware) fetches data and injects it
into `SensorSnapshot.forecast` before handing the snapshot to `SurplusCalculator` (pure Python).

The lesson for tests: **construct `SensorSnapshot` objects directly** — no mocking of HA state
objects, no `MagicMock`, no `pytest-homeassistant-custom-component`. Tests read as plain Python:

```python
# Clean, readable, HA-free
snap = SensorSnapshot(soc_percent=95, pv_production_w=3500, ...)
result = SurplusCalculator(config).calculate_surplus(snap)
assert result.charging_state == "ACTIVE"
```

This is the key advantage of the HA-free `SurplusCalculator` design — tests are fast, portable,
and require only `pytest`.

### Running the Tests

```bash
# Install dev deps (one-time)
pip install -r requirements-dev.txt

# Run all tests
python -m pytest tests/ -v

# Run just surplus calculator tests
python -m pytest tests/test_surplus_calculator.py -v

# Run with short output
python -m pytest tests/ -q
```

Expected output when all stories are implemented:
```
tests/test_surplus_calculator.py::test_normal_sunny_day PASSED
tests/test_surplus_calculator.py::test_cloudy_buffer_fills_gap PASSED
tests/test_surplus_calculator.py::test_soc_at_hard_floor_no_buffer PASSED
tests/test_surplus_calculator.py::test_soc_below_hard_floor_failsafe PASSED
tests/test_surplus_calculator.py::test_time_window_morning_floor_100 PASSED
tests/test_surplus_calculator.py::test_time_window_free_window_floor_50 PASSED
tests/test_surplus_calculator.py::test_time_window_evening_floor_80 PASSED
tests/test_surplus_calculator.py::test_time_window_no_sunset_uses_default PASSED
tests/test_surplus_calculator.py::test_forecast_good_floor_unchanged PASSED
tests/test_surplus_calculator.py::test_forecast_poor_floor_raised PASSED
tests/test_surplus_calculator.py::test_forecast_unavailable_conservative PASSED
11 passed in 0.XXs
```

### Numeric Precision

Use `pytest.approx` for all float comparisons:

```python
import pytest
assert result.real_surplus_kw == pytest.approx(2.3)
assert result.buffer_used_kw == pytest.approx(1.9)
assert result.reported_kw == pytest.approx(4.2)
```

Default `pytest.approx` tolerance is `1e-6` relative — adequate for these calculations.

### `pytest.ini` / `pyproject.toml` — Not Required

No `pytest.ini` needed. The `sys.path.insert` in `conftest.py` handles discovery.
If py-test auto-discovery fails (e.g. can't find `tests/`), add a minimal `pytest.ini`:

```ini
[pytest]
testpaths = tests
```

### Regression Protection

This story creates new files only:
- `requirements-dev.txt` (new)
- `tests/__init__.py` (new)
- `tests/conftest.py` (new)
- `tests/test_surplus_calculator.py` (new)

**Do NOT modify any existing file** — no `surplus_engine.py`, no `sensor.py`, no `__init__.py`.

## Dev Agent Record

### Agent Model Used

_to be filled by dev agent_

### Debug Log References

### Completion Notes List

### File List

- `requirements-dev.txt` (create)
- `tests/__init__.py` (create)
- `tests/conftest.py` (create)
- `tests/test_surplus_calculator.py` (create)
