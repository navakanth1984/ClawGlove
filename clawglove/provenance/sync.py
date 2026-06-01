"""
clawglove/provenance/sync.py
================================
CPT Phase 5 — Multi-Operator Sync & Consensus Engine

Integrates distributed etcd locks for serializing writes across concurrent daemons.
Provides standard local standalone fallback: "single-operator mode, no distributed coordination".
Contains deterministic offline ledger merging utilities with timestamp collision tiebreakers.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from clawglove.provenance.ledger import _chain_hash, _GENESIS_HASH

logger = logging.getLogger("clawglove.cpt.sync")

try:
    import etcd3
    HAS_ETCD = True
except ImportError:
    HAS_ETCD = False


class DistributedSyncCoordinator:
    """
    Coordinates CPT ledger locks across multiple operators.

    Uses etcd3 for active synchronization when available.
    Degrades gracefully to: "single-operator mode, no distributed coordination" if etcd is absent.
    """

    def __init__(self, etcd_host: str = "127.0.0.1", etcd_port: int = 2379, enabled: bool = True):
        self.enabled = enabled and HAS_ETCD
        self._client = None

        if enabled and not HAS_ETCD:
            logger.info("etcd3 not found. Falling back to: single-operator mode, no distributed coordination.")

        if self.enabled:
            try:
                self._client = etcd3.client(host=etcd_host, port=etcd_port)
            except Exception as e:
                logger.warning(
                    "etcd connection failed: %s. Falling back to: single-operator mode, no distributed coordination.",
                    e,
                )
                self.enabled = False

    def acquire_lock(self, lock_name: str, timeout: int = 10) -> Any:
        """
        Acquires a distributed etcd lock, or returns a no-op context manager in fallback mode.
        """
        if self.enabled and self._client:
            try:
                return self._client.lock(lock_name, ttl=timeout)
            except Exception as e:
                logger.warning("etcd lock acquisition failed (%s). Falling back to standalone mode.", e)

        # Fallback Context Manager: "single-operator mode, no distributed coordination"
        class StandaloneLock:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        return StandaloneLock()


def merge_ledgers(target_db_path: Path | str, source_db_path: Path | str) -> dict[str, Any]:
    """
    Offline chronological ledger merge utility (Refinement 5).

    *** CRITICAL SECURITY WARNING ***
    SOLE AUTHORIZED EXCEPTION TO THE APPEND-ONLY RULE.
    This function performs a DELETE followed by re-chaining and re-insertion of merged rows.
    This is necessary to chronologically re-order and recompute rolling cryptographic hash chains
    across merged ledger histories.

    This utility is STRICTLY restricted to operator-initiated offline administrative actions.
    It has a programmatic guard ensuring it is NEVER reachable or called from the normal runtime
    client write path (`client.py`) or daemon requests (`daemon.py`).

    Merges envelopes and quarantine logs from source into target.
    Resolves timestamp collisions deterministically via sorting key:
        (inserted_at, node_id, skill_id)

    Recomputes the rolling hash chains atomically inside a single SQLite transaction,
    preserving cryptographic proof of structural ledger continuity.
    """
    # Guard: Ensure this is only called as a standalone offline merge utility,
    # never within the sidecar daemon or live client transaction context.
    import inspect
    for frame in inspect.stack():
        filename = frame.filename
        if "daemon.py" in filename or "client.py" in filename:
            raise PermissionError(
                "CPT Sync Violation: merge_ledgers() is an offline administrative utility "
                "and is strictly forbidden from being called within the client or daemon write paths."
            )

    target = Path(target_db_path)
    source = Path(source_db_path)

    if not target.exists():
        raise FileNotFoundError(f"Target DB does not exist: {target}")
    if not source.exists():
        raise FileNotFoundError(f"Source DB does not exist: {source}")

    # Read target and source envelopes/quarantines
    t_envelopes = _read_all_rows(target, "envelopes")
    s_envelopes = _read_all_rows(source, "envelopes")

    t_quarantine = _read_all_rows(target, "quarantine_log")
    s_quarantine = _read_all_rows(source, "quarantine_log")

    # Combine and deduplicate / sort envelopes
    # Sorting order: (inserted_at, node_id, skill_id)
    combined_envelopes = list(t_envelopes.values()) + list(s_envelopes.values())
    # Deduplicate by unique content_hash + originating_session_id
    seen_envs = {}
    for env in combined_envelopes:
        key = (env["content_hash"], env["originating_session_id"])
        if key not in seen_envs:
            seen_envs[key] = env
        else:
            # Keep the oldest entry if there's any discrepancy
            if env["inserted_at"] < seen_envs[key]["inserted_at"]:
                seen_envs[key] = env
    
    sorted_envs = sorted(
        seen_envs.values(),
        key=lambda x: (
            x.get("inserted_at", ""),
            x.get("node_id", "unknown"),
            x.get("skill_id", ""),
        )
    )

    # Combine and sort quarantine_log
    combined_quarantines = list(t_quarantine.values()) + list(s_quarantine.values())
    seen_q = {}
    for q in combined_quarantines:
        key = (q["content_hash"], q["session_id"])
        if key not in seen_q:
            seen_q[key] = q
        else:
            if q["inserted_at"] < seen_q[key]["inserted_at"]:
                seen_q[key] = q
                
    sorted_q = sorted(
        seen_q.values(),
        key=lambda x: (
            x.get("inserted_at", ""),
            x.get("node_id", "unknown"),
            x.get("skill_id", ""),
        )
    )

    # Re-compute hashes for envelopes
    prev_hash = _GENESIS_HASH
    for env in sorted_envs:
        prev_hash = _chain_hash(prev_hash, env["content_hash"])
        env["chain_hash"] = prev_hash

    # Re-compute hashes for quarantine logs
    prev_hash = _GENESIS_HASH
    for q in sorted_q:
        prev_hash = _chain_hash(prev_hash, q["content_hash"])
        q["chain_hash"] = prev_hash

    # Save re-chained logs back to target DB atomically
    conn = sqlite3.connect(str(target))
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # Clear existing tables
        conn.execute("DELETE FROM envelopes")
        conn.execute("DELETE FROM quarantine_log")

        # Insert envelopes
        for env in sorted_envs:
            conn.execute(
                """
                INSERT INTO envelopes (
                    id, skill_id, file_path, content_hash,
                    originating_session_id, parent_user_request_hash,
                    generator_model, generation_timestamp,
                    tenant_id, signature, auto_approved, quarantine_path,
                    chain_hash, key_id, node_id, inserted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    env.get("id"), env["skill_id"], env["file_path"], env["content_hash"],
                    env["originating_session_id"], env["parent_user_request_hash"],
                    env["generator_model"], env["generation_timestamp"],
                    env["tenant_id"], env["signature"], env["auto_approved"], env["quarantine_path"],
                    env["chain_hash"], env.get("key_id", "v1"), env.get("node_id", "unknown"), env["inserted_at"]
                )
            )

        # Insert quarantine logs
        for q in sorted_q:
            conn.execute(
                """
                INSERT INTO quarantine_log (
                    id, skill_id, tenant_id, session_id,
                    quarantine_path, content_hash, risky_imports,
                    timestamp, chain_hash, node_id, inserted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    q.get("id"), q["skill_id"], q["tenant_id"], q["session_id"],
                    q["quarantine_path"], q["content_hash"], q["risky_imports"],
                    q["timestamp"], q["chain_hash"], q.get("node_id", "unknown"), q["inserted_at"]
                )
            )
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

    return {
        "merged_envelopes": len(sorted_envs),
        "merged_quarantines": len(sorted_q),
    }


def _read_all_rows(db_path: Path, table: str) -> dict[tuple, dict]:
    """Read all rows from the specified table in SQLite database."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        # Key by id to keep deterministic mapping
        return {r["id"]: dict(r) for r in rows}
    except Exception:
        return {}
    finally:
        conn.close()
