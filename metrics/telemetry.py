import time

class TelemetryManager:
    """
    Standardizes telemetry, enforces sampling policies to prevent DoS,
    and detects Red Zone threshold breaches.
    """
    def __init__(self, event_store, node_id="node_unknown"):
        self.event_store = event_store
        self.node_id = node_id
        
        # Sampling state
        self._last_emit_time = {}
        self._emit_counts = {}
        
        # Red Zone Thresholds
        self.thresholds = {
            "queue_depth": {"warning": 10000, "critical": 50000},
            "replay_latency_ms": {"warning": 500, "critical": 5000},
            "auth_failures_per_min": {"warning": 100, "critical": 1000},
            "autoscaler_oscillation_per_min": {"warning": 3, "critical": 10},
            "orphaned_tasks": {"warning": 1, "critical": 50}
        }
        
        # High-frequency metrics definition (sample every 5s)
        self.high_frequency_metrics = {
            "queue_depth",
            "active_workers",
            "events_replayed_per_sec",
            "cpu_usage",
            "memory_usage"
        }

    def emit_metric(self, category, name, value, tenant_id="system", severity="info"):
        """
        Emits a canonical telemetry event, applying sampling policies
        if the metric is high frequency.
        """
        # 1. Sampling Policy
        if name in self.high_frequency_metrics:
            now = time.time()
            last_time = self._last_emit_time.get(name, 0)
            if now - last_time < 5.0:
                # Skip emitting to prevent telemetry DoS
                return
            self._last_emit_time[name] = now

        # 2. Canonical Telemetry Envelope
        metric_event = {
            "event_type": "METRIC",
            "metric_category": category,
            "metric_name": name,
            "metric_value": value,
            "timestamp": time.time(),
            "node_id": self.node_id,
            "tenant_id": tenant_id,
            "severity": severity
        }
        
        self.event_store.append(metric_event)
        
        # 3. Red Zone Threshold Detection
        self._check_threshold(name, value)

    def _check_threshold(self, name, value):
        if name not in self.thresholds:
            return
            
        limits = self.thresholds[name]
        breach_severity = None
        
        if value >= limits["critical"]:
            breach_severity = "critical"
        elif value >= limits["warning"]:
            breach_severity = "warning"
            
        if breach_severity:
            self.event_store.append({
                "event_type": "THRESHOLD_BREACH",
                "metric_name": name,
                "metric_value": value,
                "threshold": limits[breach_severity],
                "severity": breach_severity,
                "node_id": self.node_id,
                "timestamp": time.time()
            })

    def emit_critical_event(self, name, details, tenant_id="system"):
        """Always emits critical OS events immediately."""
        self.event_store.append({
            "event_type": "CRITICAL_SYSTEM_EVENT",
            "event_name": name,
            "details": details,
            "timestamp": time.time(),
            "node_id": self.node_id,
            "tenant_id": tenant_id,
            "severity": "critical"
        })
