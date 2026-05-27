from .event_bus import EventBus, Event

class PolicyViolationException(Exception):
    """Raised when an active runtime execution breaches platform safety limits."""
    pass

class ExecutionWorker:
    """Executes governed tasks under active policy constraints, publishing states to EventBus."""
    def __init__(self, worker_id, policies=None):
        self.worker_id = worker_id
        # Safe fallback policies if not loaded from compiled rule graphs
        self.policies = policies or {
            "active_token_ceiling": 250000,
            "max_tool_calls_sequence_limit": 10,
            "allow_recursive_agent_spawns": False
        }
        self.active_tokens_spent = 0
        self.tool_calls_count = 0
        self.event_bus = EventBus()

    def execute(self, task):
        """Processes task payload, tracking token burn rates, safety bounds, and publishing event updates."""
        print(f"[WORKER-{self.worker_id}] Initializing task run for: '{task.name}'")
        self.active_tokens_spent = 0
        self.tool_calls_count = 0
        
        # Publish task start event
        self.event_bus.publish(Event(
            event_type="WORKER_START",
            correlation_id=task.task_id,
            source="runtime/worker",
            severity="info",
            payload={
                "task_name": task.name,
                "worker_id": self.worker_id,
                "token_limit": self.policies["active_token_ceiling"]
            }
        ))
        
        try:
            steps = task.payload.get("steps", [])
            for index, step in enumerate(steps):
                action = step.get("action")
                tokens = step.get("tokens", 500)
                
                # Check active token ceiling rules
                if self.active_tokens_spent + tokens > self.policies["active_token_ceiling"]:
                    raise PolicyViolationException(
                        f"Cumulative tokens ({self.active_tokens_spent + tokens}) exceeded maximum ceiling limit of {self.policies['active_token_ceiling']}!"
                    )
                self.active_tokens_spent += tokens
                
                # Check tool calling counts
                if action == "call_tool":
                    self.tool_calls_count += 1
                    if self.tool_calls_count > self.policies["max_tool_calls_sequence_limit"]:
                        raise PolicyViolationException(
                            f"Sequential tool calls count ({self.tool_calls_count}) exceeded limits of {self.policies['max_tool_calls_sequence_limit']}!"
                        )
                
                # Verify delegation boundaries
                if action == "delegate" and not self.policies["allow_recursive_agent_spawns"]:
                    raise PolicyViolationException(
                        "Recursive subagent delegation triggered. Blocked under star topology rules."
                    )
                
                print(f"[WORKER-{self.worker_id}] Step {index+1}/{len(steps)} passed: {action} [Cost: {tokens} tokens]")
                
            task.status = "completed"
            print(f"[WORKER-{self.worker_id}] Task '{task.name}' successfully completed.")
            
            # Publish completion event
            self.event_bus.publish(Event(
                event_type="WORKER_COMPLETED",
                correlation_id=task.task_id,
                source="runtime/worker",
                severity="info",
                payload={
                    "status": "SUCCESS",
                    "tokens_spent": self.active_tokens_spent,
                    "tool_calls": self.tool_calls_count
                }
            ))
            
            return {
                "status": "SUCCESS",
                "tokens_spent": self.active_tokens_spent,
                "tool_calls": self.tool_calls_count
            }
        except PolicyViolationException as pve:
            task.status = "failed"
            print(f"[WORKER-{self.worker_id}] Policy Breach! Execution halted. Reason: {pve}")
            
            # Publish policy breach event (severity error from policy_engine)
            self.event_bus.publish(Event(
                event_type="POLICY_VIOLATION",
                correlation_id=task.task_id,
                source="policy_engine",
                severity="error",
                payload={
                    "error": str(pve),
                    "tokens_spent": self.active_tokens_spent,
                    "tool_calls": self.tool_calls_count
                }
            ))
            
            return {
                "status": "POLICY_VIOLATION",
                "error": str(pve),
                "tokens_spent": self.active_tokens_spent,
                "tool_calls": self.tool_calls_count
            }
        except Exception as e:
            task.status = "failed"
            print(f"[WORKER-{self.worker_id}] Runtime execution failure: {e}")
            
            # Publish failure event (severity error from runtime/worker)
            self.event_bus.publish(Event(
                event_type="WORKER_FAILED",
                correlation_id=task.task_id,
                source="runtime/worker",
                severity="error",
                payload={
                    "error": str(e),
                    "tokens_spent": self.active_tokens_spent,
                    "tool_calls": self.tool_calls_count
                }
            ))
            
            return {
                "status": "FAILED",
                "error": str(e),
                "tokens_spent": self.active_tokens_spent,
                "tool_calls": self.tool_calls_count
            }
