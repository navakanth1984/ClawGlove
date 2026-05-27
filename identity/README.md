# ACDLC Identity Service

The Identity Service is the foundational OS-level subsystem introduced in **ACDLC v1.7**. It replaces the static skill catalog model with a dynamic agent identity layer that carries live trust scores, execution reputation, and resource quotas.

## Architecture

```text
ProfileManager          ← builds and validates AgentProfile objects
       ↓
IdentityRegistry        ← in-memory agent profile store (keyed by agent_id)
       ↓
TrustEngine             ← computes clamped trust scores [0.0, 1.0]
       ↓
ReputationEngine        ← tracks success/failure history → feeds TrustEngine
       ↓
QuotaManager            ← enforces per-agent token, concurrency, and retry limits
```

## OS Analogy

| OS Concept  | ACDLC v1.7       |
|---|---|
| User        | Agent            |
| Permissions | Trust Level      |
| Scheduler   | Routing Engine   |
| Processes   | Tasks            |
| Resources   | Quota Manager    |

## Module Reference

| File | Purpose |
|---|---|
| `registry.py` | Stores and retrieves live agent profiles |
| `profile_manager.py` | Builds validated `AgentProfile` dicts matching `schemas/agent-profile.json` |
| `trust_engine.py` | Computes clamped `[0.0, 1.0]` trust scores from profile state |
| `reputation_engine.py` | Records success/failure/violation history and feeds trust penalties |
| `quota_manager.py` | Enforces per-agent daily token budget, concurrency, and retry limits |

## Trust Score Formula

```text
raw = trust_level_base - (policy_violations × 0.1) + (recent_successes × 0.05)
trust_score = max(0.0, min(1.0, raw))   # Hard-clamped to [0.0, 1.0]
```

Trust level bases (`policies/routing-weights.yaml`):
- `high` → 0.90
- `standard` → 0.70
- `restricted` → 0.40

## Reputation Scorecard Output

```json
{
  "agent_id": "builder_001",
  "success_rate": 0.97,
  "avg_retry_count": 0.3,
  "policy_violations": 1,
  "trust_score": 0.88
}
```

## Integration Points

- `runtime/routing_engine.py` reads `trust_score` from `TrustEngine.get_score(agent_id)` during route selection
- `runtime/state_manager.py` calls `ReputationEngine.record_success()` / `record_violation()` on terminal events
- `identity/registry.py` publishes `AGENT_REGISTERED` / `AGENT_DEREGISTERED` events to the Event Bus
