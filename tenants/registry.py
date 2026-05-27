class TenantRegistry:
    def __init__(self):
        self._tenants = {}

    def register_tenant(self, tenant_profile):
        tenant_id = tenant_profile.get("tenant_id")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        self._tenants[tenant_id] = tenant_profile
        print(f"[TENANT] Registered tenant: {tenant_id} (tier: {tenant_profile.get('tier')})")

    def get_tenant(self, tenant_id):
        return self._tenants.get(tenant_id)

    def is_valid_tenant(self, tenant_id):
        return tenant_id in self._tenants
