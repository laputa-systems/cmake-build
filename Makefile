PYTHON ?= python3
TARGET ?=
TARGET_ARG = $(if $(TARGET),--target $(TARGET))

.PHONY: build verify lint clean fetch package repro controller-test

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
	$(PYTHON) build.py controller-test

lint:
	uv run --frozen ruff check .
	uv run --frozen ty check

clean:
	rm -rf .venv .ruff_cache .work/build .work/rust .work/phases .work/artifacts .work/generations .work/benchmark-results .work/tmp
	find . -path './.git' -prune -o -path './.work' -prune -o -name __pycache__ -type d -prune -exec rm -rf {} +
