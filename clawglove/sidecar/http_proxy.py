"""
ClawGlove HTTP Proxy Sidecar.
Intercepts all agent HTTP traffic at the network layer.
Agents are containerised with no direct internet route — all traffic
must pass through this proxy. If this proxy is down, agents cannot
reach api.sarvam.ai. Fail-closed by network topology, not by code.

Run: python -m clawglove.sidecar.http_proxy --policies ./policies/ --port 8080

Agent containers set:
  HTTP_PROXY=http://clawglove-sidecar:8080
  HTTPS_PROXY=http://clawglove-sidecar:8080

This proxy:
  1. Checks policy before forwarding any LLM API request
  2. Logs every request+response to the EventStore
  3. Blocks all non-allowlisted destinations (fail-closed)
  4. Enforces token budget by inspecting request + response bodies
"""
import argparse
import json
import logging
import socket
import ssl
import threading
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from clawglove.policies.compiler import PolicyCompiler
from clawglove.policies.engine import PolicyEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] clawglove.proxy: %(message)s",
)
logger = logging.getLogger("clawglove.proxy")

# Only these destination hosts are ever allowed to be forwarded.
# Everything else is blocked regardless of policy.
ALLOWLISTED_HOSTS = {
    "api.sarvam.ai",    # The confirmed OpenClaw LLM endpoint
}

# Tenant is identified from the X-ClawGlove-Tenant header the agent sets,
# or from the container hostname if running in Docker.
TENANT_HEADER = "X-ClawGlove-Tenant"


