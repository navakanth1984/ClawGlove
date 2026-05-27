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
        self._bootstrap_servers = bootstrap_servers
        self._producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "acks": "all",           # Wait for all replicas — no data loss
            "retries": 5,
            "enable.idempotence": True,
        })

    def _topic(self, domain: str, tenant_id: str) -> str:
        # Topic naming convention: clawglove.tenant_alpha.operational
        # Kafka topic names allow dots and underscores.
        safe_tenant = tenant_id.replace("-", "_")
        safe_domain = domain.replace("-", "_")
        return f"clawglove.{safe_tenant}.{safe_domain}"

    def append(self, event: dict) -> None:
        """
        Append event to the tenant/domain partition.
        Blocks until the broker acknowledges write (acks=all).
        """
        tenant_id = event.get("tenant_id", "default")
        domain = event.get("domain", "operational")
        topic = self._topic(domain, tenant_id)

        payload = json.dumps(event, sort_keys=True, ensure_ascii=False).encode("utf-8")

        def delivery_callback(err, msg):
            if err:
                logger.error("EventStore append failed: topic=%s err=%s", topic, err)
            else:
                logger.debug("EventStore append: topic=%s offset=%s", topic, msg.offset())

        self._producer.produce(topic, value=payload, callback=delivery_callback)
        # Flush immediately — governance events must not be batched silently.
        self._producer.flush(timeout=10)

    def get_all_events(self, domain: str, tenant_id: str) -> list[dict]:
        """
        Replay all events from the beginning of the topic partition.
        Used for state reconstruction and forensic replay.
        """
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
