class ReputationEngine:
    """Tracks rolling execution history per agent and produces performance scorecards.

    History feeds back into TrustEngine via record_violation() which calls
    trust_engine.penalize(). This creates an automatic trust degradation loop
    on repeated policy breaches without requiring external coordination.

    Scorecard format:
        {
            "agent_id": "builder_001",
            "success_rate": 0.97,
            "avg_retry_count": 0.3,
            "policy_violations": 1,
            "trust_score": 0.88
        }
    """

    def __init__(self, registry, trust_engine, storage_provider=None):
        """
        Args:
            registry:     IdentityRegistry providing profile access
            trust_engine: TrustEngine for penalize/restore callbacks
            storage_provider: StorageProvider for persistent state
        """
        self._registry = registry
        self._trust_engine = trust_engine
        self._storage = storage_provider
        # agent_id -> {"successes": int, "failures": int, "violations": int, "retries": int}
        self._history = {}
        
        if self._storage:
            if hasattr(self._storage, "reconstruct_scorecards"):
                self._history = self._storage.reconstruct_scorecards()
            elif hasattr(self._storage, "load_reputation_history"):
                self._history = self._storage.load_reputation_history()
            print(f"[REPUTATION] Loaded history for {len(self._history)} agents from storage.")

    def _save(self):
        if self._storage and hasattr(self._storage, "save_reputation_history"):
            self._storage.save_reputation_history(self._history)

    def _init_agent(self, agent_id):
        if agent_id not in self._history:
            self._history[agent_id] = {
                "successes": 0,
                "failures": 0,
                "violations": 0,
                "retries": 0
            }

    def record_success(self, agent_id):
        """Records a successful task completion and increments the profile's recent_successes."""
        self._init_agent(agent_id)
        self._history[agent_id]["successes"] += 1

        # Increment recent success counter in profile (capped at 5 to prevent score inflation)
        profile = self._registry.get(agent_id)
        if profile:
            profile["_recent_successes"] = min(5, profile.get("_recent_successes", 0) + 1)

        print(f"[REPUTATION] Success recorded for agent '{agent_id}'. "
              f"Total: {self._history[agent_id]['successes']}")
        if self._storage and hasattr(self._storage, "append_event"):
            self._storage.append_event(agent_id, "Success")
        self._save()

    def record_failure(self, agent_id, retry=False):
        """Records a task failure. If retry=True also increments the retry counter."""
        self._init_agent(agent_id)
        self._history[agent_id]["failures"] += 1
        if retry:
            self._history[agent_id]["retries"] += 1

        print(f"[REPUTATION] Failure recorded for agent '{agent_id}' "
              f"(retry={retry}). Total failures: {self._history[agent_id]['failures']}")
        if self._storage and hasattr(self._storage, "append_event"):
            self._storage.append_event(agent_id, "Retry" if retry else "Failure")
        self._save()

    def record_violation(self, agent_id):
        """Records a policy violation and triggers trust penalization."""
        self._init_agent(agent_id)
        self._history[agent_id]["violations"] += 1

        # Feed penalty directly into the trust engine
        self._trust_engine.penalize(agent_id, reason="policy_violation")
        print(f"[REPUTATION] Policy violation recorded for agent '{agent_id}'. "
              f"Total violations: {self._history[agent_id]['violations']}")
        if self._storage and hasattr(self._storage, "append_event"):
            self._storage.append_event(agent_id, "Violation")
        self._save()

    def get_scorecard(self, agent_id):
        """Returns a reputation scorecard dict for the given agent.

        Returns:
            dict with success_rate, avg_retry_count, policy_violations, trust_score
        """
        self._init_agent(agent_id)
        h = self._history[agent_id]
        total = h["successes"] + h["failures"]

        success_rate = round(h["successes"] / total, 4) if total > 0 else 1.0
        avg_retries = round(h["retries"] / total, 2) if total > 0 else 0.0
        trust_score = self._trust_engine.get_score(agent_id)

        return {
            "agent_id": agent_id,
            "success_rate": success_rate,
            "avg_retry_count": avg_retries,
            "policy_violations": h["violations"],
            "trust_score": trust_score
        }

    def get_all_scorecards(self):
        """Returns scorecards for all agents with tracked history."""
        return [self.get_scorecard(aid) for aid in self._history]
