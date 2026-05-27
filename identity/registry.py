import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.event_bus import EventBus, Event


class IdentityRegistry:
    """In-memory active agent profile store.

    Maintains agent profiles keyed by agent_id. Publishes AGENT_REGISTERED
    and AGENT_DEREGISTERED events to the platform Event Bus on mutations.
    """

    def __init__(self, storage_provider=None):
        self._event_bus = EventBus()
        self._storage = storage_provider
        self._profiles = {}   # agent_id -> AgentProfile dict
        
        if self._storage:
            self._profiles = self._storage.load_profiles()
            print(f"[IDENTITY] Loaded {len(self._profiles)} profiles from storage.")

    def register(self, profile):
        """Registers an agent profile. Raises ValueError if agent_id is missing."""
        agent_id = profile.get("agent_id")
        if not agent_id:
            raise ValueError("Profile missing required field: agent_id")

        self._profiles[agent_id] = profile
        if self._storage:
            self._storage.save_all_profiles(self._profiles)
        print(f"[IDENTITY] Registered agent: '{agent_id}' (role: {profile.get('role')}, "
              f"trust: {profile.get('trust_level')})")

        self._event_bus.publish(Event(
            event_type="AGENT_REGISTERED",
            correlation_id=agent_id,
            source="identity/registry",
            severity="info",
            agent_id=agent_id,
            tenant_id=profile.get("tenant_id", "default"),
            payload={
                "role": profile.get("role"),
                "trust_level": profile.get("trust_level"),
                "capabilities": list(profile.get("capabilities", {}).keys())
            }
        ))

    def deregister(self, agent_id):
        """Removes an agent profile from the registry."""
        if agent_id in self._profiles:
            del self._profiles[agent_id]
            if self._storage:
                self._storage.save_all_profiles(self._profiles)
            print(f"[IDENTITY] Deregistered agent: '{agent_id}'")

            self._event_bus.publish(Event(
                event_type="AGENT_DEREGISTERED",
                correlation_id=agent_id,
                source="identity/registry",
                severity="info",
                agent_id=agent_id,
                payload={}
            ))

    def get(self, agent_id):
        """Returns profile dict for agent_id or None if not found."""
        return self._profiles.get(agent_id)

    def list_by_role(self, role):
        """Returns all profiles matching the given role."""
        return [p for p in self._profiles.values() if p.get("role") == role]

    def list_by_capability(self, capability):
        """Returns all profiles that declare the given capability."""
        return [p for p in self._profiles.values()
                if capability in p.get("capabilities", {})]

    def all_profiles(self):
        """Returns all registered profiles as a list."""
        return list(self._profiles.values())

    def count(self):
        """Returns the number of registered agents."""
        return len(self._profiles)
