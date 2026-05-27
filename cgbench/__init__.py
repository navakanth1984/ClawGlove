"""
CGBench: ClawGlove Adversarial Governance Benchmark Suite.
Audits runtime constraints, probabilistic drift, multi-agent contamination, malware-like persistence, and chaotic infrastructural resilience.
"""
from cgbench.metrics import TrustEpochMetrics, calculate_entropy, GovernanceGrade
from cgbench.runner import CGBenchRunner

__all__ = [
    "TrustEpochMetrics",
    "calculate_entropy",
    "GovernanceGrade",
    "CGBenchRunner",
]
