import os
import yaml
import shutil
import datetime

class PolicyPromoter:
    """Manages the governance lifecycle of policies from staging to production."""
    def __init__(self, base_dir):
        self.staging_dir = os.path.join(base_dir, "staging")
        self.approved_dir = os.path.join(base_dir, "approved")
        self.production_dir = os.path.join(base_dir, "production")
        
        for d in [self.staging_dir, self.approved_dir, self.production_dir]:
            os.makedirs(d, exist_ok=True)

    def validate_and_approve(self, policy_id, approved_by):
        """Moves a policy from staging to approved."""
        src = os.path.join(self.staging_dir, f"{policy_id}.yaml")
        dst = os.path.join(self.approved_dir, f"{policy_id}.yaml")
        
        if not os.path.exists(src):
            print(f"[PROMOTER] Policy {policy_id} not found in staging.")
            return False
            
        # Write promotion manifest
        manifest_path = os.path.join(self.approved_dir, f"{policy_id}_manifest.yaml")
        manifest = {
            "policy_id": policy_id,
            "approved_by": approved_by,
            "validation_status": "APPROVED",
            "created_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            yaml.dump(manifest, f, default_flow_style=False)
            
        shutil.move(src, dst)
        print(f"[PROMOTER] Policy {policy_id} approved by {approved_by}.")
        return True

    def promote_to_production(self, policy_id, target_filename="routing-weights.yaml"):
        """Promotes an approved policy to active production use."""
        src = os.path.join(self.approved_dir, f"{policy_id}.yaml")
        dst = os.path.join(self.production_dir, target_filename)
        
        if not os.path.exists(src):
            print(f"[PROMOTER] Policy {policy_id} not found in approved dir.")
            return False
            
        shutil.copy(src, dst)
        print(f"[PROMOTER] Policy {policy_id} promoted to production as {target_filename}.")
        return True
