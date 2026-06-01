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
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from clawglove.events.kafka_store import KafkaEventStore
from clawglove.metrics.otel_telemetry import OTelTelemetry
from clawglove.policies.compiler import PolicyCompiler
from clawglove.policies.engine import PolicyEngine
from clawglove.sidecar.escalation import ThreatEscalationTracker, ThreatLevel
from clawglove.sidecar._explorer_html import EXPLORER_HTML

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("clawglove.daemon")


class AuditHttpHandler(BaseHTTPRequestHandler):
    daemon: 'ClawGloveDaemon' = None

    def log_message(self, fmt, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")

        if path == "/audit/tenants":
            try:
                tenants = self.daemon._cpt_client._ledger.get_quarantined_tenants()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(tenants).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        elif path.startswith("/audit/quarantine/"):
            tenant_id = path.split("/")[-1]
            try:
                log = self.daemon._cpt_client.get_quarantine_log(tenant_id)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(log).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        elif path.startswith("/audit/envelope/"):
            parts = path.split("/")
            if len(parts) >= 5:
                tenant_id = parts[-2]
                skill_id = parts[-1]
                try:
                    env = self.daemon._cpt_client.get_envelope(skill_id, tenant_id)
                    env_dict = {
                        "skill_id": env.skill_id,
                        "file_path": env.file_path,
                        "content_hash": env.content_hash,
                        "originating_session_id": env.originating_session_id,
                        "parent_user_request_hash": env.parent_user_request_hash,
                        "generator_model": env.generator_model,
                        "generation_timestamp": env.generation_timestamp,
                        "tenant_id": env.tenant_id,
                        "signature": env.signature,
                        "auto_approved": env.auto_approved,
                        "quarantine_path": env.quarantine_path,
                    }
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(env_dict).encode("utf-8"))
                except KeyError:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": f"No envelope for skill {skill_id} in tenant {tenant_id}"}).encode("utf-8"))
                except Exception as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            else:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid path format"}).encode("utf-8"))
            return

        elif path == "/audit/chain/verify":
            try:
                env_metrics = self.daemon._cpt_client._ledger.verify_chain("envelopes")
                env_status = {"status": "VERIFIED", **env_metrics}
            except Exception as e:
                env_status = {"status": "VIOLATION", "error_detail": str(e)}

            try:
                q_metrics = self.daemon._cpt_client._ledger.verify_chain("quarantine_log")
                q_status = {"status": "VERIFIED", **q_metrics}
            except Exception as e:
                q_status = {"status": "VIOLATION", "error_detail": str(e)}

            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "envelopes": env_status,
                "quarantine_log": q_status,
                "node_id": self.daemon._cpt_client._ledger.node_id,
                "active_key_id": self.daemon._cpt_client._active_key_id,
            }).encode("utf-8"))
            return

        elif path == "" or path == "/index.html":
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(EXPLORER_HTML.encode("utf-8"))
            return

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")

        if path.startswith("/audit/reconcile/"):
            tenant_id = path.split("/")[-1]
            try:
                res = self.daemon._cpt_client.reconcile_quarantine(tenant_id)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return
        
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")


class ClawGloveDaemon:

    def __init__(
        self,
        policies_dir: str,
        workspace: str = ".",
        http_host: str = "127.0.0.1",
        http_port: int = 50052,
        kafka_servers: str = "localhost:9092",
        otlp_endpoint: str = "http://localhost:4317",
        port: int = 50051,
    ):
        logger.info("ClawGlove daemon starting...")

        self._workspace = workspace
        self._http_host = http_host
        self._http_port = http_port

        from clawglove.provenance.client import CPTClient
        from pathlib import Path
        self._cpt_client = CPTClient.from_workspace(Path(workspace))

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

        # Start the background HTTP server for CPT Auditing Explorer UI
        def _run_http():
            handler_class = type("AuditHttpHandlerInjected", (AuditHttpHandler,), {"daemon": self})
            self._httpd = HTTPServer((self._http_host, self._http_port), handler_class)
            logger.info("Audit Explorer UI listening on http://%s:%d", self._http_host, self._http_port)
            try:
                self._httpd.serve_forever()
            except Exception as e:
                logger.error("HTTP server error: %s", e)

        http_thread = threading.Thread(target=_run_http, daemon=True)
        http_thread.start()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", self._port))
            server.listen(32)
            logger.info("Daemon listening on 0.0.0.0:%d", self._port)
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
                    if hasattr(self, "_httpd"):
                        self._httpd.shutdown()
                    break
                except Exception as e:
                    if not self._running:
                        break
                    logger.error("Error in accept loop: %s", e)


def main():
    parser = argparse.ArgumentParser(description="ClawGlove governance sidecar daemon")
    parser.add_argument("--policies", required=True)
    parser.add_argument("--kafka",    default="localhost:9092")
    parser.add_argument("--otlp",     default="http://localhost:4317")
    parser.add_argument("--port",     type=int, default=50051)
    parser.add_argument("--workspace", default=".", help="Workspace root directory")
    parser.add_argument("--http-host", default="127.0.0.1", help="HTTP server bind host")
    parser.add_argument("--http-port", type=int, default=50052, help="HTTP server bind port")
    args = parser.parse_args()

    import sys
    from pathlib import Path
    from clawglove.provenance.ledger import ProvenanceLedger, LedgerChainViolation

    workspace = Path(args.workspace)
    db_path = workspace / "provenance_ledger.db"

    # Close the T-001 chain detection loop on sidecar startup
    try:
        ledger = ProvenanceLedger(db_path)
        ledger.verify_all_chains()
        logger.info("CPT durable provenance ledger integrity verified successfully at %s", db_path)

        # Run reconciliation/self-healing across all quarantined tenants (Design Refinement 5)
        quarantined_tenants = ledger.get_quarantined_tenants()
        if quarantined_tenants:
            from clawglove.provenance.client import CPTClient
            cpt_client = CPTClient.from_workspace(workspace)
            for tenant in quarantined_tenants:
                res = cpt_client.reconcile_quarantine(tenant)
                logger.info("Reconciliation complete for tenant '%s': verified %d records, pruned %d untracked files",
                            tenant, res["verified_count"], len(res["pruned_files"]))
    except LedgerChainViolation as exc:
        logger.critical("LEDGER_CHAIN_VIOLATION: %s. Fails closed.", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error("Failed to initialize or verify provenance ledger: %s", exc)

    daemon = ClawGloveDaemon(
        policies_dir=args.policies,
        workspace=args.workspace,
        http_host=args.http_host,
        http_port=args.http_port,
        kafka_servers=args.kafka,
        otlp_endpoint=args.otlp,
        port=args.port,
    )
    daemon.serve()


if __name__ == "__main__":
    main()
