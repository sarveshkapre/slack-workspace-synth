PYTHON=python3
VENV=.venv
BIN=$(VENV)/bin

.PHONY: setup dev test lint typecheck build check release

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e .[dev]

dev:
	SWSYNTH_DB=./data/workspace.db $(BIN)/uvicorn slack_workspace_synth.api:app --reload --host 127.0.0.1 --port 8080

test:
	$(BIN)/pytest -q

lint:
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

typecheck:
	$(BIN)/mypy src/slack_workspace_synth

build:
	@if $(BIN)/python -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('setuptools.build_meta') else 1)"; then \
		$(BIN)/python -m build --no-isolation; \
	else \
		echo "Skipping build (setuptools not installed). Install with: $(BIN)/pip install setuptools wheel"; \
	fi

check: lint typecheck test build

release: build
