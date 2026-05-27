class ModelCapabilities:
    @staticmethod
    def supports_capability(model_profile, required_capability):
        """Checks if a model supports a specific capability (e.g., 'coding', 'reasoning')."""
        capabilities = model_profile.get("capabilities", [])
        return required_capability in capabilities

    @staticmethod
    def get_capable_models(models, required_capability):
        """Filters a list of models to those supporting the capability."""
        return [m for m in models if ModelCapabilities.supports_capability(m, required_capability)]
