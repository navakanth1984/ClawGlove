import json
import os
from .storage import StorageProvider

class JsonlStorageBackend(StorageProvider):
    """JSON Lines backend for persisting identity and reputation."""
    
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.profiles_path = os.path.join(data_dir, "identities.jsonl")
        self.reputation_path = os.path.join(data_dir, "reputation.jsonl")
        os.makedirs(self.data_dir, exist_ok=True)
        
    def load_profiles(self):
        profiles = {}
        if os.path.exists(self.profiles_path):
            with open(self.profiles_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        p = json.loads(line)
                        profiles[p["agent_id"]] = p
        return profiles
        
    def save_all_profiles(self, profiles_dict):
        with open(self.profiles_path, "w", encoding="utf-8") as f:
            for p in profiles_dict.values():
                f.write(json.dumps(p) + "\n")
                
    def load_reputation_history(self):
        history = {}
        if os.path.exists(self.reputation_path):
            with open(self.reputation_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        h = json.loads(line)
                        agent_id = h.pop("agent_id")
                        history[agent_id] = h
        return history
        
    def save_reputation_history(self, history_dict):
        with open(self.reputation_path, "w", encoding="utf-8") as f:
            for agent_id, data in history_dict.items():
                record = {"agent_id": agent_id}
                record.update(data)
                f.write(json.dumps(record) + "\n")
