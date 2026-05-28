"""
ClawGlove sidecar client.
Thin wrapper that lives inside the OpenClaw agent's Python process.
Sends every agent action to the sidecar daemon for policy validation.

IMPORTANT: This client makes the interception point explicit — the agent
developer must call client.check() before any governed action. For mandatory
interception, the container networking ensures the agent cannot reach external
services without going through the sidecar proxy.

TODO: Once OpenClaw's execution model is confirmed, replace the manual
client.check() calls with automatic interception hooks that match how
OpenClaw agents invoke tools and LLM calls. Options:
  - Monkey-patch the LLM client at container startup (safe since agent is
    already isolated in a container and cannot patch the sidecar process)
  - Wrap OpenClaw's tool registry to auto-check on every tool call
  - Use a transparent HTTP proxy (CLAWGLOVE_HTTP_PROXY env var) for all
    outbound LLM API calls
"""
import json
import logging
import socket
import time

logger = logging.getLogger(__name__)


class PolicyViolationError(Exception):
    """Raised when the sidecar denies an agent action."""


class ClawGloveClient:
    """
    Thin client that connects to the ClawGlove sidecar daemon.
    Raises PolicyViolationError if the sidecar denies the action.
    Raises ConnectionError if the sidecar is unavailable (fail-closed).
    """

    def __init__(
        self,
        tenant_id: str,
        daemon_host: str = "127.0.0.1",
        daemon_port: int = 50051,
        timeout_seconds: float = 5.0,
    ):
        self._tenant_id = tenant_id
        self._host = daemon_host
        self._port = daemon_port
        self._timeout = timeout_seconds

    def _send(self, payload: dict) -> dict:
        """Send one JSON request to the sidecar and return the response."""
        try:
            with socket.create_connection((self._host, self._port), timeout=self._timeout) as sock:
                sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
                response_bytes = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response_bytes += chunk
                    if b"\n" in response_bytes:
                        break
                return json.loads(response_bytes.split(b"\n")[0].decode("utf-8"))
        except ConnectionRefusedError:
            raise ConnectionError(
                "ClawGlove sidecar is not running. "
                "Fail-closed: agent action blocked."
            )

    def check(self, agent_action: str, context: dict | None = None) -> None:
        """
        Check if agent_action is allowed for this tenant.
        Raises PolicyViolationError if denied.
        Raises ConnectionError if sidecar is unavailable (fail-closed).

        Usage:
            client = ClawGloveClient(tenant_id="tenant_alpha")
            client.check("llm_call", {"tokens_used": 1500})
            # Only reaches here if sidecar allows the action
            response = openai.chat.completions.create(...)
        """
        payload = {
            "action": "check_policy",
            "tenant_id": self._tenant_id,
            "agent_action": agent_action,
            "context": context or {},
        }
        result = self._send(payload)

        if "error" in result:
            raise RuntimeError(f"Sidecar error: {result['error']}")

        if not result.get("allowed", False):
            logger.warning(
                "Policy violation: tenant=%s action=%s reason=%s",
                self._tenant_id, agent_action, result.get("reason")
            )
            raise PolicyViolationError(
                f"Action '{agent_action}' denied for tenant '{self._tenant_id}': "
                f"{result.get('reason', 'no reason given')}"
            )

    def log_event(self, event_type: str, data: dict) -> None:
        """Log an agent event to the sidecar's EventStore."""
        payload = {
            "action": "log_event",
            "event": {
                "type": event_type,
                "tenant_id": self._tenant_id,
                "domain": "operational",
                "ts": time.time(),
                **data,
            },
        }
        self._send(payload)

    def ping(self) -> bool:
        """Health check. Returns True if sidecar is reachable."""
        try:
            result = self._send({"action": "ping"})
            return "pong" in result
        except ConnectionError:
            return False

    def get_threat_state(self) -> dict:
        """Return the current threat level and violation count for this tenant."""
        return self._send({"action": "get_threat_state", "tenant_id": self._tenant_id})

    def reset_quarantine(self) -> bool:
        """
        Operator reset: clear quarantine for this tenant.
        Only call this after reviewing the violation audit log.
        """
        result = self._send({"action": "reset_tenant", "tenant_id": self._tenant_id})
        return result.get("ok", False)
