# Project Coding Rules

These rules apply to AI-assisted code changes in this repository.

1. Before making changes that affect more than two modules or files, propose an architectural
   option first and wait for user approval.
2. Change tests only after the user has approved the changes in the main project code.
3. Delete `*/__pycache__` directories only after an explicit user request.

## Project Architecture

Keep the repository a minimal, reusable template for hardware test automation. Do not add
vendor-specific behavior, organization addresses, real credentials, or abstractions without a
current requirement.

### Terminology and Configuration Boundaries

Use these terms consistently:

- `settings`: global runtime defaults, credentials, and secrets;
- `inventory`: physical devices, transports, stands, and topology;
- `stand`: one physical test setup exposed to tests through logical roles;
- `devices`: physical equipment represented by domain APIs;
- `configs`: data for individual test scenarios.

Use `stand`, `TestStand`, `StandConfig`, and `stands.yaml`. Do not introduce `bench`, `TestBench`,
`BenchConfig`, or `benches.yaml`.

Respect these ownership rules:

1. `pydantic-settings` models may load runtime settings and secrets from environment variables.
2. Inventory YAML must use regular Pydantic models, never `BaseSettings`.
3. Inventory contains hosts, ports, device definitions, and credential references, but no secrets.
4. Scenario configs contain test data, but no stands, topology, or credentials.
5. Passwords use `SecretStr`; `.env` and real credentials must never be committed.
6. `stands.yaml` lists physical-device sources explicitly through `device_files`; resolve those
   paths relative to `stands.yaml` and do not discover inventory files with globs.
7. Device IDs must be unique across every file in `device_files`; reject duplicates with an error
   that identifies both conflicting sources.

### Dependency Direction

Preserve this composition flow:

```text
pytest options and fixtures
        -> inventory models and loader
        -> StandFactory
        -> DeviceFactory and TransportFactory
        -> TestStand
        -> device APIs
        -> Transport protocol
        -> concrete transport implementation
```

Follow these constraints:

1. Use constructor dependency injection and composition over inheritance.
2. `TestStand` receives constructed devices; it must not read YAML or environment variables and
   must not create transports.
3. Device classes depend on the `Transport` protocol, not Paramiko or another client library.
4. Hardware tests use logical roles such as `stand.dut`, not physical inventory identifiers.
5. Factories own construction and mapping logic; pytest fixtures only coordinate lifecycle.
6. Concrete client libraries must remain encapsulated in their transport implementations.
7. Do not introduce singletons, service locators, mutable global state, generic `utils.py`, or
   unnecessary manager/service layers.

### Python and Tooling

1. Support Python 3.14 and keep the package in the `src/hardware_test` layout.
2. Fully type production and test code.
3. Use Ruff as the only formatter, linter, and import sorter.
4. Use ty for static type checking; do not add mypy.
5. Use `pathlib.Path` for filesystem paths.
6. Keep runtime dependencies in `[project].dependencies` when they are required to collect or run
   hardware tests. Keep development-only tools in the `dev` dependency group.
7. Use `yaml-test-params` through its automatically loaded pytest plugin and
   `@yaml_parametrize`; do not add a project `pytest_generate_tests` hook unless integration with
   another generator requires it.

### Tests and Resource Lifecycle

1. Unit tests must not use networks or physical equipment.
2. Integration tests must use fakes and must not open real SSH connections.
3. Only tests under `tests/hardware` may communicate with physical equipment.
4. Hardware tests require `--stand`; unit and integration tests must not require it.
5. Hardware tests call device domain APIs and must not execute SSH commands directly.
6. Session and state-changing fixtures must use `yield` with `try/finally` so cleanup runs after
   failures.
7. Do not run hardware tests unless the user explicitly requests them and a real stand is ready.
8. Keep pytest markers registered and run pytest with `--strict-markers`.

### Hardware Base Test

1. Keep the shared `BaseTest` class in `tests/hardware/base.py`; do not expose it from the
   production `hardware_test` package.
2. Use `BaseTest` only for class-based hardware tests that repeatedly execute, log, or validate DUT
   command-line operations. Prefer plain pytest functions when inheritance adds no value.
3. Implement reusable helpers as class methods. Pass a `Dut` explicitly and do not store a
   `TestStand`, device, transport, logger, command result, or other mutable runtime state on the
   class or in globals.
4. Execute commands only through a public device API; never access `device._transport` or
   construct an SSH client in `BaseTest`.
5. Keep connection lifecycle in pytest fixtures. `BaseTest` must not connect, close, construct, or
   configure stands, devices, or transports.
6. Keep assertions and test-specific expected values in the test layer. Production device APIs
   return `CommandResult` or domain values and must not assert test expectations.
7. Use `run_command` and `check_command` separately when a test has intervening logic; use
   `run_and_check_command` only for the common immediate-check path. Return `CommandResult` so the
   calling test can perform additional validation.
