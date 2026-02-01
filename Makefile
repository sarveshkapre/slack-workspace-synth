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
	$(BIN)/python -m build

check: lint typecheck test build

release: build
