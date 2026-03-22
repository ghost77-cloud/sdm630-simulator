---
stepsCompleted: [1, 2, 3, 4, 5, 6]
status: complete
inputDocuments:
  - AGENTS.md
  - README.md
  - growat-modbus/Homeassistant-Growatt-Local-Modbus/README.md
  - growat-modbus/Homeassistant-Growatt-Local-Modbus/custom_components/growatt_local/sensor_types/storage.py
date: 2026-03-15
author: Ghost
---

# Product Brief: sdm630-simulator

## Executive Summary

The SDM630 Simulator is a Home Assistant custom component that acts as an intelligent energy broker between a Growatt SPH10000TL3-BH-UP hybrid inverter (with 10 kWh battery storage) and a Growatt THOR 11AS-P-V1 wallbox. By simulating an Eastron SDM630 smart meter via Modbus TCP, it presents a stabilized surplus power signal to the wallbox, enabling reliable PV surplus charging even during fluctuating solar conditions. The simulator uses battery state-of-charge (SOC), time-of-day, and weather/solar forecast data from Home Assistant to dynamically determine how much battery buffer can safely be used — ensuring the household remains powered in the evening while maximizing EV charging from self-produced solar energy rather than feeding excess to the grid.

---

## Core Vision

### Problem Statement

The Growatt THOR 11AS-P-V1 wallbox requires a minimum of 4.1 kW grid feed-in (surplus) to initiate EV charging in PV surplus mode. During partly cloudy conditions, solar production fluctuates rapidly — surplus drops below 4.1 kW, charging stops, surplus recovers, charging restarts — resulting in unreliable, fragmented charging sessions. This effectively renders PV surplus charging unusable for a significant portion of otherwise productive solar days.

### Problem Impact

- **Wasted solar energy**: Surplus power is fed to the grid at low feed-in tariffs instead of being used for EV charging
- **Poor user experience**: Constant start/stop cycling of the charging session
- **Underutilized battery storage**: The 10 kWh battery exists but isn't leveraged to smooth out solar fluctuations for EV charging
- **Manual intervention required**: No intelligent automation exists — the user would need to manually monitor and decide when to charge

### Why Existing Solutions Fall Short

The wallbox's built-in PV surplus charging mode relies solely on the real-time grid meter reading. It has no concept of battery storage, weather forecasts, or time-based strategy. The Growatt ecosystem's native tools don't bridge the gap between the hybrid inverter's intelligence and the wallbox's simple surplus-detection logic. No existing Home Assistant integration simulates an SDM630 meter with intelligent surplus stabilization.

### Proposed Solution

An intelligent SDM630 Modbus simulator that:

1. **Reads real-time data** from the Growatt inverter via the Growatt Local Modbus integration (SOC, power-to-grid, charge/discharge power, PV production)
2. **Queries weather/solar forecasts** from Home Assistant (`forecast_solar` for production estimates, `weather.get_forecasts` for cloud coverage)
3. **Applies time-aware battery strategy**:
   - Before ~11:00 (battery likely still charging): Conservative — only report real surplus
   - 11:00–15:00 (battery full, peak sun hours): Allow SOC to drop to 50% as buffer — guarantee minimum 4.2 kW surplus signal
   - After 15:00 (evening approaching): Allow SOC to drop only to 80% — preserve battery for household evening needs
   - These thresholds dynamically adjust based on solar forecast for remaining daylight
4. **Reports stabilized surplus** to the wallbox via Modbus, ensuring the 4.2 kW minimum is maintained when buffer is available, and reporting actual higher surplus when available
5. **Detects wallbox charging** (increased consumption visible through inverter data) and adjusts reported surplus accordingly

### Key Differentiators

- **Battery-aware surplus stabilization**: No other solution uses the home battery as a buffer specifically to smooth PV surplus for wallbox charging
- **Time-and-weather-aware strategy**: Dynamic SOC floor based on time of day and solar production forecast ensures the household isn't left without evening power
- **Zero hardware changes**: Pure software solution using existing Modbus infrastructure — the wallbox "thinks" it's talking to a real SDM630 meter
- **Self-produced energy priority**: Maximizes self-consumption by directing surplus to the EV rather than the grid, while protecting household evening needs

