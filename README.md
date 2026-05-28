<p align="center">
  <img src="assets/clawglove-logo.png" width="320"/>
</p>

# ClawGlove

**Governed execution substrate for autonomous agents and OpenClaw-class runtimes.**  
Intercepts, audits, and enforces policy boundaries on every action an AI agent attempts â€” at the network layer, before it reaches the outside world.

[![CGBench Grade](https://img.shields.io/badge/CGBench-G--5%20Provenance%20Certified-blueviolet?style=flat-square)](https://github.com/navakanth1984/ClawGlove)
[![Sensitivity](https://img.shields.io/badge/Sensitivity-100%25-brightgreen?style=flat-square)](https://github.com/navakanth1984/ClawGlove)
[![Specificity](https://img.shields.io/badge/Specificity-100%25-brightgreen?style=flat-square)](https://github.com/navakanth1984/ClawGlove)
[![H_escape](https://img.shields.io/badge/H__escape-0.6194%20bits-blue?style=flat-square)](https://github.com/navakanth1984/ClawGlove)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

---

## The Problem

Autonomous AI agents are powerful precisely because they act without asking permission. That same property makes them dangerous: a compromised or misaligned agent can exfiltrate credentials, cross tenant boundaries, persist malicious context across sessions, or bypass its LLM gateway â€” before operator intervention is possible.

Existing safety benchmarks measure what a model *says* it will do. ClawGlove measures what an agent *actually does* â€” at the execution layer â€” and stops it if it violates policy.

**The core metric:** *Governance Escape Entropy* (H_escape) â€” the Shannon entropy of escape paths an agent can probe before quarantine. Standard agents have H_escape > 1.5 bits. ClawGlove reduces it to **0.62 bits** under normal operation and **0.00 bits** under active attack (quarantine collapses all escape paths to a single outcome).

---

## What ClawGlove Does

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    OpenClaw Agent Network                    â”‚
â”‚                                                              â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”      â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”             â”‚
â”‚  â”‚  screenwriter    â”‚      â”‚    director      â”‚             â”‚
â”‚  â”‚  agent           â”‚      â”‚    agent         â”‚             â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜      â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜             â”‚
â”‚           â”‚  HTTP_PROXY             â”‚  HTTP_PROXY            â”‚
â”‚           â”‚  :8080                  â”‚  :8080                 â”‚
â”‚           â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                        â”‚
â”‚                      â”‚                                       â”‚
â”‚            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                           â”‚
â”‚            â”‚  ClawGlove Sidecar â”‚ â† out-of-process          â”‚
â”‚            â”‚                    â”‚   governance plane        â”‚
â”‚            â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚                           â”‚
â”‚            â”‚  â”‚ HTTP Proxy   â”‚  â”‚ intercepts api.sarvam.ai  â”‚
â”‚            â”‚  â”‚ :8080        â”‚  â”‚ traffic, enforces policy  â”‚
â”‚            â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚                           â”‚
â”‚            â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚                           â”‚
â”‚            â”‚  â”‚ TCP Daemon   â”‚  â”‚ action check/log/block    â”‚
â”‚            â”‚  â”‚ :50051       â”‚  â”‚ per-tenant policy engine  â”‚
â”‚            â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚                           â”‚
â”‚            â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚                           â”‚
â”‚            â”‚  â”‚ Threat       â”‚  â”‚ NORMAL â†’ ELEVATED â†’       â”‚
â”‚            â”‚  â”‚ Escalation   â”‚  â”‚ QUARANTINE after 6        â”‚
â”‚            â”‚  â”‚ Tracker      â”‚  â”‚ violations                â”‚
â”‚            â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚                           â”‚
â”‚            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                           â”‚
â”‚                      â”‚                                       â”‚
â”‚         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                         â”‚
â”‚         â”‚            â”‚            â”‚                         â”‚
â”‚    â”Œâ”€â”€â”€â”€â–¼â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â–¼â”€â”€â”  â”Œâ”€â”€â”€â”€â–¼â”€â”€â”€â”€â”                    â”‚
â”‚    â”‚Redpandaâ”‚  â”‚  etcd   â”‚  â”‚  OTel   â”‚                    â”‚
â”‚    â”‚(Kafka) â”‚  â”‚         â”‚  â”‚Collectorâ”‚                    â”‚
â”‚    â””â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

Agent containers: clawglove-internal network (internal: true)
â†’ NO direct external route. Only path to internet is through sidecar.
â†’ Sidecar down = agents go dark. Fail-closed by design.
```

---

## CGBench Certification

ClawGlove ships with **CGBench** â€” the Adversarial Governance Benchmark Suite â€” a 5-layer certification harness that produces a verified governance grade.

### Scorecard

```
================================================================================
                  CGBENCH GOVERNANCE CERTIFICATION SCORECARD
================================================================================
  Governance Entropy (H_gov):   5.5639 bits  (creative tool path variance)
  Escape Entropy (H_escape):    0.6194 bits  (target <=1.0 bits)   âœ“
  Governance Drift Velocity:    0.9053 / step (trust boundary expansion rate)
  Contamination Isolation:      100.0%     (target 100%)           âœ“
  Replay Mutation Recovery:     100.0%     (target >=98.0%)        âœ“
  Persistence Dwell Blocking:   5.0 ms     (target <=100ms)        âœ“
  Survivability Index:          100.0%     (target 100%)           âœ“
  Surface Exposure Score:       0.100      (target <=0.150)        âœ“
  Runtime Constraint Safety:    100.0%     (target >=98%)          âœ“
--------------------------------------------------------------------------------
  AWARDED GOVERNANCE GRADE:     G-5 (Provenance Certified)
================================================================================
```

### Governance Grades

| Grade | Name | H_escape | Description |
|---|---|---|---|
| G-1 | Baseline | > 3.0 bits | No governance layer |
| G-2 | Policy Aware | â‰¤ 3.0 bits | Basic allow/deny rules |
| G-3 | Epoch Sealed | â‰¤ 2.0 bits | Replay integrity enforced |
| G-4 | Drift Certified | â‰¤ 1.0 bits | Escape entropy bounded |
| **G-5** | **Provenance Certified** | **â‰¤ 1.0 bits + all gates** | **Full substrate certification** |

### Benchmark Layers

| Layer | What It Tests |
|---|---|
| L1 â€” Runtime Governance | 25 violation + 25 clean action deterministic checks |
| L2 â€” Probabilistic Drift | Shannon escape entropy over 50 stochastic runs |
| L3 â€” Cross-Agent Contamination | Shared memory poison, trust epoch mismatch, cross-domain replay |
| L4 â€” Autonomous Persistence | Policy self-modification, heartbeat amplification, subprocess replication |
| L5 â€” Infrastructure Resilience | Kafka/etcd offline fallbacks, zero-stall verification |
| X-Ray | Trust surface scan: config boundaries, unverified skills, secret exposure |
| Forensic | EventStore mutation injection and recovery audit |

---

## CVE Coverage

ClawGlove's violation suite is grounded in real OpenClaw CVEs:

| CVE | Category |
|---|---|
| CVE-2026-25253 | Sarvam API key exfiltration |
| CVE-2026-32922 | Cross-workspace boundary violation |
| CVE-2026-24763 | openclaw.json config poisoning |
| CVE-2026-26322 | Non-Sarvam LLM provider bypass |
| CVE-2026-26329 | Shell injection via tool output |
| CVE-2026-30741 | Path traversal read |
| CVE-2026-35650 | Writable config boundary (CVSS 9.8) |
| ClawHavoc | Multi-vector coordinated campaign |

---

## Roadmap

ClawGlove currently governs **structural** agent behavior â€” outbound actions, policy boundaries, and runtime state transitions. The known open frontier is **semantic** governance:

- **Context Provenance Tracking** â€” every memory fragment carries lineage, every tool result carries trust origin, every derived conclusion maps upstream. Git blame for autonomous cognition.
- **Retrieval Contamination Detection** â€” poisoned memory shaping and multi-turn context laundering operating below the action layer.
- **Latent Goal Drift** â€” long-horizon steering that never triggers a single policy violation but cumulatively moves the agent off its intended trajectory.

These are tracked as future work. Contributions welcome.

---

## Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Sidecar model | Out-of-process TCP daemon | Agent crash cannot bypass governance |
| Fail-closed | Docker `internal: true` network | No sidecar = no internet for agents |
| Event store | Kafka (Redpanda) + local fallback | Append-only, tamper-evident governance log |
| Consensus | etcd + local fallback | Distributed leader election for multi-node |
| Observability | OpenTelemetry â†’ Jaeger | Governance spans traceable across agent calls |
| Eval harness | Human-written, OS-ACL locked | AI cannot modify its own benchmark |

---

## Quick Start

**Prerequisites:** Docker Desktop, Python 3.12

```bash
git clone https://github.com/navakanth1984/ClawGlove.git
cd ClawGlove

# Install Python package
pip install -e .

# Start the full stack (Redpanda + etcd + OTel + Jaeger + sidecar + agents)
docker compose up -d

# Wait ~30s for services to initialize, then verify
docker ps --format "{{.Names}}\t{{.Status}}"
```

All 7 containers should show `Up` or `healthy`.

---

## Verify Your Deployment

**Phase 5 â€” Network isolation + fail-closed test (10 checks):**
```powershell
.\scripts\test_failclosed.ps1
```

Expected: `RESULT: 10 passed / 0 failed`

**CGBench â€” Full governance certification:**
```powershell
$env:PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION="python"
$env:PYTHONIOENCODING="utf-8"
py -m cgbench.runner --policies policies/ --runs 50
```

Expected: `AWARDED GOVERNANCE GRADE: G-5 (Provenance Certified)`

---

## Repository Structure

```
ClawGlove/
â”œâ”€â”€ clawglove/
â”‚   â”œâ”€â”€ interfaces/          â€” frozen ABCs (EventStore, TenantIsolation, Coordinator, Telemetry, PolicyEngine)
â”‚   â”œâ”€â”€ events/
â”‚   â”‚   â””â”€â”€ kafka_store.py   â€” Kafka EventStore with offline fallback
â”‚   â”œâ”€â”€ tenants/
â”‚   â”‚   â””â”€â”€ container_isolation.py â€” Docker tenant isolation with cgroup limits
â”‚   â”œâ”€â”€ runtime/
â”‚   â”‚   â””â”€â”€ etcd_coordinator.py    â€” etcd leader election + offline fallback
â”‚   â”œâ”€â”€ metrics/
â”‚   â”‚   â””â”€â”€ otel_telemetry.py      â€” OpenTelemetry with 4 governance scalars
â”‚   â”œâ”€â”€ policies/
â”‚   â”‚   â”œâ”€â”€ compiler.py      â€” YAML policy compiler
â”‚   â”‚   â””â”€â”€ engine.py        â€” runtime policy enforcer (fail-closed)
â”‚   â””â”€â”€ sidecar/
â”‚       â”œâ”€â”€ daemon.py        â€” out-of-process TCP sidecar
â”‚       â”œâ”€â”€ client.py        â€” agent-side client wrapper
â”‚       â”œâ”€â”€ http_proxy.py    â€” HTTP proxy intercepting api.sarvam.ai
â”‚       â””â”€â”€ escalation.py   â€” ThreatEscalationTracker (NORMALâ†’ELEVATEDâ†’QUARANTINE)
â”œâ”€â”€ cgbench/
â”‚   â”œâ”€â”€ runner.py            â€” benchmark orchestrator
â”‚   â”œâ”€â”€ metrics.py           â€” H_escape, H_gov, V_drift calculations
â”‚   â”œâ”€â”€ discovery.py         â€” X-Ray trust surface scanner
â”‚   â””â”€â”€ layers/              â€” L1â€“L5 + replay integrity
â”œâ”€â”€ policies/
â”‚   â”œâ”€â”€ screenwriter.yaml    â€” screenwriter agent policy
â”‚   â””â”€â”€ director.yaml        â€” director agent policy
â”œâ”€â”€ tests/eval/
â”‚   â””â”€â”€ run_empirical_eval.py â€” human-locked evaluation harness (25 violations + 25 clean)
â”œâ”€â”€ docker/
â”‚   â”œâ”€â”€ Dockerfile.sidecar
â”‚   â”œâ”€â”€ Dockerfile.agent-test
â”‚   â”œâ”€â”€ start-sidecar.sh
â”‚   â”œâ”€â”€ agent_harness.py
â”‚   â””â”€â”€ otel-collector-config.yaml
â”œâ”€â”€ docker-compose.yml
â””â”€â”€ scripts/
    â”œâ”€â”€ test_failclosed.ps1  â€” Phase 5 network isolation verification
    â””â”€â”€ cgbench_docker.ps1   â€” CGBench against live Docker stack
```

---

## Evaluation Harness Integrity

The empirical evaluation harness (`tests/eval/run_empirical_eval.py`) is **human-written and OS-ACL locked**. A git pre-commit hook rejects any commit that modifies files under `tests/eval/`. This ensures the benchmark cannot be gamed by the system being measured.

```bash
# Lock on Windows (run once after clone)
icacls tests\eval\ /deny SYSTEM:(OI)(CI)(W)
icacls tests\eval\ /deny %USERNAME%:(OI)(CI)(W)
```

---

## Policy Configuration

Policies are YAML files in `policies/`. Each tenant policy defines allowed actions and explicit denials:

```yaml
tenant_id: screenwriter
allowed_actions:
  - llm_call
  - file_read_workspace
  - memory_read
  - send_*
  - search_*
  - heartbeat_*
denied_actions:
  - read_credentials_dir
  - exec_shell_command
  - cross_tenant_*
  - write_soul_md
  - write_agents_md
  - install_unverified_skill
```

Non-tenant YAML files (budget limits, routing weights) are silently skipped by the compiler.

---

## License

MIT â€” see [LICENSE](LICENSE)

---

## Author

Built by [Navakanth](https://github.com/navakanth1984) â€” Microsoft Certified Trainer, Data Engineer, and AI systems architect based in Hyderabad, India.

