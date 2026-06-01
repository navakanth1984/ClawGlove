"""clawglove.provenance — Context Provenance Tracking (CPT) subsystem."""
from .client import CPTClient, CPTWriteRequest, ProvenanceEnvelope
from .exceptions import (
    CPTError,
    IdentityHaltError,
    InterceptTimeoutError,
    OrphanedPayloadError,
    SkillQuarantinedError,
    TenantIsolationError,
)
__all__ = [
    "CPTClient", "CPTWriteRequest", "ProvenanceEnvelope",
    "CPTError", "IdentityHaltError", "InterceptTimeoutError",
    "OrphanedPayloadError", "SkillQuarantinedError", "TenantIsolationError",
]
