# Test runner authentication

## Result

Added optional environment-controlled authentication for the test runner UI and API. Successful
login creates a signed, expiring `HttpOnly`, `SameSite=Strict` cookie; credentials are never stored
in the cookie. Login, logout, configuration, Docker Compose passthrough, documentation, and tests
are included.

## Verification

- Focused authentication and API tests: 8 passed.
- `./scripts/ci.sh`: passed, including pre-commit, Ruff, ShellCheck, ty, and all non-hardware tests.
- Updated the FastAPI lifespan annotation to `AsyncGenerator[None]` for Python 3.14/Pylance.
