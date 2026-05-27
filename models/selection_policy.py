class ModelSelectionPolicy:
    def __init__(self, model_registry):
        self._registry = model_registry

    def select_best_model(self, required_capability, cost_limit=None):
        """
        Selects the best model for a capability.
        If cost_limit is provided, filters out models exceeding the limit.
        """
        models = self._registry.get_all_models()
        capable_models = [m for m in models if required_capability in m.get("capabilities", [])]
        
        if cost_limit is not None:
            capable_models = [m for m in capable_models if m.get("cost_per_1k_tokens", 0) <= cost_limit]
            
        if not capable_models:
            return None
            
        # Example logic: pick highest tier model available within limits
        capable_models.sort(key=lambda m: m.get("tier_score", 0), reverse=True)
        best = capable_models[0]
        print(f"[MODELS] Selected model {best['model_id']} for {required_capability}")
        return best
