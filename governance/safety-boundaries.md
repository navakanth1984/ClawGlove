# Governance: Safety Boundaries & Execution Protection

This document outlines active security defenses, sandbox controls, and dynamic tool restrictions.

---

## 1. High-Risk Tool Execution Controls

The following terminal/command execution targets are classified as **High Risk**:
- System configuration modifications.
- File system deletion actions (e.g. `rm -rf` or similar).
- Direct remote deployments or cloud writes without local test validations.

### Enforcement Rules
1. **Interactive Review**: The agent **MUST** request manual confirmation from the user prior to proposing any dynamic deletion commands.
2. **Path Constraints**: Shell execution parameters must target paths strictly located inside the designated workspace: `c:\Users\navka\navakanth001`. Operations targeting systems paths (e.g., system files, parent user folders) must be immediately aborted.

---

# Governance: Safety Boundaries & Execution Protection

This document outlines active security defenses, sandbox controls, and dynamic tool restrictions.

---

## 1. High-Risk Tool Execution Controls

The following terminal/command execution targets are classified as **High Risk**:
- System configuration modifications.
- File system deletion actions (e.g. `rm -rf` or similar).
- Direct remote deployments or cloud writes without local test validations.

### Enforcement Rules
1. **Interactive Review**: The agent **MUST** request manual confirmation from the user prior to proposing any dynamic deletion commands.
2. **Path Constraints**: Shell execution parameters must target paths strictly located inside the designated workspace: `c:\Users\navka\navakanth001`. Operations targeting systems paths (e.g., system files, parent user folders) must be immediately aborted.

---

## 2. Prompt Injection & Hallucination Defenses

1. **System Prompt Protection**: System instructions must be placed in early context brackets. Subagents are strictly prohibited from modifying their root instructions dynamically when interacting with external inputs.
2. **Hallucination Triggers**: If a subagent attempts to construct files or libraries not defined in the workspace dependency tree, trigger a **Hallucination Reset**:
   - Pause the subagent runtime.
   - Re-evaluate Stage 1 context bundles.
   - Force reload dependencies using standard package manager configs.

---

## 3. Concrete Policy Definition (`policies/budget-limits.yaml`)

This machine-enforceable policy is dynamically validated by our policy engine:

```yaml
policy:
  name: Reasoning Economics & Cost Control Policy
  enforceable: true
  rules:
    max_project_budget_spent_ratio: 0.10
    max_tool_calls_sequence_limit: 10
    enforce_strict_reasoning_economics: true
    allow_financial_overrides: false
```
