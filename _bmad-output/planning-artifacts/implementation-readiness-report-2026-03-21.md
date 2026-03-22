---
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
  - remediation-applied-2026-03-21
documentsAnalyzed:
  prd: _bmad-output/planning-artifacts/prd.md
  architecture: _bmad-output/planning-artifacts/architecture.md
  epics: _bmad-output/planning-artifacts/epics.md
  ux: NOT FOUND (N/A - pure backend)
date: 2026-03-21
remediationDate: 2026-03-21
project: sdm630-simulator
assessor: GitHub Copilot (bmad-check-implementation-readiness)
status: REMEDIATED
---

# Implementation Readiness Assessment Report

**Date:** 2026-03-21
**Project:** sdm630-simulator
**Assessor:** bmad-check-implementation-readiness workflow

---

## Document Inventory

| Document Type | File | Size | Modified | Status |
|---|---|---|---|---|
| PRD | `prd.md` | 33.983 Bytes | 2026-03-15 | ✅ Complete |
| Architecture | `architecture.md` | 18.881 Bytes | 2026-03-21 | ✅ Complete |
| Epics & Stories | `epics.md` | 35.773 Bytes | 2026-03-21 | ✅ Complete |
| UX Design | Not found | — | — | ⚠️ N/A (pure backend) |
| Product Brief | `product-brief-sdm630-simulator-2026-03-15.md` | 13.701 Bytes | 2026-03-15 | ✅ Reference |

No duplicate documents found. No sharded documents found.

---

## PRD Analysis

### Functional Requirements Extracted

| # | FR | Category |
|---|---|---|
| FR1 | Read real-time SOC % from Growatt inverter HA entity | Surplus Calculation |
| FR2 | Read real-time power-to-grid from Growatt inverter HA entity | Surplus Calculation |
| FR3 | Read real-time PV production power from Growatt inverter HA entity | Surplus Calculation |
| FR4 | Read real-time household consumption (power-user-load) from Growatt inverter | Surplus Calculation |
| FR5 | Calculate available surplus (PV − load − grid feed-in) | Surplus Calculation |
| FR6 | Determine battery buffer capacity (current SOC minus applicable SOC floor) | Surplus Calculation |
| FR7 | Enforce hard SOC floor of 50% — never violated under any circumstances | SOC Strategy |
| FR8 | Determine seasonal SOC target at sunset by month (100% winter, 90–100% spring/autumn, 70–100% summer) | SOC Strategy |
| FR9 | Read sunrise and sunset times from `sun.sun` HA entity | SOC Strategy |
| FR10 | Adjust allowed SOC buffer based on time of day | SOC Strategy |
| FR11 | Dynamically adjust SOC target based on weather/solar forecast quality | SOC Strategy |
| FR12 | Query PV production forecast from `forecast_solar` HA integration | Forecast |
| FR13 | Query weather forecast (cloud coverage) via `weather.get_forecasts` | Forecast |
| FR14 | Classify forecast quality (good/moderate/poor) | Forecast |
| FR15 | Fall back to conservative seasonal defaults when forecast unavailable | Forecast |
| FR16 | Report calculated surplus (kW) via SDM630 Modbus TCP registers | Modbus Signal |
| FR17 | Guarantee minimum reported surplus of 4.2 kW when buffer permits | Modbus Signal |
| FR18 | Report actual surplus when it exceeds 4.2 kW | Modbus Signal |
| FR19 | Apply hysteresis — minimum 4.2 kW held for at least 10 min once charging signaled | Modbus Signal |
| FR20 | Report 0 kW surplus to stop wallbox charging when conditions require | Modbus Signal |
| FR21 | Detect that the wallbox is actively charging the EV (via consumption/power flow changes) | Wallbox Detection |
| FR22 | Adjust reported surplus to account for wallbox's own power draw during active charging | Wallbox Detection |
| FR23 | Detect when inverter sensor entities are in `unavailable` or `unknown` state | Fail-Safe |
| FR24 | Immediately report 0 kW when any critical sensor entity becomes unavailable | Fail-Safe |
| FR25 | Automatically resume normal calculation when sensor entities recover | Fail-Safe |
| FR26 | Validate sensor values within plausible ranges before use in calculations | Fail-Safe |
| FR27 | Log each evaluation cycle with all inputs (SOC, PV, grid, consumption, forecast, time) | Logging |
| FR28 | Log calculated surplus decision and reported Modbus value with reasoning | Logging |
| FR29 | Log fail-safe activations with specific trigger reason | Logging |
| FR30 | Support configurable log levels (DEBUG traces, INFO summaries, WARNING fail-safes) | Logging |
| FR31 | Configure Growatt entity IDs via YAML | Configuration |
| FR32 | Configure forecast entity IDs via YAML | Configuration |
| FR33 | Configure SOC floor value via YAML (default 50%) | Configuration |
| FR34 | Configure seasonal SOC sunset targets via YAML | Configuration |
| FR35 | Configure minimum surplus threshold via YAML (default 4.2 kW) | Configuration |
| FR36 | Configure hysteresis duration via YAML (default 10 min) | Configuration |
| FR37 | Configure evaluation cycle interval via YAML (default 10–30 s) | Configuration |
| FR38 | Validate configured entity IDs exist and reporting data on startup | Configuration |

