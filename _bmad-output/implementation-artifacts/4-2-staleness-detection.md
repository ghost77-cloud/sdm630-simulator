# Story 4.2: Staleness Detection

Status: ready-for-dev

## Story

As the surplus engine,
I want the engine to detect sensors that stopped updating (showing a frozen
last-known value) and trigger fail-safe when staleness exceeds the configured
threshold,
so that a frozen sensor reading (more dangerous than `unavailable` because it
looks normal) does not silently cause incorrect surplus calculations.

## Acceptance Criteria

**AC1 — Stale critical sensor triggers FAILSAFE**

Given `CACHE_KEY_SOC` was last updated more than `stale_threshold_seconds`
(default 60) seconds ago\
When `_evaluation_tick` calls `_check_staleness()`\
Then `self._hysteresis.force_failsafe(reason)` is called\
And `_LOGGER.warning("SDM630 FAIL-SAFE: %s stale for %ds. Reporting 0 kW.",
entity_id, elapsed_seconds)` emits\
And subsequent `_evaluation_tick` writes `0.0` to the Modbus register

**AC2 — FAILSAFE clears on sensor recovery**

Given a sensor resumes emitting state-change events after a stale period\
When `_handle_state_change` processes a new valid value\
Then the cache entry's `last_changed` timestamp is refreshed\
And on the next evaluation tick, `_check_staleness()` finds elapsed ≤ threshold\
And normal evaluation resumes via the same recovery path established in Story 4.1

**AC3 — Strict boundary: exactly at threshold is NOT stale**

Given `stale_threshold_seconds` = 60\
When a sensor's last update was exactly 60 seconds ago\
Then `_check_staleness()` does NOT trigger FAILSAFE (boundary: strictly
`elapsed > threshold`; `elapsed == threshold` is safe)

**AC4 — Startup grace period: `None` timestamps are skipped**

Given HA starts up and entities have not yet emitted any state-change events\
When the first `_evaluation_tick` fires within the first `stale_threshold_seconds`
seconds\
Then `_check_staleness()` skips any cache entry whose `last_changed is None`
(no false FAILSAFE on cold start)\
And after `stale_threshold_seconds` seconds elapse without any update to a
critical sensor, FAILSAFE triggers normally\
And the startup grace period equals `stale_threshold_seconds` — there is no
separate hardcoded grace period constant

**AC5 — Only critical sensors checked**

Given `CACHE_KEY_BATTERY_DISCHARGE` is absent from the config\
When `_check_staleness()` runs\
Then only the three critical sensors are checked:
`CACHE_KEY_SOC`, `CACHE_KEY_PV_PRODUCTION`, and `CACHE_KEY_POWER_TO_USER`\
And optional sensors not present in `_cache_key_to_entity_id` are silently
skipped (no `KeyError`, no FAILSAFE)

**AC6 — HA-free `SurplusCalculator` unchanged**

Given staleness detection is added to `SurplusEngine`\
When the implementation is complete\
Then `SurplusCalculator` has zero new imports (no `dt_util`, no HA objects)\
And all staleness logic lives in `SurplusEngine._check_staleness()` only

## Tasks / Subtasks

