"""
clawglove/provenance/rotate.py
================================
CPT Phase 5 — CLI Administrative Key Rotation Engine

Triggers key rotation securely on the local operator shell, eliminating
network-based secret transmission.

Usage:
    python -m clawglove.provenance.rotate --workspace ./ --new-secret <hex>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from clawglove.provenance.client import _load_or_bootstrap_keyring
from clawglove.provenance.ledger import ProvenanceLedger


def rotate_key(workspace_root: Path, new_secret_hex: str | None = None) -> dict[str, Any]:
    """
    Appends a new secure key to the keyring (.clawglove_secrets) and sets it active.
    Returns status dict on success.
    """
    if not workspace_root.exists():
        raise FileNotFoundError(f"Workspace path does not exist: {workspace_root}")

    # 1. Load existing keyring
    keyring = _load_or_bootstrap_keyring(workspace_root)
    old_active_id = keyring.get("active_key_id")

    # 2. Determine/Generate new key
    if new_secret_hex:
        new_secret_hex = new_secret_hex.strip()
        try:
            bytes.fromhex(new_secret_hex)
        except ValueError:
            raise ValueError("The provided new secret is not a valid hex string.")
        if len(new_secret_hex) < 64:
            raise ValueError("The secret must be at least a 256-bit hex string (64 characters).")
    else:
        new_secret_hex = os.urandom(32).hex()

    new_key_id = hashlib.sha256(bytes.fromhex(new_secret_hex)).hexdigest()[:16]

    if new_key_id in keyring["keys"]:
        raise ValueError(f"Key version '{new_key_id}' already exists in the keyring.")

    # 3. Add to keyring and activate
    keyring["keys"][new_key_id] = new_secret_hex
    keyring["active_key_id"] = new_key_id

    # 4. Save updated keyring securely
    secrets_file = workspace_root / ".clawglove_secrets"
    secrets_file.write_text(json.dumps(keyring, indent=2), encoding="utf-8")

    # Also keep singular .clawglove_secret active for legacy systems compatibility
    secret_file = workspace_root / ".clawglove_secret"
    try:
        secret_file.write_text(new_secret_hex, encoding="utf-8")
    except Exception:
        pass

    # 5. Run standard ledger validation checks to ensure zero integrity regressions
    db_path = workspace_root / "provenance_ledger.db"
    ledger = ProvenanceLedger(db_path)
    try:
        verify_res = ledger.verify_all_chains()
    finally:
        ledger.close()

    return {
        "status": "SUCCESS",
        "old_key_id": old_active_id,
        "new_key_id": new_key_id,
        "key_count": len(keyring["keys"]),
        "ledger_verified": verify_res,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CPT Phase 5 — CLI Administrative Key Rotation Engine"
    )
    parser.add_argument(
        "--workspace",
        required=True,
        help="Absolute or relative path to the workspace root directory.",
    )
    parser.add_argument(
        "--new-secret",
        default=None,
        help="Optional hex-encoded 256-bit signing key. If omitted, a cryptographically secure key is generated automatically.",
    )

    args = parser.parse_args()

    try:
        res = rotate_key(Path(args.workspace), args.new_secret)
        print("=" * 60)
        print("CLAWGLOVE CPT KEY ROTATION COMPLETE")
        print("=" * 60)
        print(f"Status:            {res['status']}")
        print(f"Old Key version:   {res['old_key_id']}")
        print(f"New Key version:   {res['new_key_id']}")
        print(f"Keyring Capacity:  {res['key_count']} keys registered")
        print(f"Ledger Verification Check:")
        print(f"  - Envelopes Table:      {res['ledger_verified']['envelopes']['verified_rows']} rows verified")
        print(f"  - Quarantine Table:     {res['ledger_verified']['quarantine_log']['verified_rows']} rows verified")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"CRITICAL ERROR: Key rotation failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
