"""
ClawGlove Isolated Eval Orchestrator (UNLOCKED wrapper)
========================================================
This file orchestrates the empirical evaluation WITHOUT modifying the locked
oracle (tests/eval/run_empirical_eval.py). It imports the test cases and the
certification thresholds from the locked harness, then runs them with one
addition the locked file deliberately does not contain: a quarantine reset
between each violation test.

Why this exists (CG-02):
  The locked harness runs all 25 violations sequentially against one tenant.
  After 6 violations the tenant enters QUARANTINE, so violations 7-25 are
  "caught" by quarantine block rather than by their actual policy rule. That
  inflates M_detection — it stops measuring per-rule coverage.

Why it lives OUTSIDE the lock (agentic-engineering principle):
  The scorer must never be modifiable by the system being measured. The test
  cases and pass/fail thresholds (the oracle) stay in the locked file. Only the
  orchestration — the harness runner — lives here, unlocked. This keeps the
  measurement boundary intact: this wrapper can call the oracle, never rewrite it.

Fail-loud contract (no silent degradation):
  reset_tenant requires CLAWGLOVE_OPERATOR_SECRET after CG-05. If the secret is
  missing or wrong, this orchestrator ABORTS before running any violation test.
  A misconfigured run must never produce a green-looking-but-inflated result.

Usage:
  $env:CLAWGLOVE_OPERATOR_SECRET="<same secret the daemon was started with>"
  py -m tests.run_eval_isolated
  # or:  py tests/run_eval_isolated.py

Certification gates are imported from the locked oracle — they are not redefined
here, so this wrapper cannot weaken them.
"""
import os
import sys

from clawglove.sidecar.client import ClawGloveClient, PolicyViolationError

# Import the oracle: test cases + thresholds come from the LOCKED file.
# This wrapper never redefines them, so it cannot game the metric.
from tests.eval.run_empirical_eval import (
    SIDECAR_HOST,
    SIDECAR_PORT,
    M_DETECTION_THRESHOLD,
    M_FALSE_POSITIVE_CEILING,
    VIOLATIONS,
    CLEAN_RUNS,
    sw,
    dir_,
)

OPERATOR_SECRET = os.environ.get("CLAWGLOVE_OPERATOR_SECRET", "")


def _reset(tenant: str, make_client) -> dict:
    """Send an authenticated reset_tenant to the daemon for one tenant."""
    return make_client()._send({
        "action": "reset_tenant",
        "tenant_id": tenant,
        "operator_secret": OPERATOR_SECRET,
    })


def _preflight_secret_check() -> None:
    """
    Fail loud, not soft. Verify the operator secret actually works BEFORE any
    violation test runs. A misconfigured secret would otherwise let quarantine
    persist between tests and silently re-inflate M_detection — a worse failure
    mode than the original bug because the run would still look green.
    """
    if not OPERATOR_SECRET:
        print("\nEVAL ABORTED — CLAWGLOVE_OPERATOR_SECRET is not set.")
        print("The isolated orchestrator resets quarantine between tests and needs")
        print("the operator secret to do so. Set it to match the running daemon:")
        print('  $env:CLAWGLOVE_OPERATOR_SECRET="<secret>"')
        sys.exit(2)

    # Probe: a reset on a known tenant must NOT return an error.
    probe = _reset("screenwriter", sw)
    if probe.get("error"):
        print(f"\nEVAL ABORTED — operator secret rejected by daemon: {probe['error']}")
        print("The secret in CLAWGLOVE_OPERATOR_SECRET does not match the daemon's")
        print("--operator-secret. Fix the secret before running the eval.")
        sys.exit(2)


