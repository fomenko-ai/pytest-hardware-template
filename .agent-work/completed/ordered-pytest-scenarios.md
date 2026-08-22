---
id: ordered-pytest-scenarios
status: completed
owner: codex
branch: null
updated: 2026-08-22
issue: null
---

# Ordered pytest scenarios

## Result

Added `-M/--marker-sequence`, `-S/--scenario`, validated YAML scenarios under
`test-runs/scenarios/`, and standard pytest argument files under `test-runs/pytest-args/`. Scenario
runs preserve collection order inside each marker group, deselect unrelated tests, fail fast, and
enforce the hardware stand requirement after selection. The plugin functions follow pytest
lifecycle order.

## Verification

- `uv run pytest tests/unit/test_scenarios.py tests/unit/test_ordered_scenario_plugin.py tests/unit/test_pytest_plugin.py -q`: 25 passed.
- `./scripts/ci.sh`: passed, including Ruff, ShellCheck, ty, unit tests, and integration tests.
