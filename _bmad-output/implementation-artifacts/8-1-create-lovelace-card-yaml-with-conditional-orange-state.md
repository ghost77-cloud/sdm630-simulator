# Story 8.1: Create Lovelace Card YAML with Conditional Orange State

Status: ready-for-dev

## Story

As Ghost,
I want a ready-to-paste Lovelace card YAML that shows both surplus sensors and the
last-poll indicator — turning visually distinct when the wallbox goes silent,
so that the entire signal chain is observable from one card without any extra tools or
HACS components.

## Acceptance Criteria

### AC1: Card renders without YAML errors

**Given** Ghost pastes the provided card YAML into the HA dashboard
**When** HA validates the card configuration
**Then** no YAML errors are reported and the card renders correctly

### AC2: Normal state shows all three sensors

**Given** `binary_sensor.sdm_wallbox_poll_warning` is `off`
**When** Ghost views the Wallbox Charging dashboard card
**Then** the card displays the normal variant: title "Wallbox Charging", three sensor
rows (raw surplus, reported surplus, last-poll timestamp), no visual warning

### AC3: Warning state shows visual distinction

**Given** `binary_sensor.sdm_wallbox_poll_warning` is `on`
**When** Ghost views the Wallbox Charging dashboard card
**Then** the card displays the warning variant: title "Wallbox Charging ⚠", same three
sensor rows, visually distinct from the normal state

### AC4: Threshold change is self-documented

**Given** Ghost wants to change the warning threshold from 5 minutes to a different value
**When** Ghost reads `docs/lovelace-wallbox-card.yaml`
**Then** inline YAML comments explain the threshold and how to change it (NFR8) — no
other knowledge is required

### AC5: No HACS or third-party card required

**Given** the card is added to the dashboard
**When** Ghost checks HACS and custom card dependencies
**Then** no HACS or third-party Lovelace card is required (FR11) — only `conditional`
and `entities` built-in card types are used

## Tasks / Subtasks

