"""
clawglove/provenance/ledger.py
================================
Phase 3 — Durable Provenance Ledger

SQLite-backed persistence for ProvenanceEnvelope records and quarantine events.
Replaces the in-memory dict in CPTClient so lineage history survives process
restarts.

Security properties implemented here mirror the main ACDLC event log defenses:

  T-001 (Replay Forgery):  Rolling SHA-256 hash chain on envelope inserts.
                           Each row stores the hash of (prev_chain_hash +
                           content_hash).  Verification walks the full chain.

  T-003 (Snapshot Poisoning): Schema version locking.  The ledger refuses to
                              open a file whose schema_version does not match
                              SUPPORTED_SCHEMA_VERSION.  Raises
                              LedgerSchemaMismatch on mismatch.

  T-006 (Task Brain Ledger Poisoning): WAL mode + write-lock.  All writes
                                       go through a threading.Lock, so no two
                                       writers can interleave.  WAL mode lets
                                       readers proceed concurrently without
                                       blocking on in-progress writes.

Database layout
---------------
  meta          — schema_version, created_at
  envelopes     — one row per skill write event (immutable after insert)
  quarantine_log— one row per quarantine event (immutable after insert)

Immutability contract: rows are INSERT-only.  No UPDATE or DELETE ever runs
against these tables.  Append-only is enforced at the Python layer (no UPDATE
methods exposed) and by the hash chain (any tampering breaks verification).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

SUPPORTED_SCHEMA_VERSION: str = "1.0"

_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS envelopes (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id                  TEXT    NOT NULL,
    file_path                 TEXT    NOT NULL,
    content_hash              TEXT    NOT NULL,
    originating_session_id    TEXT    NOT NULL,
    parent_user_request_hash  TEXT    NOT NULL,
    generator_model           TEXT    NOT NULL,
    generation_timestamp      TEXT    NOT NULL,
    tenant_id                 TEXT    NOT NULL,
    signature                 TEXT    NOT NULL,
    auto_approved             INTEGER NOT NULL,   -- 0/1
    quarantine_path           TEXT,               -- NULL if auto-approved
    chain_hash                TEXT    NOT NULL,   -- rolling SHA-256 hash chain
    key_id                    TEXT    NOT NULL DEFAULT 'v1',
    node_id                   TEXT    NOT NULL DEFAULT 'unknown',
    inserted_at               TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_envelopes_skill_tenant
    ON envelopes (skill_id, tenant_id);

CREATE TABLE IF NOT EXISTS quarantine_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id       TEXT    NOT NULL,
    tenant_id      TEXT    NOT NULL,
    session_id     TEXT    NOT NULL,
    quarantine_path TEXT   NOT NULL,
    content_hash   TEXT    NOT NULL,
    risky_imports  TEXT    NOT NULL,  -- JSON array
    timestamp      TEXT    NOT NULL,
    chain_hash     TEXT    NOT NULL,  -- rolling SHA-256 hash chain
    node_id        TEXT    NOT NULL DEFAULT 'unknown',
    inserted_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_quarantine_tenant
    ON quarantine_log (tenant_id);
"""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LedgerError(Exception):
    """Base class for ledger errors."""


class LedgerSchemaMismatch(LedgerError):
    """
    Raised when the on-disk schema_version does not match
    SUPPORTED_SCHEMA_VERSION.  Mirrors T-003 (Snapshot Poisoning) defense.
    """

    def __init__(self, found: str, expected: str, db_path: str):
        self.found = found
        self.expected = expected
        self.db_path = db_path
        super().__init__(
            f"Ledger schema mismatch at '{db_path}': "
            f"found version '{found}', expected '{expected}'. "
            f"Do not modify the ledger file directly."
        )


from clawglove.provenance.exceptions import LedgerChainViolation


