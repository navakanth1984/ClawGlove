# AGENTS.md — ClawGlove

> Governed Execution Substrate and Forensic Replay Engine for Autonomous Systems

---

## Project Overview

ClawGlove is a Python-based governed execution framework for autonomous agents. It provides:
- **Runtime governance** — enforced policy evaluation before/during agent action
- **Forensic replay** — deterministic reconstruction of agent execution history
- **Identity & tenant isolation** — multi-tenant agent identity management
- **Observable execution** — OTEL-instrumented metrics, events, and structured logging

The codebase is security-critical. Every change must be evaluated against
`THREAT_MODEL.md` and `SECURITY.md` before merging.

---

## Repository Structure

```
clawglove/        Core Python package — runtime engine, policy evaluator
governance/       Policy definitions, governance rules
policies/         Policy source files (compiled → compiled-policies/)
compiled-policies/ Pre-compiled policy artefacts (DO NOT hand-edit)
runtime/          Execution substrate, agent harness
workers/          Async worker definitions
workflows/        Workflow orchestration
identity/         Tenant identity management
tenants/          Per-tenant configuration
memory/           Agent memory backends
models/           Data models and schema contracts
schemas/          JSON/YAML schema definitions
events/           Event bus, event type registry
analytics/        Metrics aggregation and dashboards
metrics/          Prometheus / OTEL metric definitions
tests/            All tests — unit, integration, simulation
simulations/      Simulation harness for replay testing
cgbench/          Benchmark suite (outputs: cgbench_certification_report.md)
docs/             Long-form documentation
rfcs/             Architectural RFCs (read before implementing major features)
scripts/          Dev tooling — setup, migration, CI helpers
docker/           Dockerfile definitions per service
cluster/          Cluster deployment configs
registry/         Agent/plugin registry
assets/           Static assets, diagrams
templates/        Code and config templates
.github/          CI/CD workflows
.git-hooks/       Pre-commit hooks (install via scripts/)
```

---

## Tech Stack

- **Language**: Python 3.11+
- **Build**: `pyproject.toml` (PEP 621)
- **Containerisation**: Docker + Docker Compose (`docker-compose.yml`)
- **Observability**: OpenTelemetry (`otel-collector-config.yaml`)
- **Policy engine**: Compiled policy format (see `compiled-policies/`)
- **State backend**: etcd (`fix_etcd.py` — etcd migration utilities)
- **Runtime state**: `runtime_state.json` (never commit with live state)

---

## Critical Rules

### Security
- **NEVER** weaken a policy without explicit human sign-off and THREAT_MODEL.md update.
- **NEVER** commit secrets, credentials, or API keys. The `.gitignore` is strict — respect it.
- `SECURITY.md` defines the vulnerability disclosure process. Follow it.
- All code touching `identity/`, `tenants/`, or `governance/` requires security review comment in PR.

### Policies
- Edit **source** policies in `policies/` only. Never hand-edit `compiled-policies/`.
- Re-compile policies after any edit using the scripts in `scripts/`.
- Policy changes must include a simulation run in `simulations/` as proof of regression-free behaviour.

### Architecture
- Read `ARCHITECTURE.md` and `ARCHITECTURE_PHILOSOPHY.md` before adding new modules.
- Major structural changes require an RFC in `rfcs/` first.
- All new modules must have a corresponding entry in `registry/`.

### Testing
- All PRs must pass `tests/` suite. Run: `python -m pytest tests/`
- Benchmark regressions in `cgbench/` must be explained in the PR body.
- Simulation tests in `simulations/` must be re-run for any runtime/workflow change.

### Commits & PRs
- Write atomic commits. One logical change per commit.
- PR description must reference the relevant RFC or ADR if applicable.
- Tag security-sensitive PRs with `security` label.

---

## Build & Run

```bash
# Install dependencies
pip install -e ".[dev]"

# Install git hooks
bash scripts/install-hooks.sh

# Start full stack locally
docker-compose up

# Run tests
python -m pytest tests/ -v

# Run benchmarks
python -m cgbench run

# Compile policies
python scripts/compile_policies.py
```

---

## Jules-Specific Guidance

- **Priority fix areas**: `fix2.py`, `fix3.py`, `fix_etcd.py`, `fix_harness.py` are known
  temporary patches — they are candidates for proper resolution; don't extend them further.
- **manifest.yaml** and **VERSION** must stay in sync — update both when bumping versions.
- When writing tests, prefer the simulation harness in `simulations/` for end-to-end coverage.
- `SKILL.md` describes the AI skill interface — update it when agent APIs change.
- Do not modify `runtime_state.json` — it is runtime-generated.
- When in doubt, check `ROADMAP.md` for intended direction before implementing.
