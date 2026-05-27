import json
import os
import datetime
import uuid

class AuditLogger:
    """Immutable JSON log for ALLOW/DENY decisions."""
    def __init__(self, storage_dir):
        self._storage_dir = storage_dir
        self._log_path = os.path.join(storage_dir, "audit_log.jsonl")
        os.makedirs(self._storage_dir, exist_ok=True)

    def record(self, actor, action, resource, result):
        """result must be 'ALLOW', 'DENY', or 'ESCALATE'"""
        entry = {
            "audit_id": f"aud_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "actor": actor,
            "action": action,
            "resource": resource,
            "result": result
        }
        
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            
        print(f"[AUDIT] {result}: {actor} attempted {action} on {resource}")

    def get_records(self):
        records = []
        if os.path.exists(self._log_path):
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
        return records
