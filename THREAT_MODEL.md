# ACDLC Forensic Threat Model

This document establishes the formal threat catalog, risk rating matrix, mitigation algorithms, and architectural security boundaries of the ACDLC Governed Execution Substrate.

---

## 1. Threat Matrix & Risk Ratings

| Threat ID | Threat Vector | Impact Target | Risk Rating | Architectural Mitigation |
| --------- | ------------- | ------------- | ----------- | ------------------------ |
| **T-001** | Replay Forgery | Event Lineage Audit Trail | **High** | Rolling SHA-256 Hash Chain & Epoch ID Verification |
| **T-002** | Cross-Tenant Bleeding | Logical Memory Boundaries | **Critical** | Physical Directory Partitioning & Auth Gateway Check |
| **T-003** | Snapshot Poisoning | Reconstructive State Manager | **High** | Strict Schema Version Locking (`ReplaySchemaMismatch`) |
| **T-004** | Telemetry Ingestion DoS| Observability Plane | **Medium** | Active 5s Telemetry Sampling & Event Log Throttling |
| **T-005** | Split-Brain Conflict | Cluster Governance & Election | **Critical** | Epoch-Locked Term Registry & Fenced Leadership Promos |
| **T-006** | Task Brain Ledger Poisoning | SQLite State Ledger | **High** | SQLite WAL-level Event Provenance Checking |
| **T-007** | Unsandboxed Multi-Transport Completion | API / Direct System Calls | **Medium** | Pluggable API Adapters (LiteLLM, ACP) with Call Interception |
| **T-008** | Unapproved Cross-Session Skill Accumulation | Long-Term Skill Repositories | **Critical** | Context Provenance Tracking & Skill Quarantine |
| **T-009** | Recursive Self-Evolution / AVO Loops | Agent Identity Continuity | **Critical** | Identity Continuity Protocol (Research / RFC Boundary) |

---

## 2. Granular Threat Breakdowns & Defenses

### 🛡️ T-001: Replay Forgery & Archive Tampering
* **Threat Vector**: An attacker gains root access to host storage, directly edits historical `.jsonl.gz` logs to erase security breaches, and updates file timestamps.
* **Impact**: Forensic reports and replay reconstruction are compromised, producing falsified state history.
* **ACDLC Defense**:
  * **rolling Cryptographic Hash Chain**: Every rotated log file has its SHA-256 hash computed and recorded inside `hash_chain.json`.
  * **Archive Epoch IDs**: Each log rotation writes a standard `ARCHIVE_LINK` event into the newly created active log. This links the active session's starting sequence to the previous archive's hash and sequential epoch counter.
  * **Verification**: During time-travel replay, the engine recalculates the SHA-256 of all rotated partitions and matches them against the hash chain ledger. If any hash discrepancy or missing epoch sequence is detected, the validation envelope flags the audit path as **compromised**.

### 🚪 T-002: Cross-Tenant Data Bleeding
* **Threat Vector**: A compromised agent running in `tenant_alpha` executes a malicious directory traversal or invokes a replay loop targeting `tenant_beta`'s private databases.
* **Impact**: Information disclosure, privacy breach, and unauthorized exfiltration of proprietary tenant memory.
* **ACDLC Defense**:
  * **Physical Fencing**: ACDLC enforces isolation at the storage level. Pathing is partitioned dynamically on I/O. Custom tenants route strictly to subfolders `domain/tenant_id/` under the main data scope.
  * **Pre-Execution Gating**: Before raw reads or replays are initiated, the `AuthorizationEngine` demands SystemAdmin credentials or checks that the identity's `tenant_id` exactly matches the targeted partition boundary. Cross-tenant reads are terminated immediately at the gateway before any file descriptors are allocated.

### 🧬 T-003: Snapshot Poisoning & Schema Evolution Exploits
* **Threat Vector**: An attacker modifies the snapshot `.json` files to inject falsified metrics (e.g. `state["processed_count"] = 999999`) or exploits schema evolution discrepancies to force parsing memory crashes in the reconstruction loop.
* **Impact**: State Manager memory corruption, crash-loop denial of service, or logic bypass.
* **ACDLC Defense**:
  * **Strict Schema Locking**: The `ReplayEngine` demands an exact version match between the snapshot file and the executing Platform ABI (`SUPPORTED_SCHEMA_VERSION = "1.0"`).
  * **Fail-Fast Gating**: If the snapshot schema version drifts, the engine halts immediately and raises a `ReplaySchemaMismatch` exception instead of executing silent, dangerous memory updates.
  * **Stable Event Canonicalization**: Standardizes all on-disk event serialization by sorting dictionary keys (`sort_keys=True`) and enforcing stable UTF-8 normalization. This future-proofs archive hashing against formatting drift.

