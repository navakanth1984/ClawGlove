# Security Policy & Isolation Guarantees

This document establishes the threat model, security assumptions, isolation boundaries, and the responsible disclosure process for ACDLC.

---

## 1. Threat Model & Isolation Boundaries

ACDLC is designed as a **Governed Execution Substrate** that safely contains and logs autonomous workflows. We assume that the LLM models ("the brains") and the agent actions they execute are naturally probabilistic, noisy, and potentially malicious. Our security model focuses on **containment, reconstruction, and fencing** rather than attempting to enforce security inside the model itself.

```text
       [Untrusted Workload / Probabilistic LLM]
                          │
       Gated By ACDLC Policy & Isolation Substrate
                          ▼
 ┌──────────────────────────────────────────────────┐
 │                   ACDLC Core                     │
 │  ┌─────────────────┐  ┌───────────────────────┐  │
 │  │ Tenant Fencing  │  │ Compiled Policies     │  │
 │  │ (Physical paths)│  │ (Token/tool ceilings) │  │
 │  └────────┬────────┘  └──────────┬────────────┘  │
 └───────────┼──────────────────────┼───────────────┘
             ▼                      ▼
┌────────────────────────┐┌────────────────────────┐
│  Durable EventStore    ││ Replay Verification    │
│  (Rolling Hash Chains) ││ (Evidentiary Provenance│
└────────────────────────┘└────────────────────────┘
```

### A. Tenant Isolation Borders
* **Guarantees**: ACDLC guarantees physical data separation at the filesystem layer. Events are routed dynamically on write into tenant-specific directory partitions (e.g. `operational/tenant_gamma/`).
* **Cross-Tenant Prevention**: Direct file I/O and historical replays are gated by our `AuthorizationEngine`. Replays are strictly restricted to the caller's tenant boundary unless the caller possesses explicit `SystemAdmin` role clearance.

### B. Execution Contamination Defense
* **Compiled Policies**: ACDLC schedules tasks using a sandboxed `PriorityTaskQueue`. Task parameters (such as token consumption limits, delegation depths, and tool sequence calls) are checked by compiled active policy interceptors at execution time.
* **Escalation Gating**: If an active policy is breached, the runtime suspends execution immediately, tags the status as `POLICY_VIOLATION`, and dispatches an immutable `HUMAN_ESCALATION` event to lock down the worker state.

### C. Forensic Durability (Tamper-Evidence)
* **rolling SHA-256 Chains**: The historical log fabric computes rolling cryptographic SHA-256 hashes and sequential **Archive Epoch IDs** across all rotated logs. 
* **Detection**: If a log or archive file is modified, deleted, or injected out of sequence, the `ReplayEngine` chain verification step immediately flags the audit trail as compromised within the **Replay Validation Envelope**.

---

## 2. Reporting a Vulnerability

If you discover a security vulnerability in ACDLC, please report it privately. **Do not open a public GitHub issue.**

### Responsible Disclosure Process
1. Email your findings to the security team at **security@proton.me** or submit a private draft via GitHub Security Advisories.
2. Include a detailed description of the vulnerability, steps to reproduce, and a minimal proof of concept (PoC).
3. We will acknowledge receipt of your report within 24 hours, triage the issue, and coordinate a patch within 15 days.
4. Once the patch is merged and published to the core repository, we will coordinate public disclosure with full attribution to the finder.

---

## 3. Supported Versions

Security updates are actively backported to the following release tracks:

| Version | Supported | Release Date |
| ------- | --------- | ------------ |
| v2.1.x  | ✅ Yes     | 2026-05-27   |
| v2.0.x  | ⚠️ Security | 2026-05-20   |
| < v2.0  | ❌ No      | Obsolete     |
