---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
status: complete
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - AGENTS.md
classification:
  projectType: iot_embedded
  domain: energy
  complexity: low
  projectContext: brownfield
workflowType: prd
---

# Product Requirements Document - SDM630 Simulator Wallbox Dashboard Extension

**Author:** Ghost
**Date:** 2026-03-22

## Executive Summary

The SDM630 Simulator Wallbox Dashboard Extension adds operational observability to the
existing surplus engine by exposing the simulator's internal computation state as Home
Assistant sensor entities and a ready-to-use Lovelace card. The extension addresses a gap
in the current implementation: the Modbus communication between simulator and wallbox is
invisible to the operator — there is no indication of what value is being reported, whether
the wallbox is actively polling, or whether the system is functioning correctly.

Two new sensor entities expose the computed surplus signal at both stages of processing:
the raw PV surplus (pre-hysteresis, pre-buffer) and the reported surplus (post-hysteresis,
the value actually served to the wallbox via Modbus register). A third sensor tracks the
last Modbus poll timestamp from the wallbox. A Lovelace card configuration groups these
three sensors into a dedicated "Wallbox Charging" dashboard section, with the last-poll
sensor visually highlighted in orange when the wallbox has not polled within a configurable
threshold (default: 5 minutes).

The primary use case is passive reassurance: Ghost glances at the dashboard and instantly
confirms the system is alive and computing correctly — without opening logs, checking
entities manually, or investigating further. The orange warning state triggers only when
attention is needed.

### What Makes This Special

The Growatt THOR wallbox has no native connectivity to Home Assistant and exposes no status
information via any API. The only observable interaction is the Modbus TCP poll it issues
to the simulated SDM630 meter. This extension makes that invisible communication visible
for the first time — a timestamp that proves the wallbox is active and the simulator is
serving it data. Combined with the dual surplus display, Ghost can verify the entire signal
chain (PV production → surplus calculation → hysteresis → Modbus register → wallbox) from
a single card, without any additional tooling.

### Project Classification

- **Project Type:** IoT/Embedded — Home Assistant custom component, Modbus TCP server,
  new HA sensor entities, Lovelace UI configuration
- **Domain:** Energy — EV charging observability, PV surplus signal visibility
- **Complexity:** Low — Three new sensor entities, one Lovelace card, no new data sources
  or external integrations
- **Project Context:** Brownfield — Extends existing SDM630 simulator; surplus engine,
  Modbus server, and HA sensor platform already operational

## Success Criteria

### User Success

- **Signal-Chain verifiable at a glance**: Ghost can confirm that raw surplus, reported
  surplus, and wallbox poll activity are all functioning correctly from a single Lovelace
  card — without opening HA logs or entity inspector.
- **Orange warning on loss of wallbox communication**: When the wallbox has not polled
  within 5 minutes, the last-poll sensor is visually highlighted in orange. Ghost notices
  without actively checking.
- **Passive reassurance in daily use**: The card is present in the dashboard. On a normal
  day, Ghost glances at it and sees normal state — no action needed, confidence confirmed.
- **Last known values survive HA restart**: After a Home Assistant restart, all three
  sensors display their last known values immediately upon HA coming back online, not
  `unknown` or `unavailable`.

### Business Success

*N/A — Personal project. No commercial objectives.*

The singular success metric: **The first implementation is verifiable without log
inspection. Ghost can trust the system is computing and communicating correctly from the
dashboard alone.**

### Technical Success

- **Three sensor entities operational**: `sensor.sdm_raw_surplus`,
  `sensor.sdm_reported_surplus`, and `sensor.sdm_wallbox_last_poll` are registered in
  Home Assistant, update in real time, and display correct values.
- **Orange state trigger functional**: The last-poll sensor state changes to a warning
  state (exposable as orange via Lovelace card template) when no Modbus poll has been
  received within 300 seconds (5 minutes).
- **Lovelace card configuration provided**: A ready-to-use YAML card configuration is
  provided that Ghost can paste into the dashboard — no custom card dependency, uses
  standard HA components only.
- **Last known value persistence**: Sensor state survives HA restart via HA's native
  `restore_state` mechanism, showing last valid value on startup.