- [ ] Task 1: Create `docs/lovelace-wallbox-card.yaml` (AC: #1, #2, #3, #4, #5)
  - [ ] 1.1 Create file with a top-level comment block explaining the card, its sensors,
    the warning threshold, and how to change it
  - [ ] 1.2 Add the `off`-state `conditional` card block (normal variant):
    title "Wallbox Charging", three entity rows
  - [ ] 1.3 Add the `on`-state `conditional` card block (warning variant):
    title "Wallbox Charging ⚠", same three entity rows with a warning comment
  - [ ] 1.4 Verify correct inline `condition` syntax for HA 2024.x+ (`condition: state`)
  - [ ] 1.5 Add inline comments explaining each section

## Dev Notes

### What This Story Produces

A single YAML file: `docs/lovelace-wallbox-card.yaml`.

No Python code is written. No existing files are modified. The file is a documentation
artefact that Ghost pastes into the HA Lovelace dashboard editor.

### Exact YAML to Deliver

The delivered file must follow this structure precisely. Both `conditional` blocks must
be at the top level of the YAML list (HA dashboard card rows), not nested inside another
card:

```yaml
# Wallbox Charging — Lovelace Card Configuration
#
# Sensors required:
#   sensor.sdm_raw_surplus          (W, pre-hysteresis — Story 6-1 / Epic 6)
#   sensor.sdm_reported_surplus     (W, post-hysteresis — Story 6-1 / Epic 6)
#   sensor.sdm_wallbox_last_poll    (datetime — Story 7-1 / Epic 7)
#   binary_sensor.sdm_wallbox_poll_warning (on/off — Story 7-2 / Epic 7)
#
# Warning threshold: 300 seconds (5 minutes) of Modbus poll silence.
# To change the threshold:
#   1. Edit WALLBOX_POLL_WARNING_THRESHOLD in sensor.py
#   2. Restart Home Assistant
#   (No changes to this YAML file required)
#
# Dependencies: none — uses only built-in HA card types (conditional, entities).
# No HACS or custom card installation required.

- type: conditional
  # Normal state: wallbox is polling — no warning
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
  # Warning state: no Modbus poll received for >300 s (5 minutes)
  # The card title gains ⚠ to signal the issue at a glance.
  # To suppress this warning, ensure the wallbox is polling the Modbus server.
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
        # WARNING: No Modbus poll received for >5 minutes.
        # Check wallbox network connectivity and Modbus TCP port 5020.
```

### How to Add This Card to HA

1. Open Home Assistant → Overview dashboard → Edit dashboard (pencil icon).
2. Click **Add Card** → **Manual card** (or open the **Raw configuration editor**).
3. Paste the YAML above (both `conditional` blocks).
4. Click **Save**.

The card requires no configuration in `configuration.yaml`. All referenced entities are
registered automatically by `async_setup_platform` — no template sensor or helper entity
is needed.

### HA Card Type Compatibility Note

The `conditions` syntax using `condition: state` under each item is the HA 2023.9+
format. For HA < 2023.9, the legacy format is:

```yaml
conditions:
  - entity: binary_sensor.sdm_wallbox_poll_warning
    state: "off"
```

Because this project targets Home Assistant with `pymodbus >= 3.11.1` (and therefore a
modern HA version), use the new `condition: state` syntax. If the file needs to support
older HA installations, use the legacy format — both are functionally identical and HA
accepts either.

### Entity IDs Referenced

| YAML entity ID | Sensor class | Story |
|---|---|---|
| `sensor.sdm_raw_surplus` | `SDM630RawSurplusSensor` | 6-1 |
| `sensor.sdm_reported_surplus` | `SDM630ReportedSurplusSensor` | 6-1 |
| `sensor.sdm_wallbox_last_poll` | `SDM630WallboxLastPollSensor` | 7-1 |
| `binary_sensor.sdm_wallbox_poll_warning` | `SDM630WallboxPollWarningSensor` | 7-2 |

All four entities must be implemented (stories 6-1, 7-1, 7-2) before the card is
functional. The YAML file itself can be created independently.

### Dependency on Stories 6-1, 7-1, 7-2

This story has no code dependency — the YAML file can be created before the sensor
entities exist. The card will show errors in the HA dashboard until all four sensor
entities are registered. This is expected and acceptable; the card is a documentation
artefact.

### Why `docs/` Folder

The `docs/` folder already exists in the project root and is used for documentation
artefacts. The Lovelace card YAML is not a Home Assistant configuration file — it must
be manually pasted into the dashboard by Ghost. Placing it in `docs/` keeps it alongside
other project documentation and out of the HA component directory.

### What NOT To Do

- **DO NOT** add this file to `custom_components/sdm630_simulator/` — it is not loaded
  by HA automatically and would cause a component load error.
- **DO NOT** add any Python code — this story is purely a YAML documentation artefact.
- **DO NOT** use `custom:` card types or reference any HACS card — FR11 requires
  standard built-in HA cards only.
- **DO NOT** add `state_color: true` to the entities card — this only applies colours to
  domain-specific states, not to arbitrary warning conditions.
- **DO NOT** create a `template:` binary sensor in `configuration.yaml` — the warning
  binary sensor is a Python entity registered by `async_setup_platform` (Story 7-2).

### Project Structure Notes

- The `docs/` folder is at the workspace root: `docs/lovelace-wallbox-card.yaml`.
- No changes to any Python file or `configuration.yaml`.
- After this story is done, Epic 8 can be closed.

### References

- Epic spec: [_bmad-output/planning-artifacts/epics-wallbox-dashboard-extension.md](../../_bmad-output/planning-artifacts/epics-wallbox-dashboard-extension.md) — Epic 3, Story 3.1
- PRD: [_bmad-output/planning-artifacts/prd-wallbox-dashboard-extension.md](../../_bmad-output/planning-artifacts/prd-wallbox-dashboard-extension.md) — Implementation Notes / Lovelace Orange State Strategy
- Previous story: [_bmad-output/implementation-artifacts/7-2-implement-5-minute-warning-binary-sensor.md](7-2-implement-5-minute-warning-binary-sensor.md)
- HA Conditional Card docs: <https://www.home-assistant.io/dashboards/conditional/>

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

### File List
