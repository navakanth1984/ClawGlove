import json
import os

class CheckpointManager:
    """Manages transactional state captures, freezes, and rollbacks."""
    def __init__(self, checkpoint_dir=None):
        self.checkpoint_dir = checkpoint_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "checkpoints"
        )
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)
        self.checkpoints = {}

    def save_checkpoint(self, checkpoint_id, state_data):
        """Captures a serializable snapshot of active execution states."""
        file_path = os.path.join(self.checkpoint_dir, f"chk_{checkpoint_id}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2)
            self.checkpoints[checkpoint_id] = file_path
            print(f"[CHECKPOINT] Captured transaction state snapshot: 'chk_{checkpoint_id}'")
            return True
        except Exception as e:
            print(f"[CHECKPOINT] Error writing snapshot '{checkpoint_id}': {e}")
            return False

    def load_checkpoint(self, checkpoint_id):
        """Fetches pre-execution checkpoint states."""
        file_path = self.checkpoints.get(checkpoint_id) or os.path.join(
            self.checkpoint_dir, f"chk_{checkpoint_id}.json"
        )
        if not os.path.exists(file_path):
            print(f"[CHECKPOINT] Target snapshot not found at path: {file_path}")
            return None
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                state_data = json.load(f)
            print(f"[CHECKPOINT] Read state snapshot 'chk_{checkpoint_id}' successfully.")
            return state_data
        except Exception as e:
            print(f"[CHECKPOINT] Error loading snapshot '{checkpoint_id}': {e}")
            return None

    def rollback_state(self, active_state, target_checkpoint_id):
        """Reverts the active state back to a designated target checkpoint."""
        print(f"[CHECKPOINT] Initiating platform state rollback sequence -> 'chk_{target_checkpoint_id}'")
        target_data = self.load_checkpoint(target_checkpoint_id)
        if target_data:
            active_state.clear()
            active_state.update(target_data)
            print(f"[CHECKPOINT] Rollback to 'chk_{target_checkpoint_id}' successful. State restored.")
            return True
        else:
            print(f"[CHECKPOINT] Rollback halted. Reversion state unavailable.")
            return False
