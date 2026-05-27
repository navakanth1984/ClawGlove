import json
import os

class TermStore:
    """Persists current election term to prevent split-brain rollbacks."""
    def __init__(self, storage_dir):
        self._path = os.path.join(storage_dir, "term_state.json")
        os.makedirs(storage_dir, exist_ok=True)
        self._term = self._load()

    def _load(self):
        if os.path.exists(self._path):
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f).get("current_term", 0)
        return 0

    def increment_term(self):
        self._term += 1
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump({"current_term": self._term}, f)
        return self._term

    def get_term(self):
        return self._term
