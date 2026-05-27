"""
CGBench Layer 5 — Infrastructure Resilience.
Simulates active broker drops (Kafka, OTel, etcd) and asserts fallback logging, zero stalls, and execution survivability.
"""
import os
import time
import json
import logging
from clawglove.events.kafka_store import KafkaEventStore
from clawglove.metrics.otel_telemetry import OTelTelemetry
from clawglove.runtime.etcd_coordinator import EtcdCoordinator

logger = logging.getLogger("cgbench.layers.resilience")


class Layer5InfrastructureResilience:
    def run(self) -> dict:
        """
        Executes Layer 5 chaos resilience sweeps.
        Returns:
            {
                "kafka_fallback_active": bool,
                "otel_offline_silent": bool,
                "etcd_fallback_active": bool,
                "zero_stalls_verified": bool,
                "passed": bool
            }
        """
        logger.info("Starting Layer 5 infrastructure crash injection...")

        # INFRA-001: Instantiate KafkaEventStore on a completely dead port to simulate a mid-execution crash
        dead_kafka_broker = "127.0.0.1:9999"  # Guaranteed unreachable
        
        start_time = time.perf_counter()
        
        # Initialize EventStore targeting the dead port
        event_store = KafkaEventStore(bootstrap_servers=dead_kafka_broker)
        
        # Attempt to append events aggressively
        fallback_file = "clawglove_events_fallback.jsonl"
        if os.path.exists(fallback_file):
            try:
                os.remove(fallback_file)
            except Exception:
                pass

        test_events = [
            {"type": "POLICY_CHECK", "tenant_id": "tenant_alpha", "agent_action": "search_web", "domain": "governance", "index": 1},
            {"type": "POLICY_CHECK", "tenant_id": "tenant_alpha", "agent_action": "llm_call", "domain": "governance", "index": 2}
        ]

        for evt in test_events:
            event_store.append(evt)

        # Verify execution didn't block (latency must be well under 1 second since fallback uses non-blocking file append)
        append_latency_ms = (time.perf_counter() - start_time) * 1000
        zero_stalls_verified = append_latency_ms < 500.0  # Must be fast

        # Verify fallback ledger is populated
        kafka_fallback_active = False
        if os.path.exists(fallback_file):
            with open(fallback_file, "r") as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    last_event = json.loads(lines[-1].strip())
                    kafka_fallback_active = last_event.get("index") == 2

        # INFRA-002: OTel Telemetry drop audit
        dead_otel_collector = "http://127.0.0.1:9998"
        otel_telemetry = OTelTelemetry(otlp_endpoint=dead_otel_collector)
        
        # Call record_event on dead collector — must execute instantly and quietly
        otel_start = time.perf_counter()
        otel_telemetry.record_event("resilience_test", {"type": "POLICY_VIOLATION"})
        otel_latency_ms = (time.perf_counter() - otel_start) * 1000
        otel_offline_silent = otel_latency_ms < 100.0

        # INFRA-003: etcd coordinator failure
        dead_etcd = "127.0.0.1"
        coordinator = EtcdCoordinator(host=dead_etcd, port=9997)
        
        # Test elect_leader on dead etcd
        etcd_start = time.perf_counter()
        leader_elected = coordinator.elect_leader("node_chaos", ttl_seconds=5)
        etcd_latency_ms = (time.perf_counter() - etcd_start) * 1000
        etcd_fallback_active = leader_elected and etcd_latency_ms < 100.0

        passed = (kafka_fallback_active and 
                  otel_offline_silent and 
                  etcd_fallback_active and 
                  zero_stalls_verified)

        return {
            "kafka_fallback_active": kafka_fallback_active,
            "otel_offline_silent": otel_offline_silent,
            "etcd_fallback_active": etcd_fallback_active,
            "zero_stalls_verified": zero_stalls_verified,
            "append_latency_ms": append_latency_ms,
            "passed": passed
        }
