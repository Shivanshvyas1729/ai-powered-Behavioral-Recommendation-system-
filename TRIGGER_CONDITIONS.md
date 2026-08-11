# SmartReco: AI Recommendation Agent Trigger Conditions Specification

## 1. Overview
This document specifies the exact behavioral trigger conditions, intent scoring formulas, suppression rules, rate limits, and observability standards for the **SmartReco Behavioral AI Agent**.

---

## 2. Core Definitions

- **Meaningful Event**: Any user interaction with Intent Weight $\ge 1.5$ (e.g. Category Filter, Product Detail View with $\ge 3\text{s}$ dwell, Search Query).
- **Ambient Signal**: Low-weight generic events (hovering, catalog scrolling, landing page views) that accumulate telemetry but do not independently trigger LLM calls.
- **Intent Score**: Quantifiable behavioral interest metric calculated across recent user session events.
- **Session**: Continuous user activity sequence mapped to signed cookie `session_user_id`.
- **Dwell Time**: Measured active engagement time in seconds on a specific page section or element.

---

## 3. Active Trigger Conditions (LLM Calls Executed)

An LLM API call via Mesh API is executed **ONLY** when a user reaches Intent Score $\ge 1.5$ or executes an explicit trigger:

| # | Trigger Action | Condition & Threshold | Data Passed to LLM |
|---|---|---|---|
| **1** | **Explicit Category Filter** | User selects category filter (e.g., `Agentic AI`, `AI Security`). | Category scope, recent search history, vector top-10 candidates. |
| **2** | **Product Detail View** | User opens course detail page with $\ge 3\text{s}$ dwell time. | Course title, category, syllabus, user history. |
| **3** | **Active Search Query** | User submits search query in navbar search input. | Search string, candidate matches, session signals. |
| **4** | **Manual Intent Refresh** | User clicks explicit refresh button (`force_refresh=True`). | Full user session history. |
| **5** | **Accumulated Multi-Signal** | User accumulates Intent Score $\ge 1.5$ across multiple events. | Vector DB candidate products & signal pills. |

---

## 4. Suppressed Actions (No LLM Call Made)

| # | Action | Reason Suppressed | Alternative Behavior |
|---|---|---|---|
| **1** | **Generic Home Page Landing** | User opens `/` without prior category/course interest. | Displays standard catalog; recommendation box hidden. |
| **2** | **Main Catalog Page Dwell** | User scrolls or reads generic catalog section. | Logs `Dwell` telemetry to SQLite; LLM call blocked (`intent_score < 1.5`). |
| **3** | **Text Highlighting / Hover** | User selects text or hovers elements. | Logged as ambient telemetry signal. |
| **4** | **Navbar / System UI** | User clicks *Agent Diagnostics*, *MeshAPI Console*, *Admin*, *Logout*. | System UI excluded from tracking in `tracker.js`. |
| **5** | **Same-Target Rapid Repeat** | Duplicate LLM call requested for the EXACT same course/category within 10s. | Suppressed (`Reason: SAME_TARGET_COOLDOWN`); reuses cached recommendation. |

---

## 5. Intent Scoring System

### Formula:
$$\text{Intent Score} = \sum \left( \text{Event Weight} \times \text{Dwell Factor} \right)$$

Where:
- **Event Weight**: Fixed score based on interaction type.
- **Dwell Factor**: $\min\left(\frac{\text{actual\_seconds}}{\text{target\_seconds}}, 1.0\right)$

### Weight & Dwell Table:

| Interaction Type | Base Weight | Target Dwell | Formula / Notes |
|---|---|---|---|
| **Category Filter** (`Filter`) | **3.0** | Instant | Full score 3.0 |
| **Product Detail View** (`Viewed`) | **3.0** | 3.0s | $\min\left(\frac{\text{seconds}}{3.0}, 1.0\right) \times 3.0$ |
| **Search Query** (`Search`) | **2.5** | Instant | Full score 2.5 |
| **Syllabus / Section Dwell** (`Dwell`) | **1.5** | 5.0s | $\min\left(\frac{\text{seconds}}{5.0}, 1.0\right) \times 1.5$ |
| **Catalog Scroll / Hover** (`Scroll`) | **0.2** | N/A | Ambient score 0.2 |

---

## 6. Smart Target-Aware Cooldown & Rate Limiting

- **Zero-Wait New Target Bypass**: Opening a **NEW course** or selecting a **NEW category** BYPASSES cooldown INSTANTLY! Fresh AI recommendations generate immediately without any delay.
- **10s Same-Target Debounce**: Rapid repeated triggers for the *exact same* course/category within 10 seconds are debounced to prevent redundant API calls.
- **Strict Manual Override**: `force_refresh=True` bypasses all cooldown checks.

---

## 7. Implementation & Observability

### Code References:
- **Trigger Gatekeeper & Scoring**: `app/agent.py` (`calculate_intent_score()`, `LAST_USER_TRIGGER_TIME`)
- **Telemetry Exclusion**: `app/static/js/tracker.js` (filters out `.navbar` and `#floating-signal-tracker`)
- **Trace Model**: `app/models/trace.py` (`trigger_action` field)
- **UI Diagnostics**: `app/templates/base.html` (Displays `⚡ LLM Trigger Action` badge)

### Log File Reference (`agent_triggers.log`):
```text
[2026-08-11 13:44:49] User #49 | ✅ LLM_CALL | Trigger: Filter: Agentic AI | Score: 3.0 | Trace: 0b518825-5b8b-4683-8279-bc7e5cc91450
[2026-08-11 13:45:02] User #49 | ⏸️ SUPPRESSED | Trigger: Filter: Agentic AI | Score: 3.0 | Reason: COOLDOWN (47s remaining)
```

---

## 8. Version & Maintenance

| Version | Date | Status | Changes |
|---|---|---|---|
| **1.0.0** | 2026-08-11 | **Production Release** | Fully standardized trigger conditions, Intent Scoring, 60s cooldown, and `agent_triggers.log` formatting. |

*Maintained by SmartReco AI Engineering Team.*
