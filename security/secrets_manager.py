class SecretsManager:
    """Secure enclave for secrets. Prevents plaintext leaks in memory payloads."""
    def __init__(self):
        self._vault = {}

    def store_secret(self, key, value):
        self._vault[key] = value

    def get_secret(self, key):
        """Retrieves the secret for execution only. Must not be logged."""
        return self._vault.get(key)

    def obfuscate_payload(self, payload):
        """Redacts known secrets from a dictionary before it hits the EventBus or Audit log."""
        if not isinstance(payload, dict):
            return payload
            
        clean_payload = {}
        for k, v in payload.items():
            if isinstance(v, str):
                # Simple exact match obfuscation for simulation purposes
                if v in self._vault.values() and v != "":
                    clean_payload[k] = "********"
                else:
                    clean_payload[k] = v
            elif isinstance(v, dict):
                clean_payload[k] = self.obfuscate_payload(v)
            else:
                clean_payload[k] = v
        return clean_payload