**Total FRs: 38**

### Non-Functional Requirements Extracted

| # | NFR | Category |
|---|---|---|
| NFR1 | 24/7 operation — no manual restarts for normal operation | Reliability |
| NFR2 | Auto-recover from HA restarts — resume within 60 seconds of entity availability | Reliability |
| NFR3 | Fail-safe activates within 1 evaluation cycle (≤30 s) of sensor unavailability | Reliability |
| NFR4 | Modbus TCP server maintains persistent connectivity — no drops during normal operation | Reliability |
| NFR5 | 60-second grace period after HA restart before fail-safe triggers | Reliability |
| NFR6 | Evaluation cycle completes within 1 second including all sensor reads and forecast queries | Performance |
| NFR7 | Modbus TCP response to wallbox within 100 ms | Performance |
| NFR8 | CPU < 1% average, RAM < 50 MB footprint | Performance |
| NFR9 | Compatible with pymodbus ≥ 3.9.2 | Integration |
| NFR10 | Compatible with Home Assistant 2024.x and later | Integration |
| NFR11 | Compatible with any weather integration supporting `weather.get_forecasts` + `cloud_coverage` | Integration |
| NFR12 | Compatible with Forecast.Solar integration | Integration |
| NFR13 | Compatible with Growatt Local Modbus integration (RTU Protocol 2 v1.24) | Integration |
| NFR14 | All config adjustable via `configuration.yaml` without code changes | Maintainability |
| NFR15 | Decision logs contain full context (all inputs + output + reason) | Maintainability |
| NFR16 | Surplus calculation logic as separable module — independent from Modbus and HA sensor code | Maintainability |
| NFR17 | Never write invalid IEEE 754 float values to Modbus registers (NaN, Infinity, negative surplus) | Data Integrity |
| NFR18 | Validate sensor values before use: SOC 0–100%, power values within expected ranges | Data Integrity |

**Total NFRs: 18**

### PRD Completeness Assessment

The PRD is well-written, comprehensive, and production-quality. Requirements are clearly categorized and numbered. Success criteria are measurable. User journeys are concrete and trace well to FRs. The PRD is suitable as a reference document for implementation.

---

## Epic Coverage Validation

### Coverage Matrix

> **Note:** The epics document uses an independent FR numbering (Epics-FR1 through Epics-FR8) that does NOT align with PRD FR1–FR38, making direct traceability harder. The matrix below maps PRD FRs to epics stories directly.

