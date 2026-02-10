# Incidents And Learnings

## Entry Schema
- Date
- Trigger
- Impact
- Root Cause
- Fix
- Prevention Rule
- Evidence
- Commit
- Confidence

## Entries

- Date: 2026-02-09
  Trigger: GitHub Actions CI failures on `main` after adding a CLI test asserting a specific error string.
  Impact: `ci` workflow failed for commits `ff66ccd` and `d7ea972` until test was fixed.
  Root Cause: Typer emitted ANSI-styled (colorized) error output in GitHub Actions; the test asserted on raw text
    without normalizing/stripping ANSI sequences, making it brittle across environments.
  Fix: Strip ANSI escape sequences before asserting on CLI error text in `tests/test_cli_seed_live.py`.
  Prevention Rule: In CLI tests, normalize `CliRunner` output by stripping ANSI codes before substring assertions.
  Evidence: CI run `21825469379` succeeded after the fix.
  Commit: ab8640f
  Confidence: high

- Date: 2026-02-10
  Trigger: GitHub Actions failures on `main` after adding `export-jsonl --incremental-state`.
  Impact: `ci` workflow failed for run `21857963197` until a follow-up fix was pushed.
  Root Cause: Two issues landed together:
    1) Local `make check` was not run before push, leaving ruff lint and mypy typecheck failures.
    2) The `gitleaks/gitleaks-action@v2` step scanned a `git log` revision range, but `actions/checkout@v4` used
       `fetch-depth: 1`, so the parent commit was not present and gitleaks errored with an ambiguous revision range.
  Fix: Fix the lint/typecheck issues and set the gitleaks job checkout to `fetch-depth: 0` in `.github/workflows/ci.yml`.
  Prevention Rule: Run `make check` before pushing; for history/range-based scanners (gitleaks), ensure checkout depth
    includes required commits (use `fetch-depth: 0` or at least `2`).
  Evidence: CI run `21858065043` succeeded after the fix.
  Commit: cece02b
  Confidence: high
