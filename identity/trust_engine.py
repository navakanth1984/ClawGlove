import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.event_bus import EventBus, Event

# Trust level base scores sourced from policies/routing-weights.yaml
TRUST_LEVEL_BASES = {
    "high": 0.90,
    "standard": 0.70,
    "restricted": 0.40
}


class TrustEngine:
    """Computes and maintains clamped trust scores [0.0, 1.0] for registered agents.

    Formula:
        raw  = trust_level_base - (policy_violations × 0.1) + (recent_successes × 0.05)
        score = max(0.0, min(1.0, raw))   # Hard-clamped; prevents runaway values

    Scores are recomputed on every penalize/restore call and cached for fast reads.
    """

    def __init__(self, registry):
        """
        Args:
            registry: IdentityRegistry instance providing profile access
        """
        self._registry = registry
        self._score_cache = {}   # agent_id -> float
        self._event_bus = EventBus()

    def compute_score(self, agent_id):
        """Recomputes and caches the trust score for an agent from current profile state."""
        profile = self._registry.get(agent_id)
        if not profile:
            return 0.0

        base = TRUST_LEVEL_BASES.get(profile.get("trust_level", "standard"), 0.70)
        violations = profile.get("_policy_violations", 0)
        successes = profile.get("_recent_successes", 0)

        raw = base - (violations * 0.1) + (successes * 0.05)
        # Hard clamp: enforces [0.0, 1.0] ceiling and floor
        score = max(0.0, min(1.0, raw))

        self._score_cache[agent_id] = score
        return score

    def get_score(self, agent_id):
        """Returns cached score, recomputing if not yet calculated."""
        if agent_id not in self._score_cache:
            return self.compute_score(agent_id)
        return self._score_cache[agent_id]

    def penalize(self, agent_id, reason="policy_violation"):
        """Increments policy violation counter and recomputes score."""
        profile = self._registry.get(agent_id)
        if not profile:
            return

        profile["_policy_violations"] = profile.get("_policy_violations", 0) + 1
        score = self.compute_score(agent_id)
        print(f"[TRUST] Agent '{agent_id}' penalized ({reason}). New score: {score:.3f}")

        self._event_bus.publish(Event(
            event_type="TRUST_SCORE_UPDATED",
            correlation_id=agent_id,
            source="identity/trust_engine",
            severity="warning",
            agent_id=agent_id,
            payload={"reason": reason, "trust_score": score, "violations": profile["_policy_violations"]}
        ))

    def restore(self, agent_id):
        """Decrements policy violation counter by 1 and recomputes score (floor 0)."""
        profile = self._registry.get(agent_id)
        if not profile:
            return

        profile["_policy_violations"] = max(0, profile.get("_policy_violations", 1) - 1)
        score = self.compute_score(agent_id)
        print(f"[TRUST] Agent '{agent_id}' restored. New score: {score:.3f}")

        self._event_bus.publish(Event(
            event_type="TRUST_SCORE_UPDATED",
            correlation_id=agent_id,
            source="identity/trust_engine",
            severity="info",
            agent_id=agent_id,
            payload={"reason": "restored", "trust_score": score}
        ))