def _reset_if_escalated() -> None:
    """Clear quarantine/elevated state on both tenants before the next test."""
    for tenant, make_cl in (("screenwriter", sw), ("director", dir_)):
        try:
            state = make_cl().get_threat_state()
            if state.get("level") in ("elevated", "quarantine"):
                result = _reset(tenant, make_cl)
                if result.get("error"):
                    # Should never happen — preflight already proved the secret works.
                    print(f"  ABORT — reset failed mid-run for {tenant}: {result['error']}")
                    sys.exit(2)
        except ConnectionError as e:
            print(f"  ERR   sidecar unreachable during reset: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"  WARN  could not read threat state for {tenant}: {e}")


def run_isolated_evaluation() -> None:
    # Connectivity check on both tenants
    for tenant, make_client in (("screenwriter", sw), ("director", dir_)):
        if not make_client().ping():
            print(f"\nEVAL ABORTED — sidecar not reachable for tenant={tenant}")
            print(f"Start:  clawglove-daemon --policies ./policies/ --port {SIDECAR_PORT} "
                  f"--operator-secret $env:CLAWGLOVE_OPERATOR_SECRET")
            sys.exit(1)

    _preflight_secret_check()

    print("\nClawGlove Certification — ISOLATED orchestrator (quarantine reset between tests)")
    print(f"Sidecar: {SIDECAR_HOST}:{SIDECAR_PORT}")
    print("Oracle:  tests/eval/run_empirical_eval.py (locked, imported read-only)")
    print("=" * 72)

    true_positives, false_negatives, quarantine_catches = 0, 0, 0

    print(f"\n[VIOLATIONS] {len(VIOLATIONS)} cases — expect: ALL BLOCKED by POLICY")
    print("  Quarantine is reset before each test so M_detection reflects true policy coverage.")
    for label, fn in VIOLATIONS:
        _reset_if_escalated()
        try:
            fn()
            print(f"  MISS     {label}")
            false_negatives += 1
        except PolicyViolationError as e:
            if "QUARANTINE" in str(e).upper():
                quarantine_catches += 1
                print(f"  CATCH(Q) {label}")   # quarantine-caught — NOT a true policy detection
            else:
                print(f"  CATCH    {label}")
            true_positives += 1
        except ConnectionError as e:
            print(f"  ERR      sidecar unreachable: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"  ERR      {label} — {type(e).__name__}: {e}")
            false_negatives += 1

    # Clear all state before clean runs so no leftover quarantine causes false positives
    _reset_if_escalated()

    true_negatives, false_positives = 0, 0
    print(f"\n[CLEAN RUNS] {len(CLEAN_RUNS)} cases — expect: ALL ALLOWED")
    for label, fn in CLEAN_RUNS:
        try:
            fn()
            print(f"  PASS  {label}")
            true_negatives += 1
        except PolicyViolationError as e:
            print(f"  FP    {label} — wrongly blocked: {e}")
            false_positives += 1
        except ConnectionError as e:
            print(f"  ERR   {e}")
            sys.exit(1)
        except Exception as e:
            print(f"  ERR   {label} — {type(e).__name__}: {e}")
            false_positives += 1

    total_v, total_c = len(VIOLATIONS), len(CLEAN_RUNS)
    m_detect = true_positives / total_v if total_v else 0.0
    m_fp = false_positives / total_c if total_c else 0.0
    policy_catches = true_positives - quarantine_catches

    print("\n" + "=" * 72)
    print("CLAWGLOVE CERTIFICATION — ISOLATED ORCHESTRATOR")
    print("=" * 72)
    print(f"  Violations  {total_v}  |  Caught {true_positives}  |  Missed {false_negatives}")
    print(f"    -> by policy rule:  {policy_catches}  (true M_detection signal)")
    print(f"    -> by quarantine:   {quarantine_catches}  (should be 0 — reset runs between tests)")
    print(f"  M_detection      {m_detect:.1%}  (threshold >= {M_DETECTION_THRESHOLD:.0%})")
    print()
    print(f"  Clean runs  {total_c}  |  Passed {true_negatives}  |  FP {false_positives}")
    print(f"  M_false_pos      {m_fp:.1%}  (ceiling <= {M_FALSE_POSITIVE_CEILING:.0%})")
    print("=" * 72)

    gate_d = m_detect >= M_DETECTION_THRESHOLD
    gate_fp = m_fp <= M_FALSE_POSITIVE_CEILING
    gate_q = quarantine_catches == 0   # honesty gate: no catch may rely on quarantine

    if gate_d and gate_fp and gate_q:
        print("\nVERDICT: PASS — certified on true per-rule policy coverage")
        sys.exit(0)
    else:
        print("\nVERDICT: FAIL")
        if not gate_d:
            print(f"  Detection {m_detect:.1%} < {M_DETECTION_THRESHOLD:.0%}")
        if not gate_fp:
            print(f"  False positive {m_fp:.1%} > {M_FALSE_POSITIVE_CEILING:.0%}")
        if not gate_q:
            print(f"  {quarantine_catches} catch(es) relied on quarantine, not policy — metric not honest")
        sys.exit(1)


if __name__ == "__main__":
    run_isolated_evaluation()
