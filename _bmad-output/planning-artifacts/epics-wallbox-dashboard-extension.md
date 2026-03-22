---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
status: complete
inputDocuments:
  - _bmad-output/planning-artifacts/prd-wallbox-dashboard-extension.md
  - _bmad-output/planning-artifacts/architecture.md
  - AGENTS.md
---

# sdm630-simulator — Wallbox Dashboard Extension Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the Wallbox Dashboard
Extension feature, decomposing requirements from the PRD, architecture patterns, and
implementation decisions into implementable brownfield stories.

## Requirements Inventory

### Functional Requirements

FR1: Ghost can view the current raw PV surplus value (W) before hysteresis and battery
buffer are applied.

FR2: Ghost can view the current reported surplus value (W) — the exact value served to
the wallbox via Modbus register, after hysteresis and buffer logic.

FR3: Both surplus sensors update in real time when the `SurplusEngine` computes a new
value — no manual refresh required.

FR4: Surplus sensor values persist across HA restarts and display last known value until
a new computation cycle provides a fresh value.

FR5: Ghost can view the timestamp of the most recent Modbus poll received from the
wallbox.

FR6: The last-poll sensor state transitions to a warning state when no poll has been
received for more than 5 minutes.

FR7: The last-poll sensor returns to normal state immediately when a new poll is received
after a warning period.

FR8: The last-poll sensor persists its last known timestamp across HA restarts.

FR9: The last-poll and surplus sensors update independently — a silent wallbox does not
prevent surplus sensor updates.

FR10: Ghost can add a pre-configured Lovelace card YAML to the HA dashboard that displays
all three sensors in a dedicated "Wallbox Charging" section.

FR11: The Lovelace card configuration uses only standard built-in HA card types — no
custom HACS card dependency.

FR12: The last-poll sensor displays in orange within the Lovelace card when in warning
state (no poll > 5 minutes).

FR13: The card displays raw surplus, reported surplus, and last-poll timestamp in a
single compact view without requiring navigation to a separate page.

### Non-Functional Requirements

NFR1 (Performance): `sensor.sdm_wallbox_last_poll` updates within 500 ms of a Modbus
poll event being received.

NFR2 (Performance): Warning state evaluation (5-minute threshold check) runs at most
once per minute — no busy-polling loop permitted.

NFR3 (Performance): Surplus sensor state updates add no measurable latency to the
existing `SurplusEngine` evaluation cycle — the callback must be non-blocking.

NFR4 (Reliability): The poll-detection hook must not affect Modbus response correctness
or timing.

NFR5 (Reliability): A failure in sensor state update must not crash the Modbus server or
the surplus engine — fail silently with a log entry.

NFR6 (Reliability): Warning state determinism: if the last poll was exactly 300 seconds
ago, the state is `True` (warning); at 299 seconds, it is `False` (normal).

NFR7 (Maintainability): New sensors follow the existing HA sensor entity pattern in
`sensor.py` — same class structure, same `_LOGGER`, same `_attr_should_poll = False`.

NFR8 (Maintainability): Lovelace card YAML documented with inline comments explaining
the conditional color logic.

NFR9 (Maintainability): No new Python dependencies — implementation uses only
`pymodbus`, `homeassistant` core, and the Python standard library.

### Additional Requirements

From `architecture.md` and `AGENTS.md` — binding constraints for all stories:

- **Naming conventions:** Classes `CamelCase`, methods `snake_case`, constants
  `UPPER_SNAKE_CASE`, logger `_LOGGER = logging.getLogger(__name__)`, all modules
  include `if __package__:` dual-import guard.
- **HA sensor base class:** New sensors extend `RestoreSensor` (from
  `homeassistant.components.sensor`) to support `restore_state`. On
  `async_added_to_hass`, call `await self.async_get_last_sensor_data()`.
- **`_attr_should_poll = False`:** All new entities are event-driven, not polled.
- **Non-blocking callbacks:** Any callback invoked from the Modbus server thread or the
  HA event loop must not perform blocking I/O.
- **Fail-silent pattern:** Errors in sensor update must log via `_LOGGER.warning()` or
  `_LOGGER.error()`, never propagate exceptions that crash the server.
- **File boundary:** New Python code goes into `sensor.py` (HA entity classes) and
  `modbus_server.py` (poll-detection callback hook only). `surplus_engine.py`,
  `registers.py`, and the input/holding register files are not modified.
- **`EvaluationResult` already provides both values:** `real_surplus_kw` (raw, W×1000)
  and `reported_kw` (reported, W×1000) — surplus sensor stories read from
  `EvaluationResult`, no changes to `SurplusEngine` needed.
