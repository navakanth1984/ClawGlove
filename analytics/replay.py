import os
import json
import time
import uuid
import hashlib

class ReplaySchemaMismatch(Exception):
    """Raised when snapshot schema version does not match engine's supported schema version."""
    pass

class MockEvent:
    """Helper to wrap dict back into an object expected by state manager."""
    def __init__(self, d):
        self.event_type = d.get("event_type")
        self.correlation_id = d.get("correlation_id")
        self.source = d.get("source")
        self.payload = d.get("payload", {})
        self.timestamp = d.get("timestamp")
        self.agent_id = d.get("agent_id")
        self.tenant_id = d.get("tenant_id")
        self.trace_id = d.get("trace_id")

class ReplayEngine:
    """Domain-aware engine enabling time-travel debugging and O(delta) state hydration."""
    SUPPORTED_SCHEMA_VERSION = "1.0"

    def __init__(self, event_store, domain="operational", authz_engine=None):
        self._event_store = event_store
        self.domain = domain
        self._authz_engine = authz_engine
        self.last_validation_envelope = None

    def export_snapshot(self, state_manager, tenant_id, last_sequence):
        """Saves physical isolated tenant state snapshot to disk."""
        snapshot_dir = os.path.join(self._event_store._storage_dir, "snapshots", tenant_id)
        os.makedirs(snapshot_dir, exist_ok=True)
        
        timestamp = int(time.time())
        snapshot_path = os.path.join(snapshot_dir, f"snapshot_{timestamp}.json")
        
        # Capture state dict
        state_data = getattr(state_manager, "state", getattr(state_manager, "__dict__", {}))
        
        snapshot = {
            "tenant_id": tenant_id,
            "domain": self.domain,
            "last_sequence": last_sequence,
            "state": state_data,
            "timestamp": timestamp,
            "schema_version": self.SUPPORTED_SCHEMA_VERSION
        }
        
        temp_path = snapshot_path + ".tmp"
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, snapshot_path)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e
            
        return f"snapshot_{timestamp}"

    def load_snapshot(self, state_manager, tenant_id):
        """Loads and hydrates latest snapshot for the tenant."""
        snapshot_dir = os.path.join(self._event_store._storage_dir, "snapshots", tenant_id)
        if not os.path.exists(snapshot_dir):
            return None
            
        snapshots = sorted([f for f in os.listdir(snapshot_dir) if f.endswith(".json")])
        if not snapshots:
            return None
            
        latest = os.path.join(snapshot_dir, snapshots[-1])
        try:
            with open(latest, 'r', encoding='utf-8') as f:
                snap = json.load(f)
                
            # Strict schema validation: raise mismatch exception
            snap_schema = snap.get("schema_version", "1.0")
            if snap_schema != self.SUPPORTED_SCHEMA_VERSION:
                raise ReplaySchemaMismatch(
                    f"Snapshot schema version '{snap_schema}' does not match "
                    f"supported version '{self.SUPPORTED_SCHEMA_VERSION}'"
                )
                
            # Hydrate the state manager
            state = snap.get("state", {})
            if hasattr(state_manager, "state") and isinstance(state_manager.state, dict):
                state_manager.state.update(state)
            else:
                state_manager.__dict__.update(state)
                
            return snap
        except ReplaySchemaMismatch:
            # Let schema mismatch propagate up
            raise
        except Exception as e:
            print(f"[REPLAY] Failed to load snapshot {latest}: {e}")
            return None

    def replay_events(self, state_manager, tenant_id="system", identity=None, up_to_sequence=None, trigger_snapshot_every_n=None):
        """Reconstructs state by feeding events back into state manager, utilizing snapshots and O(delta) complexity."""
        # 1. Authorization and boundary checks
        if self._authz_engine and identity:
            allowed = self._authz_engine.check_permission(identity, "ReplayTenantHistory")
            cross_allowed = self._authz_engine.check_cross_tenant_access(identity, tenant_id)
            if not allowed or not cross_allowed:
                print(f"[REPLAY] ACCESS DENIED: Identity lacks ReplayTenantHistory or cross-tenant clearance.")
                return 0

        # 2. O(delta) Replay Optimization: Load latest snapshot anchor
        last_sequence = 0
        snapshot_anchor = "none"
        snapshot = self.load_snapshot(state_manager, tenant_id)
        if snapshot:
            last_sequence = snapshot.get("last_sequence", 0)
            snapshot_anchor = f"snapshot_{snapshot.get('timestamp')}"
            print(f"[REPLAY] Hydrated state from snapshot anchor '{snapshot_anchor}' (Up to sequence: {last_sequence})")

        # 3. Retrieve all events
        all_events = self._event_store.get_all_events(domain=self.domain, tenant_id=tenant_id)
        
        events_scanned = len(all_events)
        replayed = 0
        corrupted_skipped = getattr(self._event_store, "last_corrupted_skipped", 0)
        
        # 4. Replay O(delta) events
        for evt_record in all_events:
            seq = evt_record.get("sequence", 0)
            
            # Skip historical events loaded from snapshot
            if seq <= last_sequence:
                continue
                
            # Gated ceiling
            if up_to_sequence and seq > up_to_sequence:
                break
                
            e = MockEvent(evt_record)
            state_manager.intercept(e)
            replayed += 1
            
            # Hybrid Snapshot Anchor trigger (Incremental N events limit)
            if trigger_snapshot_every_n and replayed % trigger_snapshot_every_n == 0:
                snap_name = self.export_snapshot(state_manager, tenant_id, seq)
                snapshot_anchor = snap_name

        # 5. Cryptographic chain verification
        chain_verified = True
        partition_dir = self._event_store._get_partition_dir(self.domain, tenant_id)
        chain_path = os.path.join(partition_dir, "hash_chain.json")
        if os.path.exists(chain_path):
            try:
                with open(chain_path, 'r', encoding='utf-8') as f:
                    chain = json.load(f)
                for archive_name, recorded_hash in chain.items():
                    archive_path = os.path.join(partition_dir, archive_name)
                    if os.path.exists(archive_path):
                        sha256 = hashlib.sha256()
                        with open(archive_path, 'rb') as f:
                            while True:
                                data = f.read(65536)
                                if not data:
                                    break
                                sha256.update(data)
                        real_hash = sha256.hexdigest()
                        if real_hash != recorded_hash:
                            chain_verified = False
                            break
            except Exception:
                chain_verified = False

        # Emit Replay Validation Envelope
        self.last_validation_envelope = {
            "replay_id": f"rep_{uuid.uuid4().hex[:8]}",
            "events_scanned": events_scanned,
            "events_restored": replayed,
            "corrupted_skipped": corrupted_skipped,
            "archive_chain_verified": chain_verified,
            "snapshot_anchor": snapshot_anchor,
            "timestamp": int(time.time())
        }
        
        print("\n--- REPLAY VALIDATION ENVELOPE ---")
        print(json.dumps(self.last_validation_envelope, indent=2))
        print("----------------------------------\n")
        
        return replayed