| PRD FR | Requirement Summary | Epic/Story Coverage | Status |
|---|---|---|---|
| FR1 | Read SOC from HA entity | Epic 1 Stories 1.2, 1.3 (`SensorSnapshot.soc_percent`, cache) | ✅ Covered |
| FR2 | Read power-to-grid | Epic 1 Stories 1.2, 1.3 (`SensorSnapshot.power_to_grid_w`) | ✅ Covered |
| FR3 | Read PV production | Epic 1 Stories 1.2, 1.3 (`SensorSnapshot.pv_production_w`) | ✅ Covered |
| FR4 | Read household consumption | Epic 1 Stories 1.2, 1.3 (`SensorSnapshot.power_to_user_w`) | ✅ Covered |
| FR5 | Calculate surplus | Epic 2 Story 2.2 (`calculate_surplus()`) | ✅ Covered |
| FR6 | Battery buffer capacity | Epic 2 Story 2.2 (buffer formula) | ✅ Covered |
| FR7 | Hard SOC floor 50% | Epic 4 Story 4.3 + epics NFR3 | ✅ Covered |
| FR8 | Seasonal SOC target at sunset (monthly) | **NOT in coverage map** — Stories replace seasonality with static time windows only | ❌ Missing |
| FR9 | Read sunrise/sunset from `sun.sun` | Epic 2 Story 2.1 implementation note | ✅ Covered (partial — impl note only) |
| FR10 | Adjust buffer based on time of day | Epic 2 Story 2.1 | ✅ Covered |
| FR11 | Dynamic SOC adjustment from forecast quality | Epic 3 Story 3.2 | ✅ Covered |
| FR12 | Query `forecast_solar` | Epic 3 Story 3.1 | ✅ Covered |
| FR13 | Query `weather.get_forecasts` cloud coverage | Epic 3 Story 3.1 | ✅ Covered |
| FR14 | Classify forecast quality good/moderate/poor | Epic 3 Story 3.2 (uses numeric thresholds <20 / >70) | ✅ Covered |
| FR15 | Conservative fallback when forecast unavailable | Epic 3 Stories 3.1, 3.2 (`forecast_available=False` path) | ✅ Covered |
| FR16 | Report surplus via SDM630 Modbus TCP | Epic 1 Story 1.3 (writes `reported_kw` to register) | ✅ Covered |
| FR17 | Guarantee min 4.2 kW when buffer permits | Epic 2 Story 2.2 (threshold enforcement) | ✅ Covered |
| FR18 | Report actual surplus when > 4.2 kW | Epic 2 Story 2.2 | ✅ Covered |
| FR19 | Hysteresis — 10-min hold once charging signaled | Epic 2 Story 2.3 | ✅ Covered |
| FR20 | Report 0 kW when conditions require | Epic 2 Story 2.3 + Epic 4 Stories 4.1–4.3 | ✅ Covered |
| FR21 | Detect wallbox actively charging EV | **NOT in any story** | ❌ Missing |
| FR22 | Adjust reported surplus for wallbox power draw | **NOT in any story** (only implicit via `power_to_user`) | ❌ Missing |
| FR23 | Detect `unavailable`/`unknown` sensor states | Epic 4 Story 4.1 | ✅ Covered |
| FR24 | Immediately report 0 kW on sensor unavailability | Epic 4 Story 4.1 | ✅ Covered |
| FR25 | Resume calculation when sensors recover | Epic 4 Story 4.1 | ✅ Covered |
| FR26 | Validate sensor value ranges (SOC 0–100%, power bounds) | **NOT in any story** — only type/availability checks covered | ❌ Missing |
| FR27 | Log all inputs per cycle | Epic 1 Story 1.4 (structured DEBUG format) | ✅ Covered |
| FR28 | Log decision + reasoning | Epic 1 Story 1.4 | ✅ Covered |
| FR29 | Log fail-safe with trigger reason | Epic 1 Story 1.4 | ✅ Covered |
| FR30 | Configurable log levels (DEBUG/INFO/WARNING) | Epic 1 Story 1.4 (DEBUG + WARNING; INFO only for startup log) | ⚠️ Partial |
| FR31 | Configure Growatt entity IDs via YAML | Epic 1 Story 1.1 | ✅ Covered |
| FR32 | Configure forecast entity IDs via YAML | Epic 1 Story 1.1 | ✅ Covered |
| FR33 | Configure SOC floor via YAML | Epic 1 Story 1.1 (DEFAULTS dict) | ✅ Covered |
| FR34 | Configure seasonal SOC sunset targets via YAML | **NOT in YAML schema** — seasonal targets absent | ❌ Missing |
| FR35 | Configure min surplus threshold via YAML | Epic 1 Story 1.1 (DEFAULTS: `wallbox_threshold_kw=4.2`) | ✅ Covered |
| FR36 | Configure hysteresis duration via YAML | Epic 1 Story 1.1 (DEFAULTS: `hold_time_minutes=10`) | ✅ Covered |
| FR37 | Configure evaluation interval via YAML | Epic 1 Story 1.1 (DEFAULTS: `evaluation_interval=15`) | ✅ Covered |
| FR38 | Validate entity IDs on startup | Epic 1 Story 1.1 (missing SOC → ERROR + FAILSAFE) | ✅ Covered |

