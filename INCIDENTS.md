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

### 2026-02-12T20:01:15Z | Codex execution failure
- Date: 2026-02-12T20:01:15Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-2.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:04:42Z | Codex execution failure
- Date: 2026-02-12T20:04:42Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-3.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:08:10Z | Codex execution failure
- Date: 2026-02-12T20:08:10Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-4.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:11:41Z | Codex execution failure
- Date: 2026-02-12T20:11:41Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-5.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:15:13Z | Codex execution failure
- Date: 2026-02-12T20:15:13Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-6.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:18:42Z | Codex execution failure
- Date: 2026-02-12T20:18:42Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-7.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:22:08Z | Codex execution failure
- Date: 2026-02-12T20:22:08Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-8.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:25:38Z | Codex execution failure
- Date: 2026-02-12T20:25:38Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-9.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:29:14Z | Codex execution failure
- Date: 2026-02-12T20:29:14Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-10.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:32:45Z | Codex execution failure
- Date: 2026-02-12T20:32:45Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-11.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:36:14Z | Codex execution failure
- Date: 2026-02-12T20:36:14Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-12.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:39:40Z | Codex execution failure
- Date: 2026-02-12T20:39:40Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-13.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:43:12Z | Codex execution failure
- Date: 2026-02-12T20:43:12Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-14.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:46:43Z | Codex execution failure
- Date: 2026-02-12T20:46:43Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-15.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:50:14Z | Codex execution failure
- Date: 2026-02-12T20:50:14Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-16.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:53:52Z | Codex execution failure
- Date: 2026-02-12T20:53:52Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-17.log
- Commit: pending
- Confidence: medium

### 2026-02-12T20:57:18Z | Codex execution failure
- Date: 2026-02-12T20:57:18Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-18.log
- Commit: pending
- Confidence: medium

### 2026-02-12T21:00:45Z | Codex execution failure
- Date: 2026-02-12T21:00:45Z
- Trigger: Codex execution failure
- Impact: Repo session did not complete cleanly
- Root Cause: codex exec returned a non-zero status
- Fix: Captured failure logs and kept repository in a recoverable state
- Prevention Rule: Re-run with same pass context and inspect pass log before retrying
- Evidence: pass_log=logs/20260212-101456-slack-workspace-synth-cycle-19.log
- Commit: pending
- Confidence: medium
