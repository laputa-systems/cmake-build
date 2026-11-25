"""Target descriptions: the targets this repository builds, taken from buildlib."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from buildlib import targets as shared
from buildlib.targets import MACOS, UnsupportedTargetError

CPU_BASELINES: Mapping[str, str] = MappingProxyType({
    "x86_64-unknown-linux-musl": "x86-64",
    "aarch64-unknown-linux-musl": "armv8-a",
    "aarch64-apple-darwin": "apple-m1",
})

LINUX_TRIPLES = ("x86_64-unknown-linux-musl", "aarch64-unknown-linux-musl")
DARWIN_TRIPLE = "aarch64-apple-darwin"


@dataclass(frozen=True)
class Target:
    triple: str
    machine: str
    family: str
    executable_format: str
    cpu_baseline: str
    alpine_arch: str
    docker_platform: str
    musl_loader: str
    elf_machine: int
    deployment_target: str = ""
    cpu_baseline_cflag: str = ""

    @property
    def is_macos(self) -> bool:
        return self.family == MACOS


def _adopt(item: shared.Target) -> Target:
    baseline = CPU_BASELINES.get(item.triple)
    if (baseline is None or item.docker_platform is None or item.alpine_arch is None
            or item.musl_loader is None or item.elf_machine is None):
        raise UnsupportedTargetError(f"target not implemented: {item.triple} (supported: {sorted(CPU_BASELINES)})")
    return Target(
        triple=item.triple,
        machine=item.machine,
        family=item.family,
        executable_format=item.executable_format,
        cpu_baseline=baseline,
        alpine_arch=item.alpine_arch,
        docker_platform=item.docker_platform,
        musl_loader=item.musl_loader,
        elf_machine=item.elf_machine,
    )


def _darwin() -> Target:
    return Target(
        triple=DARWIN_TRIPLE,
        machine="arm64",
        family=MACOS,
        executable_format="mach-o",
        cpu_baseline=CPU_BASELINES[DARWIN_TRIPLE],
        alpine_arch="",
        docker_platform="",
        musl_loader="",
        elf_machine=0,
        deployment_target="27.0",
        cpu_baseline_cflag="-mcpu=apple-m1",
    )


TARGETS: Mapping[str, Target] = MappingProxyType(
    {triple: _adopt(shared.target_for_triple(triple)) for triple in LINUX_TRIPLES}
    | {DARWIN_TRIPLE: _darwin()}
)


def target(triple: str) -> Target:
    try:
        return TARGETS[triple]
    except KeyError as error:
        raise UnsupportedTargetError(
            f"target not implemented: {triple} (supported: {sorted(TARGETS)})"
        ) from error


def native_target() -> Target:
    return target(shared.native_target().triple)
