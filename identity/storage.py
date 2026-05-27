class StorageProvider:
    """Abstract interface for Identity and Reputation persistence."""
    
    def load_profiles(self):
        """Returns a dict of agent_id -> profile."""
        raise NotImplementedError
        
    def save_all_profiles(self, profiles_dict):
        """Saves all profiles to storage."""
        raise NotImplementedError
        
    def load_reputation_history(self):
        """Returns a dict of agent_id -> reputation_history."""
        raise NotImplementedError
        
    def save_reputation_history(self, history_dict):
        """Saves all reputation history to storage."""
        raise NotImplementedError