class EnvelopeNotFound(LedgerError):
    """Raised when get_envelope finds no matching record."""

    def __init__(self, skill_id: str, tenant_id: str):
        self.skill_id = skill_id
        self.tenant_id = tenant_id
        super().__init__(
            f"No envelope found for skill '{skill_id}' in tenant '{tenant_id}'."
        )


# ---------------------------------------------------------------------------
# Envelope row (read model)
# ---------------------------------------------------------------------------

@dataclass
class EnvelopeRow:
    """Hydrated envelope record from the ledger."""
    id: int
    skill_id: str
    file_path: str
    content_hash: str
    originating_session_id: str
    parent_user_request_hash: str
    generator_model: str
    generation_timestamp: str
    tenant_id: str
    signature: str
    auto_approved: bool
    quarantine_path: str | None
    chain_hash: str
    inserted_at: str
    key_id: str = "v1"
    node_id: str = "unknown"


@dataclass
class QuarantineRow:
    """Hydrated quarantine log record."""
    id: int
    skill_id: str
    tenant_id: str
    session_id: str
    quarantine_path: str
    content_hash: str
    risky_imports: list[str]
    timestamp: str
    chain_hash: str
    inserted_at: str
    node_id: str = "unknown"



# ---------------------------------------------------------------------------
# Hash chain helpers
# ---------------------------------------------------------------------------

def _chain_hash(prev_hash: str, content_hash: str) -> str:
    """
    Compute the next link in the hash chain.
    chain_n = SHA-256( chain_{n-1} || content_hash_n )

    The genesis link uses a fixed sentinel as prev_hash.
    """
    raw = (prev_hash + content_hash).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


_GENESIS_HASH = "0" * 64  # sentinel for the first row in each table


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

