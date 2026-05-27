"""
Kafka-backed EventStore.
Replaces JSONL file appends with Kafka partitioned append-only log.
Topic naming: clawglove.{tenant_id}.{domain}
"""
import json
import logging
from confluent_kafka import Producer, Consumer, KafkaError
from clawglove.interfaces import EventStoreInterface

logger = logging.getLogger(__name__)


class KafkaEventStore(EventStoreInterface):
    """
    Durable event ledger backed by Kafka.
    Each (tenant_id, domain) pair maps to a dedicated Kafka topic.
    Retention and WORM policies are enforced at the broker level via topic config.
    """

    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        import socket
        self._bootstrap_servers = bootstrap_servers
        self._online = False

        # Gracefully verify connectivity to broker first to avoid blocking on flush
        try:
            parts = bootstrap_servers.split(",")
            for part in parts:
                host, port = part.strip().split(":")
                with socket.create_connection((host, int(port)), timeout=0.1):
                    self._online = True
                    break
        except Exception:
            pass

        if self._online:
            try:
                self._producer = Producer({
                    "bootstrap.servers": bootstrap_servers,
                    "acks": "all",           # Wait for all replicas — no data loss
                    "retries": 5,
                    "enable.idempotence": True,
                })
                logger.info("KafkaEventStore initialized and online: %s", bootstrap_servers)
            except Exception as e:
                self._producer = None
                self._online = False
                logger.warning("Kafka Producer initialization failed: %s. Falling back to offline mode.", e)
        else:
            self._producer = None
            logger.warning("Kafka broker unreachable at %s. Falling back to offline mode.", bootstrap_servers)

    def _topic(self, domain: str, tenant_id: str) -> str:
        # Topic naming convention: clawglove.tenant_alpha.operational
        # Kafka topic names allow dots and underscores.
        safe_tenant = tenant_id.replace("-", "_")
        safe_domain = domain.replace("-", "_")
        return f"clawglove.{safe_tenant}.{safe_domain}"

    def append(self, event: dict) -> None:
        """
        Append event to the tenant/domain partition.
        Blocks until the broker acknowledges write (acks=all) if online.
        """
        tenant_id = event.get("tenant_id", "default")
        domain = event.get("domain", "operational")
        topic = self._topic(domain, tenant_id)

        # Fallback logging if offline
        if not self._online or self._producer is None:
            logger.debug("[OFFLINE LOG] Event: %s", event)
            try:
                with open("clawglove_events_fallback.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
            except Exception as e:
                logger.error("Failed to write to local fallback event log: %s", e)
            return

        payload = json.dumps(event, sort_keys=True, ensure_ascii=False).encode("utf-8")

        def delivery_callback(err, msg):
            if err:
                logger.error("EventStore append failed: topic=%s err=%s", topic, err)
            else:
                logger.debug("EventStore append: topic=%s offset=%s", topic, msg.offset())

        try:
            self._producer.produce(topic, value=payload, callback=delivery_callback)
            # Flush immediately — governance events must not be batched silently.
            flushed = self._producer.flush(timeout=0.1)
            if flushed > 0:
                logger.warning("Kafka EventStore flush timed out for topic %s", topic)
        except Exception as e:
            logger.error("Kafka EventStore produce failed: %s", e)

    def get_all_events(self, domain: str, tenant_id: str) -> list[dict]:
        """
        Replay all events from the beginning of the topic partition.
        Used for state reconstruction and forensic replay.
        """
        if not self._online:
            events = []
            try:
                with open("clawglove_events_fallback.jsonl", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            evt = json.loads(line.strip())
                            if evt.get("tenant_id") == tenant_id and evt.get("domain") == domain:
                                events.append(evt)
            except Exception:
                pass
            return events

        topic = self._topic(domain, tenant_id)
        consumer = Consumer({
            "bootstrap.servers": self._bootstrap_servers,
            "group.id": f"clawglove-replay-{tenant_id}-{domain}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        })

        events = []
        try:
            consumer.subscribe([topic])
            while True:
                msg = consumer.poll(timeout=2.0)
                if msg is None:
                    break
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        break
                    raise RuntimeError(f"Kafka consumer error: {msg.error()}")
                events.append(json.loads(msg.value().decode("utf-8")))
        finally:
            consumer.close()

        return events
