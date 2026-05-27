# Attribution & Architectural Ancestry

ACDLC is a clean-room, independently designed governed agent runtime built from the ground up for policy-controlled autonomous systems. In the spirit of open engineering, transparency, and defensive intellectual property clarity, this document records our architectural inspirations, lineage, and external design patterns.

## 1. Core Architectural Inspirations

While the implementation of the ACDLC operating substrate is entirely original, we draw inspiration from established distributed computing, event-driven infrastructure, and observability paradigms:

### A. Event-Sourced Agent Architectures
* **Inspiration**: The concept of representing autonomous software executions as a durable, replayable log.
* **Relation**: Research frameworks like **ESAA (Event Sourcing for Autonomous Agents)** describe the theoretical value of replayability in LLM-based software engineering. ACDLC shares this core thesis but goes significantly deeper by implementing a concrete, production-ready multi-tenant runtime with **O(delta) Snapshot Hydration**, **cryptographic SHA-256 rolling archive chains**, and strict **Schema Locking** designed for enterprise systems rather than research sandboxes.

### B. Distributed Orchestration Platforms
* **Inspiration**: **Temporal** (and its predecessor AWS Simple Workflow).
* **Relation**: We admire Temporal's approach to durable execution and deterministic time-travel state reconstruction. ACDLC adapts this durability-first philosophy to the unique requirements of autonomous AI systems, implementing active policy interceptors and sandboxed boundary enforcement at the execution engine layer.

### C. System Observability & Tracing
* **Inspiration**: **OpenTelemetry**.
* **Relation**: Standardized span tracing and semantic metrics envelopes are critical to enterprise ops. ACDLC implements its own lightweight telemetry Managers to handle micro-second execution logs, but aligns conceptually with OpenTelemetry's metrics categories to facilitate future exporter plug-ins.

### D. Agent Orchestration Frameworks
* **Inspiration**: **LangGraph**, **Microsoft AutoGen**, and **Semantic Kernel**.
* **Relation**: These libraries focus on developer ergonomics, prompt orchestration, and routing. ACDLC is **not** an agent-writing framework. It acts as the lower-level execution substrate that sits underneath these frameworks, enforcing tenant boundaries, token ceilings, priority scheduling, and cryptographic auditability for the agents they orchestrate.

---

## 2. Terminology Safeguards & Originality

To avoid branding confusion, ACDLC defines its own distinct, descriptive, and trademark-compliant systems vocabulary:
* **Governed Agent Runtime / Substrate**: The core executing kernel (avoiding terms like *Agent OS* or *Agent Mesh*).
* **EventStore**: The append-only durable log partitioned by tenant and domain.
* **Replay Validation Envelope**: The cryptographic and forensic metadata packet validating audit trails.
* **Active Policy Interceptors**: Sandboxed execution rules evaluated inside the priority scheduler.

---

## 3. Clean-Room Implementation Guarantees

All code inside this repository—including our telemetry managers, tiered storage architectures, priority task queues, cryptographic hash and epoch chaining, and chaos simulations—has been developed independently without direct inclusion of third-party source files or restricted licenses (GPL/AGPL). All external dependencies are tracked cleanly under `pyproject.toml` and are bounded by MIT or Apache 2.0 terms.
