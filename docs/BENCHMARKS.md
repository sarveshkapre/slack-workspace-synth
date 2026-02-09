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

## Notes
- Benchmarks are machine-dependent. Use them for relative comparisons on the same machine and commit range.
- If you want faster exports, prefer SSD storage and keep `--compress` off while iterating.

