---
id: containerized-hardware-runs
status: completed
owner: Codex
branch: null
updated: 2026-08-24
issue: null
---

# Containerized hardware runs

## Result

Added a provider-independent shell launcher for running one named hardware scenario from a
pre-built Docker image. Inventory is mounted read-only, runtime access is explicit, pytest
artifacts persist on the host, and the Docker exit code is preserved.

Added inactive executable examples for GitHub Actions, GitLab CI, and Jenkins, plus common usage,
security, stand-serialization, and activation documentation. Unit tests exercise validation and
Docker command construction through a fake executable without network or hardware access.

## Verification

- `uv run pytest tests/unit/test_hardware_run_script.py -vv`: 9 passed.
- ShellCheck for `scripts/run-hardware-tests.sh`: passed.
- `./scripts/ci.sh`: passed on the clean second run, including all unit and integration tests.
- Physical hardware tests were not run.
