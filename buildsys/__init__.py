"""Build-system controller for the CMake musl distribution."""

from .inputs import (
    Cache,
    Input,
    InputError,
    canonical_json,
    identity,
    load_bootstrap,
    load_sources,
    safe_extract,
    tree_digest,
)
from .phases import PhaseCache, PhaseError, PhaseResult
from .targets import TARGETS, Target, UnsupportedTargetError, native_target, target

__all__ = [
    "Cache",
    "Input",
    "InputError",
    "PhaseCache",
    "PhaseError",
    "PhaseResult",
    "TARGETS",
    "Target",
    "UnsupportedTargetError",
    "canonical_json",
    "identity",
    "load_bootstrap",
    "load_sources",
    "native_target",
    "safe_extract",
    "target",
    "tree_digest",
]