- [ ] Task 1: Add `_cache_key_to_entity_id` reverse mapping to `SurplusEngine.__init__` (AC: #1, #5)
  - [ ] Build `self._cache_key_to_entity_id: dict[str, str]` from `self._config["entities"]`
    keyed by `CACHE_KEY_*` constants, mapping to the configured entity ID strings
  - [ ] Include only the three critical keys:
    `CACHE_KEY_SOC`, `CACHE_KEY_PV_PRODUCTION`, `CACHE_KEY_POWER_TO_USER`
  - [ ] `CACHE_KEY_POWER_TO_GRID` is non-critical (informational); exclude from staleness checks
  - [ ] Example mapping (resolved from config):
    ```python
    self._cache_key_to_entity_id = {
        CACHE_KEY_SOC:           config["entities"]["soc"],
        CACHE_KEY_PV_PRODUCTION: config["entities"]["pv_production"],
        CACHE_KEY_POWER_TO_USER: config["entities"]["power_to_user"],
    }
    ```

- [ ] Task 2: Implement `SurplusEngine._check_staleness()` method (AC: #1–#5)
  - [ ] Signature: `def _check_staleness(self) -> bool`
  - [ ] Read `threshold = self._config.get("stale_threshold_seconds", 60)` (int seconds)
  - [ ] Call `now = dt_util.utcnow()` (requires `from homeassistant.util import dt as dt_util`)
  - [ ] Iterate over `self._cache_key_to_entity_id.items()` (only critical keys — see Task 1)
  - [ ] For each `(cache_key, entity_id)`:
    - [ ] `entry = self._sensor_cache.get(cache_key)` — if `None`, `continue` (startup grace)
    - [ ] Unpack `value, last_changed, is_valid = entry`
    - [ ] If `last_changed is None`, `continue` (startup grace — AC4)
    - [ ] `elapsed = (now - last_changed).total_seconds()`
    - [ ] If `elapsed > threshold` (strict `>`, not `>=` — AC3):
      - [ ] `reason = f"{entity_id} stale for {int(elapsed)}s"`
      - [ ] `_LOGGER.warning("SDM630 FAIL-SAFE: %s stale for %ds. Reporting 0 kW.", entity_id, int(elapsed))`
      - [ ] `self._hysteresis.force_failsafe(reason)`
      - [ ] `return True`
  - [ ] Return `False` if no staleness detected

- [ ] Task 3: Wire `_check_staleness()` into `_evaluation_tick` (AC: #1, #2)
  - [ ] Call `self._check_staleness()` at the top of `_evaluation_tick`,
    BEFORE the unavailability check from Story 4.1 and BEFORE snapshot assembly
  - [ ] Order of checks in `_evaluation_tick` (combined with Story 4.1):
    1. `stale = self._check_staleness()`      ← Story 4.2 — NEW
    2. `unavailable = self._check_availability()`  ← Story 4.1 (already exists)
    3. Recovery: if `not stale and not unavailable and self._hysteresis.state == "FAILSAFE"` →
       `self._hysteresis.resume()` + `_LOGGER.info(...)` (same path as Story 4.1)
    4. Build `SensorSnapshot` and call `evaluate_cycle(snapshot)` as before
  - [ ] The hysteresis filter handles FAILSAFE output automatically: when
    `self._hysteresis.state == "FAILSAFE"`, `update()` returns `0.0` and
    `charging_state` becomes `"FAILSAFE"` — no extra result manipulation needed

- [ ] Task 4: Confirm `_handle_state_change` stores `last_changed` timestamp (Story 4.1 contract — verify only, no new code)
  - [ ] Verify that Story 4.1's `_handle_state_change` stores cache tuples as
    `(float(new_state.state), new_state.last_changed, True)` when value is valid
  - [ ] Verify that `new_state.last_changed` is a timezone-aware `datetime`
    (HA `State` object contract)
  - [ ] If Story 4.1 used a different cache format, update `_check_staleness()` accordingly
    (this task is read-only — no code added until story 4.1 format is confirmed)

- [ ] Task 5: Unit tests in `tests/test_surplus_engine_staleness.py` or extend existing test file
  - [ ] AC1 test: mock `_sensor_cache` with `last_changed = dt_util.utcnow() - timedelta(seconds=61)`,
    assert `force_failsafe` called, warning logged
  - [ ] AC2 test: after stale period, update cache with fresh `last_changed`,
    assert `_check_staleness()` returns `False`
  - [ ] AC3 test: `elapsed == 60` (exact threshold) → returns `False` (no FAILSAFE)
  - [ ] AC4 test: cache entry `(0.0, None, True)` → skipped, returns `False`
  - [ ] AC4 test: empty `_sensor_cache` (no entries yet) → returns `False`
  - [ ] AC5 test: only `CACHE_KEY_SOC` stale, `CACHE_KEY_BATTERY_DISCHARGE` not in
    `_cache_key_to_entity_id` → only SOC triggers FAILSAFE, no `KeyError`
  - [ ] AC6 check: `SurplusCalculator` module has no new `homeassistant` imports

## Dev Notes

### ⚠️ Mandatory Prerequisite: Story 4.1 MUST be completed first

| Prerequisite | Why Required |
|---|---|
| **Story 4.1** (Sensor Unavailability) | Establishes `_sensor_cache` as `dict[str, tuple[float, datetime \| None, bool]]`. Story 4.2 reads the `last_changed` field from those tuples. `HysteresisFilter.force_failsafe()` and `resume()` must already be integrated. |

If Story 4.1 is not yet merged:

- Do NOT change the cache format — align with whatever 4.1 defines
- Stub `_check_staleness()` to `return False` and integrate the call site,
  then fill in the real logic once the cache structure is confirmed

### Files to Modify

Only **`surplus_engine.py`** is changed in this story:

```
custom_components/sdm630_simulator/
└── surplus_engine.py   ← MODIFY: add _check_staleness(),
                                   add _cache_key_to_entity_id to __init__,
                                   wire into _evaluation_tick
tests/
└── test_surplus_engine_staleness.py  ← ADD (or extend existing test file)
```

Files that remain unchanged: `__init__.py`, `sensor.py`, `modbus_server.py`,
`registers.py`, `sdm630_input_registers.py`, `sdm630_holding_registers.py`.

### Sensor Cache Structure (established by Story 4.1)

```python
# _sensor_cache[CACHE_KEY_*] = (value, last_changed, is_valid)
#   value:        float   — last numeric reading
#   last_changed: datetime | None — timezone-aware UTC datetime from HA State,
#                                    None if not yet received (startup grace)
#   is_valid:     bool    — False when STATE_UNAVAILABLE / STATE_UNKNOWN (Story 4.1)
self._sensor_cache: dict[str, tuple[float, datetime | None, bool]] = {}
```

`_handle_state_change` stores (from Story 4.1):

```python
# Valid reading:
self._sensor_cache[cache_key] = (float(new_state.state), new_state.last_changed, True)

# Unavailable/Unknown — Story 4.1 keeps old value or stores (0.0, existing_ts, False)
# → last_changed is preserved / not updated when invalid
```

Key fact: `new_state.last_changed` is updated by HA only when the **value**
changes — not on every state write. This means a sensor reporting the same
value over and over **legitimately** will NOT update `last_changed`.

> **Design decision**: The project has decided to accept this limitation and to
> rely on `last_changed` for staleness. An inverter offline will eventually stop
> emitting state-change events entirely, which is the primary target scenario.

### `_check_staleness()` Implementation Reference

```python
def _check_staleness(self) -> bool:
    """Check critical sensor cache entries for staleness.

    Called at the start of each _evaluation_tick, before snapshot assembly.
    Returns True and triggers FAILSAFE if any critical sensor timestamp
    is stale (elapsed > stale_threshold_seconds). Returns False if all
    critical sensors are fresh or not yet received (startup grace).
    """
    threshold: int = self._config.get("stale_threshold_seconds", 60)
    now = dt_util.utcnow()

    for cache_key, entity_id in self._cache_key_to_entity_id.items():
        entry = self._sensor_cache.get(cache_key)
        if entry is None:
            continue  # sensor not in cache yet — startup grace

        _value, last_changed, _is_valid = entry

        if last_changed is None:
            continue  # explicit startup grace sentinel

        elapsed = (now - last_changed).total_seconds()

        if elapsed > threshold:
            _LOGGER.warning(
                "SDM630 FAIL-SAFE: %s stale for %ds. Reporting 0 kW.",
                entity_id,
                int(elapsed),
            )
            self._hysteresis.force_failsafe(
                f"{entity_id} stale for {int(elapsed)}s"
            )
            return True

    return False
```

### `_evaluation_tick` Integration Pattern (after Stories 4.1 + 4.2)

```python
async def _evaluation_tick(self, now: datetime) -> None:
    if self._first_tick:
        _LOGGER.info(
            "SDM630 SurplusEngine started. Interval=%ds, entities=%d configured",
            self._config.get("evaluation_interval", 15),
            len(self._config.get("entities", {})),
        )
        self._first_tick = False

    # --- Fault detection (order matters) ---
    stale       = self._check_staleness()   # Story 4.2
    unavailable = self._check_availability()  # Story 4.1

    # --- Recovery: both checks must pass ---
    if (
        not stale
        and not unavailable
        and self._hysteresis.state == "FAILSAFE"
    ):
        self._hysteresis.resume()
        _LOGGER.info("SDM630 recovered from FAILSAFE. Resuming normal evaluation.")

    # --- Snapshot assembly and evaluation (unchanged from Story 1.3) ---
    snapshot = self._build_snapshot(now)       # assembles SensorSnapshot
    result   = await self.evaluate_cycle(snapshot)

    # HysteresisFilter handles FAILSAFE output — no extra guard needed here
    input_data_block.set_float(TOTAL_POWER, result.reported_kw)
    ...
```

### Required Import Addition in `surplus_engine.py`

```python
from homeassistant.util import dt as dt_util
```

This import already exists in `sensor.py` (added in Story 1.3 for `sun.sun`
parsing). In `surplus_engine.py` it is NEW — add it to the HA-specific imports
at the top, guarded by `if __package__:` if the dual-import convention is used.

> **HA-free boundary**: `dt_util` is an HA import and lives in `SurplusEngine`
> (orchestrator). `SurplusCalculator` must NOT import it — staleness logic
> belongs in the orchestrator layer only (consistent with Architecture NFR4).

### `dt_util.utcnow()` vs `datetime.utcnow()`

Always use `dt_util.utcnow()` (from `homeassistant.util.dt`), NOT
`datetime.utcnow()`. HA's `State.last_changed` is timezone-aware UTC;
`datetime.utcnow()` is timezone-naive and the subtraction will raise a
`TypeError`. `dt_util.utcnow()` returns a timezone-aware UTC `datetime` that
is compatible with `State.last_changed`.

```python
# ✅ Correct
elapsed = (dt_util.utcnow() - last_changed).total_seconds()

# ❌ Wrong — TypeError: can't subtract offset-naive and offset-aware datetimes
elapsed = (datetime.utcnow() - last_changed).total_seconds()
```

### marq24 `ha-evcc` Pattern Reference

The `evcc_intg` integration uses `async_track_time_interval` with a polling
coordinator and the concept that data from a remote API can become stale.
Although `evcc_intg` polls rather than subscribing to HA state events, the
architectural insight is identical: **a value that looks valid may be stale if
its source stopped updating**. The `DataUpdateCoordinator` in `evcc_intg` raises
`UpdateFailed` when data is not fresh — the equivalent mechanism here is
checking `last_changed` timestamp and triggering `force_failsafe()`.

The specific HA field used here — `new_state.last_changed` — is the canonical
HA attribute for "when did this value last change". It is timezone-aware UTC,
compatible with `dt_util.utcnow()` arithmetic.

### Boundary Condition Reference

| Elapsed (seconds) | Threshold (seconds) | `elapsed > threshold` | Result |
|---|---|---|---|
| 59 | 60 | `False` | No FAILSAFE |
| 60 | 60 | `False` | No FAILSAFE (boundary is safe — AC3) |
| 61 | 60 | `True` | **FAILSAFE triggered** |
| 0 | 60 | `False` | No FAILSAFE (just updated) |

### Startup Grace Period Mechanics

| Cache entry state | `_check_staleness()` behaviour |
|---|---|
| Entry absent (`sensor_cache.get()` → `None`) | `continue` — startup grace |
| Entry exists, `last_changed = None` | `continue` — explicit startup grace |
| Entry exists, `last_changed` set, elapsed ≤ threshold | No FAILSAFE |
| Entry exists, `last_changed` set, elapsed > threshold | **FAILSAFE** |

The startup grace period IS `stale_threshold_seconds`. There is no separate
hardcoded constant. On a cold start with no events within 60 s, FAILSAFE
activates — this is intentional (inverter not responding after 60 s is a fault).

### Project Structure Notes

- `_check_staleness()` is a method of `SurplusEngine` (the HA-aware orchestrator),
  consistent with Architecture decision Arch-2 and the layer separation rule.
- Keeping staleness detection in the orchestrator preserves NFR4 (SurplusCalculator is HA-free).
- The three critical sensors (`soc`, `pv_production`, `power_to_user`) are the
  same ones listed in FR5 as fail-safe triggers. `power_to_grid` is tracked but
  not fail-safe critical (it is used only for logging / reference calculations).

### References

- [Source: epics.md — Story 4.2: Staleness Detection]
- [Source: architecture.md — FR-8 Staleness Detection / `SurplusEngine._sensor_cache`]
- [Source: architecture.md — Sensor Cache Keys / CACHE_KEY_* constants]
- [Source: architecture.md — Logging Patterns / Fail-safe WARNING format]
- [Source: architecture.md — Configuration Defaults / `stale_threshold_seconds=60`]
- [Source: stories/1-3 — `_handle_state_change` cache pattern, `dt_util` import in sensor.py]
- [Source: stories/4-1 — cache tuple format `(float, datetime | None, bool)`, `HysteresisFilter.force_failsafe()` / `resume()` integration]
- [Source: marq24/ha-evcc — `DataUpdateCoordinator` stale-data pattern as architectural inspiration]

## Dev Agent Record

### Agent Model Used

<!-- to be filled by dev agent -->

### Debug Log References

### Completion Notes List

### File List
