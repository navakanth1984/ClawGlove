"""
etcd-backed coordinator.
Replaces in-memory Python threading locks with distributed consensus.
Uses etcd leases for leader election and KV store for state checkpoints.
"""
import json
import logging
import etcd3
from clawglove.interfaces import CoordinatorInterface

logger = logging.getLogger(__name__)


class EtcdCoordinator(CoordinatorInterface):
    """
    Distributed consensus via etcd.
    Leader election uses etcd leases — lease expiry automatically
    releases leadership without zombie lock risk.
    State checkpoints use etcd's strongly consistent KV store.
    """

    def __init__(self, host: str = "localhost", port: int = 2379):
        self._client = etcd3.client(host=host, port=port)
        self._active_leases: dict[str, any] = {}

    def elect_leader(self, node_id: str, ttl_seconds: int = 10) -> bool:
        """
        Attempt to acquire leadership for node_id.
        Uses etcd lease + compare-and-swap to ensure exactly one leader.
        Returns True if this node is now the leader.
        """
        lease = self._client.lease(ttl=ttl_seconds)
        leader_key = "/clawglove/leader"

        # Attempt to write our node_id only if the key does not exist
        success, _ = self._client.transaction(
            compare=[self._client.transactions.version(leader_key) == 0],
            success=[self._client.transactions.put(leader_key, node_id, lease=lease)],
            failure=[],
        )

        if success:
            self._active_leases[node_id] = lease
            logger.info("Leader elected: node=%s ttl=%ds", node_id, ttl_seconds)
            return True

        # Check if we are already the leader (re-election on TTL refresh)
        current_leader, _ = self._client.get(leader_key)
        if current_leader and current_leader.decode() == node_id:
            logger.debug("Refreshed leadership: node=%s", node_id)
            return True

        logger.debug("Leadership not acquired: node=%s", node_id)
        return False

    def checkpoint_state(self, key: str, state: dict) -> None:
        """
        Persist state checkpoint to etcd.
        Key format: /clawglove/checkpoints/{key}
        """
        etcd_key = f"/clawglove/checkpoints/{key}"
        value = json.dumps(state, sort_keys=True, ensure_ascii=False)
        self._client.put(etcd_key, value)
        logger.debug("Checkpoint saved: key=%s", etcd_key)

    def load_checkpoint(self, key: str) -> dict | None:
        """
        Load last checkpoint from etcd. Returns None if not found.
        """
        etcd_key = f"/clawglove/checkpoints/{key}"
        value, _ = self._client.get(etcd_key)
        if value is None:
            return None
        return json.loads(value.decode("utf-8"))

    def revoke_leadership(self, node_id: str) -> None:
        """Explicitly release the leadership lease."""
        lease = self._active_leases.pop(node_id, None)
        if lease:
            lease.revoke()
            logger.info("Leadership revoked: node=%s", node_id)
