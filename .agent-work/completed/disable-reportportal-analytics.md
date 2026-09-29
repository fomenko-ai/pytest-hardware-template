---
id: disable-reportportal-analytics
status: completed
owner: codex
branch: null
updated: 2026-09-29
issue: null
---

# Disable ReportPortal analytics

## Result

ReportPortal usage analytics now defaults to disabled before client creation. The project-owned
root test configuration uses `os.environ.setdefault`, while Docker, CI, the hardware launcher, and
the Test Runner establish the same runtime invariant at their execution boundaries. Keeping this
policy out of the reusable pytest plugin preserves the library boundary from ADR 0001.

## Verification

- Focused root tests: 26 passed, 6 optional cases skipped.
- ReportPortal integration with the locked optional group: 3 passed, 3 Allure variants skipped.
- Test Runner Docker command tests: 7 passed.
- `docker build --check --file Dockerfile .`: passed with no warnings.
- `./scripts/ci.sh`: passed, including Ruff, ShellCheck, ty, unit, and integration tests.
- Locked versions confirmed: `pytest-reportportal==5.6.11`, `reportportal-client==5.7.10`.
