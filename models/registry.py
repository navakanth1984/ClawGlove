class ModelRegistry:
    def __init__(self):
        self._models = {}

    def register_model(self, model_profile):
        model_id = model_profile.get("model_id")
        if not model_id:
            raise ValueError("model_id is required")
        self._models[model_id] = model_profile
        print(f"[MODELS] Registered model: {model_id}")

    def get_model(self, model_id):
        return self._models.get(model_id)

    def get_all_models(self):
        return list(self._models.values())
