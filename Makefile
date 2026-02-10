PYTHON=python3
VENV=.venv
BIN=$(VENV)/bin

.PHONY: setup dev test lint typecheck build check bench smoke release clean slack-smoke

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

smoke:
	rm -rf smoke_out
	mkdir -p smoke_out
	$(BIN)/swsynth generate --workspace "Smoke Test" --users 20 --channels 5 --messages 200 --files 20 --seed 1 --db ./smoke_out/source.db
	$(BIN)/swsynth validate-db --db ./smoke_out/source.db --require-workspace --quiet
	$(BIN)/swsynth export-jsonl --db ./smoke_out/source.db --out ./smoke_out/export
	$(BIN)/swsynth import-jsonl --source ./smoke_out/export --db ./smoke_out/imported.db
	$(BIN)/swsynth import-jsonl --source ./smoke_out/export --db ./smoke_out/imported.db --mode append
	$(BIN)/swsynth validate-db --db ./smoke_out/imported.db --require-workspace --quiet

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
