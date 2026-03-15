---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
status: complete
inputDocuments:
  - _bmad-output/planning-artifacts/product-brief-sdm630-simulator-2026-03-15.md
  - AGENTS.md
  - README.md
  - growat-modbus/Homeassistant-Growatt-Local-Modbus/custom_components/growatt_local/sensor_types/storage.py
  - growat-modbus/Homeassistant-Growatt-Local-Modbus/custom_components/growatt_local/sensor_types/inverter.py
  - growat-modbus/Homeassistant-Growatt-Local-Modbus/custom_components/growatt_local/API/device_type/base.py
  - growat-modbus/Homeassistant-Growatt-Local-Modbus/custom_components/growatt_local/API/device_type/storage_120.py
documentCounts:
  briefs: 1
  research: 0
  brainstorming: 0
  projectDocs: 5
classification:
  projectType: iot_embedded
  domain: energy
  complexity: high
  projectContext: brownfield
workflowType: 'prd'
---

# Product Requirements Document - sdm630-simulator

**Author:** Ghost
**Date:** 2026-03-15

## Executive Summary

The SDM630 Simulator extends an existing Home Assistant custom component to serve as an intelligent energy broker between a Growatt SPH10000TL3-BH-UP hybrid inverter (10 kWh battery) and a Growatt THOR 11AS-P-V1 wallbox. The existing component already simulates an Eastron SDM630 smart meter via Modbus TCP. This PRD defines the new intelligent surplus stabilization logic that uses battery SOC, time-of-day, weather forecasts, and solar production data to present a stabilized surplus signal to the wallbox — enabling reliable PV surplus EV charging even during fluctuating solar conditions.

The system enforces a strict priority: household energy autonomy first, EV charging second, grid feed-in as last resort. A hard SOC floor of 50% is never violated. Season- and forecast-aware SOC targets at sunset ensure the household battery covers overnight needs. The wallbox's 4.1 kW minimum surplus threshold is met through intelligent battery buffering, with a safety margin of 4.2 kW reported to prevent edge-case dropouts.

### What Makes This Special

The simulator exploits an architectural gap in the Growatt ecosystem: the THOR wallbox reads a standard meter for surplus detection but has no awareness of battery storage, weather, or time. By intercepting this communication via Modbus simulation, the system injects intelligence that neither the wallbox nor the inverter provide alone. The 10 kWh battery — already present for household use — becomes a dynamic buffer for EV charging without any hardware modifications. Three data dimensions (real-time inverter telemetry, solar/weather forecast, time-based strategy) converge into a single stabilized power value that the wallbox consumes as if from a physical meter.

## Project Classification

- **Project Type:** IoT/Embedded — Modbus protocol simulation, hardware communication (wallbox, inverter), sensor data processing, Home Assistant custom component
- **Domain:** Energy — PV surplus management, battery storage control, smart-grid-adjacent logic
- **Complexity:** High — Real-time decisions across multiple data sources (SOC, weather, time), fail-safe requirements, hardware protocol communication
- **Project Context:** Brownfield — Existing SDM630 simulator with functional Modbus TCP server, register implementation, and Home Assistant sensor integration. Adding intelligent surplus calculation engine.

## Success Criteria

### User Success

- **Zero morning grid draws**: The household never needs to pull power from the grid before PV production starts due to a depleted battery. This is the absolute top-priority success criterion.
- **Hands-off operation**: The system runs fully autonomously day after day. Ghost never needs to manually intervene, check, or adjust the surplus logic during normal operation.
- **Stable EV charging sessions**: Once PV surplus charging starts, it runs continuously without stop/start cycling for at least 10 minutes per session, even during partly cloudy conditions.
- **Evening peace of mind**: Battery SOC at sunset meets the seasonal target (100% winter, 90–100% spring/autumn, 70–100% summer), dynamically adjusted by weather forecast.

### Business Success

*N/A — Personal project. No commercial objectives.*

The singular success metric: **Self-produced energy is consumed intelligently — household first, EV second, grid only as last resort.**

### Technical Success

