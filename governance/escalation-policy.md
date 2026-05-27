# Governance: Escalation & Human-in-the-Loop Policy

This document defines standard protocols for transferring execution authority when agents encounter unresolved anomalies or hit dynamic budget thresholds.

---

## 1. Trigger Conditions for Human Escalation

Execution must halt and request human-in-the-loop validation under these trigger states:

### A. Relative Budget Overflow Triggers
Instead of hardcoded monetary parameters, the platform tracks cost using relative bounds:
- Accumulated task token expenditure exceeds **percentage of total project token allocation (Target SLA: Max 10% of global project budget)**.
- Total accumulated context size exceeds **max allowed tokens per stage (Target SLA: 250,000 active tokens)**.
- A single task run requires >3 separate subagent context updates.

### B. Persistent Execution Failures
- The codebase compilation/test suite fails to resolve after **3 consecutive automated recovery attempts**.
- A subagent experiences infinite-loop syntax errors on a single class or module.

### C. Scope Ambiguity Anomalies
- The builder detects a requirement dependency that falls outside the explicit GPS Stage 0 PRD (Scope creep hazard).
- Missing configuration files or database credentials that are not present in environment variables.

---

## 2. Escalation Handover Protocol

When an escalation trigger condition is met:
1. **Freeze Execution State**: Pause all active subagent tasks and background schedules.
2. **Compile Incident Report**: Write a clean trace summary containing:
   - *Active Stage*: The current ACDLC stage.
   - *Failure Context*: Raw execution crash log, active token counts, or parameter causing the leak.
   - *Remediation Options*: Propose 2-3 logical solutions (e.g. modify scope boundaries, adjust active token caps, or override percentage thresholds).
3. **Notify User**: Display the trace report clearly in the user-chat interface. Pause execution until the user manually selects a remediation pathway or approves a budget override.
