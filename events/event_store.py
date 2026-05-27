import json
import os
import time
import gzip
import shutil
import hashlib
import threading

class EventStore:
    """Append-only durable log partitioned by tenant and domain with integrity chaining and compression."""
    def __init__(self, storage_dir, event_bus=None, max_file_size_mb=50):
        self._storage_dir = storage_dir
        self._log_path_override = None
        self._max_file_size_bytes = max_file_size_mb * 1024 * 1024
        os.makedirs(self._storage_dir, exist_ok=True)
        
        # In-memory sequences cache per (domain, tenant_id)
        self._sequences = {}
        
        if event_bus:
            event_bus.subscribe("*", self._on_event)

    def _get_partition_dir(self, domain, tenant_id):
        # For legacy default domain/tenant, return root to maintain complete backward compatibility
        if domain == "operational" and tenant_id == "system":
            return self._storage_dir
        # Enforce physical segregation for custom domains/tenants
        partition_dir = os.path.join(self._storage_dir, domain, tenant_id)
        os.makedirs(partition_dir, exist_ok=True)
        return partition_dir

    @property
    def _log_path(self):
        if hasattr(self, "_log_path_override") and self._log_path_override is not None:
            return self._log_path_override
        return self._get_log_path("operational", "system")

    @_log_path.setter
    def _log_path(self, value):
        self._log_path_override = value

    def _get_log_path(self, domain, tenant_id):
        if hasattr(self, "_log_path_override") and self._log_path_override is not None:
            return self._log_path_override
        return os.path.join(self._get_partition_dir(domain, tenant_id), "event_log.jsonl")

    def _get_sequence(self, domain, tenant_id):
        key = (domain, tenant_id)
        if key in self._sequences:
            return self._sequences[key]
            
        # Reconstruct sequence from existing log files
        seq = 0
        log_path = self._get_log_path(domain, tenant_id)
        
        # Read from active log if exists
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            try:
                                evt = json.loads(line)
                                s = evt.get("sequence", 0)
                                if s > seq:
                                    seq = s
                            except json.JSONDecodeError:
                                pass
            except Exception:
                pass
                
        self._sequences[key] = seq
        return seq

    def _increment_sequence(self, domain, tenant_id):
        key = (domain, tenant_id)
        seq = self._get_sequence(domain, tenant_id) + 1
        self._sequences[key] = seq
        return seq

    def _compress_and_hash_archive(self, raw_path, base_rotated_path, domain, tenant_id, epoch):
        """Background worker that gzips the raw rotated file and computes SHA-256 chain."""
        try:
            gz_path = base_rotated_path + ".jsonl.gz"
            
            # Compress using gzip
            with open(raw_path, 'rb') as f_in:
                with gzip.open(gz_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove raw rotated file
            os.remove(raw_path)
            
            # Compute rolling SHA-256 hash of the compressed archive
            sha256 = hashlib.sha256()
            with open(gz_path, 'rb') as f:
                while True:
                    data = f.read(65536)
                    if not data:
                        break
                    sha256.update(data)
            archive_hash = sha256.hexdigest()
            
            # Create Forensic Metadata sidecar with region residency tags and archive_epoch
            metadata = {
                "archive_name": os.path.basename(gz_path),
                "archive_hash": archive_hash,
                "archive_epoch": epoch,
                "region": "eu-west",  # Standard residency requirement
                "timestamp": int(time.time()),
                "tenant_id": tenant_id,
                "domain": domain
            }
            meta_path = base_rotated_path + ".metadata.json"
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
                
            # Persist to local partition's hash chain
            chain_path = os.path.join(self._get_partition_dir(domain, tenant_id), "hash_chain.json")
            chain = {}
            if os.path.exists(chain_path):
                try:
                    with open(chain_path, 'r', encoding='utf-8') as f:
                        chain = json.load(f)
                except Exception:
                    pass
            chain[os.path.basename(gz_path)] = archive_hash
            with open(chain_path, 'w', encoding='utf-8') as f:
                json.dump(chain, f, indent=2)
                
        except Exception as e:
            print(f"[EVENT_STORE] Rotation archiving failure: {e}")

    def _get_partition_epoch(self, domain, tenant_id):
        partition_dir = self._get_partition_dir(domain, tenant_id)
        if not os.path.exists(partition_dir):
            return 1
        # Count gzipped archives
        archives = [f for f in os.listdir(partition_dir) if f.endswith(".jsonl.gz")]
        return len(archives) + 1

    def _rotate_log_if_needed(self, domain, tenant_id):
        log_path = self._get_log_path(domain, tenant_id)
        if not os.path.exists(log_path):
            return
            
        if os.path.getsize(log_path) >= self._max_file_size_bytes:
            timestamp = int(time.time())
            partition_dir = self._get_partition_dir(domain, tenant_id)
            
            # Temp raw file to be processed in background
            temp_rotated_path = os.path.join(partition_dir, f"event_log_{timestamp}.jsonl.tmp")
            base_rotated_path = os.path.join(partition_dir, f"event_log_{timestamp}")
            
            # Rename active log to temp path
            os.rename(log_path, temp_rotated_path)
            
            # Read last hash from chain before creating a new log
            last_hash = "0" * 64
            last_file = ""
            chain_path = os.path.join(partition_dir, "hash_chain.json")
            if os.path.exists(chain_path):
                try:
                    with open(chain_path, 'r', encoding='utf-8') as f:
                        chain = json.load(f)
                        if chain:
                            # Last key is the previous file
                            last_file = list(chain.keys())[-1]
                            last_hash = chain[last_file]
                except Exception:
                    pass
            
            epoch = self._get_partition_epoch(domain, tenant_id)
            
            # Create a new active log and immediately insert the ARCHIVE_LINK chain header
            link_record = {
                "event_type": "ARCHIVE_LINK",
                "domain": domain,
                "tenant_id": tenant_id,
                "sequence": self._get_sequence(domain, tenant_id),
                "timestamp": timestamp,
                "previous_archive_hash": last_hash,
                "previous_archive_file": last_file,
                "archive_epoch": epoch
            }
            
            # Enforce stable canonical serialization
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(link_record, sort_keys=True, ensure_ascii=False) + "\n")
                
            # Spawn compression and hash chaining to a background thread to prevent IO blocking
            threading.Thread(
                target=self._compress_and_hash_archive,
                args=(temp_rotated_path, base_rotated_path, domain, tenant_id, epoch),
                daemon=True
            ).start()

    def _on_event(self, event_dict):
        # 1. Infer domain & tenant
        tenant_id = event_dict.get("tenant_id", "system")
        domain = event_dict.get("domain")
        
        if not domain:
            # Domain-awareness classification
            evt_type = event_dict.get("event_type", "")
            res_val = event_dict.get("result", "")
            if "SECURITY" in evt_type or "DENY" in res_val or "revocation" in evt_type.lower():
                domain = "security"
            elif "AUDIT" in evt_type or "POLICY" in evt_type:
                domain = "audit"
            else:
                domain = "operational"

        # Increment sequence per partition
        seq = self._increment_sequence(domain, tenant_id)
        
        record = dict(event_dict)
        record["sequence"] = seq
        record["tenant_id"] = tenant_id
        record["domain"] = domain
        
        # 2. Check and perform rotation
        self._rotate_log_if_needed(domain, tenant_id)
        
        # 3. Write event to partition log
        log_path = self._get_log_path(domain, tenant_id)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")

    def append(self, event_dict):
        """Manual append interface."""
        self._on_event(event_dict)

    def get_all_events(self, domain="operational", tenant_id="system"):
        """Retrieves all events ordered by sequence across rotated archives and the active log."""
        events = []
        corrupted_skipped = 0
        partition_dir = self._get_partition_dir(domain, tenant_id)
        
        # 1. Load rotated archives
        if os.path.exists(partition_dir):
            files = os.listdir(partition_dir)
            # Find and sort gzipped archives
            archive_files = sorted([f for f in files if f.endswith(".jsonl.gz")])
            for archive in archive_files:
                archive_path = os.path.join(partition_dir, archive)
                try:
                    with gzip.open(archive_path, 'rt', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                try:
                                    events.append(json.loads(line))
                                except json.JSONDecodeError:
                                    corrupted_skipped += 1
                except Exception:
                    corrupted_skipped += 1
        
        # 2. Load current active log
        log_path = self._get_log_path(domain, tenant_id)
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            try:
                                events.append(json.loads(line))
                            except json.JSONDecodeError:
                                corrupted_skipped += 1
            except Exception:
                pass
                
        # Sort in strict chronological order by sequence
        events.sort(key=lambda x: x.get("sequence", 0))
        self.last_corrupted_skipped = corrupted_skipped
        return events
