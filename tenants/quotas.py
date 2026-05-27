class TenantQuotaManager:
    def __init__(self, tenant_registry):
        self._registry = tenant_registry
        self._usage = {} # tenant_id -> {"tokens_used": int, "active_agents": int}

    def _init_usage(self, tenant_id):
        if tenant_id not in self._usage:
            self._usage[tenant_id] = {"tokens_used": 0, "active_agents": 0}

    def consume_tokens(self, tenant_id, tokens):
        tenant = self._registry.get_tenant(tenant_id)
        if not tenant:
            return False
            
        self._init_usage(tenant_id)
        limit = tenant.get("quotas", {}).get("daily_tokens", 0)
        
        if self._usage[tenant_id]["tokens_used"] + tokens > limit:
            print(f"[TENANT-QUOTA] {tenant_id} exceeded daily token limit ({limit})")
            return False
            
        self._usage[tenant_id]["tokens_used"] += tokens
        return True