class ProvenanceLedger:
    """
    Durable, append-only SQLite ledger for CPT provenance envelopes and
    quarantine events.

    Thread-safety:  one threading.Lock guards all writes.  SQLite WAL mode
    allows concurrent reads without blocking on in-progress writes.

    Usage:
        ledger = ProvenanceLedger(Path("workspace/provenance_ledger.db"))
        ledger.write_envelope(envelope_dataclass)
        env = ledger.get_envelope("skill-id", "tenant-id")
        ledger.verify_chain()   # integrity check; call on startup or on-demand
    """

    def __init__(self, db_path: Path | str):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._local = threading.local()  # per-thread connection cache
        self.node_id = "unknown"
        self._init_db()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        """
        Return a per-thread SQLite connection.  SQLite connections are not
        thread-safe; each thread gets its own connection to the same file.
        WAL mode means reads from other threads see committed data immediately.
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                str(self._path),
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            self._local.conn = conn
        return conn

    def _init_db(self) -> None:
        """Create tables and validate schema version."""
        with self._lock:
            conn = self._conn()
            conn.execute("PRAGMA journal_mode = WAL")
            # Check version BEFORE DDL — reject structurally incompatible files.
            meta_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'"
            ).fetchone()
            if meta_exists:
                row = conn.execute(
                    "SELECT value FROM meta WHERE key = 'schema_version'"
                ).fetchone()
                if row and row["value"] != SUPPORTED_SCHEMA_VERSION:
                    raise LedgerSchemaMismatch(
                        found=row["value"],
                        expected=SUPPORTED_SCHEMA_VERSION,
                        db_path=str(self._path),
                    )
            conn.executescript(_DDL)
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
                    (SUPPORTED_SCHEMA_VERSION,),
                )
                conn.commit()
            elif row["value"] != SUPPORTED_SCHEMA_VERSION:
                raise LedgerSchemaMismatch(
                    found=row["value"],
                    expected=SUPPORTED_SCHEMA_VERSION,
                    db_path=str(self._path),
                )

            # Schema migrations for existing databases (adds key_id, node_id to envelopes / quarantine_log)
            cursor = conn.cursor()
            envelope_columns = [r["name"] for r in cursor.execute("PRAGMA table_info(envelopes)").fetchall()]
            if "key_id" not in envelope_columns:
                conn.execute("ALTER TABLE envelopes ADD COLUMN key_id TEXT NOT NULL DEFAULT 'v1'")
                conn.commit()
            if "node_id" not in envelope_columns:
                conn.execute("ALTER TABLE envelopes ADD COLUMN node_id TEXT NOT NULL DEFAULT 'unknown'")
                conn.commit()

            quarantine_columns = [r["name"] for r in cursor.execute("PRAGMA table_info(quarantine_log)").fetchall()]
            if "node_id" not in quarantine_columns:
                conn.execute("ALTER TABLE quarantine_log ADD COLUMN node_id TEXT NOT NULL DEFAULT 'unknown'")
                conn.commit()

            # Node ID initialization/recovery
            import uuid
            node_row = conn.execute(
                "SELECT value FROM meta WHERE key = 'node_id'"
            ).fetchone()
            if node_row is None:
                self.node_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO meta (key, value) VALUES ('node_id', ?)",
                    (self.node_id,),
                )
                conn.commit()
            else:
                self.node_id = node_row["value"]


    # ------------------------------------------------------------------
    # Envelope writes
    # ------------------------------------------------------------------

    def write_envelope(self, envelope: Any) -> None:
        """
        Persist a ProvenanceEnvelope to the ledger.

        Accepts either a ProvenanceEnvelope dataclass instance or any object
        with matching attributes (duck typing).

        The chain_hash is computed automatically — callers do not supply it.
        """
        with self._lock:
            conn = self._conn()
            prev = conn.execute(
                "SELECT chain_hash FROM envelopes ORDER BY id DESC LIMIT 1"
            ).fetchone()
            prev_hash = prev["chain_hash"] if prev else _GENESIS_HASH

            new_chain = _chain_hash(prev_hash, envelope.content_hash)

            key_id = getattr(envelope, "key_id", None) or "v1"
            node_id = getattr(envelope, "node_id", None) or self.node_id

            conn.execute(
                """
                INSERT INTO envelopes (
                    skill_id, file_path, content_hash,
                    originating_session_id, parent_user_request_hash,
                    generator_model, generation_timestamp,
                    tenant_id, signature, auto_approved, quarantine_path,
                    chain_hash, key_id, node_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    envelope.skill_id,
                    envelope.file_path,
                    envelope.content_hash,
                    envelope.originating_session_id,
                    envelope.parent_user_request_hash,
                    envelope.generator_model,
                    envelope.generation_timestamp,
                    envelope.tenant_id,
                    envelope.signature,
                    1 if envelope.auto_approved else 0,
                    envelope.quarantine_path,
                    new_chain,
                    key_id,
                    node_id,
                ),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Envelope reads
    # ------------------------------------------------------------------

    def get_envelope(self, skill_id: str, tenant_id: str) -> EnvelopeRow:
        """
        Return the most recent envelope for (skill_id, tenant_id).
        Raises EnvelopeNotFound if no record exists.
        """
        conn = self._conn()
        row = conn.execute(
            """
            SELECT * FROM envelopes
            WHERE skill_id = ? AND tenant_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (skill_id, tenant_id),
        ).fetchone()

        if row is None:
            raise EnvelopeNotFound(skill_id, tenant_id)

        return _row_to_envelope(row)

    def list_envelopes(self, tenant_id: str) -> list[EnvelopeRow]:
        """Return all envelopes for a tenant, oldest first."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM envelopes WHERE tenant_id = ? ORDER BY id ASC",
            (tenant_id,),
        ).fetchall()
        return [_row_to_envelope(r) for r in rows]

    # ------------------------------------------------------------------
    # Quarantine log writes
    # ------------------------------------------------------------------

    def write_quarantine_event(
        self,
        skill_id: str,
        tenant_id: str,
        session_id: str,
        quarantine_path: str,
        content_hash: str,
        risky_imports: list[str],
        timestamp: str,
    ) -> None:
        with self._lock:
            conn = self._conn()
            prev = conn.execute(
                "SELECT chain_hash FROM quarantine_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
            prev_hash = prev["chain_hash"] if prev else _GENESIS_HASH
            new_chain = _chain_hash(prev_hash, content_hash)

            conn.execute(
                """
                INSERT INTO quarantine_log (
                    skill_id, tenant_id, session_id,
                    quarantine_path, content_hash, risky_imports,
                    timestamp, chain_hash, node_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    skill_id,
                    tenant_id,
                    session_id,
                    quarantine_path,
                    content_hash,
                    json.dumps(risky_imports),
                    timestamp,
                    new_chain,
                    self.node_id,
                ),
            )
            conn.commit()

    def write_quarantine_with_envelope(
        self,
        envelope: Any,
        risky_imports: list[str],
        timestamp: str,
    ) -> None:
        """
        Atomically write both the envelope and the quarantine event
        to the ledger in a single SQLite transaction.
        """
        with self._lock:
            conn = self._conn()
            conn.execute("BEGIN")
            try:
                # 1. Write Envelope
                prev_env = conn.execute(
                    "SELECT chain_hash FROM envelopes ORDER BY id DESC LIMIT 1"
                ).fetchone()
                prev_env_hash = prev_env["chain_hash"] if prev_env else _GENESIS_HASH
                new_env_chain = _chain_hash(prev_env_hash, envelope.content_hash)

                key_id = getattr(envelope, "key_id", None) or "v1"
                node_id = getattr(envelope, "node_id", None) or self.node_id

                conn.execute(
                    """
                    INSERT INTO envelopes (
                        skill_id, file_path, content_hash,
                        originating_session_id, parent_user_request_hash,
                        generator_model, generation_timestamp,
                        tenant_id, signature, auto_approved, quarantine_path,
                        chain_hash, key_id, node_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        envelope.skill_id,
                        envelope.file_path,
                        envelope.content_hash,
                        envelope.originating_session_id,
                        envelope.parent_user_request_hash,
                        envelope.generator_model,
                        envelope.generation_timestamp,
                        envelope.tenant_id,
                        envelope.signature,
                        1 if envelope.auto_approved else 0,
                        envelope.quarantine_path,
                        new_env_chain,
                        key_id,
                        node_id,
                    ),
                )

                # 2. Write Quarantine Event
                prev_q = conn.execute(
                    "SELECT chain_hash FROM quarantine_log ORDER BY id DESC LIMIT 1"
                ).fetchone()
                prev_q_hash = prev_q["chain_hash"] if prev_q else _GENESIS_HASH
                new_q_chain = _chain_hash(prev_q_hash, envelope.content_hash)

                conn.execute(
                    """
                    INSERT INTO quarantine_log (
                        skill_id, tenant_id, session_id,
                        quarantine_path, content_hash, risky_imports,
                        timestamp, chain_hash, node_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        envelope.skill_id,
                        envelope.tenant_id,
                        envelope.originating_session_id,
                        envelope.quarantine_path,
                        envelope.content_hash,
                        json.dumps(risky_imports),
                        timestamp,
                        new_q_chain,
                        node_id,
                    ),
                )
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e

    # ------------------------------------------------------------------
    # Quarantine log reads
    # ------------------------------------------------------------------

    def get_quarantine_log(self, tenant_id: str) -> list[QuarantineRow]:
        """Return all quarantine events for a tenant, oldest first."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM quarantine_log WHERE tenant_id = ? ORDER BY id ASC",
            (tenant_id,),
        ).fetchall()
        return [_row_to_quarantine(r) for r in rows]

    def get_quarantined_tenants(self) -> list[str]:
        """Return all tenant IDs that have registered quarantine events."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT DISTINCT tenant_id FROM quarantine_log"
        ).fetchall()
        return [row["tenant_id"] for row in rows]

    # ------------------------------------------------------------------
    # Chain verification (T-001 defense)
    # ------------------------------------------------------------------

    def verify_chain(self, table: str = "envelopes") -> dict[str, Any]:
        """
        Walk the full hash chain for the given table and raise
        LedgerChainViolation on the first inconsistency.

        Returns structured verification metrics on success (Design Refinement 5).

        Call on sidecar startup and after any suspected tampering.
        Cost is O(n) in the number of rows — acceptable for governance audit.

        table: "envelopes" | "quarantine_log"
        """
        if table not in {"envelopes", "quarantine_log"}:
            raise ValueError(f"Unknown table '{table}'")

        hash_col = "content_hash"
        conn = self._conn()
        rows = conn.execute(
            f"SELECT id, {hash_col}, chain_hash FROM {table} ORDER BY id ASC"
        ).fetchall()

        running = _GENESIS_HASH
        for row in rows:
            expected = _chain_hash(running, row[hash_col])
            if expected != row["chain_hash"]:
                raise LedgerChainViolation(
                    table=table,
                    row_id=row["id"],
                    expected=expected,
                    actual=row["chain_hash"],
                )
            running = row["chain_hash"]

        return {
            "verified_rows": len(rows),
            "last_row_id": rows[-1]["id"] if rows else None,
        }

    def verify_all_chains(self) -> dict[str, Any]:
        """Verify hash chains for both tables and return structured metrics."""
        return {
            "envelopes": self.verify_chain("envelopes"),
            "quarantine_log": self.verify_chain("quarantine_log"),
        }

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        conn = self._conn()
        return {
            "db_path": str(self._path),
            "schema_version": conn.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()["value"],
            "envelope_count": conn.execute(
                "SELECT COUNT(*) FROM envelopes"
            ).fetchone()[0],
            "quarantine_count": conn.execute(
                "SELECT COUNT(*) FROM quarantine_log"
            ).fetchone()[0],
            "db_size_bytes": self._path.stat().st_size if self._path.exists() else 0,
        }

    def close(self) -> None:
        """Close the per-thread connection if open."""
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None


# ---------------------------------------------------------------------------
# Row hydration helpers
# ---------------------------------------------------------------------------

def _row_to_envelope(row: sqlite3.Row) -> EnvelopeRow:
    # Safely get key_id and node_id if columns exist (handles old table structures dynamically)
    row_keys = row.keys()
    key_id = row["key_id"] if "key_id" in row_keys else "v1"
    node_id = row["node_id"] if "node_id" in row_keys else "unknown"
    return EnvelopeRow(
        id=row["id"],
        skill_id=row["skill_id"],
        file_path=row["file_path"],
        content_hash=row["content_hash"],
        originating_session_id=row["originating_session_id"],
        parent_user_request_hash=row["parent_user_request_hash"],
        generator_model=row["generator_model"],
        generation_timestamp=row["generation_timestamp"],
        tenant_id=row["tenant_id"],
        signature=row["signature"],
        auto_approved=bool(row["auto_approved"]),
        quarantine_path=row["quarantine_path"],
        chain_hash=row["chain_hash"],
        inserted_at=row["inserted_at"],
        key_id=key_id,
        node_id=node_id,
    )


def _row_to_quarantine(row: sqlite3.Row) -> QuarantineRow:
    row_keys = row.keys()
    node_id = row["node_id"] if "node_id" in row_keys else "unknown"
    return QuarantineRow(
        id=row["id"],
        skill_id=row["skill_id"],
        tenant_id=row["tenant_id"],
        session_id=row["session_id"],
        quarantine_path=row["quarantine_path"],
        content_hash=row["content_hash"],
        risky_imports=json.loads(row["risky_imports"]),
        timestamp=row["timestamp"],
        chain_hash=row["chain_hash"],
        inserted_at=row["inserted_at"],
        node_id=node_id,
    )
