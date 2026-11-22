PYTHON ?= sh bootstrap/buildlib-run --
TARGET ?=
TARGET_ARG = $(if $(TARGET),--target $(TARGET))

.PHONY: test test-native test-ci coverage build verify lint clean fetch package repro controller-test reproduction-git-test setup

setup:
	sh scripts/setup-dev

fetch:
	$(PYTHON) build.py fetch $(TARGET_ARG)

build:
	$(PYTHON) build.py build $(TARGET_ARG)
	$(PYTHON) build.py package $(TARGET_ARG)

package:
	$(PYTHON) build.py package $(TARGET_ARG)

verify:
	$(PYTHON) build.py qualify $(TARGET_ARG)

repro:
	$(PYTHON) build.py reproduce $(TARGET_ARG)

controller-test:
	$(PYTHON) build.py controller-test --scope portable

test-native:
	$(PYTHON) build.py controller-test --scope native

lint:
	uv run --frozen ruff check .
	uv run --frozen ty check

clean:
	@for parent in ./.work; do \
	  if test -L "$$parent"; then printf '%s\n' "make clean: $$parent must be a local directory" >&2; exit 1; fi; \
	done
	@for artifact in ./.ruff_cache ./.work/build ./.work/rust ./.work/phases; do \
	  if test -L "$$artifact" || { test -e "$$artifact" && ! test -d "$$artifact"; }; then \
	    printf '%s\n' "make clean: $$artifact must be a local build directory" >&2; exit 1; \
	  fi; \
	done
	rm -rf -- ./.ruff_cache ./.work/build ./.work/rust ./.work/phases

test: controller-test reproduction-git-test

reproduction-git-test:
	mkdir -p .work/tmp
	TMPDIR="$(CURDIR)/.work/tmp" PYTHONPATH="$(CURDIR)" $(PYTHON) -m unittest discover -s tests/host -p test_reproduction_git.py

coverage:
	$(PYTHON) -m scripts.controller_coverage "$(TARGET)"

test-ci:
	TMPDIR="$(CURDIR)/.work/tmp" python3 -c 'import sys; from pathlib import Path; import build; target=build.describe_target("x86_64-unknown-linux-musl"); image=build.sandbox.image_tag(build.load_bootstrap(build.BOOTSTRAP_LOCK),target,build.DOCKERFILE); r=build.sandbox.run_sealed(image,["python3","build.py","controller-test"],target=target,mounts=[(Path.cwd(),"/src")],env={"TMPDIR":"/src/.work/tmp","PYTHONPATH":"/src","PATH":"/src/.work/tools:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},timeout=300); print(r.stdout,end=""); print(r.stderr,end="",file=sys.stderr); sys.exit(r.returncode)'

.PHONY: bench bench-check bench-list

bench:
	$(PYTHON) -m buildsys.bench $(BENCH_ARGS)

bench-check:
	$(PYTHON) -m buildsys.bench --check $(BENCH_ARGS)

bench-list:
	$(PYTHON) -m buildsys.bench --list
