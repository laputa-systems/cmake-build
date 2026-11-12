"""Target descriptions: the Linux musl targets this repository builds, taken from buildlib."""

from __future__ import annotations

import platform
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from buildlib import targets as shared
from buildlib.targets import UnsupportedTargetError

CPU_BASELINES: Mapping[str, str] = MappingProxyType({
    "x86_64-unknown-linux-musl": "x86-64",
    "aarch64-unknown-linux-musl": "armv8-a",
})


@dataclass(frozen=True)
class Target:
    triple: str
    machine: str
    alpine_arch: str
    docker_platform: str
    musl_loader: str
    elf_machine: int
    cpu_baseline: str


def _adopt(item: shared.Target) -> Target:
    baseline = CPU_BASELINES.get(item.triple)
    if (baseline is None or item.docker_platform is None or item.alpine_arch is None
            or item.musl_loader is None or item.elf_machine is None):
        raise UnsupportedTargetError(f"target not implemented: {item.triple} (supported: {sorted(CPU_BASELINES)})")
    return Target(
        triple=item.triple,
        machine=item.machine,
        alpine_arch=item.alpine_arch,
        docker_platform=item.docker_platform,
        musl_loader=item.musl_loader,
        elf_machine=item.elf_machine,
        cpu_baseline=baseline,
    )


TARGETS: Mapping[str, Target] = MappingProxyType(
    {triple: _adopt(shared.target_for_triple(triple)) for triple in CPU_BASELINES}
)


def target(triple: str) -> Target:
    try:
        return TARGETS[triple]
    except KeyError as error:
        raise UnsupportedTargetError(
            f"target not implemented: {triple} (supported: {sorted(TARGETS)})"
        ) from error


def native_target() -> Target:
    return target(shared.native_target("Linux", platform.machine()).triple)
