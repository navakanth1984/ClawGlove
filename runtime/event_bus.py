import uuid
import threading
from datetime import datetime

class Event:
    """Standardized event unit tracking correlation, source, severity, and ISO time coordinates.

    v1.7 optional fields (default None / 'default'):
        agent_id   - Identity of the agent producing the event
        tenant_id  - Multi-tenant execution context
        trace_id   - Links event to a parent end-to-end execution trace
    """
    def __init__(self, event_type, correlation_id, payload,
                 source="runtime/kernel", severity="info",
                 agent_id=None, tenant_id="default", trace_id=None):
        self.event_id = f"evt_{uuid.uuid4().hex[:8]}"
        self.correlation_id = correlation_id
        self.timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.event_type = event_type
        self.source = source
        self.severity = severity  # info, warning, error
        self.schema_version = "1.0"
        # v1.7 identity and tracing fields (optional, reserved for multi-agent deployments)
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.trace_id = trace_id
        self.payload = payload

    def to_dict(self):
        """Serializes event metadata for pub-sub dissemination."""
        d = {
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "source": self.source,
            "severity": self.severity,
            "schema_version": self.schema_version,
            "tenant_id": self.tenant_id,
            "payload": self.payload
        }
        # Include optional identity/tracing fields only when set
        if self.agent_id is not None:
            d["agent_id"] = self.agent_id
        if self.trace_id is not None:
            d["trace_id"] = self.trace_id
        return d

class EventBus:
    """Thread-safe Pub-Sub Broker governing ACDLC communications."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(EventBus, cls).__new__(cls, *args, **kwargs)
                cls._instance._subscribers = {}
                cls._instance._subscribers_lock = threading.Lock()
        return cls._instance

    def subscribe(self, event_type, callback):
        """Subscribes an execution callback to a specific event stream."""
        with self._subscribers_lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            print(f"[EVENT_BUS] Callback registered for: '{event_type}'")

    def publish(self, event):
        """Dispatches an event to all matched subscribers dynamically."""
        event_dict = event.to_dict()
        event_type = event.event_type
        
        # Copy callbacks under lock to prevent mutation during execution
        callbacks = []
        with self._subscribers_lock:
            if event_type in self._subscribers:
                callbacks.extend(self._subscribers[event_type])
            if "*" in self._subscribers:
                callbacks.extend(self._subscribers["*"])

        for callback in callbacks:
            try:
                callback(event_dict)
            except Exception as e:
                print(f"[EVENT_BUS] Subscriber callback execution error on '{event_type}': {e}")
