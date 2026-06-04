"""
etcd-backed coordinator.
Replaces in-memory Python threading locks with distributed consensus.
Uses etcd leases for leader election and KV store for state checkpoints.
"""
import json
import logging

try:
    import etcd3
    _HAS_ETCD3 = True
except (ImportError, TypeError):
    # TypeError: protobuf >= 4.x raises TypeError on etcd3 0.12.0's generated _pb2 stubs
    etcd3 = None  # type: ignore[assignment]
    _HAS_ETCD3 = False

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
        import socket
        import threading
        self._online = False
        self._host = host
        self._port = port

        if _HAS_ETCD3:
            try:
                with socket.create_connection((host, port), timeout=0.1):
                    self._online = True
            except Exception:
                pass

            if self._online:
                try:
                    self._client = etcd3.client(host=host, port=port)
                    self._active_leases = {}
                    logger.info("EtcdCoordinator initialized and online: %s:%d", host, port)
                except Exception as e:
                    logger.warning("etcd initialization failed: %s. Falling back to offline mode.", e)
                    self._online = False
        else:
            logger.info("etcd3 library unavailable (protobuf incompatibility or not installed). Using local-only mode.")

        if not self._online:
            self._local_kv = {}
            self._local_leases = {}
            self._lock = threading.Lock()
            logger.info("EtcdCoordinator initialized in offline/local-only mode.")

    def elect_leader(self, node_id: str, ttl_seconds: int = 10) -> bool:
        """
        Attempt to acquire leadership for node_id.
        Uses etcd lease + compare-and-swap to ensure exactly one leader.
        Returns True if this node is now the leader.
        """
        if not self._online:
            import time
            with self._lock:
                leader_key = "/clawglove/leader"
                now = time.time()
                current_leader = self._local_kv.get(leader_key)
                current_expiry = self._local_leases.get(current_leader, 0.0) if current_leader else 0.0

                # If no leader, or leader lease has expired, or we are the current leader
                if current_leader is None or now > current_expiry or current_leader == node_id:
                    self._local_kv[leader_key] = node_id
                    self._local_leases[node_id] = now + ttl_seconds
                    logger.info("Leader elected (offline): node=%s ttl=%ds", node_id, ttl_seconds)
                    return True
                return False

        try:
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
        except Exception as e:
            logger.error("etcd elect_leader failed: %s. Falling back to offline election.", e)
            self._online = False
            return self.elect_leader(node_id, ttl_seconds)

    def checkpoint_state(self, key: str, state: dict) -> None:
        """
        Persist state checkpoint to etcd.
        Key format: /clawglove/checkpoints/{key}
        """
        if not self._online:
            with self._lock:
                self._local_kv[key] = json.loads(json.dumps(state, sort_keys=True, ensure_ascii=False))
                logger.debug("Checkpoint saved (offline): key=%s", key)
            return

        try:
            etcd_key = f"/clawglove/checkpoints/{key}"
            value = json.dumps(state, sort_keys=True, ensure_ascii=False)
            self._client.put(etcd_key, value)
            logger.debug("Checkpoint saved: key=%s", etcd_key)
        except Exception as e:
            logger.error("etcd checkpoint failed: %s. Falling back to offline checkpoint.", e)
            self._online = False
            self.checkpoint_state(key, state)

    def load_checkpoint(self, key: str) -> dict | None:
        """
        Load last checkpoint from etcd. Returns None if not found.
        """
        if not self._online:
            with self._lock:
                return self._local_kv.get(key)

        try:
            etcd_key = f"/clawglove/checkpoints/{key}"
            value, _ = self._client.get(etcd_key)
            if value is None:
                return None
            return json.loads(value.decode("utf-8"))
        except Exception as e:
            logger.error("etcd load_checkpoint failed: %s. Falling back to offline load.", e)
            self._online = False
            return self.load_checkpoint(key)

    def revoke_leadership(self, node_id: str) -> None:
        """Explicitly release the leadership lease."""
        if not self._online:
            with self._lock:
                leader_key = "/clawglove/leader"
                if self._local_kv.get(leader_key) == node_id:
                    self._local_kv.pop(leader_key, None)
                    self._local_leases.pop(node_id, None)
                    logger.info("Leadership revoked (offline): node=%s", node_id)
            return

        try:
            lease = self._active_leases.pop(node_id, None)
            if lease:
                lease.revoke()
                logger.info("Leadership revoked: node=%s", node_id)
        except Exception as e:
            logger.error("etcd revoke_leadership failed: %s", e)
