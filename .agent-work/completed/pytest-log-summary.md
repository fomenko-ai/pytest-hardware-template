---
id: pytest-log-summary
status: completed
owner: codex
branch: null
updated: 2026-08-24
issue: null
---

# Add a pytest log summary

## Result

Each run-specific `pytest.log` and its hard-linked `artifacts/latest.log` end with a clearly
delimited summary containing the selected test total, outcome counts, duration, exit code, and
failed test node IDs. Test-class headers use hyphen separators, while the final session summary
uses equals-sign separators. Synthetic summary unit tests mock the logger and do not pollute the
real session log.

## Verification

- `uv run pytest tests/unit/test_pytest_plugin.py -vv`: 11 passed.
- `./scripts/ci.sh`: passed, including Ruff, ShellCheck, ty, and 151 unit/integration tests.
