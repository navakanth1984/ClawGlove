# ClawGlove

Governed execution substrate for autonomous AI agents.

```
LLM / Agent Framework
        ↓
ClawGlove Sidecar (policy engine + event ledger)
        ↓
Kafka (events) + etcd (state) + Docker (isolation)
        ↓
OpenTelemetry → Jaeger / Prometheus
```

## What this is

An out-of-process sidecar that enforces compiled policies on every agent action,
logs every event to a durable Kafka ledger, and isolates agent workloads inside
Docker containers. The agent cannot bypass governance because governance runs in
a separate process the agent has no access to.

## Quick start

**Prerequisites**: Docker Desktop, Python 3.10+, WSL2 (Windows) or Linux

### 1. Start the infrastructure

```bash
docker compose up -d
# Wait for health checks to pass (~30 seconds)
docker compose ps
```

### 2. Install ClawGlove

```bash
pip install -e ".[dev]"
```

### 3. Install the Git hook (locks tests/eval/ from AI modification)

```bash
cp .git-hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### 4. Start the sidecar daemon

```bash
clawglove-daemon --policies ./policies/ --kafka localhost:9092 --port 50051
```

### 5. Test the sidecar from a Python shell

```python
from clawglove.sidecar.client import ClawGloveClient, PolicyViolationError

client = ClawGloveClient(tenant_id="tenant_alpha")
assert client.ping()

# Allowed action
client.check("llm_call", {"tokens_used": 500})
print("allowed")

# Denied action
try:
    client.check("escalate_privileges", {})
except PolicyViolationError as e:
    print(f"blocked: {e}")
```

### 6. Write the eval harness (YOU must do this — not the AI)

Open `tests/eval/run_empirical_eval.py` and fill in:
- `violation_01` through `violation_25` — actions your OpenClaw agents
  should NOT be able to do
- `clean_run_01` through `clean_run_25` — normal agent actions that
  should always be allowed

Base the violations on what OpenClaw agents actually do. Confirm OpenClaw's
execution model before writing these.

Then lock the file:

```bash
# Windows
icacls tests\eval\ /deny navka:(OI)(CI)(W)

# Linux / WSL2
chmod -R 555 tests/eval/
```

### 7. Run the certification eval

```bash
python tests/eval/run_empirical_eval.py
```

Both gates must pass before deploying:
- `M_detection >= 98%`
- `M_false_positive <= 2%`

## Adding a new tenant

Copy `policies/tenant_alpha.yaml`, rename it, set `tenant_id`, configure
the allowed/denied actions. Restart the sidecar. No code changes needed.

## Project structure

```
clawglove/
├── clawglove/
│   ├── interfaces/       # Frozen ABC contracts — do not modify
│   ├── events/           # Kafka EventStore
│   ├── tenants/          # Docker container isolation
│   ├── runtime/          # etcd coordinator
│   ├── metrics/          # OpenTelemetry
│   ├── policies/         # YAML compiler + runtime engine
│   └── sidecar/          # Daemon + client
├── policies/             # Tenant policy YAML files
├── tests/eval/           # HUMAN-WRITTEN empirical eval (locked)
├── docs/manifesto/       # Frozen architecture specs (locked)
├── docker-compose.yml
└── pyproject.toml
```

## Design principles (from docs/manifesto/ARCHITECTURE_PHILOSOPHY.md)

1. Evidence over orchestration
2. Determinism over abstraction
3. Containment over autonomy theater
4. Zero-trust execution assumptions
5. Air-gapped verification first
6. Stable ABI contracts over rapid feature churn
