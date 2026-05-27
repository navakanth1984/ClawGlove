# ACDLC Substrate Release Roadmap

This roadmap outlines the planned engineering milestones for ACDLC as a secure, policy-governed execution substrate and forensic audit runtime for autonomous systems.

---

## The Containment Evolution Path

```text
                  ┌─────────────────────────────────┐
                  │   Core Engine Stabilized (v2.1) │
                  └────────────────┬────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Phase A: Plugs  │      │  Phase B: Visual │      │ Phase C: Scaling │
│ (Postgres/Kafka) │      │ (Explorer Web UI)│      │  (Multi-Region)  │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

---

## Active & Planned Milestones

### 🏁 Phase 0: Core Durability & Stabilization (Completed)
* **Goal**: Prove multi-tenant boundary correctness, time-travel replay consistency, and $O(\text{delta})$ recovery mechanics under synthetic entropy.
* **Deliverables**:
  * Done: physically segregated tenant log writes and Authorization Gates.
  * Done: Asynchronous background `gzip` rotation with **Archive Epoch IDs** and rolling SHA-256 chains.
  * Done: O(delta) Snapshot Hydration engine with **Strict Schema Version Locking**.
  * Done: Standardized `.acdlc-replay` Forensic Package schema contract and Verification CLI.
  * Done: 6 high-fidelity automated stress and chaos simulations.

### 🔌 Phase A: Pluggable Storage & Persistence Backends (Q3 2026)
* **Goal**: Transition from disk-bound JSONL active logs to pluggable, production-ready enterprise databases while maintaining identical platform ABI properties.
* **Deliverables**:
  * Pluggable Storage Adapter API specification.
  * **Relational Store**: PostgreSQL adapter with transaction-locked writes and native tenant partitioning.
  * **Event Streaming Store**: Apache Kafka / Redpanda adapter to support massive ingestion streams and parallel consumer sweeps.
  * **Cold Storage Archiver**: Object storage adapter (AWS S3, Google Cloud Storage, Azure Blob) supporting background uploads of `.jsonl.gz` compressed partitions.

### 🖥️ Phase B: Time-Travel Web Explorer & Control Plane (Q4 2026)
* **Goal**: Provide operators with high-fidelity visual representations of execution lineage, active policy breaches, and incident timelines.
* **Deliverables**:
  * **Forensic Timeline UI**: A slider interface that loads `.acdlc-replay` evidence packages and allows systems operators to scrub step-by-step through execution loops.
  * **Policy Visualizer Canvas**: Visual dashboard to monitor and test compiled task policies (starvation thresholds, token ceilings, tool loops).
  * **Centralized Control Plane**: Minimal managed control plane offering hosted telemetry ingestion and centralized replay validation logs.

### 🛡️ Phase C: Enterprise Access Controls & Scaling (Q1 2027)
* **Goal**: Enable global-scale governed worker clusters, secrets management, and enterprise-grade organizational borders.
* **Deliverables**:
  * **Access Boundaries**: SSO/SAML, LDAP, and fine-grained Role-Based Access Control (RBAC) integrations.
  * **Managed Secrets Vault**: Automated integrations with HashiCorp Vault, AWS KMS, or GCP Secret Manager to encrypt snapshots and archives at rest.
  * **Multi-Region Sync**: Distributed synchronization algorithms allowing tenant snapshot state anchors to propagate across geographic availability zones safely.

### ⚖️ Phase D: Regulatory Auditing & Compliance Integrations (Q2 2027)
* **Goal**: Bridge the gap between engineering audit logs and corporate legal compliance frameworks.
* **Deliverables**:
  * **EU AI Act & Regulatory Standard Maps**: Auto-generated report exporter mapping ACDLC Forensic Package metrics directly to regional compliance mandates.
  * **Audit Cryptography Package**: Hardware Security Module (HSM) signing of `.acdlc-replay` certificates to prove zero-tampering chain of custody in court-admissible forensic packages.