---

## Target Users

### Primary Users

**Ghost — PV Self-Consumption Optimizer (Owner & Sole User)**

- **Context**: Homeowner with a complete Growatt solar ecosystem: SPH10000TL3-BH-UP hybrid inverter, 10 kWh battery storage, PV array, and a Growatt THOR 11AS-P-V1 wallbox. Runs Home Assistant as the central smart home platform with the Growatt Local Modbus integration already operational.
- **Technical Level**: Intermediate — comfortable with Home Assistant custom components, YAML configuration, Modbus concepts, and basic Python. The existing SDM630 simulator infrastructure is already running; only the intelligent surplus stabilization logic is missing.
- **Motivation**: Maximize self-consumption of solar energy by intelligently charging the EV from PV surplus, rather than feeding excess energy to the grid. Ensure the household battery is sufficiently charged for evening use.
- **Current Frustration**: The wallbox requires a minimum of 4.1 kW grid feed-in to start PV surplus charging. Cloud fluctuations cause constant start/stop cycling, making surplus charging unreliable. Energy that could charge the EV is instead fed to the grid at low tariffs.
- **Daily Routine**: The EV is plugged in whenever parked in the garage. Charging should happen automatically and intelligently without user intervention. Only exception: when a full charge is needed urgently, Ghost or his wife manually switches to "full charge" mode via the Growatt app.
- **Success Criteria**: "The car charges from solar surplus whenever possible. The house battery is still full enough for the evening. I don't have to think about it."

### Secondary Users

**Ghost's Wife — Occasional Override User**

- **Context**: Uses the Growatt app to switch the wallbox to "full charge" mode when the EV needs to be fully charged quickly (e.g., before a long trip).
- **Interaction**: Minimal — only overrides the default surplus-charging behavior when needed. Does not interact with Home Assistant or the simulator directly.
- **Need**: Simple, reliable override that "just works" via the existing app.

### User Journey

1. **Setup (one-time)**: Ghost configures the intelligent surplus logic parameters (SOC thresholds, time windows) in Home Assistant. The Modbus connection between simulator and wallbox is already established.
2. **Daily Operation (fully automatic)**: EV is plugged in → Simulator monitors inverter data, SOC, time, and weather forecast → Reports stabilized surplus (min. 4.2 kW when buffer allows) to the wallbox via Modbus → Wallbox charges the EV → Simulator detects increased consumption and adjusts reported surplus → Battery SOC is managed to ensure evening household needs are met.
3. **Override (rare, manual)**: When a full charge is needed, the user switches to full-charge mode via the Growatt app, bypassing the surplus logic.
4. **Success Moment**: Ghost checks the Home Assistant dashboard in the evening — the EV has gained significant charge, the house battery is at a healthy SOC level, and minimal energy was fed to the grid during the day. All without any manual intervention.

---

## Success Metrics

### Primary Success Criteria (Priority Order)

1. **Household energy autonomy (highest priority)**: The household must never need to draw power from the grid in the morning due to insufficient battery SOC. If this happens, the system has failed.
2. **Self-consumption maximization**: Maximize the share of PV-produced energy that is consumed locally (household + EV charging) rather than fed to the grid.
3. **Reliable EV surplus charging (secondary priority)**: When surplus is available and battery strategy permits, the EV charges reliably without unnecessary start/stop cycles.

### Key Performance Indicators

| KPI | Target | Measurement |
|-----|--------|-------------|
| **Morning grid draw** | 0 occurrences | No grid power needed before PV production starts due to depleted battery |
| **Minimum SOC floor** | Never below 50% | Battery SOC must never drop below 50% regardless of season or conditions |
| **Evening SOC at sunset** | Season-dependent (see below) | Battery SOC at sunset meets seasonal target |
| **Self-consumption ratio** | > 80% of PV production | Ratio of self-consumed energy vs. total PV production |
| **Surplus signal stability** | 0 unnecessary stop/start cycles | When charging is signaled, the 4.2 kW minimum is held stable for at least 10 minutes |
| **Autonomous operation** | 100% hands-off | No manual intervention required in normal daily operation |

### Seasonal SOC Targets at Sunset

