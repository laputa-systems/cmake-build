#!/usr/bin/env bash
set -euo pipefail

if [[ -n $(git status --porcelain=v1 -- . ':(exclude).work') ]]; then
  printf '%s\n' 'Mutation selection requires a clean checkout of committed changes.' >&2
  exit 1
fi

root="$PWD"
mkdir -p "$root/.work/tmp"
scratch=$(mktemp -d "$root/.work/tmp/cmake-mutants.XXXXXXXX")
trap 'rm -rf -- "$scratch"' EXIT
export TMPDIR="$scratch"
git -C "$2" archive "$(< .github/mutation-buildlib-revision)" scripts/mutants_gate.py | tar -x -C "$scratch"
reader="$scratch/scripts"
modules=$(uv run --no-project --python 3.15.2 python .github/scripts/select_mutation_sources.py "$1" "$reader" \
  --qualified-modules .github/mutation-dispositions.toml --lines)
if [[ -z $modules ]]; then
  if [[ -n $3 ]]; then
    printf 'No changed mutation scope matches %s.\n' "$3" >&2
    exit 1
  fi
  printf '%s\n' 'No changed mutation scopes.'
  exit 0
fi
if [[ -n $3 ]]; then
  if ! printf '%s\n' "$modules" | awk -v candidate="$3" '$0 == candidate { found = 1 } END { exit !found }'; then
    printf 'No changed mutation scope matches %s.\n' "$3" >&2
    exit 1
  fi
  modules=$3
fi

run_module() (
  module=$1
  source="buildsys/$module.py"
  paths=(build.py buildsys tests .github bootstrap.lock.json sources.lock.json
         release-budgets.json pyproject.toml uv.lock docker patches scripts)
  git ls-tree -r --full-tree HEAD -- "${paths[@]}" |
    awk '$1 == "120000" || $1 == "160000" { print "unsupported archive entry: " $0 > "/dev/stderr"; bad = 1 } END { exit bad }'
  module_copy=
  case "$module" in
    benchmark_process) tests='["tests/controller/test_benchmark_accounting.py"]' ;;
    bootstrap)
      tests='["tests/controller/test_bootstrap.py"]'
      module_copy=', "docker", "patches", "scripts"'
      ;;
    buildlib_wheel) tests='["tests/controller/test_buildlib_wheel.py::CacheAdmissionTests"]' ;;
    budgets) tests='["tests/controller/test_budgets.py", "tests/controller/test_package_reproduce.py",
                      "tests/controller/test_package_generations.py", "tests/controller/test_cli.py"]' ;;
    cmake|dependencies)
      tests='["tests/controller/test_cmake.py"]'
      if [[ $module == dependencies ]]; then
        tests='["tests/controller/test_cmake.py", "tests/controller/test_dependency_inventory.py"]'
      fi
      module_copy=', "docker", "patches", "scripts"'
      ;;
    generations) tests='["tests/controller/test_package_archive.py", "tests/controller/test_package_generations.py",
                          "tests/controller/test_package_commands.py"]' ;;
    licenses|stage) tests='["tests/controller/test_licenses.py"]' ;;
    inputs) tests='["tests/controller/test_inputs.py", "tests/controller/test_phases.py"]' ;;
    targets) tests='["tests/controller/test_cli.py", "tests/controller/test_targets.py"]' ;;
    reference) tests='["tests/controller/test_reference.py"]' ;;
    reproduce) tests='["tests/controller/test_package_reproduce.py", "tests/host/test_reproduction_git.py"]' ;;
    package) tests='["tests/controller/test_package_archive.py", "tests/controller/test_package_generations.py",
                      "tests/controller/test_package_commands.py"]' ;;
    patches) tests='["tests/controller/test_patches.py"]' ;;
    phases) tests='["tests/controller/test_phases.py"]' ;;
    qualify)
      tests='["tests/controller/test_projects.py", "tests/controller/test_network_qualification.py",
              "tests/controller/test_parity_qualification.py"]'
      module_copy=', "docker", "patches", "scripts"'
      if [[ $(uname -s) == Linux ]]; then
        mkdir -p "$scratch/tools"
        jaq_blob=$(uv run --frozen --python 3.15.2 python -c '
from pathlib import Path
import sys
from buildsys.inputs import Cache, load_sources

entry = next(item for item in load_sources(Path("sources.lock.json")) if item.name == sys.argv[1])
print(Cache(Path(".work/cache")).fetch(entry))
' "jaq-$(uname -m)")
        install -m 0755 "$jaq_blob" "$scratch/tools/jaq"
        export PATH="$scratch/tools:$PATH"
      else
        jaq --version
      fi
      ;;
    rust)
      tests='["tests/controller/test_sandbox.py", "tests/controller/test_tls.py", "tests/controller/test_rust.py",
               "tests/controller/test_kache.py", "-k", "not locked_graph and not locked_dependency_graph"]'
      module_copy=', "docker", "patches", "scripts"'
      ;;
    sandbox|sysroot|toolchain)
      tests='["tests/controller/test_sandbox.py"]'
      module_copy=', "docker", "patches", "scripts"'
      ;;
    tls)
      tests='["tests/controller/test_tls.py", "-k", "not locked_graph and not locked_dependency_graph"]'
      module_copy=', "docker", "patches", "scripts"'
      ;;
    *) exit 2 ;;
  esac
  export PYTHONCOERCECLOCALE=0 PYTHONUTF8=0
  if [ "$(uname -s)" = Darwin ]; then
    export LC_ALL=en_US.UTF-8
  else
    export LC_ALL=C.UTF-8
  fi
  proof="$scratch/$module"
  mkdir -p "$proof/.work/tmp"
  touch "$proof/.work/tmp/.keep"
  export TMPDIR="$proof/.work/tmp" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
  git archive HEAD -- "${paths[@]}" | tar -x -C "$proof"
  cache_copy=
  if [ "$module" = buildlib_wheel ]; then
    (cd "$proof"; uv run --frozen --python 3.15.2 python -c 'from buildsys import WHEEL')
    cache_copy=', ".work/cache"'
  fi
  cat >> "$proof/pyproject.toml" <<TOML

[tool.mutmut]
source_paths = ["buildsys"]
only_mutate = ["$source"]
also_copy = ["build.py", "bootstrap.lock.json", "sources.lock.json", "release-budgets.json", "pyproject.toml", "uv.lock", ".github", ".work/tmp"$cache_copy$module_copy]
pytest_add_cli_args_test_selection = $tests
use_setproctitle = false
TOML
  uv run --no-project --python 3.15.2 python .github/scripts/check_mutation_results.py \
    "$source" "$proof" .github/mutation-dispositions.toml "$reader" --run-budget "$2"
)

while IFS= read -r module; do
  run_module "$module" "$4"
done <<< "$modules"
