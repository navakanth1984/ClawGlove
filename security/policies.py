from .authorization import AuthorizationEngine
from .roles import Permissions

class SecurityPolicies:
    """Enforces runtime boundary constraints for models and execution."""
    def __init__(self, authz_engine: AuthorizationEngine):
        self.authz = authz_engine
        
        # Example model entitlements
        self._model_entitlements = {
            "TenantBasic": ["GPT-3.5", "Claude-Haiku"],
            "TenantPro": ["GPT-4", "GPT-Ultra", "Claude-Opus"]
        }

    def check_model_access(self, identity, model_name):
        """Checks if a tenant is entitled to a specific model."""
        # SystemAdmin bypasses tenant model limits
        if self.authz.check_permission(identity, Permissions.SYSTEM_ADMIN, resource="model_access"):
            # The check_permission call already logs ALLOW/DENY
            return True
            
        tenant_id = identity.get("tenant_id", "default")
        entitlements = self._model_entitlements.get(tenant_id, [])
        
        if model_name in entitlements:
            self.authz.audit.record(identity.get("actor_id"), "model_access", model_name, "ALLOW")
            return True
            
        self.authz.audit.record(identity.get("actor_id"), "model_access", model_name, "DENY")
        return False