8. Treat arbitrary commands as appropriate only when the DUT CLI is itself the tested public
   interface. Otherwise, hide command strings behind named domain methods on the device.
9. Log command execution details through the module's standard logger at `INFO` level. Keep
   numbered `StepLogger` calls in tests and fixtures so they describe significant scenario actions,
   not internal helper operations. Never pass commands or expected values containing passwords,
   tokens, or other secrets to helpers that log them.
10. Unit-test `BaseTest` with fake transports only. Do not require `--stand`, network access, or
    physical equipment for its tests.
11. When one hardware-test group needs shared behavior or fixtures, place a local `base.py` in
    that group's directory. Its custom base class inherits from `tests.hardware.base.BaseTest`.
12. A group-local base class may define typed class-scoped fixtures as class methods. Put
    `@pytest.fixture(scope="class")` above `@classmethod`, accept `cls` instead of `self`, and
    obtain devices from the injected `TestStand` through logical roles. Do not store runtime state
    on the class; use `yield` with `try/finally` when a fixture changes device state.
13. In test modules, import the group-specific base under the common local name `BaseTest`, for
    example `from tests.hardware.recovery.base import RecoveryBaseTest as BaseTest`.

### Step Logging

1. Log significant test actions through `StepLogger`; do not duplicate its numbering manually.
2. Prefer `func_step_logger`, whose numbering restarts for each test function.
3. Use `cls_step_logger` only when numbered steps intentionally continue between methods of one
   test class.
4. Step logs supplement assertions and must not replace validation of expected results.
5. Never write passwords, tokens, `SecretStr` values, or other secrets to step messages.

### Timeouts and Test Artifacts

1. Keep the global `pytest-timeout` limit enabled for unit, integration, and hardware tests.
2. Override the 120-second default with `@pytest.mark.timeout(...)` only when a test has a
   justified longer or shorter runtime.
3. Do not force the timeout method to `thread` without a platform-specific requirement because
   process termination may prevent fixture teardown and hardware cleanup.
4. Let the project pytest plugin create one `artifacts/<run-id>/` directory containing
   `pytest.log` and `reports/junit.xml`; tests must not hardcode a run-directory name.
5. Treat `artifacts/latest.log` only as a stable link to the most recently started session log;
   use a run-specific `pytest.log` when results from parallel sessions must be distinguished.
6. Treat JUnit XML as the machine-readable test result and `pytest.log` as the human-readable
   diagnostic log.
7. Keep generated artifacts out of Git and use `./scripts/clean-artifacts.sh` when cleanup is
   required.

### Docker

1. Keep the Docker image reproducible from `uv.lock` and based on Python 3.14.
2. Keep `.git`, `.env`, credentials, local virtual environments, caches, and generated artifacts
   out of the Docker build context.
3. Run only unit and integration tests in the default container command; never run hardware tests
   implicitly.
4. Require explicit runtime injection of credentials, trusted SSH host keys, network access, and
   physical-device mounts for containerized hardware tests.
5. Do not treat the container as a replacement for `./scripts/ci.sh`; the image intentionally has
   no Git metadata required by pre-commit and the final worktree-diff check.
6. Do not add Docker Compose until the project requires multiple cooperating services.

## Required Verification

After changing files, run the narrowest relevant check first. Before handing off a completed
change, run the full non-hardware quality gate:

```bash
./scripts/ci.sh
```

Do not run the commands contained in `scripts/ci.sh` separately unless diagnosing a failure. The
script already runs `uv sync --locked`, all pre-commit hooks, Ruff, ShellCheck, ty, unit and
integration tests, creates the standard pytest artifacts, and verifies that hooks leave no
unstaged changes.

Additional requirements:

1. Run `uv lock` after dependency metadata changes and verify `uv sync --locked` succeeds.
2. Run ShellCheck through pre-commit for shell script changes.
3. Run the relevant YAML-parametrized test with `-vv` after changing its models or YAML cases.
4. If a pre-commit hook modifies files, accept the intended changes, stage them, and repeat the
   hooks until a second run passes without changes.
5. Do not report success when a required check was skipped or failed. State the exact reason when
   a check cannot be run.
6. Never include hardware tests in the ordinary pre-commit or CI quality gate.

## Commit Message Rules

Follow the existing linear commit history style:

1. Use an English Conventional Commit subject: `<type>: <imperative summary>`.
2. Prefer the existing types: `feat`, `fix`, `refactor`, and `chore`.
3. Keep the subject short, lowercase after the type, and without a trailing period.
4. Do not add a scope unless it materially clarifies a broad or ambiguous change.
5. Base the message on the staged diff (`git diff --cached`), not on unrelated working-tree changes.
6. For broad commits, name the dominant user-visible change in the subject and put supporting refactors, docs, or tests in the body only when needed.