### Missing Requirements

#### Critical Missing FRs

**FR8: Seasonal SOC Target at Sunset**

- **PRD Text:** "The system can determine a seasonal SOC target at sunset based on the current month (100% winter, 90–100% spring/autumn, 70–100% summer)"
- **Impact:** Without seasonal awareness, the system applies identical SOC protection year-round. In summer, the battery may be over-protected (unnecessarily reducing EV charging headroom). In winter, it may be under-protected (not recognizing short days require a full charge). This directly affects the primary success criterion "Zero morning grid draws."
- **Recommendation:** Add seasonal SOC target to `configuration.yaml` schema and implement month→target lookup in `SurplusCalculator.get_soc_floor()` or a new `get_seasonal_target()` method. This integrates with Story 2.1 or needs a new Story 2.1b.

**FR21: Wallbox Charging Detection**

- **PRD Text:** "The system can detect that the wallbox is actively charging the EV by observing increased household consumption or power flow changes in the inverter data"
- **Impact:** Without active wallbox detection, the surplus calculation may not correctly attribute power flow changes to EV charging vs. household load. `charging_state = "ACTIVE"` is used in Story 2.2 ACs but the mechanism to transition into ACTIVE state (beyond threshold math) is unspecified.
- **Recommendation:** Add explicit AC to Story 2.2 or a new Story 2.2b: "Given wallbox consumption observed in `power_to_user_w` delta greater than 1 kW in a single evaluation — Then `charging_state` confirms ACTIVE wallbox."

**FR22: Adjust Reported Surplus for Wallbox Power Draw**

- **PRD Text:** "The system can adjust the reported surplus to account for the wallbox's own power draw during active charging"
- **Impact:** While the PRD states this adjustment is needed, the epics assume `power_to_user` already includes wallbox consumption (which it does on the Growatt inverter). This assumption is correct for the SPH inverter but is not documented as an architectural decision or verified in ACs. If the assumption fails, the surplus will be miscalculated during active charging.
- **Recommendation:** Add an explicit acceptance criterion to Story 2.2: "Given the wallbox is actively charging — Then the `power_to_user_w` value from the Growatt integration includes wallbox power draw — And no separate adjustment is needed." This documents the assumption and verifies it rather than leaving it silent.

#### High Priority Missing FRs

**FR26: Sensor Value Range Validation**

- **PRD Text:** "The system can validate sensor values are within plausible ranges before using them in calculations"
- **NFR18 text:** "SOC must be 0–100%, power values must be non-negative (or appropriately signed for bidirectional flow)"
- **Impact:** Without range validation, an erroneous SOC value of 150% or a negative PV production value would silently corrupt surplus calculations. Story 4.1 covers non-numeric and unavailable states but not out-of-range numeric values.
- **Recommendation:** Add Story 4.4: "Sensor Range Validation" — before using a value in calculation, check SOC ∈ [0, 100], power values within configurable bounds. Out-of-range → FAILSAFE with `"<entity>: value <X> out of range [min, max]"` reason.

**FR34: YAML Configuration for Seasonal SOC Targets**

- **PRD Text:** "The user can configure the seasonal SOC sunset targets via YAML"
- **Impact:** Related to FR8. Even if seasonal logic is added to the implementation, without YAML configuration the user has no control over seasonal targets — requiring code changes. This violates NFR14.
- **Recommendation:** Extend `time_strategy:` YAML block or add a `seasonal_targets:` block to `configuration.yaml` schema (Story 1.1 scope extension).

### Coverage Statistics

| Metric | Value |
|---|---|
| Total PRD FRs | 38 |
| Fully covered in epics | 31 |
| Partially covered | 2 (FR9, FR30) |
| Missing / not covered | 5 (FR8, FR21, FR22, FR26, FR34) |
| **Coverage percentage** | **81.6%** |

---

## UX Alignment Assessment

### UX Document Status

Not found — **intentional and accepted**.

The PRD explicitly states: "**Explicitly NOT in MVP:** Dashboard" and "UX Design Requirements: N/A — pure Modbus backend; no UI component." The epics confirm: "UX Design Requirements: N/A — pure Modbus backend; no UI component."

### Alignment Issues

None — no UX document is required or expected for this project.

