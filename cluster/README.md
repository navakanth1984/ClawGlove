# Distributed Worker Nodes

This subsystem breaks the single-process execution barrier, enabling external worker processes.

- `node_registry.py`: Exposes endpoints for remote workers to announce capabilities.
- `node_health.py`: Manages `NODE_HEARTBEAT` events, purging offline nodes.
- `node_scheduler.py`: Bridges `RoutingEngine` and `EventBus` to distribute tasks across the cluster.
