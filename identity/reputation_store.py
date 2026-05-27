import json
import os
import datetime

class ReputationEventStore:
    """Event-sourced reputation history store."""
    def __init__(self, storage_dir):
        self._storage_dir = storage_dir
        self._log_path = os.path.join(storage_dir, "reputation_events.jsonl")
        os.makedirs(self._storage_dir, exist_ok=True)

    def append_event(self, agent_id, event_type, details=None):
        """event_type: 'Success', 'Failure', 'Violation', 'Retry'"""
        record = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "agent_id": agent_id,
            "event_type": event_type,
            "details": details or {}
        }
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def reconstruct_scorecards(self):
        """Reconstructs the current state of all scorecards from the event log."""
        scorecards = {}
        if not os.path.exists(self._log_path):
            return scorecards
            
        with open(self._log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                agent_id = record["agent_id"]
                etype = record["event_type"]
                
                if agent_id not in scorecards:
                    scorecards[agent_id] = {"successes": 0, "failures": 0, "violations": 0, "retries": 0}
                    
                if etype == "Success":
                    scorecards[agent_id]["successes"] += 1
                elif etype == "Failure":
                    scorecards[agent_id]["failures"] += 1
                elif etype == "Violation":
                    scorecards[agent_id]["violations"] += 1
                elif etype == "Retry":
                    scorecards[agent_id]["retries"] += 1
                    
        return scorecards
