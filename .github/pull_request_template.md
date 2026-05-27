# Pull Request Checklist: ACDLC Forensic Substrate Hardening

Before submitting this Pull Request, please ensure that your contribution complies with our uncompromising clean-room infrastructure guidelines.

## 1. Naming & Philosophy Standardization
- [ ] Uses only standard terminology: **Governed Execution Substrate for Autonomous Systems**
- [ ] No AGI hype, multi-agent swarm simulation, or "consciousness" theater in code, variable names, or comments.
- [ ] Restrained to core governance, containment, and audit functions.

## 2. ABI Compatibility & Integrity Checks
- [ ] **ABI Stability**: Core platform contracts (`.acdlc-replay` and `Replay Validation Envelope` schemas) are fully preserved. Any change is strictly backward-compatible.
- [ ] **State Canonicalization**: All JSON serialization logic uses deterministic sorting (`sort_keys=True`) and normalizes to standard UTF-8.
- [ ] **Client-Side Autonomy**: No changes inject web sockets, analytics tracking, cloud authentication, or hidden API network dependencies. All verification remains zero-network and runnable offline.

## 3. Verification & Chaos Suite Success
- [ ] The full verification suite passes locally without error:
  ```bash
  python examples/secure_agent_runtime/run_golden_path.py
  ```
- [ ] The new or affected simulations have been validated under active stress:
  ```bash
  python simulations/chaos/chaos_006_snapshot_hydration.py
  ```
- [ ] All diagnostic outputs in `verify_replay.py` use platform-agnostic ASCII formatting to prevent console crashes under alternative code pages.

## 4. Documentation & Lineage Audit
- [ ] **THIRD_PARTY.md** is updated with accurate conceptual attribution if any new systems patterns were adopted.
- [ ] Code modifications do not violate the clean-room Apache 2.0 lineage rules.
- [ ] **THREAT_MODEL.md** is updated if any new threat vectors or containment boundaries were introduced.
