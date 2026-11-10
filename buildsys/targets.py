"""Target descriptions: the one place architecture-specific data lives."""

from __future__ import annotations

import platform
from dataclasses import dataclass


class UnsupportedTargetError(Exception):
    """No target description exists for this machine or triple."""


@dataclass(frozen=True)
class Target:
    triple: str
    machine: str
    alpine_arch: str
    docker_platform: str
    musl_loader: str
    cpu_baseline: str
    elf_machine: int

    def __post_init__(self) -> None:
        if not all((self.triple, self.machine, self.alpine_arch, self.docker_platform)):
            raise UnsupportedTargetError(f"{self.triple}: incomplete target description")
        if not self.musl_loader.startswith("/lib/ld-musl-"):
            raise UnsupportedTargetError(f"{self.triple}: bad musl loader {self.musl_loader!r}")


TARGETS: dict[str, Target] = {
    "x86_64-unknown-linux-musl": Target(
        triple="x86_64-unknown-linux-musl",
        machine="x86_64",
        alpine_arch="x86_64",
        docker_platform="linux/amd64",
        musl_loader="/lib/ld-musl-x86_64.so.1",
        cpu_baseline="x86-64",
        elf_machine=62,
    ),
    "aarch64-unknown-linux-musl": Target(
        triple="aarch64-unknown-linux-musl",
        machine="aarch64",
        alpine_arch="aarch64",
        docker_platform="linux/arm64",
        musl_loader="/lib/ld-musl-aarch64.so.1",
        cpu_baseline="armv8-a",
        elf_machine=183,
    ),
}

_MACHINE_ALIASES = {"amd64": "x86_64", "arm64": "aarch64"}


def target(triple: str) -> Target:
    try:
        return TARGETS[triple]
    except KeyError as error:
        raise UnsupportedTargetError(
            f"target not implemented: {triple} (supported: {sorted(TARGETS)})"
        ) from error


def native_target() -> Target:
    machine = platform.machine()
    machine = _MACHINE_ALIASES.get(machine, machine)
    for candidate in TARGETS.values():
        if candidate.machine == machine:
            return candidate
    raise UnsupportedTargetError(f"this machine ({machine}) has no target description")