### 📊 T-004: Telemetry Ingestion DoS & Starvation Storms
* **Threat Vector**: A failing agent loops indefinitely, dispatching 100,000 telemetry events per second to choke CPU execution or fill disks.
* **Impact**: Infrastructure exhaustion, telemetry blindness, or starvation of legitimate priority tasks.
* **ACDLC Defense**:
  * **Active Sampling Policies**: The Telemetry plane limits high-frequency metric sampling (like queue depth) to a fixed 5-second interval.
  * **Backpressure Queueing**: Schedulers employ a `PriorityTaskQueue` that schedules execution based on explicit priority thresholds. If a task queue floods, the autoscaler executes scale-up triggers, isolating high-volume noise threads from P0 recovery lines.

### 🧠 T-005: Split-Brain Consensus Conflict
* **Threat Vector**: A network partition isolates Node A from the cluster. Node A continues to schedule tasks and record states, while Node B promotes itself to Leader and appends conflict sequences.
* **Impact**: State divergence, double-allocation of resources, and historical write conflict.
* **ACDLC Defense**:
  * **Fenced Registry Epochs**: The global state uses an epoch-locked `TermStore`.
  * **Promotion Fencing**: follower promotion is validated against the highest epoch term registered. When a partition heals, Node A's stale writes are immediately rejected by the fenced TermStore because its local epoch is lower than Node B's active term registry.

### 💾 T-006: Task Brain Ledger Poisoning & State Inversion
* **Threat Vector**: An attacker or rogue subprocess gains write-access to the agent's internal SQLite state database (e.g., OpenClaw's Task Brain ledger) and directly writes falsified executions or queued commands.
* **Impact**: Subversion of subagent execution queues, execution of arbitrary non-user tasks, or bypass of session state locks.
* **ACDLC Defense**:
  * **WAL-Level Provenance Checks**: The execution engine monitors SQLite's Write-Ahead Log (WAL) or triggers database assertions on writes, checking the cryptographic hash of the task's parent context block before allowing dispatch.
  * **Log-to-Ledger Cross-Correlation**: Task dispatches from the unified ledger must exactly match the state sequence recorded in the read-only, SHA-256 locked active `.jsonl.gz` event logs.
  * **Sole Authorized Append-Only Exception (Phase 5 Merge Utility)**: The offline synchronization utility `merge_ledgers()` in `sync.py` is the **only** authorized context where ledger tables are cleared (`DELETE`) and chronologically reconstructed to allow re-chaining across disjoint histories. This offline merge path is guarded programmatically using stack-frame inspection to ensure it is **completely unreachable** from the live client runtime write path (`client.py`) and sidecar daemon request loops (`daemon.py`).

### 🌐 T-007: Unsandboxed Multi-Transport API Execution
* **Threat Vector**: Modern agents (like OpenHands) run unsandboxed by default and route commands using LiteLLM or other transport routers rather than standard ACP ports.
* **Impact**: Execution of malicious system commands or network exfiltration outside of restricted proxy channels.
* **ACDLC Defense**:
  * **Pluggable API Call Interceptors**: Integrates hook templates directly into the agent's active completion/routing client (e.g. wrapper around LiteLLM endpoints).
  * **Host-level System Call Shimming**: Combined with out-of-process checks that validate system modifications against predefined workspace and path safety boundaries defined in `safety-boundaries.md`.

### 🎓 T-008: Unapproved Cross-Session Skill Accumulation
* **Threat Vector**: Self-improving agents (like Nous's Hermes Agent) permanently build skills across sessions. A compromised or misaligned agent generates a skill payload that is safe within the active session but acts as a malicious trigger in future sessions.
* **Impact**: State-persistence backdoor, cross-session privilege escalation, or silent corruption of the agent's long-term capabilities without manual audit.
* **ACDLC Defense**:
  * **Context Provenance Tracking (CPT)**: The workspace monitors active skill updates and tags each skill file with an immutable lineage envelope (originating session ID, user request context hash, and validation metrics).
  * **Skill Quarantine Staging**: All newly learned skills are forced into a quarantined directory. They are isolated from active runtime sweeps until explicit, authenticated administrator approval (or matching dynamic security policies).
  * **Skill Diff Auditor**: Generates verifiable diffs of the agent's compiled capability set between sessions, allowing operators to trace skill evolution back to specific historical requests.

### 🧬 T-009: Recursive Self-Evolution / AVO Loops
* **Threat Vector**: Self-evolving coding agents autonomously mutate their own core logic, run validation scripts, keep local code modifications, and execute recursive loops overnight.
* **Impact**: Total loss of capability bounds, generation of highly obfuscated or uncontrollable internal agent behaviors, and complete identity drift.
* **ACDLC Defense**:
  * **Identity Continuity Boundary**: ClawGlove formally treats autonomous self-modification of training loops or model weights as a hard security boundary. Any dynamic modification of internal pipeline executors instantly triggers a system Halt.
  * **Research / RFC Enforcement**: Until robust identity confirmation protocols are designed, the substrate relies on strict write restriction rules on the agent's core files and deployment pipelines.