- **SOC floor enforcement**: Battery SOC never drops below 50% under any circumstances — this is a hard, non-negotiable constraint.
- **Modbus reliability**: The simulated SDM630 responds to wallbox Modbus queries without communication failures or timeouts.
- **Signal stability**: The reported surplus value uses hysteresis (minimum 10-minute hold) to prevent wallbox start/stop cycling.
- **Fail-safe behavior**: On data loss (inverter offline, HA restart, sensor unavailability), the system defaults to reporting 0 kW surplus — never risks draining the battery.
- **Forecast integration**: Weather/solar forecast data is consumed and influences SOC buffer decisions within each evaluation cycle.

### Measurable Outcomes

| Outcome | Target | Measurement Method |
|---------|--------|-----------|
| Morning grid draws | 0 per month | HA energy dashboard: grid import before sunrise |
| SOC floor violations | 0 ever | HA history: SOC sensor minimum |
| Charging interruptions per session | 0 (while buffer available) | HA logbook: wallbox state transitions |
| Self-consumption ratio | > 80% | HA energy dashboard: production vs. export |
| Evening SOC vs. target | Within 10% of seasonal target | Custom HA sensor: actual SOC at sunset vs. target |
| Manual interventions | 0 per week | User experience (subjective) |

## Product Scope

