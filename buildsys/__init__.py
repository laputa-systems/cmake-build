"""Build-system controller for the CMake musl distribution.

Shared operations come from the pinned `laputa-buildlib` wheel: lock reading, verified
downloads, hashing, release assets, and ELF inspection. `buildsys.buildlib_wheel` admits that
wheel for every context that imports this package, including the sealed builder containers and
the benchmark runtime that cannot run `bootstrap/buildlib-run`.
"""

from .buildlib_wheel import ADMITTED
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
    "ADMITTED",
    "TARGETS",
    "Cache",
    "Input",
    "InputError",
    "PhaseCache",
    "PhaseError",
    "PhaseResult",
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
