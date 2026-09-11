# Update Allure 3 publisher

State: complete.

Result:

- upgraded the locally built publisher from Allure 3.9.0 to 3.17.0;
- updated Test Runner and virtual-stand defaults and documentation;
- retained Allure Report Storage v1.0.1 because it is already current.

Verification:

- `local/allure-publisher:3.17.0` built successfully;
- the container reported version `3.17.0`;
- `./scripts/ci.sh` passed, including Ruff, ShellCheck, ty, and unit/integration tests.