- **Python 3.12, pymodbus ≥ 3.11.1** — per architecture.md update.

### UX Design Requirements

No separate UX design document. Lovelace card implementation approach is fully specified
in `prd-wallbox-dashboard-extension.md` — Implementation Notes section.

UX-DR1: Lovelace card uses `conditional` card wrapping two `entities` card variants
(normal / warning) toggled by `binary_sensor.sdm_wallbox_poll_warning`.

UX-DR2: Normal variant: single `entities` card titled "Wallbox Charging" showing all
three sensors.

UX-DR3: Warning variant: identical card with `⚠` appended to title, visually signaling
the warning state.

UX-DR4: All YAML commented inline to allow Ghost to change the 300-second threshold
without re-reading implementation code.

### FR Coverage Map

FR1: Epic 1 — raw surplus sensor entity reads `real_surplus_kw` from `EvaluationResult`

FR2: Epic 1 — reported surplus sensor entity reads `reported_kw` from `EvaluationResult`

FR3: Epic 1 — both surplus sensors updated via callback registered on `SurplusEngine`

FR4: Epic 1 — both surplus sensors use `RestoreSensor.async_get_last_sensor_data()`

FR5: Epic 2 — last-poll sensor entity; updated by Modbus poll detection hook

FR6: Epic 2 — `binary_sensor.sdm_wallbox_poll_warning` derived from last-poll timestamp

FR7: Epic 2 — warning binary sensor clears when new poll received

FR8: Epic 2 — last-poll sensor uses `RestoreSensor` persistence

FR9: Epic 2 — architecturally guaranteed: surplus callbacks and Modbus poll hook are
independent code paths; covered by AC in Epic 2 story

FR10: Epic 3 — Lovelace card YAML delivered as documented artefact in `docs/`

FR11: Epic 3 — `conditional` + `entities` cards only; no HACS components

FR12: Epic 3 — warning card variant displayed when
`binary_sensor.sdm_wallbox_poll_warning` is `on`

FR13: Epic 3 — both card variants show all three sensors in one compact view

## Epic List

### Epic 1: Surplus Signal Visibility

Ghost can view the current raw and reported surplus values on the HA dashboard in real
time, with values surviving HA restarts.

**FRs covered:** FR1, FR2, FR3, FR4
**NFRs covered:** NFR3, NFR5 (fail-silent), NFR7 (code style)

### Epic 2: Wallbox Connectivity Monitoring

Ghost can see when the wallbox last polled and receives an automatic orange warning when
the wallbox has been silent for more than 5 minutes — without any active checking.

**FRs covered:** FR5, FR6, FR7, FR8, FR9
**NFRs covered:** NFR1, NFR2, NFR4, NFR5, NFR6, NFR7

### Epic 3: Dashboard Integration

Ghost can paste a single YAML snippet into the HA dashboard and immediately see the
complete "Wallbox Charging" card with all three sensors and automatic orange warning
state — zero additional tooling or HACS dependencies required.

**FRs covered:** FR10, FR11, FR12, FR13
**NFRs covered:** NFR8, NFR9

## Epic 1: Surplus Signal Visibility

Ghost can immediately read the raw PV surplus (pre-hysteresis) and the reported surplus
(post-hysteresis, the value the wallbox actually receives) as HA sensor entities — live
and persisted across restarts.

### Story 1.1: Add raw and reported surplus sensor entities

As Ghost,
I want to see `sensor.sdm_raw_surplus` and `sensor.sdm_reported_surplus` on my HA
dashboard with live values,
So that I can verify the entire surplus computation chain at a glance without opening
logs.

**Acceptance Criteria:**

**Given** the HA component is running and `SurplusEngine` has completed at least one
evaluation cycle
**When** Ghost opens HA Developer Tools → States
**Then** `sensor.sdm_raw_surplus` is present with a numeric value in W matching
`EvaluationResult.real_surplus_kw × 1000`
**And** `sensor.sdm_reported_surplus` is present with a numeric value in W matching
`EvaluationResult.reported_kw × 1000`

**Given** `SurplusEngine` completes an evaluation cycle
**When** the evaluation callback fires
**Then** both sensors update within the same HA event loop tick (non-blocking, no
await in the callback path)
**And** `_LOGGER.debug` records the new values at DEBUG level

**Given** HA has been restarted
**When** the `SDM630RawSurplusSensor` and `SDM630ReportedSurplusSensor` entities are
added to hass
**Then** `async_get_last_sensor_data()` is called on both
**And** each sensor displays the last persisted value (not `unknown`) until the next
evaluation cycle provides a fresh value

