# SECURITY

## Reporting
Please report security issues via GitHub Security Advisories.

## Threat model notes
- The API is read-only and intended for local use.
- No authentication is provided in MVP; do not expose it publicly.
- Plugins execute arbitrary Python code; only load trusted modules.
