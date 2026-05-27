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
import http.server
import urllib.request
import urllib.error
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


class ClawGloveProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress verbose HTTP logging
        pass

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        # Retrieve tenant ID from headers or default to tenant_alpha
        tenant_id = self.headers.get('X-Tenant-Id', 'tenant_alpha')

        try:
            req_json = json.loads(post_data.decode('utf-8'))
        except Exception:
            req_json = {}

        # Basic token estimation: 0.25 tokens per character
        messages = req_json.get("messages", [])
        prompt_text = "".join(msg.get("content", "") for msg in messages)
        estimated_tokens = max(100, len(prompt_text) // 4)

        # Query Policy Engine
        allowed, reason = self.server.engine.check("llm_call", tenant_id, {
            "tokens_used": estimated_tokens,
            "model": req_json.get("model", "sarvam-2b"),
        })

        # Append to Kafka and Telemetry via server references
        event = {
            "type": "POLICY_CHECK",
            "tenant_id": tenant_id,
            "agent_action": "llm_call",
            "allowed": allowed,
            "reason": reason,
            "domain": "governance",
            "ts": time.time(),
        }
        self.server.event_store.append(event)
        self.server.telemetry.record_event(
            "policy_check",
            {"tenant_id": tenant_id, "agent_action": "llm_call",
             "allowed": str(allowed), "reason": reason,
             "type": "POLICY_VIOLATION" if not allowed else "POLICY_ALLOW"},
        )

        if not allowed:
            self.send_response(403)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            err_resp = {
                "error": {
                    "message": f"ClawGlove Policy Denied: {reason}",
                    "type": "policy_violation",
                    "param": None,
                    "code": "forbidden"
                }
            }
            self.wfile.write(json.dumps(err_resp).encode('utf-8'))
            return

        # Forward request to the real api.sarvam.ai
        real_url = "https://api.sarvam.ai/v1" + self.path
        
        # Build headers
        req_headers = {}
        for k, v in self.headers.items():
            if k.lower() not in ('host', 'content-length', 'x-tenant-id'):
                req_headers[k] = v

        # Forward the request
        req = urllib.request.Request(
            real_url,
            data=post_data,
            headers=req_headers,
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ('transfer-encoding', 'content-encoding', 'content-length'):
                        self.send_header(k, v)
                resp_data = resp.read()
                self.send_header('Content-Length', str(len(resp_data)))
                self.end_headers()
                self.wfile.write(resp_data)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() not in ('transfer-encoding', 'content-encoding', 'content-length'):
                    self.send_header(k, v)
            resp_data = e.read()
            self.send_header('Content-Length', str(len(resp_data)))
            self.end_headers()
            self.wfile.write(resp_data)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))


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

        # Start the out-of-process HTTP/HTTPS egress proxy interceptor
        proxy_port = 50052
        try:
            proxy_server = http.server.HTTPServer(('127.0.0.1', proxy_port), ClawGloveProxyHandler)
            proxy_server.engine = self._engine
            proxy_server.event_store = self._event_store
            proxy_server.telemetry = self._telemetry
            proxy_thread = threading.Thread(target=proxy_server.serve_forever, daemon=True)
            proxy_thread.start()
            logger.info("Egress Proxy intercepting on 127.0.0.1:%d -> https://api.sarvam.ai/v1", proxy_port)
        except Exception as e:
            logger.error("Failed to start Egress Proxy interceptor: %s", e)

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
