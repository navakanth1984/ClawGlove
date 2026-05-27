"""
ClawGlove interface contracts — DO NOT MODIFY without senior review.
These are the frozen ABCs that production backends implement.
Changing these is a breaking change to the platform ABI.
"""
from abc import ABC, abstractmethod
from typing import Any


class EventStoreInterface(ABC):
    """Append-only execution ledger. Implementations must be durable."""

    @abstractmethod
    def append(self, event: dict) -> None:
        """Append a single event. Must be atomic and ordered."""

    @abstractmethod
    def get_all_events(self, domain: str, tenant_id: str) -> list[dict]:
        """Return all events for a domain/tenant in append order."""


class TenantIsolationInterface(ABC):
    """Hard boundary enforcement between agent workloads."""

    @abstractmethod
    def fence(self, tenant_id: str, workload_fn: Any, *args, **kwargs) -> Any:
        """
        Execute workload_fn inside an isolated tenant boundary.
        Must enforce: no cross-tenant filesystem access, CPU/memory limits.
        Fail-closed: if isolation cannot be established, raise and do not execute.
        """


class CoordinatorInterface(ABC):
    """Distributed consensus and state checkpointing."""

    @abstractmethod
    def elect_leader(self, node_id: str, ttl_seconds: int) -> bool:
        """Attempt to acquire leadership. Returns True if acquired."""

    @abstractmethod
    def checkpoint_state(self, key: str, state: dict) -> None:
        """Persist state checkpoint. Must be strongly consistent."""

    @abstractmethod
    def load_checkpoint(self, key: str) -> dict | None:
        """Retrieve last checkpoint. Returns None if not found."""


class TelemetryInterface(ABC):
    """Observability contract — maps to OpenTelemetry spans."""

    @abstractmethod
    def record_event(self, name: str, attributes: dict) -> None:
        """Record a named event with attributes as an OTel span."""

    @abstractmethod
    def record_metric(self, name: str, value: float, attributes: dict) -> None:
        """Record a scalar metric."""


class PolicyEngineInterface(ABC):
    """Runtime policy enforcement at the execution boundary."""

    @abstractmethod
    def check(self, action: str, tenant_id: str, context: dict) -> tuple[bool, str]:
        """
        Check if action is permitted for tenant.
        Returns (allowed: bool, reason: str).
        Must be synchronous and fast (<5ms).
        """
