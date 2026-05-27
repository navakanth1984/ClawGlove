# ACDLC Multi-Layer Verification Checklist

This template verifies the build against Stage 0 ALIGN specifications and guarantees system integrity.

---

## 1. Specification Validation (Alignment Gate)
- [ ] **Feature-Goal Alignment**: Map each completed feature back to the explicit goals defined in the PRD.
- [ ] **Exclusion Checks**: Double-check that no out-of-scope/excluded features were implemented (preventing bloat).

---

## 2. Functional Testing Gate
- [ ] **Unit Tests Passed**: Run the automated unit tests and attach outcomes.
  - *Command Run*: `[Insert command, e.g. npm test or pytest]`
- [ ] **Integration Tests Passed**: Verify end-to-end interactions between components.
- [ ] **Code Coverage Check**: Line coverage percentage must satisfy the target SLA.
  - *Actual Coverage*: `[Insert %]` | *Target SLA*: `[Insert %]`

---

## 3. Performance & Stability Testing
- [ ] **Latency SLA Checked**: Run execution profiling. Average execution or response time must satisfy constraints.
  - *Avg Latency*: `[Insert ms/sec]` | *Target SLA*: `[Insert ms/sec]`
- [ ] **Memory & Resource Benchmarking**: Verify that memory footprints remain stable and no file-descriptor or network-connection leaks are observed.

---

## 4. Security & Governance Review
- [ ] **Secret Leak Detection**: Scan code to ensure zero active API keys, passwords, or configuration secrets are checked in.
- [ ] **Command Injection Scan**: Ensure that all dynamic shell command calls (if any) have strict validation or sanitization rules.
- [ ] **Error-Bleed Gates**: Verify exceptions are captured by try-except blocks and formatted into user-friendly responses.

---

## 5. Agent Compliance Validation
- [ ] **Context Window Budget**: Confirm active subagent context did not exceed memory limits.
- [ ] **Budget Audit**: Check financial and reasoning economics usage logs.
  - *Total Cost ($)*: `[Insert cost]` | *Max Budget*: `[Insert budget]`
- [ ] **Delegation Rules Met**: Confirm subagents followed clean-delegation paths and did not spin into redundant execution chains.
