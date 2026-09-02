# Hide disabled authentication controls

## Result

Added a public read-only authentication status endpoint. The UI keeps the sign-out button hidden
by default and reveals it only when authentication is enabled, preventing an unnecessary reload
and loss of entered form values in unauthenticated deployments.

## Verification

- Focused authentication and API tests: 8 passed.
- Focused Ruff check: passed.
- Full `./scripts/ci.sh`: passed, including pre-commit, Ruff, ShellCheck, ty, and all non-hardware
  tests.