*Detailed scoping, MVP feature set, phased development plan, and risk mitigation strategy are defined in the [Project Scoping & Phased Development](#project-scoping--phased-development) section below.*

## User Journeys

### Journey 1: Ghost — Sunny Day with Clouds (Primary, Success Path)

**Opening Scene:** It's a Tuesday in June, 10:45 AM. Ghost left for work hours ago, the EV parked in the garage, plugged in as always. The PV array is producing 8 kW, the house consumes 1.2 kW, and the battery hit 100% SOC twenty minutes ago. The surplus is a comfortable 6.8 kW, well above the 4.2 kW threshold.

**Rising Action:** At 11:30, clouds roll in. PV drops to 3.5 kW — real surplus is only 2.3 kW, well below the wallbox's 4.1 kW threshold. Without the simulator, charging would stop. But the simulator checks: SOC is 98%, it's before 15:00, the forecast shows partly cloudy with clearing by 13:00. The allowed SOC floor for this time window is 50%. The simulator calculates: 2.3 kW real surplus + battery buffer available → reports 4.2 kW to the wallbox. Charging continues uninterrupted.

**Climax:** Between 11:30 and 13:00, PV fluctuates between 2 kW and 7 kW every few minutes. The simulator smooths this out — the wallbox sees a stable surplus signal, never dropping below 4.2 kW. The battery absorbs the dips, the SOC drops from 98% to 82%. At 13:00 the sky clears, PV jumps to 9 kW, the battery recharges, and the simulator reports the full real surplus of 7.8 kW to the wallbox — the car charges faster.

**Resolution:** Ghost comes home at 18:30. The EV gained 25 kWh during the day. The battery is at 88% SOC — well above the summer sunset target of 70%. The HA energy dashboard shows 92% self-consumption. Ghost didn't touch a thing all day.

### Journey 2: Ghost — Worst Case: Bad Weather Day (Primary, Edge Case)

**Opening Scene:** A grey November day. PV peaks at 2 kW around noon. The battery is at 85% SOC from yesterday (it wasn't a great day either). Tomorrow's forecast: also overcast.

**Rising Action:** The simulator evaluates: it's November, sunset SOC target is 100%. Current SOC is 85% and dropping slowly from household consumption. PV barely covers the house load. There is no surplus to report.

**Climax:** The simulator calculates: 0 kW surplus, SOC below target, poor forecast for tomorrow. Decision: report 0 kW to the wallbox. The car doesn't charge today. The battery is preserved entirely for the household.

**Resolution:** The simulator did exactly the right thing — nothing. The battery provides household power through the evening and night. Next morning at 7 AM, SOC is at 62% — the household didn't need grid power. The EV stayed at whatever charge it had, but the house is autonomous. Priority enforced.

### Journey 3: Ghost's Wife — Emergency Full Charge Override (Secondary User)

**Opening Scene:** It's Saturday morning. The family needs to drive 400 km tomorrow. The EV is at low charge. Ghost's wife knows the car needs to be fully charged by tonight.

**Rising Action:** She opens the Growatt app on her phone and switches the wallbox from "PV surplus" mode to "full charge" mode. The wallbox draws maximum power regardless of what the simulator reports.

**Climax:** The wallbox charges at full power directly from the grid + PV + battery. The simulator's reported surplus becomes irrelevant — the wallbox is in override mode. The simulator continues to monitor and log, but its signal is not controlling the wallbox in this mode.

**Resolution:** The EV is fully charged by evening. Ghost switches the wallbox back to PV surplus mode the next day. The simulator resumes intelligent control. No configuration changes needed, no HA interaction required.

### Journey 4: Ghost — System Setup and Tuning (Admin/Configuration)

**Opening Scene:** Ghost has just installed the intelligent surplus logic update. The existing Modbus infrastructure works. He needs to configure the new parameters.

**Rising Action:** In `configuration.yaml`, Ghost sets the entity IDs for the Growatt sensors (SOC, power-to-grid, PV production), the `forecast_solar` entity, and the initial strategy parameters (SOC floor: 50%, seasonal targets). He restarts Home Assistant.

**Climax:** The simulator starts up, validates that all configured entities exist and are reporting data. It logs its initial state: "SOC: 95%, surplus: 5.2 kW, forecast: sunny, sunset target: 75%, buffer available: 45%. Reporting 5.2 kW to wallbox." Ghost checks the HA log and sees the decision logic working as expected.

**Resolution:** After a few days of monitoring the logs, Ghost verifies the system behaves correctly. He adjusts one parameter — the afternoon SOC protection threshold — based on real-world observation. From this point on, the system runs autonomously.

### Journey 5: Ghost — Troubleshooting: Inverter Offline (Error Recovery)

**Opening Scene:** A thunderstorm caused the Growatt inverter to temporarily disconnect from HA. The simulator suddenly gets no data from the SOC, power-to-grid, and PV production sensors.

**Rising Action:** The simulator detects that entity states are `unavailable`. The fail-safe triggers immediately: report 0 kW surplus to the wallbox.

**Climax:** The wallbox stops charging. The simulator logs: "FAIL-SAFE: Inverter entities unavailable. Reporting 0 kW. Reason: sensor.growatt_soc = unavailable." Ghost sees this in the HA notification or log later.

**Resolution:** 20 minutes later, the inverter reconnects. Sensor values return to normal. The simulator resumes intelligent surplus calculation. Charging restarts if conditions permit. No battery was drained, no data was corrupted. Ghost reviews the log and sees exactly what happened and why.

### Journey Requirements Summary

| Journey | Capabilities Revealed |
|---------|----------------------|
| Sunny day with clouds | Surplus calculation, SOC buffer logic, time-based strategy, hysteresis, forecast integration |
| Bad weather day | Conservative mode, SOC target enforcement, priority decision (household > EV), forecast-driven no-charge decision |
| Emergency override | Graceful coexistence with wallbox's own modes, no interference when bypassed |
| System setup | YAML configuration, entity validation, startup logging, parameter tuning |
| Inverter offline | Fail-safe triggering, entity state monitoring, automatic recovery, decision logging |

## Domain-Specific Requirements

### Energy Domain Context

This project operates in the residential energy self-consumption domain — not utility-grade grid infrastructure. The relevant domain constraints are practical rather than regulatory. No grid operator certification, NERC compliance, or utility-scale safety standards apply. However, the system interacts with real electrical hardware (inverter, battery, wallbox) and incorrect behavior can cause financial loss (wasted energy, grid dependency) or equipment stress (battery over-cycling).

### Safety Constraints

- **Battery protection**: The 50% SOC hard floor protects the lithium battery from deep discharge cycles that reduce lifespan. This is not just a user preference — it's a battery health requirement.
- **No direct hardware control**: The simulator only writes Modbus register values that the wallbox reads passively. It cannot force the wallbox to charge or draw power. The wallbox always makes its own charging decision based on what it reads. This limits the blast radius of any software bug.
- **Fail-safe default**: On any error condition, the system reports 0 kW — the safest possible state. The wallbox stops charging, the battery is preserved.

### Technical Constraints

- **Real-time data dependency**: The system depends on near-real-time sensor data from the Growatt inverter (SOC, power values update every few seconds). Stale data leads to incorrect surplus calculations.
- **Modbus protocol compliance**: The wallbox expects a standards-compliant SDM630 Modbus response. Register addresses, data encoding (IEEE 754 float, big-endian), and timing must match the SDM630 specification exactly. The existing simulator already handles this.
- **Home Assistant lifecycle**: The component must handle HA restarts, entity unavailability during startup, and sensor value transitions gracefully. HA entities may be `unknown` or `unavailable` during initialization.

### Integration Requirements

- **Growatt Local Modbus integration**: Provides all inverter/battery sensor entities. Must be installed and configured with the correct protocol version (RTU Protocol 2 v1.24 for SPH hybrid inverters).
- **Forecast.Solar integration**: Provides PV production forecast. Must be configured with correct panel orientation, tilt, and kWp rating. Setup instructions must be documented.
- **Home Assistant Weather integration**: Any weather integration providing `weather.get_forecasts` with `cloud_coverage` data (e.g., OpenWeatherMap, Met.no).
- **Sun integration**: Built-in `sun.sun` entity for sunrise/sunset times. Available by default in HA.

### Risk Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Inverter data goes stale (sensor stops updating but shows last value) | Surplus calculated from outdated data, battery may drain | Implement staleness detection: if sensor timestamp hasn't changed in > 60s, trigger fail-safe |
| Forecast.Solar unavailable | Cannot assess future PV production | Fall back to conservative mode: use seasonal defaults without forecast adjustment |
| Battery degrades over time (actual capacity < 10 kWh) | SOC percentages become misleading | SOC floor at 50% provides large safety margin regardless of actual capacity |
| Wallbox firmware update changes Modbus behavior | Surplus signal no longer interpreted correctly | Log wallbox read patterns, alert on unexpected register queries |

## Innovation & Novel Patterns

### Detected Innovation Areas

1. **Constructive Modbus Deception**: The core innovation is simulating a physical smart meter to inject intelligence into a "dumb" communication channel. The wallbox believes it reads a real SDM630 meter — but the values are dynamically computed from multiple data sources. This "man-in-the-middle" pattern for energy optimization is novel in the residential PV space.

2. **Battery-as-Buffer Repurposing**: The home battery's primary purpose is household autonomy. This system repurposes it as a secondary EV charging buffer — not by controlling the battery directly, but by allowing the simulator to "promise" surplus that will temporarily come from the battery. The battery doesn't know it's being used for EV charging smoothing; the inverter manages charge/discharge automatically based on grid demand.

3. **Three-Dimensional Decision Space**: Combining real-time telemetry (SOC, power flow), temporal strategy (time-of-day, season, sunrise/sunset), and predictive data (weather forecast, solar production estimate) into a single scalar output (kW surplus) is a multi-dimensional optimization problem reduced to a simple Modbus register value.

### Market Context & Competitive Landscape

No existing Home Assistant integration or commercial product combines SDM630 meter simulation with battery-aware surplus stabilization. Existing solutions:
- **Wallbox-native PV surplus**: Uses real meter data only, no battery awareness
- **Home energy management systems (HEMS)**: Commercial solutions (e.g., SMA Sunny Home Manager) exist but require proprietary ecosystems and don't work with Growatt THOR wallbox
- **HA automations**: Users can build automations to start/stop charging, but cannot simulate a Modbus meter to enable the wallbox's built-in PV surplus mode

### Validation Approach

1. **Staged rollout**: Start with conservative parameters (high SOC floor, small buffer), observe behavior over days, then gradually increase buffer allowance
2. **Logging-first**: Every decision logged with full context (SOC, surplus, forecast, time, reported value) — enables post-hoc validation before trusting the system
3. **Dry-run mode**: Option to log what the simulator *would* report without actually writing to the Modbus register — validate logic without affecting the wallbox

### Risk Mitigation

| Innovation Risk | Mitigation |
|----------------|------------|
| Wallbox rejects simulated meter values | Existing simulator already validated — Modbus compliance proven |
| Battery drains faster than predicted | Hard SOC floor (50%) prevents dangerous depletion regardless of algorithm errors |
| Forecast data leads to wrong decisions | Conservative fallback: without forecast, use most protective seasonal defaults |
| Complexity of three-dimensional logic makes bugs hard to find | Comprehensive decision logging; each evaluation cycle logs all inputs and the resulting output |

## IoT/Embedded Specific Requirements

### Project-Type Overview

This is a software-only IoT component that communicates with physical hardware (Growatt inverter, THOR wallbox) via Modbus protocol. No custom hardware is designed or manufactured. The "embedded" aspect is the Modbus TCP server running as a Home Assistant custom component on commodity hardware (Raspberry Pi, NUC, or similar HA host).

### Hardware Requirements

| Component | Role | Interface | Existing? |
|-----------|------|-----------|----------|
| Growatt SPH10000TL3-BH-UP | Hybrid inverter with 10 kWh battery | Modbus RTU via Growatt Local HA integration | Yes |
| Growatt THOR 11AS-P-V1 | Wallbox, reads SDM630 meter | Modbus TCP (reads from simulator on port 5020) | Yes |
| Home Assistant host | Runs simulator component | Python 3.9+, pymodbus ≥ 3.9.2 | Yes |
| Network | LAN connectivity between HA host and wallbox | TCP/IP, port 5020 | Yes |

No additional hardware is required. The simulator is a pure software component.

### Connectivity Protocol

- **Wallbox ↔ Simulator**: Modbus TCP on port 5020. The wallbox acts as Modbus client, the simulator as Modbus server. Register map follows SDM630 specification (IEEE 754 float, big-endian, two consecutive 16-bit registers per value).
- **Simulator ↔ Inverter**: Indirect — the simulator reads HA entity states provided by the Growatt Local Modbus integration. No direct Modbus communication between simulator and inverter.
- **Simulator ↔ HA Services**: HA service calls for `weather.get_forecasts` and `forecast_solar` sensor entities. Standard HA async API.

### Power Profile

Not applicable for the software component itself. The HA host runs 24/7 regardless of this component. No additional power consumption.

For the *energy system* being managed:
- PV array peak production: ~10 kWp (assumed based on inverter capacity)
- Battery: 10 kWh usable capacity, SOC range 50%–100% for this system
- Wallbox: 11 kW max charging power, 4.1 kW minimum for PV surplus mode
- Household base load: ~1–2 kW typical

### Security Model

- **No external network access**: The simulator operates entirely within the local network. No cloud connectivity, no external API calls (except HA weather/forecast integrations which HA handles).
- **No authentication on Modbus**: Standard for industrial Modbus TCP — the wallbox connects to port 5020 without authentication. This is acceptable because the system operates on a private LAN.
- **No sensitive data**: The simulator processes power values and SOC percentages only. No personal data, no credentials, no financial information.
- **Input validation**: All sensor values from HA entities are validated (numeric range checks, unavailable/unknown state handling) before use in calculations.

### Update Mechanism

- **Manual update**: Copy updated component files to `custom_components/sdm630_simulator/` and restart HA. No OTA mechanism needed for a personal project.
- **Configuration changes**: YAML-based configuration in `configuration.yaml`. Changes require HA restart.
- **No versioning required**: Single-user project with direct file access.

### Implementation Considerations

- **Evaluation cycle**: The surplus calculation should run on a configurable interval (default: 10–30 seconds) to balance responsiveness with CPU load.
- **Async architecture**: Must use `async/await` patterns to integrate with HA's event loop. No blocking I/O in the main loop.
- **Existing code integration**: The intelligent surplus logic integrates into the existing `sensor.py` (state change handler) and `modbus_server.py` (register updates). The Modbus server infrastructure is already functional.
- **Logging granularity**: Configurable log levels — `DEBUG` for full decision traces during tuning, `INFO` for daily operation summaries, `WARNING` for fail-safe activations.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-Solving MVP — Deliver the core intelligent surplus stabilization that solves the primary problem (unreliable PV surplus charging). No UI, no analytics, no fancy features. Just: *the wallbox charges reliably from solar surplus, and the household battery is protected.*

**Resource Requirements:** Single developer (Ghost), Python/HA knowledge, existing codebase. No external dependencies beyond HA integrations that must be configured (Growatt Local Modbus, Forecast.Solar, Weather).

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**
- Journey 1 (Sunny day with clouds) — Full support
- Journey 2 (Bad weather day) — Full support
- Journey 4 (System setup) — Full support
- Journey 5 (Inverter offline) — Full support
- Journey 3 (Emergency override) — Passive support (wallbox override works independently, simulator doesn't interfere)

**Must-Have Capabilities:**

| # | Capability | Justification |
|---|-----------|---------------|
| 1 | Surplus calculation engine | Core value — without this, the product doesn't exist |
| 2 | Time-based SOC strategy (floor + seasonal targets) | Without this, the battery drains and priority #1 (household) fails |
| 3 | Weather/solar forecast integration | Without this, the system can't anticipate and will be too conservative or too aggressive |
| 4 | Stabilized Modbus signal with hysteresis | Without this, the wallbox still cycles start/stop |
| 5 | Fail-safe mechanisms | Without this, a bug could drain the battery — deal-breaker |
| 6 | Decision logging | Without this, tuning and debugging are impossible — essential for staged rollout |
| 7 | YAML configuration for entity mappings and thresholds | Without this, the system can't be set up |

**Explicitly NOT in MVP:**
- Dashboard (monitoring works via HA logs and existing HA energy dashboard)
- Vehicle SOC integration (EV not yet purchased, wallbox doesn't expose it)
- Dry-run mode (nice-to-have, but logging + conservative defaults suffice for validation)
- Historical analytics
- Adaptive/learning algorithms

### Post-MVP Features

**Phase 2 (Growth) — After MVP validation (~weeks of operation):**
- Home Assistant dashboard with dedicated surplus monitoring views
- Dry-run mode for testing parameter changes safely
- Staleness detection for sensor data (currently handled by unavailable state only)
- Parameter fine-tuning based on real-world observations

**Phase 3 (Expansion) — Future:**
- Vehicle SOC integration (when EV API/WiFi becomes available)
- Adaptive algorithms learning from historical data
- Multi-meter protocol support (Chint etc.)
- Electricity price awareness for tariff optimization

### Risk Mitigation Strategy

**Technical Risks:**
- *Most challenging aspect:* The three-dimensional decision logic (SOC × time × forecast). Mitigated by conservative defaults, comprehensive logging, and staged parameter adjustment.
- *Simplification:* Start with fixed seasonal thresholds; add forecast-driven dynamic adjustment incrementally.
- *Riskiest assumption:* That the forecast data is accurate enough to inform buffer decisions. Mitigated by always keeping 50% SOC floor and conservative fallback without forecast.

**Resource Risks:**
- *Single developer:* If Ghost has limited time, the MVP can be further stripped — start without forecast integration (use seasonal defaults only), add forecast later. This still solves the core problem.
- *Minimum viable scope:* Surplus calculation + SOC floor + hysteresis = already valuable without forecast intelligence.

## Functional Requirements

### Surplus Calculation

- **FR1:** The system can read real-time SOC percentage from the Growatt inverter entity in Home Assistant
- **FR2:** The system can read real-time power-to-grid value from the Growatt inverter entity in Home Assistant
- **FR3:** The system can read real-time PV production power from the Growatt inverter entity in Home Assistant
- **FR4:** The system can read real-time household consumption (power-user-load) from the Growatt inverter entity in Home Assistant
- **FR5:** The system can calculate the available surplus power considering current PV production, household consumption, and grid feed-in
- **FR6:** The system can determine the available battery buffer capacity based on current SOC minus the applicable SOC floor

### SOC Strategy & Battery Protection

- **FR7:** The system can enforce a hard SOC floor of 50% that is never violated under any circumstances
- **FR8:** The system can determine a seasonal SOC target at sunset based on the current month (100% winter, 90–100% spring/autumn, 70–100% summer)
- **FR9:** The system can read sunrise and sunset times from the Home Assistant `sun.sun` entity
- **FR10:** The system can adjust the allowed SOC buffer based on time of day (conservative before battery is full, generous midday, protective in afternoon)
- **FR11:** The system can dynamically adjust the SOC target based on weather/solar forecast quality (poor forecast → higher target, good forecast → more buffer)

### Weather & Solar Forecast Integration

- **FR12:** The system can query PV production forecast data from the `forecast_solar` integration in Home Assistant
- **FR13:** The system can query weather forecast data (cloud coverage, conditions) from a Home Assistant weather entity via `weather.get_forecasts`
- **FR14:** The system can classify forecast quality (good/moderate/poor) to influence SOC buffer decisions
- **FR15:** The system can fall back to conservative seasonal defaults when forecast data is unavailable

### Modbus Signal Management

- **FR16:** The system can report a calculated surplus power value (in kW) to the wallbox via SDM630 Modbus TCP registers
- **FR17:** The system can guarantee a minimum reported surplus of 4.2 kW when battery buffer permits charging
- **FR18:** The system can report the actual surplus when it exceeds 4.2 kW
- **FR19:** The system can apply hysteresis to the surplus signal — once charging is signaled, the minimum 4.2 kW is held for at least 10 minutes before dropping
- **FR20:** The system can report 0 kW surplus to stop wallbox charging when conditions require it

### Wallbox Charging Detection

- **FR21:** The system can detect that the wallbox is actively charging the EV by observing increased household consumption or power flow changes in the inverter data
- **FR22:** The system can adjust the reported surplus to account for the wallbox's own power draw during active charging

### Fail-Safe & Error Handling

- **FR23:** The system can detect when inverter sensor entities are in `unavailable` or `unknown` state
- **FR24:** The system can immediately report 0 kW surplus when any critical sensor entity becomes unavailable (fail-safe)
- **FR25:** The system can automatically resume normal surplus calculation when sensor entities recover to valid states
- **FR26:** The system can validate sensor values are within plausible ranges before using them in calculations

### Decision Logging

- **FR27:** The system can log each surplus evaluation cycle with all input values (SOC, PV power, grid power, household consumption, forecast quality, time)
- **FR28:** The system can log the calculated surplus decision and the reported Modbus value with the reasoning
- **FR29:** The system can log fail-safe activations with the specific trigger reason
- **FR30:** The system can support configurable log levels (DEBUG for full traces, INFO for summaries, WARNING for fail-safes)

### Configuration

- **FR31:** The user can configure the Growatt inverter entity IDs (SOC, power-to-grid, PV production, household load) via YAML
- **FR32:** The user can configure the forecast entity IDs (forecast_solar, weather) via YAML
- **FR33:** The user can configure the SOC floor value via YAML (default: 50%)
- **FR34:** The user can configure the seasonal SOC sunset targets via YAML
- **FR35:** The user can configure the minimum surplus threshold via YAML (default: 4.2 kW)
- **FR36:** The user can configure the hysteresis duration via YAML (default: 10 minutes)
- **FR37:** The user can configure the evaluation cycle interval via YAML (default: 10–30 seconds)
- **FR38:** The system can validate configured entity IDs exist and are reporting data on startup

## Non-Functional Requirements

### Reliability

- **NFR1:** The system must remain operational 24/7 as a Home Assistant component — no manual restarts required for normal operation
- **NFR2:** The system must recover automatically from HA restarts — resume surplus calculation within 60 seconds of entity availability
- **NFR3:** The fail-safe (0 kW report) must activate within 1 evaluation cycle (≤ 30 seconds) of detecting sensor unavailability
- **NFR4:** The Modbus TCP server must maintain persistent connectivity with the wallbox — no connection drops during normal operation
- **NFR5:** The system must tolerate transient sensor state changes (`unknown` → valid value) during HA startup without triggering unnecessary fail-safes (grace period of 60 seconds after HA restart)

### Performance

- **NFR6:** The surplus evaluation cycle must complete within 1 second of execution, including all sensor reads, forecast queries, and calculation
- **NFR7:** The Modbus TCP response to wallbox register reads must be served within 100ms (existing pymodbus server performance)
- **NFR8:** The system's CPU and memory footprint must be negligible on the HA host — no measurable impact on HA responsiveness (< 1% CPU average, < 50 MB RAM)

### Integration

- **NFR9:** The system must be compatible with pymodbus ≥ 3.9.2
- **NFR10:** The system must work with Home Assistant 2024.x and later
- **NFR11:** The system must function with any weather integration that supports the `weather.get_forecasts` service call with `cloud_coverage` data
- **NFR12:** The system must function with the Forecast.Solar integration for PV production estimates
- **NFR13:** The system must function with the Growatt Local Modbus integration (RTU Protocol 2 v1.24 for SPH hybrid inverters)

### Maintainability

- **NFR14:** All configuration parameters must be adjustable via `configuration.yaml` without code changes
- **NFR15:** Decision logs must contain sufficient context (all inputs + output + reasoning) to diagnose any surplus calculation issue post-hoc
- **NFR16:** The surplus calculation logic must be structured as a separable module — independent from Modbus server code and HA sensor code — to enable unit testing

### Data Integrity

- **NFR17:** The system must never write invalid IEEE 754 float values to Modbus registers (NaN, Infinity, or negative power values when reporting surplus)
- **NFR18:** Sensor values must be validated before use: SOC must be 0–100%, power values must be non-negative (or appropriately signed for bidirectional flow)
