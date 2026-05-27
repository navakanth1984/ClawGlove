# Multi-Tenant Isolation

This subsystem expands the OS from a single-user system to a multi-tenant environment.

- `registry.py`: Manages `tenant_id` profiles.
- `quotas.py`: Enforces shared tenant resource budgets.
- `isolation.py`: Guarantees strict boundary enforcement (e.g. agents from Tenant A cannot be routed tasks from Tenant B).
