# 🌌 ClawGlove Architecture Philosophy

> [!IMPORTANT]
> **Design Principle:**
> Models are replaceable.
> Execution evidence is permanent.

ClawGlove is built on a single, uncompromising structural thesis:

> **Autonomous systems are naturally probabilistic and non-deterministic, but the infrastructure that runs, governs, and audits them must be mathematically deterministic, secure, and bulletproof.**

We do not build agent frameworks. We build the lower-level **Governed Execution Substrate** that contains them. In production environments, enterprise buyers do not just ask if an agent *can* execute a task; they demand to know *what* it did, *why* it did it, and *who* authorized it—especially under failure conditions.

---

## 1. The Core Architectural Pillars

ClawGlove achieves its operational gravity by combining three core engineering primitives into a unified execution substrate:

```text
    ┌────────────────────────────────────────────────────────┐
    │              Forensic Execution Substrate              │
    └───────────────────────────┬────────────────────────────┘
                                │
       ┌────────────────────────┼────────────────────────┐
       ▼                        ▼                        ▼
┌──────────────┐        ┌──────────────┐        ┌────────────────┐
│ Multi-Tenant │        │ Durable Event│        │ Deterministic  │
│  Isolation   │        │  Log Fabric  │        │ Replay Engine  │
└──────────────┘        └──────────────┘        └────────────────┘
```

### I. Multi-Tenant Physical Segregation
We reject the practice of writing all system logs into a single, mixed-ownership file (the "lasagna blob"). ClawGlove enforces strict physical filesystem boundaries for every tenant and domain.
* **Segregated Storage Paths**: `operational/tenant_gamma/`, `audit/system/`, `security/system/`.
* **Zero Cross-Tenant Leaks**: Access to logs is gated by strict boundary authorization checks before any operational file I/O is performed.

### II. Durable, Cryptographically Chained Event Log Fabric
Event logs in ClawGlove are the system of record. Every state change, API call, and telemetry metric flows through our `EventStore`.
* **Asynchronous Rotation & Compression**: Active log files are automatically rotated on size limits and compressed to `.jsonl.gz` in a non-blocking background thread.
* **Forensic Metadata Sidecars**: Every compressed archive is written with residency tags (`"region": "eu-west"`) to fulfill corporate compliance.
* **Rolling Cryptographic Hash & Epoch Chains**: The lineage of rotated archives is linked using a sequence of rolling SHA-256 hashes and **Archive Epoch IDs**. An active log file immediately records an `ARCHIVE_LINK` pointing to the previous hash, rendering silent log tampering mathematically impossible.
* **Stable Event Canonicalization**: Standardizes all on-disk event serialization by sorting dictionary keys (`sort_keys=True`) and enforcing stable UTF-8 normalization, future-proofing archive hashing against formatting drift.

### III. Deterministic Replay Engine & O(delta) State Hydration
In most frameworks, "replaying history" means scanning millions of lines of logs in an $O(N)$ loop—an approach that becomes a bottleneck as a system ages.
* **O(delta) Hydration Optimization**: ClawGlove captures isolated **State Snapshots** (`snapshots/{tenant_id}/snapshot_{timestamp}.json`). On boot or system recovery, `ReplayEngine` loads the latest snapshot anchor to instantly hydrate the state manager, and then scans the `EventStore` only for the delta interval `(sequence > snapshot.last_sequence)`.
* **Strict Schema Version Locking**: To prevent "archaeology with landmines" during schema migrations, `ReplayEngine` enforces strict version locks, immediately raising a `ReplaySchemaMismatch` exception if a snapshot does not match the active engine schema version.
* **The Replay Validation Envelope**: Replay sessions emit an immutable cryptographic validation packet confirming events scanned, events restored, skipped corruption count, snapshot anchor loaded, and the verified status of the cryptographic hash chain.

---

## 2. Boringly, Terrifyingly Reliable (The Chaos Paradigm)

We do not prove our architecture with simple chatbots or "employee simulations." We prove it by subjecting the core substrate to extreme adversarial entropy in our **Chaos Engineering Suite**:
* **Heartbeat Storms (`CHAOS-001`)**: Flooding the monitor with 50,000 duplicate signals.
* **Concurrent Replays (`CHAOS-002`)**: Running state sweeps while actively appending 15,000 tasks concurrently under raw disk write conditions.
* **Clock Skew (`CHAOS-003`)**: Forcing time-travel and time-drift skew between cluster nodes.
* **Disk Freezes & Backpressure (`CHAOS-004`)**: Injecting I/O write delays to force backpressure queue saturation and autoscaler scale-up coordination.
* **EventStore Integrity Recovery (`CHAOS-005`)**: Injecting raw database corruption during active replays.
* **Snapshot Hydration & Schema Locking (`CHAOS-006`)**: Verifying mathematical O(delta) recovery correctness and strict schema version locks under recovery failure sweeps.

This is infrastructure built for platforms where failure is not an option. It is the plumbing that turns probabilistic AI workflows into **boringly, terrifyingly reliable enterprise operations**.
