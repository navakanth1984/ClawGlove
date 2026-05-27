import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import yaml
except ImportError:
    yaml = None

from runtime.event_bus import EventBus, Event

# Numeric competency weights used in the scoring formula
COMPETENCY_WEIGHTS = {
    "expert": 1.00,
    "advanced": 0.75,
    "intermediate": 0.50,
    "standard": 0.25
}

# Fallback weights if routing-weights.yaml cannot be loaded
DEFAULT_WEIGHTS = {
    "capability_weight": 0.5,
    "trust_weight": 0.3,
    "load_weight": 0.2,
    "saturation_threshold": 0.85
}


class RoutingEngine:
    """Weighted multi-factor routing engine for capability-aware agent selection.

    Decision pipeline:
        Candidates filtered by required_capability key presence
            ↓
        score = (capability_weight  × competency_score)
              + (trust_weight       × trust_score)
              + (load_weight        × (1.0 - current_load))
            ↓
        Highest-score candidate selected (saturation check applied first)
            ↓
        ROUTE_SELECTED event published to Event Bus

    Weights are loaded from policies/routing-weights.yaml at initialisation
    so routing behaviour is policy-driven rather than hard-coded.
    """

    def __init__(self, trust_engine=None, policy_dir=None):
        """
        Args:
            trust_engine: Optional TrustEngine instance. If provided, live trust
                          scores are fetched per agent. If None, profile trust_level
                          is used as a static fallback.
            policy_dir:   Override path for policy files (defaults to policies/)
        """
        self._trust_engine = trust_engine
        self._event_bus = EventBus()

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        policy_dir = policy_dir or os.path.join(base_dir, "policies")
        self._load_weights(os.path.join(policy_dir, "routing-weights.yaml"))

    # ------------------------------------------------------------------ #
    #  Weight Initialisation                                               #
    # ------------------------------------------------------------------ #

    def _load_weights(self, path):
        """Loads routing weights from YAML policy file with safe defaults."""
        if yaml is None:
            print("[ROUTER] PyYAML is not installed. Falling back to default routing weights.")
            self.capability_weight = DEFAULT_WEIGHTS["capability_weight"]
            self.trust_weight = DEFAULT_WEIGHTS["trust_weight"]
            self.load_weight = DEFAULT_WEIGHTS["load_weight"]
            self.saturation_threshold = DEFAULT_WEIGHTS["saturation_threshold"]
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            weights = data.get("routing_weights", {})
            self.capability_weight = float(weights.get("capability_weight",
                                                        DEFAULT_WEIGHTS["capability_weight"]))
            self.trust_weight = float(weights.get("trust_weight",
                                                   DEFAULT_WEIGHTS["trust_weight"]))
            self.load_weight = float(weights.get("load_weight",
                                                   DEFAULT_WEIGHTS["load_weight"]))
            self.saturation_threshold = float(
                data.get("saturation_threshold",
                         DEFAULT_WEIGHTS["saturation_threshold"])
            )
            print(f"[ROUTER] Weights loaded from policy: "
                  f"cap={self.capability_weight}, trust={self.trust_weight}, "
                  f"load={self.load_weight} (saturation>{self.saturation_threshold})")
        except Exception as e:
            print(f"[ROUTER] Failed to load routing-weights.yaml, using defaults: {e}")
            self.capability_weight = DEFAULT_WEIGHTS["capability_weight"]
            self.trust_weight = DEFAULT_WEIGHTS["trust_weight"]
            self.load_weight = DEFAULT_WEIGHTS["load_weight"]
            self.saturation_threshold = DEFAULT_WEIGHTS["saturation_threshold"]

    # ------------------------------------------------------------------ #
    #  Scoring                                                             #
    # ------------------------------------------------------------------ #

    def compute_score(self, agent, required_capability, current_load=0.0):
        """Computes weighted routing score for a single agent candidate.

        Args:
            agent:               Agent profile dict (must contain 'capabilities')
            required_capability: Capability key being matched (e.g. 'coding')
            current_load:        Agent's current load ratio [0.0, 1.0]

        Returns:
            float score in [0.0, 1.0], or None if agent lacks the capability
        """
        caps = agent.get("capabilities", {})
        level = caps.get(required_capability)
        if level is None:
            return None  # Agent not eligible for this capability

        cap_score = COMPETENCY_WEIGHTS.get(level, 0.0)

        # Live trust score from TrustEngine if available, else static level fallback
        if self._trust_engine:
            trust_score = self._trust_engine.get_score(
                agent.get("agent_id", agent.get("id", ""))
            )
        else:
            from identity.trust_engine import TRUST_LEVEL_BASES
            trust_score = TRUST_LEVEL_BASES.get(agent.get("trust_level", "standard"), 0.70)

        # Inverse load: full load (1.0) contributes 0; idle (0.0) contributes 1.0
        load_score = max(0.0, 1.0 - current_load)

        score = (
            (cap_score   * self.capability_weight) +
            (trust_score * self.trust_weight) +
            (load_score  * self.load_weight)
        )
        return round(score, 4)

    # ------------------------------------------------------------------ #
    #  Routing                                                             #
    # ------------------------------------------------------------------ #

    def route(self, required_capability, available_agents, load_map=None, task_tenant_id="default"):
        """Selects the highest-scoring eligible agent for a required capability.

        Agents at or above saturation_threshold are deprioritised — the engine
        will fall through to the next-best candidate. This implements the
        load-balancing override described in the v1.7 design review.

        Args:
            required_capability: Capability key (e.g. 'coding', 'planning')
            available_agents:    List of agent profile dicts
            load_map:            Optional dict mapping agent_id → load ratio [0.0, 1.0]
            task_tenant_id:      Tenant ID for the task (default: 'default')

        Returns:
            tuple (agent_dict, score_float) or (None, 0.0) if no match found
        """
        load_map = load_map or {}
        
        # 0. Enforce Multi-Tenant Isolation BEFORE scoring
        from tenants.isolation import TenantIsolation
        filtered_agents = TenantIsolation.tenant_filter(task_tenant_id, available_agents)
        if not filtered_agents:
            print(f"[ROUTER] No agents available for capability '{required_capability}' in tenant '{task_tenant_id}'")
            return None, 0.0

        candidates = []

        for agent in filtered_agents:
            agent_id = agent.get("agent_id", agent.get("id", ""))
            load = load_map.get(agent_id, 0.0)

            # Skip saturated agents on first pass; they fall through to backup routing
            if load >= self.saturation_threshold:
                print(f"[ROUTER] Agent '{agent_id}' skipped (load {load:.0%} >= "
                      f"saturation threshold {self.saturation_threshold:.0%}).")
                continue

            score = self.compute_score(agent, required_capability, load)
            if score is not None:
                candidates.append((agent, score))

        # Fall-through: if all preferred agents are saturated, include them at a penalty
        if not candidates:
            for agent in filtered_agents:
                agent_id = agent.get("agent_id", agent.get("id", ""))
                load = load_map.get(agent_id, 0.0)
                score = self.compute_score(agent, required_capability, load)
                if score is not None:
                    candidates.append((agent, score))

        if not candidates:
            print(f"[ROUTER] No capable agent found for capability: '{required_capability}'")
            return None, 0.0

        # Sort descending by score; highest wins
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_agent, best_score = candidates[0]
        agent_id = best_agent.get("agent_id", best_agent.get("id", "unknown"))

        print(f"[ROUTER] '{required_capability}' -> agent '{agent_id}' "
              f"(score: {best_score:.4f})")

        self._event_bus.publish(Event(
            event_type="ROUTE_SELECTED",
            correlation_id=agent_id,
            source="runtime/routing_engine",
            severity="info",
            agent_id=agent_id,
            payload={
                "required_capability": required_capability,
                "score": best_score,
                "candidates_evaluated": len(candidates)
            }
        ))

        return best_agent, best_score

    def get_load(self, agent_id, queue_manager):
        """Computes load ratio for an agent based on active task queue depth.

        Args:
            agent_id:      Agent identifier string
            queue_manager: PriorityTaskQueue instance

        Returns:
            float load ratio [0.0, 1.0]
        """
        # Count tasks in queue belonging to this agent_id
        active = sum(
            1 for task in queue_manager.registry.values()
            if task.status == "running" and
               getattr(task, "agent_id", None) == agent_id
        )
        # Normalised against a default concurrency ceiling of 8
        return min(1.0, active / 8.0)
