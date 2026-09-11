# Move Allure integration to the test layer

Moved the repository-specific `--allure` option and adapter configuration from the installed
`hardware_test` pytest plugin to `tests/conftest.py`. Production code now exposes only a neutral,
typed accessor for the current artifact run directory.

Moved `allure-pytest` from published optional dependencies to the repository-local `allure`
dependency group. Docker builds and documentation now use `--group allure`.

Verification:

- `uv lock` and `uv sync --locked --group allure` passed.
- A real `uv run --group allure pytest ... --allure` run passed and created per-run results.
- Focused reporting and pytest-plugin tests passed: 15 tests.
- The final `./scripts/ci.sh` run passed without changes.