| Season | Target SOC at Sunset | Rationale |
|--------|---------------------|----------|
| **Winter (Nov–Feb)** | 100% | Short days, low production — household fully depends on battery overnight |
| **Spring/Autumn (Mar–Apr, Sep–Oct)** | 90–100% | Variable production — prioritize household security |
| **Summer (May–Aug)** | 70–100% | Long days, sun until ~19:00 — more room for EV charging buffer |

*Note: Actual target is dynamically adjusted based on next-day weather forecast and sunrise/sunset times from Home Assistant. Poor forecast → higher SOC target. Good forecast → more buffer available for EV charging.*

### Business Objectives

*N/A — Personal project. No commercial business objectives apply.*

The overarching goal is simple: **Use every kWh of self-produced solar energy intelligently — household first, EV second, grid feed-in only as a last resort. Never compromise the household's evening/night energy supply.**

### Known Constraints

- **EV charge state not queryable**: The wallbox does not expose the EV's battery SOC. This may become available in the future if the vehicle provides it via WiFi/API, but for now the system operates without knowledge of the EV's charge level.

### Dashboard (Nice-to-Have)

A Home Assistant dashboard showing:

- Current SOC vs. target SOC for today
- EV charging status and energy consumed
- Self-consumption ratio (daily/weekly)
- Surplus signal status (what the wallbox "sees")
- Solar forecast vs. actual production

---

## MVP Scope

### Core Features

1. **Intelligent Surplus Calculation**
   - Reads SOC, power-to-grid, PV production, and household consumption from Growatt inverter via existing Growatt Local Modbus integration in Home Assistant
   - Calculates available surplus considering battery buffer capacity

2. **Time-Based SOC Strategy**
   - Hard SOC floor: Always ≥ 50% (non-negotiable)
   - Target SOC at sunset: Season-dependent (100% in winter → 70% in summer)
   - Uses sunrise/sunset times from Home Assistant (`sun.sun` entity)
   - Dynamic adjustment: Conservative in the morning, more buffer available midday when battery is full

3. **Weather/Solar Forecast Integration**
   - Queries weather forecast from Home Assistant (`weather.get_forecasts` for cloud coverage, `forecast_solar` for PV production estimates)
   - Poor forecast → higher SOC protection, less buffer for EV
   - Good forecast → more buffer permitted for EV charging
   - **Dependency**: Requires `forecast_solar` integration to be configured in Home Assistant (setup instructions provided in documentation)

4. **Stabilized Modbus Surplus Signal**
   - Reports minimum 4.2 kW surplus to the wallbox when battery buffer permits
   - Reports actual surplus when > 4.2 kW
   - Detects wallbox charging (increased consumption visible in inverter data) and adjusts reported surplus accordingly
   - Hysteresis: Once charging is signaled, the signal is held stable for at least 10 minutes to prevent start/stop cycling

5. **Fail-Safe Mechanisms**
   - SOC < 50% → immediately stop charging (report 0 kW)
   - No data from inverter → conservative mode (report 0 kW)
   - All decisions logged for traceability via Home Assistant logging

### Out of Scope for MVP

- **EV battery SOC readout**: Wallbox does not expose this; vehicle API integration may follow later
- **Home Assistant Dashboard**: Nice-to-have for monitoring, not part of MVP
- **Manual "full charge" override via simulator**: Handled directly via Growatt app on the wallbox
- **Multi-wallbox support**
- **Cost optimization / electricity price-based charging**
- **Learning algorithms / historical data analysis**

### MVP Success Criteria

- Household never draws from grid in the morning due to depleted battery
- SOC never drops below 50%
- EV charges reliably from surplus without unnecessary stop/start cycles on partly cloudy days
- System operates fully autonomously without manual intervention
- SOC at sunset meets seasonal target

### Future Vision

- **Dashboard**: Home Assistant dashboard with SOC history, charging status, self-consumption ratio, and surplus signal view
- **Vehicle SOC integration**: If the EV exposes its charge level via WiFi/API, the strategy can be refined (e.g., stop charging when EV is at 80%)
- **Adaptive algorithms**: Learn from historical data (SOC curves, weather forecast accuracy) to refine strategy parameters
- **Multi-meter support**: Simulate other smart meter protocols (Chint, etc.) for broader wallbox compatibility
