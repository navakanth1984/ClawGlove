import os
from .roles import Roles, Permissions

class AuthorizationEngine:
    """Evaluates permissions and boundary constraints."""
    
    def __init__(self, audit_logger=None):
        self.audit = audit_logger

    def _log(self, identity, action, resource, result):
        if self.audit:
            self.audit.record(
                actor=identity.get("actor_id", "unknown") if identity else "anonymous",
                action=action,
                resource=resource,
                result=result
            )

    def check_permission(self, identity, required_permission, resource="system"):
        """Checks if the identity has the required permission via its role."""
        if not identity:
            self._log(None, f"check_{required_permission}", resource, "DENY")
            return False
        
        role_name = identity.get("role", "Viewer")
        permissions = Roles.get_role_permissions(role_name)
        
        result = "ALLOW" if required_permission in permissions else "DENY"
        self._log(identity, f"check_{required_permission}", resource, result)
        return result == "ALLOW"

    def check_cross_tenant_access(self, identity, target_tenant_id, resource="tenant"):
        """Ensures an identity can only access its own tenant resources unless SystemAdmin."""
        if not identity:
            self._log(None, "cross_tenant_access", target_tenant_id, "DENY")
            return False
            
        role_name = identity.get("role", "Viewer")
        permissions = Roles.get_role_permissions(role_name)
        
        if Permissions.SYSTEM_ADMIN in permissions:
            self._log(identity, "cross_tenant_access", target_tenant_id, "ALLOW")
            return True
            
        result = "ALLOW" if identity.get("tenant_id") == target_tenant_id else "DENY"
        self._log(identity, "cross_tenant_access", target_tenant_id, result)
        return result == "ALLOW"
