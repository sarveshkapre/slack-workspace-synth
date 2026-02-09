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
