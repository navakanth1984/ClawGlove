import json
import os
from .event_bus import EventBus, Event

class StateManager:
    """Manages active states, subscribes to EventBus, and partitions telemetry to warehouse subfolders."""
    def __init__(self, state_file=None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.state_file = state_file or os.path.join(base_dir, "runtime_state.json")
        self.warehouse_dir = os.path.join(base_dir, "analytics", "warehouse")
        
        self.state = {
            "schema_name": "lifecycle-state",
            "schema_version": "1.0",
            "generated_by": "ACDLC-v1.7",
            "framework": "ACDLC",
            "version": "1.7",
            "task_id": "TASK-000",
            "active_stage": "Stage 0: GPS Foundation",
            "status": "INIT",
            "context_bundle": {
                "version": "1.0.0",
                "path": "templates/context-bundle-template.md",
                "compressed": False
            },
            "metrics": {
                "token_limit": 250000,
                "tokens_consumed": 0,
                "cost_consumed_usd": 0.0,
                "execution_retries": 0
            },
            "remediation": {
                "escalated_to_human": False,
                "retry_limit_hit": False
            }
        }
        
        # Load state and verify warehouse partitioning folders
        self.load_state()
        self.setup_warehouse_directories()
        
        # Subscribe to Event Bus wildcard to capture all dispatches
        self.event_bus = EventBus()
        self.event_bus.subscribe("*", self.handle_event)

    def setup_warehouse_directories(self):
        """Creates partitioned directories for structured telemetry database segments."""
        partitions = ["executions", "policies", "escalations", "simulations", "telemetry", "traces"]
        for p in partitions:
            path = os.path.join(self.warehouse_dir, p)
            if not os.path.exists(path):
                os.makedirs(path)

    def handle_event(self, event_dict):
        """Processes EventBus dispatches and logs/persists them to the telemetry warehouse."""
        event_type = event_dict.get("event_type")
        correlation_id = event_dict.get("correlation_id")
        event_id = event_dict.get("event_id")
        
        print(f"[STATE_MGR] Intercepted event: '{event_type}' (Correlation: {correlation_id})")
        
        # Determine correct warehouse directory partition
        partition = "telemetry"
        if event_type in ["WORKER_START", "WORKER_COMPLETED", "WORKER_FAILED",
                          "TASK_SCHEDULED", "TASK_COMPLETED", "TASK_REGISTERED",
                          "POOL_TASK_SUBMITTED", "POOL_TASK_COMPLETED", "POOL_CAPACITY_WARNING",
                          "AGENT_REGISTERED", "AGENT_DEREGISTERED"]:
            partition = "executions"
        elif event_type in ["POLICY_VIOLATION", "DELEGATION_VIOLATION", "TRUST_SCORE_UPDATED"]:
            partition = "policies"
        elif event_type in ["HUMAN_ESCALATION"]:
            partition = "escalations"
        elif event_type in ["SIMULATION_START", "SIMULATION_COMPLETED"]:
            partition = "simulations"
        elif event_type in ["ROUTE_SELECTED"]:
            partition = "traces"

        # Construct destination path
        dest_file = os.path.join(self.warehouse_dir, partition, f"{event_id}.json")
        try:
            with open(dest_file, "w", encoding="utf-8") as f:
                json.dump(event_dict, f, indent=2)
        except Exception as e:
            print(f"[STATE_MGR] Failed to write event {event_id} to warehouse: {e}")

        # Update metrics and status based on events
        if event_type == "WORKER_START":
            self.state["task_id"] = correlation_id
            self.state["status"] = "RUNNING"
            self.save_state()
        elif event_type == "WORKER_COMPLETED":
            self.state["status"] = "COMPLETED"
            tokens = event_dict.get("payload", {}).get("tokens_spent", 0)
            self.update_metrics(tokens_added=tokens)
        elif event_type == "POLICY_VIOLATION":
            self.state["status"] = "FAILED"
            self.trigger_escalation(reason=event_dict.get("payload", {}).get("error", "Policy breach"))

    def load_state(self):
        """Loads state database from file if available."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
                print(f"[STATE] Loaded active state database from: {self.state_file}")
            except Exception as e:
                print(f"[STATE] Failed to deserialize state database: {e}")

    def save_state(self):
        """Saves current state database back to file."""
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
            return True
        except Exception as e:
            print(f"[STATE] Serialization failure on state save: {e}")
            return False

    def update_stage(self, stage_name):
        """Transitions execution stage."""
        self.state["active_stage"] = stage_name
        self.save_state()

    def update_status(self, status):
        """Transitions runtime status state."""
        self.state["status"] = status
        self.save_state()

    def update_metrics(self, tokens_added, cost_added=0.0, retries=0):
        """Accumulates token and dollar expenditures."""
        self.state["metrics"]["tokens_consumed"] += tokens_added
        self.state["metrics"]["cost_consumed_usd"] += cost_added
        self.state["metrics"]["execution_retries"] = retries
        self.save_state()

    def trigger_escalation(self, reason):
        """Locks runtime, updates states, and publishes HUMAN_ESCALATION events."""
        if self.state["remediation"]["escalated_to_human"]:
            return
            
        self.state["status"] = "FAILED"
        self.state["remediation"]["escalated_to_human"] = True
        self.state["remediation"]["retry_limit_hit"] = True
        self.save_state()
        
        # Publish human escalation event track (severity error from runtime/state_manager)
        self.event_bus.publish(Event(
            event_type="HUMAN_ESCALATION",
            correlation_id=self.state["task_id"],
            source="runtime/state_manager",
            severity="error",
            payload={"reason": reason}
        ))