- **No polling overhead**: All three sensors are event-driven (pushed by the Modbus server
  and surplus engine), not polled by HA.

### Measurable Outcomes

| Outcome | Target | Measurement Method |
|---------|--------|--------------------|
| Sensors visible in HA | All 3 present | HA Developer Tools → States |
| Raw surplus accuracy | Matches `SurplusEngine` raw output | Manual comparison |
| Reported surplus accuracy | Matches Modbus register 0x0006 value | Modbus client read |
| Last-poll orange trigger | Fires within 5 min of wallbox stopping | Manual test: unplug wallbox |
| Post-restart state | Last known values shown, not `unknown` | HA restart test |
| Lovelace card usable | Card renders with no YAML errors | Dashboard add test |

## Product Scope

### MVP - Minimum Viable Product

- `sensor.sdm_raw_surplus` entity (W, float, event-driven)
- `sensor.sdm_reported_surplus` entity (W, float, event-driven)
- `sensor.sdm_wallbox_last_poll` entity (datetime, updated on each Modbus poll)
- Orange warning state when last poll > 5 minutes ago
- Last known value restore on HA restart
- Lovelace card YAML configuration (uses standard HA card: `entities` or `glance`)

### Growth Features (Post-MVP)

- Configurable warning threshold (currently hardcoded 5 min)
- Historical graph of surplus values in the card
- HA persistent notification when wallbox goes silent for extended period

### Vision (Future)

- Full signal-chain card showing all pipeline stages: PV production → raw surplus →
  hysteresis state → reported surplus → wallbox poll status

## User Journeys

### Journey 1 — Ghost: First Light (Primary, Happy Path)

**Opening Scene:** It's a Thursday evening. Ghost has just deployed the dashboard extension
— the three new sensor entities are registered in Home Assistant, the Lovelace card YAML is
pasted into the dashboard. Ghost opens the HA app on the phone for the first time since the
deployment.

**Rising Action:** The "Wallbox Charging" card is visible on the energy dashboard. Raw
surplus shows 1,840 W. Reported surplus shows 4,200 W — the buffer is active, the
hysteresis is holding. Last poll: 23 seconds ago. Ghost stares at the card for a moment.
The numbers make sense. The wallbox is polling. The surplus engine is running.

**Climax:** Ghost opens the car's charging app separately — it confirms the session is
active, 4.2 kW. The number matches what the card shows. The signal chain is complete and
verifiable end-to-end for the first time without a single log entry opened.

**Resolution:** Ghost puts the phone down. *"It works."* No log file, no Modbus client
tool, no SSH session. Just a card that tells the truth. The system is now observable.

**Requirements revealed:** Sensor entities readable in real time; reported surplus reflects
active Modbus register value; last-poll timestamp updates with each wallbox query.

### Journey 2 — Ghost: The Silent Wallbox (Primary, Edge Case)

**Opening Scene:** A hot July Saturday, 13:45. PV is producing 9 kW, battery at 100%,
reported surplus 4.2 kW. The EV has been charging since 10:00. Ghost is in the garden,
glances at the HA dashboard on the tablet.

**Rising Action:** Something is orange on the Wallbox card. Last poll: 8 minutes ago. Ghost
frowns — it was 23 seconds ago all morning. The raw and reported surplus values are still
showing correctly (they update from the surplus engine, not from the wallbox). But the
wallbox has gone quiet.

**Climax:** Ghost walks to the garage. The wallbox display shows it's connected but paused.
The WLAN dropped and reconnected — but the wallbox didn't restart its Modbus session
automatically. Without the orange indicator, Ghost would not have noticed for hours and
assumed the car was charging when it wasn't.

**Resolution:** Ghost power-cycles the wallbox. Within 30 seconds, the last-poll timestamp
updates, the orange disappears, charging resumes. Total downtime noticed within 8 minutes
— not discovered at the end of the day when the car is still at 40%.

**Requirements revealed:** Warning state triggers at exactly 5 minutes of poll silence;
warning is visually distinct (orange) without requiring active attention; raw/reported
surplus continue updating independently of wallbox poll state.

### Journey 3 — Ghost: Morning After Restart (System, Recovery Path)

