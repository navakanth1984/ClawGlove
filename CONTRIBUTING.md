# Contributing to ACDLC Core

We are thrilled that you want to help build and secure the governed execution substrate for autonomous systems! 

ACDLC is designed as high-integrity, high-performance infrastructure. To ensure we maintain absolute determinism, systems correctness, and legal defensive compliance, all contributions must adhere to our strict contribution protocols.

---

## 1. The Clean-Room Mandate

To protect the platform's open core and ensure compliance for enterprise environments:
* **No License Contamination**: We only accept contributions that are 100% original work or clearly licensed under Apache 2.0 or MIT.
* **No GPL/AGPL Dependencies**: Do not introduce any dependencies containing copyleft or restrictive commercial licensing obligations.
* **Branding Integrity**: All documentation and code comments must preserve our core positioning terminology (e.g., *Governed Agent Substrate*, *Forensic Replay Engine*, *EventStore*, *Forensic Package*). Do not introduce buzzword drift (e.g., *Agent OS*, *AGI*, *Superintelligence*).

---

## 2. Strict Platform ABI Versioning Constraints

ACDLC exposes a locked **Platform ABI (Version 1.0)**. 
* **Backward Compatibility**: Changes must not break existing forensic contracts. Do not modify the schema layout of the `.acdlc-replay` Forensic Package, snapshot formatting, or active log routing rules without an approved RFC.
* **Determinism Invariance**: Code changes must be mathematically proven to preserve time-travel replay consistency. Replaying identical EventStore segments must yield identical reconstructed state manager states.

---

## 3. Contribution Workflow

1. **Triage & Discuss**: Before writing any code, search the issue tracker or open a discussion outlining your planned changes.
2. **Fork & Branch**: Create a feature branch off of `main` (e.g., `feature/custom-storage-backend` or `fix/concurrency-race`).
3. **Write Tests**: Every functional modification must be validated by an accompanying Python runner simulation inside `simulations/stress/` or `simulations/chaos/`.
4. **Execute Verification**:
   ```bash
   # Run the golden path induction verification
   python examples/secure_agent_runtime/run_golden_path.py
   
   # Run the full automated chaos verification suite
   python simulations/chaos/chaos_006_snapshot_hydration.py
   python simulations/chaos/chaos_002_concurrent_replay.py
   ```
5. **Verify the AST Graph**: Run `graphify update .` to ensure your newly added classes, structures, and links are indexed cleanly within the AST code graph.
6. **Submit PR**: Open a Pull Request detailing the changes made, the specific chaos/stress test run results, and confirm adherence to the Apache 2.0 guidelines.

---

## 4. Code Review & Code Style

* **Language**: Standard Python (3.10+). Keep dependencies at zero for core primitives (`event_store.py`, `replay.py`, `authorization.py`).
* **Formatting**: Follow PEP 8 guidelines. Standardize JSON serialization across all file outputs with sorted keys (`sort_keys=True`) and UTF-8 encoding.
* **Robustness**: Build for failure. Your functions should expect clock skew, disk latency delays, malformed JSON inputs, and network partition fencing from the start.
