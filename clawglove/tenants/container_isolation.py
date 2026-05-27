"""
Docker-backed tenant isolation.
Replaces filesystem path prefixes with real container namespaces.
Each tenant workload runs in a resource-constrained Docker container.

Fail-closed: if Docker is unavailable or container cannot start,
fence() raises and the workload does NOT execute.
"""
import logging
import docker
from docker.errors import DockerException
from clawglove.interfaces import TenantIsolationInterface

logger = logging.getLogger(__name__)

# Defaults — override via policy YAML in production
DEFAULT_MEMORY_LIMIT = "512m"
DEFAULT_CPU_LIMIT = "1.0"
DEFAULT_NETWORK = "clawglove_sidecar_net"  # Must match docker-compose network name


class DockerTenantIsolation(TenantIsolationInterface):
    """
    Runs agent workloads inside Docker containers with hard resource limits.
    Network is restricted to the ClawGlove sidecar network only.
    No direct internet access from the container.

    NOTE: This implementation runs a Python callable in a subprocess container.
    For OpenClaw agents, replace _run_in_container with the agent's own
    container launch mechanism once the OpenClaw execution model is confirmed.
    """

    def __init__(
        self,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: str = DEFAULT_CPU_LIMIT,
        sidecar_socket_path: str = "/tmp/clawglove.sock",
    ):
        try:
            self._client = docker.from_env()
            self._client.ping()
        except DockerException as e:
            raise RuntimeError(
                "Docker is not available. Tenant isolation cannot be established. "
                "Fail-closed: no workloads will run without Docker."
            ) from e

        self._memory_limit = memory_limit
        self._cpu_limit = cpu_limit
        self._sidecar_socket_path = sidecar_socket_path

    def fence(self, tenant_id: str, workload_fn, *args, **kwargs):
        """
        Execute workload_fn inside an isolated Docker container.

        Security guarantees:
        - Memory hard limit: container OOM-killed if exceeded
        - CPU quota: cannot starve other tenants
        - Network: restricted to sidecar network only (no direct internet)
        - Filesystem: other tenants' paths not mounted

        IMPORTANT: workload_fn must be serialisable to a Docker exec command.
        For OpenClaw agents this will be replaced with the agent container
        launch command once the OpenClaw execution model is confirmed.
        """
        container_name = f"clawglove-tenant-{tenant_id}-workload"

        logger.info(
            "Fencing tenant=%s memory=%s cpu=%s",
            tenant_id, self._memory_limit, self._cpu_limit
        )

        try:
            container = self._client.containers.run(
                image="python:3.11-slim",
                name=container_name,
                mem_limit=self._memory_limit,
                nano_cpus=int(float(self._cpu_limit) * 1e9),
                network=DEFAULT_NETWORK,
                volumes={
                    # Mount the sidecar socket as read-only
                    # Agent can call the sidecar but cannot write to it
                    self._sidecar_socket_path: {
                        "bind": "/run/clawglove/clawglove.sock",
                        "mode": "ro",
                    }
                },
                environment={
                    "CLAWGLOVE_TENANT_ID": tenant_id,
                    "CLAWGLOVE_SIDECAR_SOCKET": "/run/clawglove/clawglove.sock",
                },
                # Prevent privilege escalation
                security_opt=["no-new-privileges:true"],
                read_only=False,  # Agent needs tmp write access
                detach=False,
                remove=True,
                # TODO: Replace with actual OpenClaw agent command once
                # the OpenClaw execution model is confirmed.
                command=["python", "-c", "import sys; print('workload placeholder')"],
            )
            return container
        except DockerException as e:
            logger.error("Container launch failed for tenant=%s: %s", tenant_id, e)
            raise RuntimeError(
                f"Tenant isolation failed for {tenant_id}. "
                "Fail-closed: workload not executed."
            ) from e
        finally:
            # Ensure container is cleaned up even on partial failure
            try:
                existing = self._client.containers.get(container_name)
                existing.remove(force=True)
            except Exception:
                pass
