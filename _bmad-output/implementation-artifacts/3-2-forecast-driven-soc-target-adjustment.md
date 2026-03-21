# Story 3.2: Forecast-Driven SOC Target Adjustment

Status: ready-for-dev

## Story

As the surplus engine,
I want `SurplusCalculator.calculate_surplus(snapshot)` to raise the effective
SOC floor when `snapshot.forecast` indicates poor upcoming solar production,
so that the household battery is better protected on days when PV output will
be insufficient to recharge it.

## Acceptance Criteria

**AC1 — Sunny forecast: floor unchanged**

Given `snapshot.forecast.cloud_coverage_avg < 20` (sunny) and
`snapshot.timestamp.hour < 15`\
When `calculate_surplus(snapshot)` is called\
Then the effective SOC floor equals the value returned by `get_soc_floor(snapshot)` unchanged\
And `result.reason` contains `"forecast_good"`\
And `result.forecast_available` = `True`

**AC2 — Overcast forecast: floor raised to seasonal target**

Given `snapshot.forecast.cloud_coverage_avg > 70` (overcast) and
`snapshot.timestamp.hour >= 13`\
When `calculate_surplus(snapshot)` is called\
Then the effective SOC floor is `max(get_soc_floor(snapshot), seasonal_targets[month])`\
And for March (month 3, seasonal_target=80), the effective floor is at minimum 80\
And for December (month 12, seasonal_target=100), the effective floor is at minimum 100\
And `result.reason` contains `"forecast_poor"`\
And `result.forecast_available` = `True`

**AC8 — Low solar remaining forecast: floor raised independent of cloud coverage**

Given `snapshot.forecast.solar_forecast_kwh_remaining` is not `None` and
its value is below the configurable threshold `solar_remaining_threshold_kwh`
(default: 2.0 kWh) and `snapshot.timestamp.hour >= 12`\
When `calculate_surplus(snapshot)` is called\
Then the effective SOC floor is raised to
`max(get_soc_floor(snapshot), seasonal_targets[month])` — same as
the overcast path in AC2\
And `result.reason` contains `"forecast_solar_low"`\
And this rule fires even when `cloud_coverage_avg` is in the neutral range
(20–70) — `solar_forecast_kwh_remaining` is the more precise signal because
it comes directly from the `forecast_solar` integration (based on panel
orientation, historical irradiation data, and weather) rather than generic
cloud coverage from a weather service

**Design rationale — solar remaining as primary signal:**
The `forecast_solar` integration delivers panel-specific production estimates.
A low `solar_forecast_kwh_remaining` value (e.g., 1.2 kWh at 14:00) is far
more actionable than generic cloud coverage because it accounts for the
panel's azimuth, tilt, shading, and local irradiation history. Cloud coverage
remains the fallback when `forecast_solar` is not configured.

**AC3 — Forecast unavailable: no change**

Given `snapshot.forecast` is `None` or
`snapshot.forecast.forecast_available == False`\
When `calculate_surplus(snapshot)` is called\
Then the time-window SOC floor from `get_soc_floor(snapshot)` is used unchanged\
And `result.forecast_available` = `False`\
And no WARNING is logged (expected degraded mode)

**AC4 — HA-free purity preserved: ForecastData via SensorSnapshot only**

Given `ForecastConsumer.get_forecast(hass)` is called in `SurplusEngine._evaluation_tick`\
When the result is stored in `snapshot.forecast` before passing to `calculate_surplus`\
Then `SurplusCalculator` accesses only `ForecastData` fields — no `hass` object\
And `SurplusCalculator` has zero HA-specific imports (stdlib + dataclasses only)

**AC5 — HA-free unit testing**

Given `SurplusCalculator` instantiated with a plain config dict\
And a `SensorSnapshot` with a manually constructed `ForecastData` object\
When unit tests for all AC1–AC3 boundary combinations run\
Then all assertions pass without any HA runtime dependency

**AC6 — Boundary: exactly at thresholds — neutral path**

