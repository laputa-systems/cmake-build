from __future__ import annotations

import argparse
import platform
import sys
import time
import tomllib
from importlib import import_module
from pathlib import Path

from select_mutation_sources import CRITICAL


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", choices=sorted(CRITICAL))
    parser.add_argument("checkout", type=Path)
    parser.add_argument("dispositions", type=Path)
    parser.add_argument("buildlib_scripts", type=Path)
    parser.add_argument("--run-budget", type=int, metavar="SECONDS")
    args = parser.parse_args()
    if args.run_budget is not None and not 1 <= args.run_budget <= 600:
        parser.error("--run-budget must be between 1 and 600 seconds")
    sys.path.insert(0, str(args.buildlib_scripts.resolve(strict=True)))
    gate = import_module("mutants_gate")
    module = Path(args.source).stem
    prefix = f"buildsys.{module}."

    with args.dispositions.open("rb") as stream:
        dispositions = tomllib.load(stream)
    host = platform.system()
    try:
        module_record = dispositions["qualified"][module]
        record = {"source_sha256": module_record["source_sha256"], "survivors": module_record[host]}
    except KeyError as error:
        raise ValueError(f"missing dispositions for {module} on {host}") from error

    try:
        if args.run_budget is not None:
            gate.run_command(
                [
                    "uv", "run", "--frozen", "--python", "3.15.2",
                    "--with", "mutmut==3.8.1", "--with", "pytest==9.2.0",
                    "python", "-m", "mutmut", "run", "--max-children", "1", prefix + "*",
                ],
                args.checkout,
                time.monotonic() + args.run_budget,
            )
        counts = gate.verify_trial_results(args.checkout, args.source, prefix, record)
    except gate.GateError as error:
        raise ValueError(str(error)) from error
    print(f"{module} on {host}: {counts}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
