import uuid
import datetime

class AuthenticationEngine:
    def __init__(self):
        self._tokens = {}

    def issue_token(self, actor_id, role, tenant_id="default"):
        token = f"tok_{uuid.uuid4().hex}"
        self._tokens[token] = {
            "actor_id": actor_id,
            "role": role,
            "tenant_id": tenant_id,
            "issued_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
        return token

    def validate_token(self, token):
        return self._tokens.get(token)

    def revoke_token(self, token):
        if token in self._tokens:
            del self._tokens[token]
            return True
        return False

    def authenticate(self, request_headers):
        """Authenticates a request based on Bearer token."""
        token = request_headers.get("Authorization")
        if token and token.startswith("Bearer "):
            token = token.split(" ")[1]
            return self.validate_token(token)
        return None
