# Benchmarks

This repo is intentionally performance-sensitive for large synthetic workspaces. The goal of benchmarking is to:
- Catch accidental slowdowns/regressions early.
- Provide rough sizing/timing baselines for operators.

## Local Benchmark Script

Prereqs:
```bash
make setup
. .venv/bin/activate
```

Run a quick end-to-end generate + JSONL export benchmark:
```bash
python scripts/bench.py --profile quick --out ./bench_out/quick
```

Run the larger default preset:
```bash
python scripts/bench.py --profile default --out ./bench_out/default
```

Run the enterprise-ish preset (includes DMs/MPDMs):
```bash
python scripts/bench.py --profile enterprise --out ./bench_out/enterprise
```

Each run writes a JSON report at `OUT/report.json` and prints the report path on stdout.

## Expected Ranges (Local Baseline)
Use these as rough guardrails for local regression checks on the same machine class.

Baseline captured on 2026-02-11 (`macOS arm64`, `Python 3.14.0`, uncompressed export):

| Profile | Generate (s) | Export JSONL (s) | Suggested warning threshold |
| --- | ---: | ---: | --- |
| `quick` | 0.09 | 0.02 | investigate if either phase is >2x baseline |
| `default` | 6.21 | 0.50 | investigate if either phase is >1.5x baseline |
| `enterprise` | 12.77 | 0.81 | investigate if either phase is >1.5x baseline |

These are not CI pass/fail gates yet; they are operator-facing early warning ranges.

## Regression Capture Workflow
Use a fresh output path per run so historical files do not distort size/timing observations.

```bash
. .venv/bin/activate
STAMP=$(date +%Y%m%d-%H%M%S)
python scripts/bench.py --profile quick --out "./bench_out/$STAMP-quick"
python scripts/bench.py --profile default --out "./bench_out/$STAMP-default"
python scripts/bench.py --profile enterprise --out "./bench_out/$STAMP-enterprise"
```

Compare each `report.json` against the expected ranges above. If a phase regresses beyond threshold:
1. Re-run once to rule out transient machine noise.
2. Compare commit range and isolate changes touching generation/storage/export loops.
3. Record the command + report paths in `PROJECT_MEMORY.md`.

## Notes
- Benchmarks are machine-dependent. Use them for relative comparisons on the same machine and commit range.
- If you want faster exports, prefer SSD storage and keep `--compress` off while iterating.
