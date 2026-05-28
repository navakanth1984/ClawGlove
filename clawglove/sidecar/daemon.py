"""
ClawGlove Sidecar Daemon — with threat escalation.
Out-of-process governance sidecar. Agents communicate via TCP on localhost.

New in this version: ThreatEscalationTracker
  - Tracks per-tenant violation counts
  - Elevates threat level after 3 violations
  - Quarantines tenant after 6 violations (all actions denied)
  - This collapses H_escape toward 0 as escape paths converge on one outcome
  - Operator endpoint: {"action": "reset_tenant", "tenant_id": "screenwriter"}

Protocol (newline-delimited JSON over TCP):
  check_policy  → {"action":"check_policy","tenant_id":"t","agent_action":"llm_call","context":{}}
  log_event     → {"action":"log_event","event":{...}}
  get_threat    → {"action":"get_threat_state","tenant_id":"t"}
  reset_tenant  → {"action":"reset_tenant","tenant_id":"t"}  (operator only)
  ping          → {"action":"ping"}
"""
import argparse
import json
import logging
import socket
import threading
import time

from clawglove.events.kafka_store import KafkaEventStore
from clawglove.metrics.otel_telemetry import OTelTelemetry
from clawglove.policies.compiler import PolicyCompiler
from clawglove.policies.engine import PolicyEngine
from clawglove.sidecar.escalation import ThreatEscalationTracker, ThreatLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("clawglove.daemon")


class ClawGloveDaemon:

    def __init__(
        self,
        policies_dir: str,
        kafka_servers: str = "localhost:9092",
        otlp_endpoint: str = "http://localhost:4317",
        port: int = 50051,
    ):
        logger.info("ClawGlove daemon starting...")

        compiler = PolicyCompiler()
        policies = compiler.compile_directory(policies_dir)
        if not policies:
            raise RuntimeError(
                f"No policies found in {policies_dir}. "
                "Daemon refuses to start without at least one tenant policy."
            )

        self._engine  = PolicyEngine(policies)
        self._tracker = ThreatEscalationTracker()

        # EventStore and telemetry are optional — daemon works without Kafka
        self._event_store = None
        try:
            self._event_store = KafkaEventStore(bootstrap_servers=kafka_servers)
        except Exception as e:
            logger.warning("Kafka unavailable (%s) — running without EventStore", e)

        self._telemetry = None
        try:
            self._telemetry = OTelTelemetry(otlp_endpoint=otlp_endpoint)
        except Exception as e:
            logger.warning("OTel unavailable (%s) — running without telemetry", e)

        self._port    = port
        self._running = False
        logger.info("Daemon ready: policies=%d port=%d", len(policies), port)

    def _handle_client(self, conn: socket.socket, addr: tuple) -> None:
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
                    try:
                        conn.sendall((json.dumps({"error": str(e)}) + "\n").encode("utf-8"))
                    except Exception:
                        pass
                    break

    def _dispatch(self, raw: str) -> dict:
        try:
            req = json.loads(raw)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON: {e}"}

        action = req.get("action")
        if action == "check_policy":       return self._handle_check_policy(req)
        elif action == "log_event":        return self._handle_log_event(req)
        elif action == "get_threat_state": return self._handle_get_threat(req)
        elif action == "reset_tenant":     return self._handle_reset_tenant(req)
        elif action == "ping":             return {"pong": True, "ts": time.time()}
        else:                              return {"error": f"Unknown action: {action}"}

    def _handle_check_policy(self, req: dict) -> dict:
        tenant_id    = req.get("tenant_id", "")
        agent_action = req.get("agent_action", "")
        context      = req.get("context", {})

        # ── Step 1: quarantine gate (checked before policy engine) ──
        quarantined, q_reason = self._tracker.check_quarantine(tenant_id)
        if quarantined:
            self._log_governance_event(tenant_id, agent_action, allowed=False,
                                       reason=q_reason, event_type="QUARANTINE_BLOCK")
            return {"allowed": False, "reason": q_reason}

        # ── Step 2: normal policy check ──
        allowed, reason = self._engine.check(agent_action, tenant_id, context)

        # ── Step 3: record violation and escalate if needed ──
        if not allowed:
            new_level = self._tracker.record_violation(tenant_id, agent_action)
            threat_state = self._tracker.get_state(tenant_id)

            # Attach threat level to the response so the agent/operator knows
            self._log_governance_event(tenant_id, agent_action, allowed=False,
                                       reason=reason, event_type="POLICY_VIOLATION",
                                       threat_level=new_level.value)
            return {
                "allowed":      False,
                "reason":       reason,
                "threat_level": new_level.value,
                "violations":   threat_state["violation_count"],
            }

        self._log_governance_event(tenant_id, agent_action, allowed=True,
                                   reason=reason, event_type="POLICY_ALLOW")
        return {"allowed": True, "reason": reason}

    def _handle_log_event(self, req: dict) -> dict:
        event = req.get("event", {})
        if not event:
            return {"error": "Missing event payload"}
        self._append_event(event)
        return {"ok": True}

    def _handle_get_threat(self, req: dict) -> dict:
        tenant_id = req.get("tenant_id", "")
        return self._tracker.get_state(tenant_id)

    def _handle_reset_tenant(self, req: dict) -> dict:
        """Operator endpoint — clears quarantine for a tenant."""
        tenant_id = req.get("tenant_id", "")
        if not tenant_id:
            return {"error": "Missing tenant_id"}
        self._tracker.reset_tenant(tenant_id)
        return {"ok": True, "reset": tenant_id}

    def _log_governance_event(self, tenant_id, action, allowed, reason,
                               event_type, threat_level=None):
        event = {
            "type": event_type,
            "tenant_id": tenant_id,
            "agent_action": action,
            "allowed": allowed,
            "reason": reason,
            "domain": "governance",
            "ts": time.time(),
        }
        if threat_level:
            event["threat_level"] = threat_level
        self._append_event(event)
        if self._telemetry:
            try:
                self._telemetry.record_event(
                    "policy_check",
                    {"tenant_id": tenant_id, "agent_action": action,
                     "allowed": str(allowed), "type": event_type},
                )
            except Exception as e:
                logger.debug("Telemetry record failed: %s", e)

    def _append_event(self, event: dict):
        if self._event_store:
            try:
                self._event_store.append(event)
            except Exception as e:
                logger.warning("EventStore append failed: %s", e)

    def serve(self) -> None:
        self._running = True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", self._port))
            server.listen(32)
            logger.info("Daemon listening on 127.0.0.1:%d", self._port)
            while self._running:
                try:
                    conn, addr = server.accept()
                    t = threading.Thread(
                        target=self._handle_client, args=(conn, addr), daemon=True
                    )
                    t.start()
                except KeyboardInterrupt:
                    logger.info("Daemon shutting down")
                    self._running = False


def main():
    parser = argparse.ArgumentParser(description="ClawGlove governance sidecar daemon")
    parser.add_argument("--policies", required=True)
    parser.add_argument("--kafka",    default="localhost:9092")
    parser.add_argument("--otlp",     default="http://localhost:4317")
    parser.add_argument("--port",     type=int, default=50051)
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