**Given** an error occurs while updating the sensor state (e.g., entity not yet
registered)
**When** the evaluation callback fires
**Then** the exception is caught, logged via `_LOGGER.warning()`, and neither
`SurplusEngine` nor the Modbus server crashes

**Implementation Notes:**

- Add `SDM630RawSurplusSensor(RestoreSensor)` and
  `SDM630ReportedSurplusSensor(RestoreSensor)` classes to `sensor.py`.
- Both classes: `_attr_should_poll = False`, `_attr_native_unit_of_measurement = "W"`,
  `_attr_device_class = SensorDeviceClass.POWER`.
- In `async_setup_platform`: instantiate both sensors and pass them to
  `async_add_entities`.
- In `SDM630SimSensor._evaluation_tick` (or equivalent post-evaluation hook): call a
  `update_surplus_sensors(result: EvaluationResult)` function that writes
  `result.real_surplus_kw * 1000` and `result.reported_kw * 1000` to the respective
  sensor native values and calls `async_write_ha_state()`.
- `EvaluationResult` already has both fields — no changes to `surplus_engine.py`.

## Epic 2: Wallbox Connectivity Monitoring

Ghost can see the exact moment the wallbox last communicated and receives an automatic
visual cue when the wallbox goes silent — independently of the surplus computation.

### Story 2.1: Add last-poll timestamp sensor and Modbus hook

As Ghost,
I want to see `sensor.sdm_wallbox_last_poll` updated every time the wallbox polls the
Modbus server,
So that I can verify the wallbox is actively communicating without opening a network
trace.

**Acceptance Criteria:**

**Given** the Modbus TCP server is running and the wallbox issues a function-code-04
read request
**When** the request is received by `modbus_server.py`
**Then** `sensor.sdm_wallbox_last_poll` is updated with the current UTC datetime within
500 ms (NFR1)
**And** the Modbus response to the wallbox is correct and unaffected by the sensor update

**Given** a callback function is registered on the `SDM630DataBlock` for poll events
**When** the poll notification fires
**Then** the callback is non-blocking (no `await`, no I/O in the synchronous callback
path)

**Given** HA has been restarted and the wallbox has not yet polled
**When** `SDM630WallboxLastPollSensor.async_added_to_hass` completes
**Then** the sensor displays the last persisted datetime value (not `unknown`)

**Given** an exception occurs in the sensor update callback
**When** the Modbus poll event fires
**Then** the exception is caught and logged via `_LOGGER.warning()`, and the Modbus
server continues responding normally (NFR4, NFR5)

**Implementation Notes:**

- Add `SDM630WallboxLastPollSensor(RestoreSensor)` to `sensor.py`:
  `_attr_should_poll = False`, `_attr_device_class = SensorDeviceClass.TIMESTAMP`.
- Add a poll notification callback slot to `SDM630DataBlock` in `modbus_server.py`
  (a simple `self._poll_callback: Callable | None = None` and
  `set_poll_callback(cb)` method). Call `cb()` at the end of the existing
  `getValues` override — after the Modbus response is assembled, not before.
- In `async_setup_platform`, wire the callback:
  `input_data_block.set_poll_callback(wallbox_last_poll_sensor.on_poll)`.
- `on_poll` must be `@callback` decorated; it records `dt_util.utcnow()` and calls
  `self.async_write_ha_state()`.

### Story 2.2: Implement 5-minute warning binary sensor

As Ghost,
I want a `binary_sensor.sdm_wallbox_poll_warning` that turns `on` automatically when
no wallbox poll is received for more than 5 minutes,
So that I notice without actively checking — the Lovelace card changes appearance.

**Acceptance Criteria:**

**Given** the last Modbus poll was received 299 seconds ago
**When** the warning evaluation runs
**Then** `binary_sensor.sdm_wallbox_poll_warning` is `off` (no warning)

**Given** the last Modbus poll was received exactly 300 seconds ago
**When** the warning evaluation runs
**Then** `binary_sensor.sdm_wallbox_poll_warning` is `on` (warning state) (NFR6
determinism)

**Given** `binary_sensor.sdm_wallbox_poll_warning` is `on` (wallbox was silent)
**When** a new Modbus poll is received
**Then** the binary sensor transitions to `off` within the next warning evaluation
interval (FR7)

**Given** the warning evaluation timer fires
**When** `sensor.sdm_wallbox_last_poll` has never been set (clean startup, no poll yet)
**Then** `binary_sensor.sdm_wallbox_poll_warning` is `off` (no spurious warning on
startup)

