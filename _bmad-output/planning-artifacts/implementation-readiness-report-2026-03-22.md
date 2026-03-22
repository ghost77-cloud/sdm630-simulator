# Implementation Readiness Report — SDM630 Wallbox Dashboard Extension

**Date:** 2026-03-22
**Assessor:** John (PM Agent)
**Scope:** `prd-wallbox-dashboard-extension.md` (PRD-only, Option B)
**PRD Status:** Complete

---

## PRD Analysis

### Functional Requirements

FR1: Ghost can view the current raw PV surplus value (W) before hysteresis and battery
buffer are applied.

FR2: Ghost can view the current reported surplus value (W) — the exact value served to the
wallbox via Modbus register, after hysteresis and buffer logic.

FR3: Both surplus sensors update in real time when the `SurplusEngine` computes a new
value — no manual refresh required.

FR4: Surplus sensor values persist across HA restarts and display last known value until a
new computation cycle provides a fresh value.

FR5: Ghost can view the timestamp of the most recent Modbus poll received from the wallbox.

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

FR13: The card displays raw surplus, reported surplus, and last-poll timestamp in a single
compact view without requiring navigation to a separate page.

**Total FRs: 13**

### Non-Functional Requirements

NFR1 (Performance): `sensor.sdm_wallbox_last_poll` updates within 500 ms of a Modbus poll
event being received.

NFR2 (Performance): Warning state evaluation (5-minute threshold check) runs at most once
per minute — no busy-polling loop permitted.

NFR3 (Performance): Surplus sensor state updates add no measurable latency to the existing
`SurplusEngine` evaluation cycle — the callback must be non-blocking.

NFR4 (Reliability): The poll-detection hook must not affect Modbus response correctness or
timing.

NFR5 (Reliability): A failure in sensor state update must not crash the Modbus server or
the surplus engine — fail silently with a log entry.

NFR6 (Reliability): Warning state determinism — exactly 300 s triggers orange; 299 s is
normal.

NFR7 (Maintainability): New sensors follow the existing HA sensor entity pattern in
`sensor.py` — same class structure, same logging conventions, same
`_attr_should_poll = False` pattern.

NFR8 (Maintainability): Lovelace card YAML documented with inline comments explaining
conditional color logic.

NFR9 (Maintainability): No new Python dependencies — implementation uses only `pymodbus`,
`homeassistant` core, and the Python standard library.

**Total NFRs: 9**

### Additional Requirements

**IoT/Embedded Constraints identified in PRD:**

- Component must run as HA custom component (no standalone daemon)
- All sensor state updates via HA event bus only
- Poll-detection must hook into existing pymodbus server without replacing it
- Wallbox uses Modbus function code 04 (read input registers) on port 5020
- No outbound communication to wallbox required (read-only observation)
- Modbus server must restart automatically via `async_setup_platform`

**Implicit Constraints (from User Journeys):**

- Lovelace card YAML must be pasteable without additional tooling
- Orange state must be visible at a glance without active checking
- All behavior must be autonomous — no manual restart after HA update

### PRD Completeness Assessment

The PRD is well-structured and complete for a low-complexity brownfield extension. All 13
FRs are clearly stated, independently testable, and traceable to specific user journeys.
NFRs are quantified (500 ms latency, 300 s threshold, once-per-minute polling cap). The
IoT constraints section precisely identifies the integration boundary. No ambiguity was
found requiring clarification before implementation.

**Findings:**

- ✅ FR coverage: 13 requirements, all uniquely numbered and unambiguous
- ✅ NFR coverage: 9 requirements, all measurable
- ✅ Success criteria: Measurable outcomes table provided with clear measurement methods
- ✅ Edge cases documented via User Journeys (loss of connectivity, HA restart)
- ✅ FR12 Lovelace orange strategy — **resolved 2026-03-22:** `binary_sensor.sdm_wallbox_poll_warning`
  (native template binary sensor) + `conditional` card pattern. Documented in PRD
  Implementation Notes section.
- ✅ HA base class for datetime sensor with `restore_state` — **resolved 2026-03-22:**
  `RestoreSensor` base class; `async_get_last_sensor_data()` on startup. Documented in
  PRD Implementation Notes section.

---

## Epic Coverage Validation

### Coverage Matrix

No epics document exists for `prd-wallbox-dashboard-extension.md`. The existing
`epics.md` covers the original surplus engine project and was not created for this feature.

| FR Number | PRD Requirement (summary) | Epic Coverage | Status |
| --------- | ------------------------- | ------------- | ------ |
| FR1 | Raw surplus sensor entity (W, pre-hysteresis) | **NOT FOUND** | ❌ MISSING |
| FR2 | Reported surplus sensor entity (W, post-hysteresis) | **NOT FOUND** | ❌ MISSING |
| FR3 | Real-time update on SurplusEngine compute cycle | **NOT FOUND** | ❌ MISSING |
| FR4 | Surplus sensor restore_state across HA restart | **NOT FOUND** | ❌ MISSING |
| FR5 | Last-poll timestamp sensor entity | **NOT FOUND** | ❌ MISSING |
| FR6 | Warning state transition at > 5 min silence | **NOT FOUND** | ❌ MISSING |
| FR7 | Warning state clears on new poll | **NOT FOUND** | ❌ MISSING |
| FR8 | Last-poll timestamp restore_state | **NOT FOUND** | ❌ MISSING |
| FR9 | Independent update paths (surplus ≠ wallbox poll) | **NOT FOUND** | ❌ MISSING |
| FR10 | Lovelace card YAML configuration | **NOT FOUND** | ❌ MISSING |
| FR11 | Standard built-in HA cards only (no HACS) | **NOT FOUND** | ❌ MISSING |
| FR12 | Orange visual state in Lovelace card | **NOT FOUND** | ❌ MISSING |
| FR13 | Single compact card view | **NOT FOUND** | ❌ MISSING |