Given `snapshot.forecast.cloud_coverage_avg == 20` (not strictly < 20) and
`snapshot.timestamp.hour < 15`\
When `calculate_surplus(snapshot)` is called\
Then the sunny fast-path is NOT taken (threshold is strict `< 20`)\
And the forecast adjustment defaults to the neutral path (floor unchanged)

Given `snapshot.forecast.cloud_coverage_avg == 70` (not strictly > 70) and
`snapshot.timestamp.hour >= 13`\
When `calculate_surplus(snapshot)` is called\
Then the overcast fast-path is NOT taken (threshold is strict `> 70`)\
And the forecast adjustment defaults to the neutral path (floor unchanged)

**AC7 — Hard floor guarantee preserved**

Given any forecast condition that raises the seasonal floor\
When `_apply_forecast_adjustment` computes the adjusted floor\
Then the result is never below `SOC_HARD_FLOOR` (50)

## Tasks / Subtasks

- [ ] Task 1: Implement `SurplusCalculator._apply_forecast_adjustment(snapshot, base_floor)` (AC: #1–#3, #6–#8)
  - [ ] Return `(base_floor, "forecast_unavailable")` if `snapshot.forecast is None` or
    `not snapshot.forecast.forecast_available`
  - [ ] Return `(base_floor, "forecast_good")` if `cloud_coverage_avg < 20` and `hour < 15`
    and solar remaining is not critically low
  - [ ] If `solar_forecast_kwh_remaining is not None` and
    `solar_forecast_kwh_remaining < solar_remaining_threshold_kwh` and `hour >= 12`:
    - [ ] Resolve seasonal target (same as cloud path)
    - [ ] Return `(max(base_floor, seasonal_floor), "forecast_solar_low")`
  - [ ] If `cloud_coverage_avg > 70` and `hour >= 13`:
    - [ ] Resolve `seasonal_targets` from config (same pattern as `get_soc_floor` — merge
      DEFAULTS with config, month key lookup)
    - [ ] `seasonal_floor = max(int(seasonal_targets.get(month, SOC_HARD_FLOOR)), SOC_HARD_FLOOR)`
    - [ ] Return `(max(base_floor, seasonal_floor), "forecast_poor")`
  - [ ] Default/neutral path: return `(base_floor, "forecast_neutral")`

- [ ] Task 2: Add `solar_remaining_threshold_kwh` config key (AC: #8)
  - [ ] Add `CONF_SOLAR_REMAINING_THRESHOLD_KWH = "solar_remaining_threshold_kwh"` to
    `__init__.py` config key constants
  - [ ] Add `"solar_remaining_threshold_kwh": 2.0` to `DEFAULTS` dict (already done)
  - [ ] Add `vol.Optional(CONF_SOLAR_REMAINING_THRESHOLD_KWH): vol.Coerce(float)` to
    `COMPONENT_SCHEMA`
  - [ ] Add key to `_SCALAR_KEYS` set in `async_setup`

- [ ] Task 3: Integrate forecast adjustment into `calculate_surplus` (AC: #1–#3, #6)
  - [ ] Replace `soc_floor = self.get_soc_floor(snapshot)` with:
    - [ ] `base_floor = self.get_soc_floor(snapshot)`
    - [ ] `soc_floor, forecast_tag = self._apply_forecast_adjustment(snapshot, base_floor)`
  - [ ] Use `soc_floor` (adjusted) for all buffer / headroom calculations (replacing `base_floor`)
  - [ ] Update `result.soc_floor_active = soc_floor` (already correctly set in Story 2.2)
  - [ ] Compose `reason` with forecast tag appended using `|` separator:
    `f"wallbox_included_in_load|{forecast_tag}"` or `f"surplus_below_threshold|{forecast_tag}"`
  - [ ] Set `result.forecast_available = snapshot.forecast.forecast_available if snapshot.forecast else False`

- [ ] Task 3: Wire `ForecastConsumer.get_forecast(hass)` into `SurplusEngine._evaluation_tick` (AC: #4)
  - [ ] In `_evaluation_tick`, add `forecast_data = await self._forecast_consumer.get_forecast(hass)` before snapshot assembly
  - [ ] Pass `forecast=forecast_data` when constructing `SensorSnapshot`
  - [ ] Ensure `self._forecast_consumer` is instantiated in `SurplusEngine.__init__` with access to `self._config`
  - [ ] Guard: if no weather or forecast_solar entity configured, `get_forecast` already returns
    `ForecastData(forecast_available=False)` silently (Story 3.1 handles this — no extra guard needed here)

- [ ] Task 4: Unit tests for forecast adjustment (AC: #5)
  - [ ] Test AC1: `cloud_coverage_avg=10`, `hour=10` → floor unchanged, reason contains `"forecast_good"`
  - [ ] Test AC2 (March): `cloud_coverage_avg=80`, `hour=14`, `month=3`, `seasonal_target=80` → floor ≥ 80,
    reason contains `"forecast_poor"`
  - [ ] Test AC2 (December): `cloud_coverage_avg=90`, `hour=15`, `month=12`, `seasonal_target=100` → floor = 100
  - [ ] Test AC3: `ForecastData(forecast_available=False)` → floor unchanged, `result.forecast_available=False`
  - [ ] Test AC3 (None): `snapshot.forecast=None` → floor unchanged
  - [ ] Test AC6: `cloud_coverage_avg=20`, `hour=10` → neutral path, floor unchanged
  - [ ] Test AC6: `cloud_coverage_avg=70`, `hour=13` → neutral path, floor unchanged
  - [ ] Test AC7: seasonal_target=30 (misconfigured, below SOC_HARD_FLOOR) → clamped to 50
  - [ ] Test AC8: `solar_forecast_kwh_remaining=1.5`, `hour=14`, threshold=2.0 →
    floor raised, reason contains `"forecast_solar_low"`
  - [ ] Test AC8 (above threshold): `solar_forecast_kwh_remaining=5.0`, `hour=14` →
    neutral path, floor unchanged
  - [ ] Test AC8 (None): `solar_forecast_kwh_remaining=None`, `cloud_coverage_avg=50` →
    neutral path (solar signal absent, cloud neutral)
  - [ ] Test AC8 (before noon): `solar_forecast_kwh_remaining=0.5`, `hour=10` →
    not triggered (too early for afternoon protection)

## Dev Notes

### ⚠️ Story Dependencies — All Three Must Be Done First

| Prerequisite Story | Why Required |
|---|---|
| **Story 3.1** (Forecast Data Fetching) | `ForecastConsumer.get_forecast(hass)` is implemented there. Until 3.1 is done, `get_forecast` raises `NotImplementedError`. `ForecastData` dataclass stub exists from Story 1.2. |
| **Story 2.2** (Surplus Calculation) | `calculate_surplus()` base implementation. Story 3.2 modifies its internals. |
| **Story 2.1** (SOC Floor) | `get_soc_floor(snapshot)` is called inside `calculate_surplus`. |

### Files to Modify

**Only `surplus_engine.py` is changed** (plus adding tests):

```
custom_components/sdm630_simulator/
├── surplus_engine.py          ← MODIFY: add _apply_forecast_adjustment(),
│                                         wire into calculate_surplus(),
│                                         wire get_forecast() into _evaluation_tick()
└── tests/
    └── test_surplus_calculator.py  ← ADD: forecast adjustment tests
```

Files that remain unchanged: `__init__.py`, `sensor.py`, `modbus_server.py`,
`registers.py`, `sdm630_input_registers.py`, `sdm630_holding_registers.py`.

### Existing Code State After Stories 2.2 and 3.1

After Story 2.2, `calculate_surplus` implementation (simplified):

```python
def calculate_surplus(self, snapshot: SensorSnapshot) -> EvaluationResult:
    soc_floor = self.get_soc_floor(snapshot)          # ← becomes base_floor in 3.2

    real_surplus_kw = (snapshot.pv_production_w - snapshot.power_to_user_w) / 1000.0
    soc_headroom = max(0.0, snapshot.soc_percent - soc_floor)
    buffer_energy_kwh = soc_headroom * self.config.get("battery_capacity_kwh", 10.0) / 100.0
    hold_time = self.config.get("hold_time_minutes", 10)
    buffer_kw_max = min(
        self.config.get("max_discharge_kw", 10.0),
        buffer_energy_kwh / (hold_time / 60.0),
    )
    wallbox_threshold = self.config.get("wallbox_threshold_kw", 4.2)
    buffer_used_kw = min(buffer_kw_max, max(0.0, wallbox_threshold - real_surplus_kw))
    augmented_kw = real_surplus_kw + buffer_used_kw

    if augmented_kw >= wallbox_threshold:
        charging_state = "ACTIVE"
        reported_kw = augmented_kw
        reason = "wallbox_included_in_load"
    else:
        charging_state = "INACTIVE"
        reported_kw = 0.0
        buffer_used_kw = 0.0
        reason = "surplus_below_threshold"

    return EvaluationResult(
        reported_kw=reported_kw,
        real_surplus_kw=real_surplus_kw,
        buffer_used_kw=buffer_used_kw,
        soc_percent=snapshot.soc_percent,
        soc_floor_active=soc_floor,          # ← will reflect adjusted floor in 3.2
        charging_state=charging_state,
        reason=reason,                       # ← will include "|forecast_tag" in 3.2
        forecast_available=False,            # ← will be real value in 3.2
    )
```

After Story 3.1, `ForecastConsumer.get_forecast(hass)` is fully implemented and
`SensorSnapshot.forecast` field exists (stub dataclass from Story 1.2).

### `_apply_forecast_adjustment` Implementation

```python
def _apply_forecast_adjustment(
    self, snapshot: "SensorSnapshot", base_floor: int
) -> "tuple[int, str]":
    """Return (adjusted_soc_floor, forecast_reason_tag).

    Raises the SOC floor to the seasonal target when forecast signals
    poor PV production for the remainder of the day.
    Uses solar_forecast_kwh_remaining (from forecast_solar) as the
    primary signal; falls back to cloud_coverage_avg (from weather).
    Never returns a floor below SOC_HARD_FLOOR.
    """
    if snapshot.forecast is None or not snapshot.forecast.forecast_available:
        return base_floor, "forecast_unavailable"

    cloud_avg = snapshot.forecast.cloud_coverage_avg
    solar_remaining = snapshot.forecast.solar_forecast_kwh_remaining
    hour = snapshot.timestamp.hour
    threshold_kwh = self.config.get("solar_remaining_threshold_kwh", 2.0)

    # Sunny fast-path: only if solar remaining is also healthy (or unknown)
    if cloud_avg < 20 and hour < 15:
        if solar_remaining is None or solar_remaining >= threshold_kwh:
            return base_floor, "forecast_good"

    # Primary signal: solar forecast remaining is critically low
    if (solar_remaining is not None
            and solar_remaining < threshold_kwh
            and hour >= 12):
        seasonal_floor = self._resolve_seasonal_floor(snapshot)
        return max(base_floor, seasonal_floor), "forecast_solar_low"

    # Fallback signal: high cloud coverage from weather service
    if cloud_avg > 70 and hour >= 13:
        seasonal_floor = self._resolve_seasonal_floor(snapshot)
        return max(base_floor, seasonal_floor), "forecast_poor"

    return base_floor, "forecast_neutral"

def _resolve_seasonal_floor(self, snapshot: "SensorSnapshot") -> int:
    """Resolve the seasonal SOC target for the current month.

    Extracted as a helper because both the solar-remaining and
    cloud-coverage paths need the same seasonal-target resolution.
    """
    if __package__:
        from . import DEFAULTS as _DEFAULTS
    else:
        _DEFAULTS = {}
    default_seasonal = _DEFAULTS.get("seasonal_targets", {})
    seasonal_targets = {
        **default_seasonal,
        **self.config.get("seasonal_targets", {}),
    }
    month = snapshot.timestamp.month
    seasonal_floor = int(seasonal_targets.get(month, SOC_HARD_FLOOR))
    return max(seasonal_floor, SOC_HARD_FLOOR)
```

### Updated `calculate_surplus` — Minimal Diff

Replace the first two lines:

```python
# BEFORE (Story 2.2):
soc_floor = self.get_soc_floor(snapshot)

# AFTER (Story 3.2):
base_floor = self.get_soc_floor(snapshot)
soc_floor, forecast_tag = self._apply_forecast_adjustment(snapshot, base_floor)
```

And update the reason composition and the `forecast_available` field in the
returned `EvaluationResult`:

```python
# Reason: append forecast tag with pipe separator
if augmented_kw >= wallbox_threshold:
    reason = f"wallbox_included_in_load|{forecast_tag}"
else:
    reason = f"surplus_below_threshold|{forecast_tag}"

return EvaluationResult(
    ...
    soc_floor_active=soc_floor,   # now the adjusted floor
    reason=reason,
    forecast_available=snapshot.forecast.forecast_available if snapshot.forecast else False,
)
```

All other lines in `calculate_surplus` remain identical — `soc_floor` is now
the adjusted value, so headroom / buffer math automatically reflects the
raised floor.

### `SurplusEngine._evaluation_tick` Wiring

In `_evaluation_tick` (already modified in Story 1.3 and extended in prior
stories), add the forecast fetch **before** snapshot construction:

```python
async def _evaluation_tick(self, now) -> None:
    # ... (existing cache reads, sun.sun solar times) ...

    # Story 3.2: fetch forecast data before assembling snapshot
    forecast_data = await self._forecast_consumer.get_forecast(self._hass)

    snapshot = SensorSnapshot(
        soc_percent=...,
        power_to_grid_w=...,
        pv_production_w=...,
        power_to_user_w=...,
        timestamp=dt_util.utcnow(),
        sunset_time=...,
        sunrise_time=...,
        forecast=forecast_data,   # ← new in Story 3.2
    )
    result = await self._engine.evaluate_cycle(snapshot)  # or sync call
    ...
```

`self._forecast_consumer` must be instantiated in `SurplusEngine.__init__`:

```python
class SurplusEngine:
    def __init__(self, config: dict, hass) -> None:
        self._config = config
        self._hass = hass
        self._calculator = SurplusCalculator(config)
        self._forecast_consumer = ForecastConsumer(config)   # ← ensure this exists
        self._hysteresis = HysteresisFilter(config)
```

Verify `SurplusEngine.__init__` signature from Story 1.3. It may already have
`hass` injected. If not, adjust accordingly — `ForecastConsumer.get_forecast`
needs `hass` passed at call time (not stored), so `SurplusEngine` passes
`self._hass` each time.

### `ForecastData` Dataclass (from Story 1.2 — do not redefine)

```python
@dataclass
class ForecastData:
    forecast_available: bool = False
    cloud_coverage_avg: float = 50.0     # 50 = neutral: neither < 20 nor > 70
    solar_forecast_kwh_remaining: float | None = None
```

**Why `cloud_coverage_avg=50.0` as default?** Deliberately placed in the
neutral zone (20–70) — neither triggers "sunny" path nor "poor" path. When
forecast is unavailable, `forecast_available=False` is the primary gate that
short-circuits before any cloud_avg check.

### Forecast Threshold Constants

The thresholds (`< 20`, `> 70`, `hour >= 13`, `hour < 15`) are **hardcoded
implementation constants** matching the specification in the FR coverage map.
They are acceptable as in-code constants for Epic 3 scope. A later epic could
promote them to YAML config keys if needed. **Do not invent config keys for
these values in this story.**

### Seasonal Targets Resolution — Dual-Import Pattern

`_apply_forecast_adjustment` uses the identical DEFAULTS dual-import pattern
as `get_soc_floor` in Story 2.1. If refactoring opportunity arises (both
methods resolve seasonal_targets), a private helper `_resolved_seasonal_targets`
could be extracted in a housekeeping story — but this is **out of scope for 3.2**.

### Naming Conventions (from AGENTS.md + architecture.md)

- Method name: `_apply_forecast_adjustment` — `snake_case`, private (`_` prefix)
- Return type annotation: `tuple[int, str]` in Python 3.12 (no `Tuple` import)
- Keep `_LOGGER = logging.getLogger(__name__)` — no new logger needed
- Zero HA-specific imports added to `SurplusCalculator`

### Inspiration from marq24/ha-evcc

The `evcc_intg` integration (`marq24/ha-evcc/custom_components/evcc_intg/sensor.py`)
demonstrates reading solar forecast timeseries from HA entity attributes
(`Tag.FORECAST_SOLAR`). The `ForecastConsumer` (Story 3.1) follows the same
pattern: reads state and attributes from the `forecast_solar` entity via
`hass.states.get()`, and uses `hass.services.async_call("weather", "get_forecasts",
..., blocking=True, return_response=True)` for weather — the same HA service
call pattern used throughout `evcc_intg`. Story 3.2 only consumes the result of
Story 3.1's fetch; no direct HA calls are needed in `SurplusCalculator`.

### Example Unit Test Sketch (for `tests/test_surplus_calculator.py`)

```python
from datetime import datetime, timezone
from surplus_engine import SurplusCalculator, SensorSnapshot, ForecastData

MARCH_CONFIG = {
    "wallbox_threshold_kw": 4.2,
    "hold_time_minutes": 10,
    "max_discharge_kw": 10.0,
    "battery_capacity_kwh": 10.0,
    "seasonal_targets": {3: 80, 12: 100},
    "time_strategy": [
        {"before": "sunrise+2h", "soc_floor": 100},
        {"before": "sunset-3h", "soc_floor": 50},
        {"default": True, "soc_floor": 80},
    ],
}

def make_snapshot(cloud_avg, hour, month=3, soc=80.0,
                  forecast_available=True, pv=5000, load=1200):
    ts = datetime(2026, month, 21, hour, 0, 0, tzinfo=timezone.utc)
    forecast = ForecastData(
        forecast_available=forecast_available,
        cloud_coverage_avg=cloud_avg,
    )
    # sunset well after 18:00 so midday window is active at hour<15
    sunset = datetime(2026, month, 21, 20, 0, 0, tzinfo=timezone.utc)
    sunrise = datetime(2026, month, 21, 6, 0, 0, tzinfo=timezone.utc)
    return SensorSnapshot(
        soc_percent=soc,
        power_to_grid_w=0.0,
        pv_production_w=float(pv),
        power_to_user_w=float(load),
        timestamp=ts,
        sunset_time=sunset,
        sunrise_time=sunrise,
        forecast=forecast,
    )

def test_forecast_good_floor_unchanged():
    calc = SurplusCalculator(MARCH_CONFIG)
    snap = make_snapshot(cloud_avg=10, hour=10)
    result = calc.calculate_surplus(snap)
    assert "forecast_good" in result.reason
    assert result.forecast_available is True
    # midday window floor is 50 — forecast does not raise it
    assert result.soc_floor_active == 50

def test_forecast_poor_raises_floor_march():
    calc = SurplusCalculator(MARCH_CONFIG)
    snap = make_snapshot(cloud_avg=80, hour=14, soc=90.0)
    result = calc.calculate_surplus(snap)
    assert "forecast_poor" in result.reason
    assert result.soc_floor_active >= 80  # seasonal March target=80

def test_forecast_unavailable_no_change():
    calc = SurplusCalculator(MARCH_CONFIG)
    snap = make_snapshot(cloud_avg=80, hour=14, forecast_available=False)
    result = calc.calculate_surplus(snap)
    assert result.forecast_available is False
    # floor is midday 50 — no adjustment
    assert result.soc_floor_active == 50

def test_boundary_cloud_avg_exactly_20():
    calc = SurplusCalculator(MARCH_CONFIG)
    snap = make_snapshot(cloud_avg=20, hour=10)
    _, tag = calc._apply_forecast_adjustment(snap, 50)
    assert tag == "forecast_neutral"  # not "forecast_good"

def test_boundary_cloud_avg_exactly_70():
    calc = SurplusCalculator(MARCH_CONFIG)
    snap = make_snapshot(cloud_avg=70, hour=13)
    _, tag = calc._apply_forecast_adjustment(snap, 50)
    assert tag == "forecast_neutral"  # not "forecast_poor"
```

## Dev Agent Record

### Agent Model Used

<!-- To be filled by dev agent on implementation -->

### Debug Log References

### Completion Notes List

### File List