### Warnings

None — the absence of UX documentation is correct for a pure Modbus backend integration with no HA dashboard or UI component in scope.

---

## Epic Quality Review

### Epic 1: Foundation — Configuration, Module Scaffold, and Logging

| Check | Status | Notes |
|---|---|---|
| User value | ⚠️ Marginal | "Foundation" is a technical milestone title. However, the epic goal states: "HA starts cleanly, module skeletons exist, evaluation loop runs without crashing" — acceptable for brownfield foundation epic. |
| Epic independence | ✅ Pass | Stands alone as the first epic. |
| Story sizing | ✅ Pass | 4 stories, appropriately scoped. |
| No forward dependencies | ⚠️ Concern | Story 1.2 defines `SensorSnapshot` without `forecast: ForecastData` field, which Epic 3 requires. `SensorSnapshot` will need modification in Epic 3 (rework). |
| ACs quality | ✅ Pass | BDD format, specific log format strings, DEFAULTS dict specified. |
| Brownfield integration | ✅ Pass | References existing modules, extends `async_setup`. |

**Issue (🟠 Major):** Story 1.3 states the evaluation tick calls `SurplusEngine.evaluate_cycle(snapshot)` which raises `NotImplementedError`. The AC requires "no blocking I/O occurs in the event loop" — but if `NotImplementedError` propagates to the tick handler, it will crash the event loop or the component. The story must specify that the stub `evaluate_cycle()` returns a default `EvaluationResult(reported_kw=0.0, ..., reason="engine_not_yet_implemented")` rather than raising.

---

### Epic 2: Core Surplus Logic — SOC Strategy, Buffer Math, and Hysteresis

| Check | Status | Notes |
|---|---|---|
| User value | ✅ Pass | "On a sunny day with clouds, simulator uses battery buffer and wallbox gets stable signal" — clear user outcome. |
| Epic independence | ✅ Pass | Uses only Epic 1 output. |
| Story sizing | ✅ Pass | 3 stories, well-scoped. |
| No forward dependencies | ✅ Pass | All dependencies point backward to Epic 1. |
| ACs quality | ✅ Pass | Concrete numerical ACs in Story 2.2. |

**Issue (🟠 Major — Buffer Formula Units):** Story 2.2 implementation note defines:

```
buffer_kw = min(MAX_BUFFER_KW, (soc_percent - soc_floor) * BATTERY_KWH / 100)
```

This formula computes **kWh available** (e.g., 45% × 10.0 kWh = 4.5 kWh), not **kW that can be delivered in the current moment**. Battery kW output depends on inverter capability and discharge rate, not just stored energy. For example, if `buffer_kw = 4.5`, it means 4.5 kWh is stored above the floor — but can the battery actually deliver 4.2 kW *right now* for 10 minutes? The formula mixes energy (kWh) and power (kW) units. Recommend renaming the intermediate variable to `buffer_energy_kwh` and adding a configurable `max_discharge_kw` parameter (the SPH10000TL3 can discharge at up to ~10 kW), which becomes the actual cap.

**Issue (🟡 Minor):** Story 2.1 passes `snapshot.sunset_time` to `SurplusCalculator`, but the logic to read `sun.sun` and populate this field lives in `SurplusEngine` (Story 1.3). Story 1.3 ACs do not mention reading `sun.sun` — this detail is only in Story 2.1's implementation note. Add an explicit AC to Story 1.3: "Given evaluation tick fires — Then `SurplusEngine` reads `hass.states.get('sun.sun')` and passes `next_setting` as `snapshot.sunset_time`."

---

### Epic 3: Forecast Integration — Weather and Solar Forecast Consumption

| Check | Status | Notes |
|---|---|---|
| User value | ✅ Pass | "On overcast afternoon, engine raises SOC floor to protect battery" — clear outcome. |
| Epic independence | ✅ Pass | Uses Epics 1+2 output. |
| Story sizing | ✅ Pass | 2 stories. |
| No forward dependencies | 🔴 Violation | Story 3.1 introduces `ForecastData` dataclass and Story 3.2 requires `SensorSnapshot.forecast: ForecastData`. But `SensorSnapshot` is defined in Story 1.2 (Epic 1) **without** the `forecast` field. Epic 3 must modify a dataclass created in Epic 1 — this is a backward rework dependency. |
| ACs quality | ⚠️ Concern | Story 3.2: "the effective SOC floor is raised toward 80%" — **"toward 80%" is vague**. Is it exactly 80%, or interpolated? The AC must state the exact expected value. |

