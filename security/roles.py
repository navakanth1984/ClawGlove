class Permissions:
    VIEW = "VIEW"
    EXECUTE = "EXECUTE"
    MANAGE_AGENTS = "MANAGE_AGENTS"
    MANAGE_TENANTS = "MANAGE_TENANTS"
    MANAGE_MODELS = "MANAGE_MODELS"
    MANAGE_POLICIES = "MANAGE_POLICIES"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    REPLAY_TENANT_HISTORY = "ReplayTenantHistory"

class Roles:
    Viewer = {Permissions.VIEW}
    Agent = {Permissions.VIEW, Permissions.EXECUTE}
    TenantAdmin = {
        Permissions.VIEW, Permissions.EXECUTE, 
        Permissions.MANAGE_AGENTS, Permissions.MANAGE_MODELS,
        Permissions.REPLAY_TENANT_HISTORY
    }
    SystemAdmin = {
        Permissions.VIEW, Permissions.EXECUTE, Permissions.MANAGE_AGENTS,
        Permissions.MANAGE_TENANTS, Permissions.MANAGE_MODELS, Permissions.MANAGE_POLICIES,
        Permissions.SYSTEM_ADMIN, Permissions.REPLAY_TENANT_HISTORY
    }

    @classmethod
    def get_role_permissions(cls, role_name):
        return getattr(cls, role_name, set())