**Opening Scene:** HA auto-updated overnight. The host rebooted at 03:17. Ghost wakes up
at 07:30, PV barely producing yet (0.3 kW, cloudy morning). Ghost opens the dashboard.

**Rising Action:** The Wallbox card shows values: raw surplus −120 W (house consuming more
than PV produces), reported surplus 0 W (floor active, SOC protection). Last poll: 4
minutes ago. These are not `unknown` — they are the last computed values restored from
HA's state store. The wallbox resumed polling after HA came back up, so the last-poll
timestamp is recent and green.

**Climax:** Ghost sees a coherent picture even though HA was offline for 4+ hours. The
sensors didn't lose their state. The wallbox reconnected automatically after HA restarted
the Modbus server. Everything picked up where it left off without manual intervention.

**Resolution:** Ghost makes coffee. The system handled it. No orange, no `unknown`, no
manual restart needed. This is what autonomous operation looks like.

**Requirements revealed:** `restore_state = True` on all three sensor entities; Modbus
server restarts cleanly with HA; wallbox reconnects automatically after Modbus server
restart.

### Journey Requirements Summary

| Journey | Capability Revealed |
|---------|---------------------|
| Journey 1 (First Light) | Real-time sensor updates; Modbus register → sensor value chain |
| Journey 2 (Silent Wallbox) | 5-min orange warning; warning independent of surplus compute |
| Journey 3 (Morning Restart) | `restore_state`; Modbus server restart resilience |

## IoT and Embedded Requirements

### Integration Constraints

- The component runs as a Home Assistant custom component inside the HA process; no
  standalone daemon or separate service is permitted.
- All sensor state updates must use the HA event bus — no direct database writes.
- The Modbus TCP server (`pymodbus >= 3.9.2`) is already running; the poll-detection
  mechanism must hook into the existing server without replacing or duplicating it.

### Hardware Communication

- The wallbox (Growatt THOR 11AS-P-V1) polls Modbus TCP port 5020 using standard function
  code 04 (read input registers). Poll detection must capture this event without interfering
  with the Modbus response.
- No outbound communication to the wallbox is required — read-only observation of inbound
  poll events.

### Reliability and Restart Behavior

- All three sensors must declare `restore_state = True` in their HA entity config to persist
  last known value across HA restarts.
- The Modbus server must restart automatically as part of the HA platform setup sequence
  (`async_setup_platform`). The wallbox must be able to reconnect without manual intervention
  after any HA restart.

## Functional Requirements

### Surplus Signal Visibility

- FR1: Ghost can view the current raw PV surplus value (W) before hysteresis and battery
  buffer are applied.
- FR2: Ghost can view the current reported surplus value (W) — the exact value served to the
  wallbox via Modbus register, after hysteresis and buffer logic.
- FR3: Both surplus sensors update in real time when the `SurplusEngine` computes a new
  value — no manual refresh required.
- FR4: Surplus sensor values persist across HA restarts and display last known value until a
  new computation cycle provides a fresh value.

### Wallbox Connectivity Monitoring

- FR5: Ghost can view the timestamp of the most recent Modbus poll received from the
  wallbox.
- FR6: The last-poll sensor state transitions to a warning state when no poll has been
  received for more than 5 minutes.
- FR7: The last-poll sensor returns to normal state immediately when a new poll is received
  after a warning period.
- FR8: The last-poll sensor persists its last known timestamp across HA restarts.
- FR9: The last-poll and surplus sensors update independently — a silent wallbox does not
  prevent surplus sensor updates.

### Dashboard Integration

- FR10: Ghost can add a pre-configured Lovelace card YAML to the HA dashboard that displays
  all three sensors in a dedicated "Wallbox Charging" section.
- FR11: The Lovelace card configuration uses only standard built-in HA card types — no
  custom HACS card dependency.
- FR12: The last-poll sensor displays in orange within the Lovelace card when in warning
  state (no poll > 5 minutes).
- FR13: The card displays raw surplus, reported surplus, and last-poll timestamp in a single
  compact view without requiring navigation to a separate page.

## Non-Functional Requirements

### Performance