### Missing Requirements

All 13 PRD Functional Requirements lack epic/story coverage. This is expected — epics have
not yet been created for this feature.

### Coverage Statistics

- Total PRD FRs: 13
- FRs covered in epics: 0
- Coverage percentage: 0%

**Assessment:** This is not a quality defect in the PRD or epics. It is the expected state
for a feature that has completed planning but has not yet entered the CE (Create Epics)
workflow. Creating epics is the mandatory next step before implementation.

---

## UX Alignment Assessment

### UX Document Status

Not Found. No dedicated UX design document exists for this feature.

### UI Requirements Implied by PRD

The PRD explicitly defines a user-facing deliverable: a Lovelace card configuration (FR10,
FR11, FR12, FR13). This constitutes a UI specification embedded within the PRD itself,
rather than a separate UX design document.

The Lovelace card specification in the PRD includes:

- Card type constraint: standard built-in HA card types only (FR11)
- Visual state requirement: orange color for warning state (FR12)
- Layout requirement: single compact view, three sensors (FR13)
- Section label: "Wallbox Charging" (implied in User Journey 1)

### Alignment Issues

No misalignments found between the implied UX requirements and the PRD. The PRD is
self-consistent regarding the dashboard output.

### Warnings

✅ **FR12 — Orange color strategy resolved (2026-03-22):** Implementation uses
`binary_sensor.sdm_wallbox_poll_warning` (native HA template binary sensor) as a
`conditional` card trigger. Two `entities` card variants (normal / warning) are toggled
by the binary sensor state. No HACS dependency — FR11 satisfied. Full decision documented
in PRD Implementation Notes section.

---

## Epic Quality Review

### Pre-Condition

No epics exist for this feature. This step validates readiness for the CE workflow, rather
than reviewing existing epics. The following findings are pre-implementation guidance for
when epics are created.

### Expected Epic Structure for This Feature

Given the PRD scope (3 new sensor entities + Lovelace card, brownfield), the natural epic
breakdown is:

**Recommended Epic Grouping:**

- **Epic 1 — Surplus Signal Visibility:**
  Covers FR1, FR2, FR3, FR4 — two new sensor entities hooked into `SurplusEngine`
  callbacks, with restore_state.
- **Epic 2 — Wallbox Connectivity Monitoring:**
  Covers FR5, FR6, FR7, FR8, FR9 — last-poll sensor, warning state timer, independent
  update path.
- **Epic 3 — Dashboard Integration:**
  Covers FR10, FR11, FR12, FR13 — Lovelace card YAML, conditional orange state, inline
  documentation.

### Pre-Creation Quality Checks

The following best practices must be observed when epics are written:

- ✅ Each epic delivers user-observable value independently — Ghost can verify surplus
  values (Epic 1) before wallbox monitoring (Epic 2) is implemented.
- ✅ Brownfield project — no project scaffolding stories needed. Stories start from the
  first code change.
- ✅ No forward dependencies expected — each epic is independent of the next.
- ⚠️ FR12 (orange color) depends on a technical decision about Lovelace implementation
  approach. Epic 3 Story for FR12 must not have a forward dependency on a `template`
  sensor that should be in Epic 2. Sequence matters: if a binary sensor is used as the
  warning indicator, it belongs in Epic 2, not Epic 3.
- ⚠️ NFR2 (warning state evaluated at most once per minute) must appear in an acceptance
  criterion of the FR6 story — not as a separate story. It is a quality constraint on the
  implementation, not a standalone deliverable.

### Dependency Risk

**Medium risk:** The orange color in Lovelace (FR12) depends on whether the implementation
produces a `state_color` attribute or a separate binary sensor. This decision gates the
Epic 3 story structure. **Resolve before CE workflow.**

---

## Summary and Recommendations

### Overall Readiness Status

**NEEDS WORK — Not ready for implementation**

The PRD is complete and high quality. The blocking gap is the absence of epics and stories.
One open technical question (Lovelace orange strategy) must be resolved before epic
creation.

### Critical Issues Requiring Immediate Action

1. **No epics exist for this feature.** All 13 FRs have 0% coverage. Implementation cannot
   begin without epics and stories. Priority: run CE (Create Epics) workflow immediately
   after resolving issue #2.

2. ~~**FR12 orange color implementation approach is unresolved.**~~ ✅ **Resolved
   2026-03-22** — `binary_sensor.sdm_wallbox_poll_warning` + `conditional` card.
   Decision documented in PRD Implementation Notes.

### Recommended Next Steps

1. **Decide the Lovelace orange strategy** — choose between `conditional` card approach or
   `template`/`binary_sensor` approach (native, no HACS). Document the decision in a
   short technical note or inline in the PRD. Estimated effort: 15 minutes.

2. **Run CE (Create Epics) workflow** — create epics and stories for
   `prd-wallbox-dashboard-extension.md` using the recommended 3-epic structure above.
   The PRD is ready to be the input document.

3. ~~**Add a brief Implementation Notes section to the PRD.**~~ ✅ **Done 2026-03-22** —
   Implementation Notes section added to PRD covering (a) Lovelace orange strategy and
   (b) `RestoreSensor` base class for datetime sensor.

### Final Note

This assessment identified 3 issues across 2 categories. 2 of the 3 have been resolved
(2026-03-22): Lovelace orange strategy documented; `RestoreSensor` base class documented.
The single remaining action is running the CE workflow.

**The PRD earns a strong foundation score. The only remaining blocker is the CE
(Create Epics) workflow — all technical questions are now resolved.**
