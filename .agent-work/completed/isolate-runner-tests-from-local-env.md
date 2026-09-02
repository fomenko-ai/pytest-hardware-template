# Isolate runner tests from local env

## Result

The shared test settings fixture now disables Pydantic's local `.env` source with `_env_file=None`
and explicitly disables the runtime env file. Local stand configuration no longer changes expected
Docker commands in unit tests.

## Verification

- Initial partial fix: 18 passed, 1 failed because `known_hosts_file` still leaked from `.env`.
- Final helper test suite: 19 passed with no warnings.
- Full `./scripts/ci.sh`: passed, including pre-commit, Ruff, ShellCheck, ty, and all non-hardware
  tests.
