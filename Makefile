PYTHON=python3
VENV=.venv
BIN=$(VENV)/bin

.PHONY: setup dev test lint typecheck build check bench release clean slack-smoke

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
	@if ! $(BIN)/python -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('build') else 1)"; then \
		echo "Skipping build (build package not installed). Install with: $(BIN)/pip install build"; \
	elif $(BIN)/python -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('setuptools') and importlib.util.find_spec('wheel') else 1)"; then \
		$(BIN)/python -m build --no-isolation; \
	else \
		echo "setuptools/wheel missing in active venv, trying isolated build."; \
		$(BIN)/python -m build || echo "Skipping build (isolated build unavailable in this environment)."; \
	fi

check: lint typecheck test build

bench:
	$(BIN)/python scripts/bench.py --profile quick --out ./bench_out/quick

release: build

clean:
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache bench_out
	rm -rf src/*.egg-info
	find src tests -type d -name __pycache__ -prune -exec rm -rf {} + || true

slack-smoke:
	@if [ -z "$$SLACK_SMOKE_TOKEN" ]; then echo "SLACK_SMOKE_TOKEN not set; skipping"; exit 0; fi
	@ARGS="--slack-token $$SLACK_SMOKE_TOKEN"; \
	if [ -n "$$SLACK_SMOKE_TEAM_ID" ]; then ARGS="$$ARGS --team-id $$SLACK_SMOKE_TEAM_ID"; fi; \
	$(BIN)/swsynth slack-smoke $$ARGS