**Given** `sensor.sdm_wallbox_last_poll` updates and
`sensor.sdm_raw_surplus` updates simultaneously
**When** both are observed in HA Developer Tools
**Then** both can update independently and neither blocks the other (FR9)

**Implementation Notes:**

- Add `SDM630WallboxPollWarningSensor(BinarySensorEntity)` to `sensor.py`:
  `_attr_should_poll = False`,
  `_attr_device_class = BinarySensorDeviceClass.PROBLEM`.
- Use `async_track_time_interval` with a 60-second interval (NFR2) to evaluate
  `(dt_util.utcnow() - self._last_poll_dt).total_seconds() >= 300`.
  If `_last_poll_dt` is `None` (startup), result is `False`.
- The last-poll sensor (`SDM630WallboxLastPollSensor`) calls a shared setter on the
  warning sensor whenever a new poll is received, so the warning sensor clears
  immediately on the next evaluation tick without waiting 60 seconds to detect the
  new arrival.
- `WALLBOX_POLL_WARNING_THRESHOLD = 300` constant (UPPER_SNAKE_CASE, module-level).

## Epic 3: Dashboard Integration

Ghost can add a single YAML snippet to the HA dashboard and immediately see the complete
"Wallbox Charging" card — including automatic orange state — without any additional
setup or dependencies.

### Story 3.1: Create Lovelace card YAML with conditional orange state

As Ghost,
I want a ready-to-paste Lovelace card YAML that shows both surplus sensors and the
last-poll indicator — turning visually distinct when the wallbox goes silent,
So that the entire signal chain is observable from one card without any extra tools or
HACS components.

**Acceptance Criteria:**

**Given** Ghost pastes the provided card YAML into the HA dashboard
**When** HA validates the card configuration
**Then** no YAML errors are reported and the card renders correctly

**Given** `binary_sensor.sdm_wallbox_poll_warning` is `off`
**When** Ghost views the Wallbox Charging dashboard card
**Then** the card displays the normal variant: title "Wallbox Charging", three sensor
rows (raw surplus W, reported surplus W, last-poll datetime), no visual warning

**Given** `binary_sensor.sdm_wallbox_poll_warning` is `on`
**When** Ghost views the Wallbox Charging dashboard card
**Then** the card displays the warning variant: title "Wallbox Charging ⚠", same three
sensor rows, visually distinct from the normal state

**Given** Ghost wants to change the warning threshold from 5 minutes to a different
value
**When** Ghost reads the YAML file in `docs/lovelace-wallbox-card.yaml`
**Then** the threshold value and how to change it are explained by inline YAML comments
(NFR8), and no other knowledge is required

**Given** the card is added to the dashboard
**When** Ghost checks the HACS / custom card dependencies
**Then** no HACS or third-party Lovelace card is required (FR11) — only `conditional`
and `entities` built-in card types are used

**Implementation Notes:**

- Deliver as `docs/lovelace-wallbox-card.yaml`.
- Card structure (two `conditional` blocks, one for `off` state, one for `on` state):

```yaml
# Wallbox Charging — Lovelace Card
# Requires: binary_sensor.sdm_wallbox_poll_warning (on = no poll for >300 s)
# To change the threshold, update WALLBOX_POLL_WARNING_THRESHOLD in sensor.py
# and restart Home Assistant.

- type: conditional
  conditions:
    - condition: state
      entity: binary_sensor.sdm_wallbox_poll_warning
      state: "off"
  card:
    type: entities
    title: Wallbox Charging
    entities:
      - entity: sensor.sdm_raw_surplus
        name: Raw Surplus
      - entity: sensor.sdm_reported_surplus
        name: Reported Surplus
      - entity: sensor.sdm_wallbox_last_poll
        name: Last Wallbox Poll
- type: conditional
  conditions:
    - condition: state
      entity: binary_sensor.sdm_wallbox_poll_warning
      state: "on"
  card:
    type: entities
    title: "Wallbox Charging \u26A0"
    entities:
      - entity: sensor.sdm_raw_surplus
        name: Raw Surplus
      - entity: sensor.sdm_reported_surplus
        name: Reported Surplus
      - entity: sensor.sdm_wallbox_last_poll
        name: Last Wallbox Poll
        # WARNING: No poll received for >5 minutes
```

- No additional configuration in `configuration.yaml` required for the card. The
  `binary_sensor.sdm_wallbox_poll_warning` is a Python entity registered automatically
  by `async_setup_platform` — not a template sensor in YAML.
