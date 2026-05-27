import os
import yaml
import uuid
import datetime

class PolicyRecommender:
    def __init__(self, staging_dir):
        self._staging_dir = staging_dir
        os.makedirs(self._staging_dir, exist_ok=True)

    def propose_routing_weights(self, new_weights):
        if not new_weights:
            return
            
        policy_id = f"policy_{uuid.uuid4().hex[:8]}"
        path = os.path.join(self._staging_dir, f"{policy_id}.yaml")
        data = {
            "policy_id": policy_id,
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "routing_weights": new_weights
        }
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False)
        print(f"[LEARNING] Proposed new routing policy '{policy_id}' to staging.")
        return policy_id