**Issue (🔴 Critical — Structural):** `SensorSnapshot` in Story 1.2 does not include `forecast: ForecastData`. When implementing Epic 3, developers must go back and modify the dataclass from Epic 1. This violates the "Append-Only Building" principle and creates unexpected rework. **Recommendation:** Either (a) add `forecast: ForecastData | None = None` to `SensorSnapshot` in Story 1.2, with `ForecastData` as a forward-declared stub, or (b) explicitly note in Story 3.1 that `SensorSnapshot` must be extended as part of that story's implementation.

---

### Epic 4: Fail-Safe and Reliability — Sensor Monitoring and Fault Handling

| Check | Status | Notes |
|---|---|---|
| User value | ✅ Pass | "Journey 5 (Inverter offline) works correctly" — specific user scenario. |
| Epic independence | ✅ Pass | Uses Epics 1+2 (`HysteresisFilter.force_failsafe()`). |
| Story sizing | ✅ Pass | 3 well-scoped stories. |
| No forward dependencies | ✅ Pass | All backward dependencies. |
| ACs quality | ✅ Pass | Specific, testable, with exact log format strings. |

**Issue (🟡 Minor):** Story 4.2 specifies that staleness triggers when `elapsed > 60s` (strictly greater than). Story 4.2 AC states: "Given `stale_threshold_seconds = 60` — When sensor last updated exactly 60 seconds ago — Then FAILSAFE is NOT triggered (boundary: strictly `> 60` triggers)." This is good. However, the startup grace period AC says "After 60 seconds without any update, FAILSAFE triggers normally" — this uses the same 60-second value as `stale_threshold_seconds`. If a user configures `stale_threshold_seconds = 30`, does the startup grace period also become 30s? The relationship between the startup grace period and `stale_threshold_seconds` is ambiguous. Recommend explicitly tying them: startup grace period = `stale_threshold_seconds`.

---

### Epic 5: Test Infrastructure — Unit Tests for Pure Logic Components

| Check | Status | Notes |
|---|---|---|
| User value | 🔴 Violation | "Test Infrastructure" is a purely technical epic. `python -m pytest tests/ -v exits with code 0` is developer value, not end-user value. This violates create-epics-and-stories best practices. |
| Epic independence | ✅ Pass | Tests validate Epics 1–4 logic, but the epic itself is completable after each prior epic. |
| Story sizing | ✅ Pass | 2 well-scoped test stories. |
| No forward dependencies | ✅ Pass | Tests validate already-implemented stories. |
| ACs quality | ✅ Pass | 11 named test scenarios in Story 5.1, 8 in Story 5.2 — very specific. |

**Issue (🟡 Minor — Technical Epic):** Epic 5 is a technical infrastructure epic. Per best practices, tests should be part of each story's Definition of Done, not a separate epic. However, for a single-developer project where tests are explicitly required by NFR4/NFR5 and the test infrastructure does not exist yet, treating it as a dedicated epic is pragmatically acceptable. **Recommendation:** Consider folding Story 5.1 into Epic 2 completion criteria and Story 5.2 into Epic 2/Story 2.3 completion criteria, so tests are written alongside the logic rather than deferred to a separate epic.

---

### Dependency Graph Summary

```
Epic 1 (Foundation)          → No dependencies
Epic 2 (Core Surplus Logic)  → Requires Epic 1
Epic 3 (Forecast)            → Requires Epics 1+2
                               ⚠️ Requires SensorSnapshot extension (Epic 1 rework)
Epic 4 (Fail-Safe)           → Requires Epics 1+2
Epic 5 (Tests)               → Requires Epics 1+2+3+4 (test targets)
```

Recommended implementation order: **1 → 2 → 4 → 3 → 5** (fail-safe before forecast for safety-first profile).

---

## Summary and Recommendations

### Overall Readiness Status

**🟠 NEEDS WORK** — The planning artifacts are high quality with strong architectural decisions and detailed acceptance criteria. However, 5 PRD functional requirements are not covered in the epics, and there are structural issues that will cause rework during implementation.

### Critical Issues Requiring Immediate Action

