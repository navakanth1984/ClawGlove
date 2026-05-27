class TenantIsolation:
    @staticmethod
    def tenant_filter(task_tenant_id, candidates):
        """
        Filters candidates to only include agents belonging to the specified tenant.
        
        Args:
            task_tenant_id (str): The tenant_id of the incoming task.
            candidates (list): List of AgentProfile dicts.
            
        Returns:
            list: Filtered candidates.
        """
        if not task_tenant_id:
            task_tenant_id = "default"
            
        filtered = []
        for profile in candidates:
            agent_tenant = profile.get("tenant_id", "default")
            if agent_tenant == task_tenant_id:
                filtered.append(profile)
                
        return filtered
