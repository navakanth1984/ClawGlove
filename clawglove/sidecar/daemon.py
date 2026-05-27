"""
ClawGlove Sidecar Daemon.
Runs as an isolated process. Agents communicate via TCP socket on localhost.
The agent process CANNOT access this process's memory space.

Fail-closed: if daemon crashes, the agent's outbound requests to
localhost:50051 will fail with ConnectionRefusedError.
The agent container's network policy must NOT have a fallback route.

Start with: clawglove-daemon --policies ./policies/ --port 50051
"""
import argparse
import json
import logging
import socket
import threading
import time
from pathlib import Path

from clawglove.events.kafka_store import KafkaEventStore
from clawglove.metrics.otel_telemetry import OTelTelemetry
from clawglove.policies.compiler import PolicyCompiler
from clawglove.policies.engine import PolicyEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("clawglove.daemon")


class ClawGloveDaemon:
    """
    Out-of-process governance sidecar.

    Protocol (newline-delimited JSON over TCP):
    Request:  {"action": "check_policy", "tenant_id": "t1", "agent_action": "llm_call", "context": {}}
    Response: {"allowed": true, "reason": "allowed"}

    Request:  {"action": "log_event", "event": {"type": "...", "tenant_id": "t1", ...}}
    Response: {"ok": true}
    """

    def __init__(
        self,
        policies_dir: str,
        kafka_servers: str = "localhost:9092",
        otlp_endpoint: str = "http://localhost:4317",
        port: int = 50051,
    ):
        logger.info("ClawGlove daemon starting...")

        # Load and compile policies — fail-closed if any policy is invalid
        compiler = PolicyCompiler()
        policies = compiler.compile_directory(policies_dir)
        if not policies:
            raise RuntimeError(
                f"No policies found in {policies_dir}. "
                "Daemon refuses to start without at least one tenant policy."
            )

        self._engine = PolicyEngine(policies)
        self._event_store = KafkaEventStore(bootstrap_servers=kafka_servers)
        self._telemetry = OTelTelemetry(otlp_endpoint=otlp_endpoint)
        self._port = port
        self._running = False

        logger.info("Daemon ready: policies=%d port=%d", len(policies), port)

    def _handle_client(self, conn: socket.socket, addr: tuple) -> None:
        """Handle a single agent connection. Each request is one JSON line."""
        logger.debug("Agent connected: addr=%s", addr)
        with conn:
            buffer = b""
            while True:
                try:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if not line.strip():
                            continue
                        response = self._dispatch(line.decode("utf-8"))
                        conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
                except Exception as e:
                    logger.error("Client handler error: %s", e)
                    error_response = {"error": str(e)}
                    try:
                        conn.sendall((json.dumps(error_response) + "\n").encode("utf-8"))
                    except Exception:
                        pass
                    break

    def _dispatch(self, raw: str) -> dict:
        """Route a request to the correct handler."""
        try:
            req = json.loads(raw)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON: {e}"}

        action = req.get("action")

        if action == "check_policy":
            return self._handle_check_policy(req)
        elif action == "log_event":
            return self._handle_log_event(req)
        elif action == "ping":
            return {"pong": True, "ts": time.time()}
        else:
            return {"error": f"Unknown action: {action}"}

    def _handle_check_policy(self, req: dict) -> dict:
        tenant_id = req.get("tenant_id", "")
        agent_action = req.get("agent_action", "")
        context = req.get("context", {})

        allowed, reason = self._engine.check(agent_action, tenant_id, context)

        # Log to event store and telemetry regardless of allow/deny
        event = {
            "type": "POLICY_CHECK",
            "tenant_id": tenant_id,
            "agent_action": agent_action,
            "allowed": allowed,
            "reason": reason,
            "domain": "governance",
            "ts": time.time(),
        }
        self._event_store.append(event)
        self._telemetry.record_event(
            "policy_check",
            {"tenant_id": tenant_id, "agent_action": agent_action,
             "allowed": str(allowed), "reason": reason,
             "type": "POLICY_VIOLATION" if not allowed else "POLICY_ALLOW"},
        )

        return {"allowed": allowed, "reason": reason}

    def _handle_log_event(self, req: dict) -> dict:
        event = req.get("event", {})
        if not event:
            return {"error": "Missing event payload"}
        self._event_store.append(event)
        self._telemetry.record_event("agent_event", {"type": "EVENT_APPEND", **event})
        return {"ok": True}

    def serve(self) -> None:
        """Start the TCP server. Blocks until interrupted."""
        self._running = True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", self._port))
            server.listen(32)
            logger.info("Daemon listening on 127.0.0.1:%d", self._port)

            while self._running:
                try:
                    conn, addr = server.accept()
                    t = threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True)
                    t.start()
                except KeyboardInterrupt:
                    logger.info("Daemon shutting down")
                    self._running = False


def main():
    parser = argparse.ArgumentParser(description="ClawGlove governance sidecar daemon")
    parser.add_argument("--policies", required=True, help="Path to policies directory")
    parser.add_argument("--kafka", default="localhost:9092", help="Kafka bootstrap servers")
    parser.add_argument("--otlp", default="http://localhost:4317", help="OTLP collector endpoint")
    parser.add_argument("--port", type=int, default=50051, help="Daemon TCP port")
    args = parser.parse_args()

    daemon = ClawGloveDaemon(
        policies_dir=args.policies,
        kafka_servers=args.kafka,
        otlp_endpoint=args.otlp,
        port=args.port,
    )
    daemon.serve()


if __name__ == "__main__":
    main()