1. **🔴 `SensorSnapshot` forward dependency (Epic 3 vs Epic 1)**
   Story 1.2 must include `forecast: ForecastData | None = None` as a field. Without this, Epic 3 implementation requires modifying a dataclass mid-sprint, breaking the append-only principle and causing unclear test failures.

2. **🔴 FR8 + FR34: Seasonal SOC Targets completely absent**
   The PRD's seasonal SOC target logic (100% winter → 70% summer at sunset) is entirely absent from both the epics' logic and YAML schema. The static time-window floors in Story 2.1 are a simplification that cannot fulfil "Zero morning grid draws" in December (100% sunset target) vs. July (70% target). Add Story 2.1b or extend 2.1 to include `seasonal_targets:` YAML and a monthly lookup.

3. **🟠 Buffer formula mixes kWh and kW units (Story 2.2)**
   The formula `buffer_kw = (soc_percent - soc_floor) * BATTERY_KWH / 100` produces kWh, not kW. While this coincidentally yields the right order of magnitude for a 10-minute window, it is semantically incorrect and will break for different hold times or battery sizes. Rename to `buffer_energy_kwh` and add a configurable `max_discharge_kw` parameter.

4. **🟠 Story 1.3: `evaluate_cycle()` stub must not raise — must return default result**
   The AC says "evaluation loop runs logging `state=INACTIVE reason=engine_not_yet_implemented`" but the stub method is `raise NotImplementedError`. Add an explicit AC that the stub returns `EvaluationResult(reported_kw=0.0, ..., reason="engine_not_yet_implemented")` so the loop never crashes.

### Recommended Next Steps

1. **Fix Story 1.2** — Add `forecast: ForecastData | None = None` to `SensorSnapshot`. Add stub `ForecastData` dataclass with `forecast_available=False` default. This prevents Epic 3 rework.

2. **Fix Story 2.1 / Story 1.1** — Add seasonal SOC target logic and `seasonal_targets:` YAML configuration key to cover FR8 + FR34. This is core to the product's primary success criterion.

3. **Add Story 4.4: Sensor Range Validation** — Cover FR26 + NFR18: validate SOC ∈ [0, 100], power values within configurable bounds before use. FAILSAFE on out-of-range values.

4. **Clarify Story 2.2 FR21/FR22** — Add explicit AC documenting the assumption that `power_to_user_w` includes wallbox consumption on the SPH inverter, satisfying FR21/FR22 by architectural contract rather than leaving it silent.

5. **Fix Story 2.2 buffer formula** — Correct unit semantics (`buffer_energy_kwh` → `buffer_kw` via `max_discharge_kw` cap).

6. **Consider Epic 5 restructuring** — Move Story 5.1 into Epic 2's DoD, Story 5.2 into Epic 2 Story 2.3 DoD, to eliminate the deferred test epic.

7. **Update PRD NFR9** — Change from `pymodbus ≥ 3.9.2` to `pymodbus ≥ 3.11.1` to match the architectural decision in the epics. These must be consistent.

### Issues by Severity

| Severity | Count | Issues |
|---|---|---|
| 🔴 Critical | 2 | `SensorSnapshot` forward dep; FR8+FR34 seasonal targets missing |
| 🟠 Major | 4 | Buffer kWh/kW units; Story 1.3 stub raises; FR21/FR22 implicit; FR26 range validation missing |
| 🟡 Minor | 5 | Story 3.2 vague "toward 80%"; NFR9 version mismatch; startup grace period ambiguity; `sun.sun` read not in Story 1.3 ACs; Epic 5 is a technical epic |

### Final Note

This assessment identified **11 issues** across **3 severity levels**. The foundation is strong — the architecture, Modbus infrastructure, and HA lifecycle patterns are well researched. Of the 38 PRD FRs, 31 are fully covered (81.6%). The 2 critical issues should be resolved in the epics before Sprint 1 begins, as they are cheap to fix now and expensive to fix mid-implementation.

**The most important action before writing a single line of code: update `SensorSnapshot` to include the `forecast` field, and decide whether seasonal SOC targets belong in Sprint 1 (Story 2.1 extension) or are accepted as a deliberate scope reduction with a clear trade-off documented.**

---

*Report generated: 2026-03-21 | Project: sdm630-simulator | Workflow: bmad-check-implementation-readiness*