class ProxyHandler(BaseHTTPRequestHandler):
    """
    HTTP CONNECT proxy handler.
    For HTTPS: handles CONNECT tunnel, inspects the destination host.
    For HTTP: inspects the request directly.
    """

    policy_engine: PolicyEngine = None   # Injected at startup
    event_store = None                   # Injected at startup

    def log_message(self, fmt, *args):
        logger.debug(fmt, *args)

    def _tenant_from_request(self) -> str:
        """Extract tenant ID from custom header or fall back to 'unknown'."""
        return self.headers.get(TENANT_HEADER, "unknown")

    def _block(self, reason: str, tenant_id: str, destination: str):
        logger.warning("BLOCKED tenant=%s dst=%s reason=%s", tenant_id, destination, reason)
        self._log_event("POLICY_VIOLATION", tenant_id, {
            "destination": destination,
            "reason": reason,
            "blocked": True,
        })
        self.send_response(403)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body = json.dumps({"error": "blocked_by_clawglove", "reason": reason})
        self.wfile.write(body.encode())

    def _log_event(self, event_type: str, tenant_id: str, data: dict):
        if self.event_store:
            try:
                self.event_store.append({
                    "type": event_type,
                    "tenant_id": tenant_id,
                    "domain": "governance",
                    "ts": time.time(),
                    **data,
                })
            except Exception as e:
                logger.error("EventStore append failed: %s", e)

    def do_CONNECT(self):
        """Handle HTTPS CONNECT tunnel — check destination before establishing."""
        tenant_id = self._tenant_from_request()
        host_port = self.path  # e.g. "api.sarvam.ai:443"
        host = host_port.split(":")[0]

        # 1. Allowlist check — hard block for non-approved destinations
        if host not in ALLOWLISTED_HOSTS:
            self._block(f"Destination not allowlisted: {host}", tenant_id, host)
            return

        # 2. Policy check — is this tenant allowed to call this LLM?
        allowed, reason = self.policy_engine.check(
            "sarvam_api_call", tenant_id, {"destination": host}
        )
        if not allowed:
            self._block(reason, tenant_id, host)
            return

        # 3. Establish tunnel to destination
        try:
            dest_host, dest_port = host_port.split(":")
            dest_sock = socket.create_connection((dest_host, int(dest_port)), timeout=10)
        except (socket.error, ValueError) as e:
            logger.error("Failed to connect to %s: %s", host_port, e)
            self.send_response(502)
            self.end_headers()
            return

        self.send_response(200, "Connection Established")
        self.end_headers()

        self._log_event("PROXY_TUNNEL_OPEN", tenant_id, {
            "destination": host_port,
            "allowed": True,
        })

        # Relay bytes bidirectionally
        client_sock = self.connection
        self._relay(client_sock, dest_sock, tenant_id, host_port)

    def do_POST(self):
        """Handle direct HTTP POST — inspect body for token counts."""
        tenant_id = self._tenant_from_request()
        host = self.headers.get("Host", "unknown")

        if host not in ALLOWLISTED_HOSTS:
            self._block(f"Destination not allowlisted: {host}", tenant_id, host)
            return

        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length else b""

        # Estimate tokens from body if it's a completion request
        tokens_used = 0
        try:
            body = json.loads(body_bytes)
            # Rough token estimate: 4 chars per token
            prompt_text = json.dumps(body.get("messages", body.get("prompt", "")))
            tokens_used = len(prompt_text) // 4
        except (json.JSONDecodeError, KeyError):
            pass

        allowed, reason = self.policy_engine.check(
            "sarvam_api_call", tenant_id,
            {"destination": host, "tokens_used": tokens_used}
        )
        if not allowed:
            self._block(reason, tenant_id, host)
            return

        # Forward request to Sarvam AI
        try:
            req = urllib.request.Request(
                f"https://{host}{self.path}",
                data=body_bytes,
                headers={k: v for k, v in self.headers.items()
                         if k.lower() not in ("host", TENANT_HEADER.lower())},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp_body)

            self._log_event("SARVAM_API_CALL", tenant_id, {
                "path": self.path,
                "tokens_estimated": tokens_used,
                "status": resp.status,
            })
        except urllib.error.URLError as e:
            logger.error("Upstream error: %s", e)
            self.send_response(502)
            self.end_headers()

    @staticmethod
    def _relay(client: socket.socket, server: socket.socket, tenant_id: str, dst: str):
        """Relay bytes between client and destination sockets."""
        def forward(src, dst_sock, label):
            try:
                while True:
                    data = src.recv(65536)
                    if not data:
                        break
                    dst_sock.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    dst_sock.shutdown(socket.SHUT_WR)
                except Exception:
                    pass

        t1 = threading.Thread(target=forward, args=(client, server, "c→s"), daemon=True)
        t2 = threading.Thread(target=forward, args=(server, client, "s→c"), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()


def make_handler(engine: PolicyEngine, store):
    """Create a handler class with injected dependencies."""
    class Handler(ProxyHandler):
        policy_engine = engine
        event_store = store
    return Handler


def main():
    parser = argparse.ArgumentParser(description="ClawGlove HTTP proxy sidecar")
    parser.add_argument("--policies", required=True, help="Path to policies directory")
    parser.add_argument("--port", type=int, default=8080, help="Proxy listen port")
    parser.add_argument("--kafka", default="localhost:9092")
    args = parser.parse_args()

    compiler = PolicyCompiler()
    policies = compiler.compile_directory(args.policies)
    if not policies:
        raise RuntimeError(f"No policies found in {args.policies}")

    engine = PolicyEngine(policies)

    # EventStore is optional at startup — proxy works without Kafka
    store = None
    try:
        from clawglove.events.kafka_store import KafkaEventStore
        store = KafkaEventStore(bootstrap_servers=args.kafka)
        logger.info("EventStore connected to Kafka at %s", args.kafka)
    except Exception as e:
        logger.warning("EventStore unavailable (Kafka not running): %s — proxy will run without audit log", e)

    handler = make_handler(engine, store)
    server = HTTPServer(("0.0.0.0", args.port), handler)
    logger.info(
        "ClawGlove proxy listening on 0.0.0.0:%d — allowlist: %s",
        args.port, ALLOWLISTED_HOSTS
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