- **NFR1:** The `sensor.sdm_wallbox_last_poll` entity updates within 500 ms of a Modbus
  poll event being received — latency between hardware event and HA state change is
  imperceptible to Ghost.
- **NFR2:** Warning state evaluation (5-minute threshold check) runs at most once per
  minute — no busy-polling loop permitted.
- **NFR3:** Surplus sensor state updates add no measurable latency to the existing
  `SurplusEngine` evaluation cycle — the callback must be non-blocking.

### Reliability

- **NFR4:** The poll-detection hook must not affect Modbus response correctness or timing —
  the wallbox must receive valid responses regardless of sensor update errors.
- **NFR5:** A failure in sensor state update (e.g., HA entity not yet registered at
  startup) must not crash the Modbus server or the surplus engine — fail silently with a
  log entry.
- **NFR6:** The warning state must be deterministic — if the last poll was exactly 300
  seconds ago, the state is orange; at 299 seconds, it is normal.

### Maintainability

- **NFR7:** The three new sensors follow the existing HA sensor entity pattern in
  `sensor.py` — same class structure, same logging conventions (`_LOGGER`), same
  `_attr_should_poll = False` pattern.
- **NFR8:** The Lovelace card YAML is documented with inline comments explaining the
  conditional color logic, enabling Ghost to modify thresholds without re-reading the full
  implementation.
- **NFR9:** No new Python dependencies are introduced — implementation uses only
  `pymodbus`, `homeassistant` core, and the Python standard library.

## Implementation Notes

These decisions were made during the Implementation Readiness check (2026-03-22) to close
open technical questions before epic creation. They are binding for story acceptance
criteria.

### Lovelace Orange State Strategy

**Decision:** Use a native HA `template` binary sensor (`binary_sensor.sdm_wallbox_poll_warning`)
as the warning indicator. The `conditional` card in Lovelace uses this binary sensor to
toggle between two `entities` card variants — normal and warning — achieving the orange
visual state without any HACS or custom card dependency.

**Rationale:** Standard `entities` and `glance` cards do not support conditional row
colour. `custom:button-card` would violate FR11 (no HACS dependency). The
`conditional`-card + native `template` binary sensor pattern is fully native, requires
zero additional integrations, and keeps the Lovelace YAML self-contained.

**Entities produced by this decision:**

- `binary_sensor.sdm_wallbox_poll_warning` — `True` when
  `sensor.sdm_wallbox_last_poll` is older than 300 seconds, `False` otherwise. Evaluated
  via a HA `template` binary sensor configured in `configuration.yaml` (or `template:`
  block). This entity is owned by Epic 2 (Wallbox Connectivity Monitoring), not Epic 3.

**Lovelace card structure (sketch):**

```yaml
type: conditional
conditions:
  - entity: binary_sensor.sdm_wallbox_poll_warning
    state: "off"
card:
  type: entities
  title: Wallbox Charging
  entities:
    - sensor.sdm_raw_surplus
    - sensor.sdm_reported_surplus
    - sensor.sdm_wallbox_last_poll
---
type: conditional
conditions:
  - entity: binary_sensor.sdm_wallbox_poll_warning
    state: "on"
card:
  type: entities
  title: Wallbox Charging ⚠
  entities:
    - sensor.sdm_raw_surplus
    - sensor.sdm_reported_surplus
    - entity: sensor.sdm_wallbox_last_poll
      # Warning state: no poll > 5 min — card row colour driven by entity state_color
```

### HA Entity Base Class for Datetime Sensor with restore_state

**Decision:** `sensor.sdm_wallbox_last_poll` uses `RestoreSensor` as its base class
(from `homeassistant.components.sensor`). On HA startup, `async_added_to_hass` calls
`await self.async_get_last_sensor_data()` to restore the last persisted `datetime` value.

**Rationale:** HA's generic `RestoreEntity` restores `state` as a string. `RestoreSensor`
restores the typed `native_value` (including `datetime` objects), which avoids string
round-trip parsing and matches the existing sensor pattern in `sensor.py`.

**Impact on stories:** The FR8 acceptance criterion ("last-poll timestamp persists across
HA restart") is satisfied by implementing `RestoreSensor` and calling
`async_get_last_sensor_data()` — no additional persistence mechanism required.
