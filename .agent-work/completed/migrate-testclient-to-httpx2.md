# Migrate TestClient to httpx2

## Result

Replaced the helper's deprecated `httpx` test dependency with `httpx2` and refreshed its lock
file. FastAPI/Starlette `TestClient` continues to use the existing imports and now selects the
supported backend without a deprecation warning.

## Verification

- `uv sync --locked`: passed.
- Helper test suite: 19 passed with no warnings.
- Full `./scripts/ci.sh`: passed, including pre-commit, Ruff, ShellCheck, ty, and all non-hardware
  tests.
