# Update Ruff and ty

State: complete

## Result

Updated the Ruff pre-commit hook from 0.14.0 to 0.16.4. Upgraded the locked Ruff version from
0.16.2 to 0.16.4 and ty from 0.0.70 to 0.0.74. No other locked packages changed.

## Verification

- `git diff --check`: passed.
- `uv sync --locked`: passed.
- `./scripts/ci.sh`: passed with all hooks and unit and integration tests.
