# Ordered test runs

The project supports three complementary ways to save or select pytest runs:

- `-m` uses a standard pytest marker expression without changing collection order;
- `-M` selects registered marker groups and orders them as declared on the command line;
- `-S` loads an ordered marker scenario from YAML;
- `@file` uses pytest's standard argument-file functionality.

These mechanisms organize test execution. They do not own test data, physical inventory, runtime
settings, or credentials.

## Directory structure

Keep named scenarios and pytest argument files separate:

```text
test-runs/
├── scenarios/
│   └── framework.yaml
└── pytest-args/
    └── framework.txt
```

Files under `configs/` remain data for individual test cases. Files under `inventory/` remain the
source of physical devices, stands, transports, and topology.

## Command-line marker sequences

Use `-M` or `--marker-sequence` with comma-separated marker names:

```bash
uv run pytest -M unit,integration
uv run pytest --marker-sequence unit,integration
```

The option performs one pytest collection, selects items with the requested markers, and orders
the resulting groups. Pytest's original collection order is preserved inside each group, including
the order of parameterized items.

The ordinary pytest `-m` option has different semantics:

```bash
uv run pytest -m "unit or integration"
```

It selects matching tests but does not use the expression to define execution order.

## Named scenarios

Store reusable sequences under `test-runs/scenarios/<name>.yaml`. For example,
`test-runs/scenarios/framework.yaml` contains:

```yaml
name: framework
markers:
  - unit
  - integration
```

The scenario name must match the filename. Run it with:

```bash
uv run pytest -S framework
uv run pytest --scenario framework
```

Scenario names may contain letters, numbers, underscores, and hyphens. Paths, absolute names, and
parent-directory references are rejected.

## Marker registration and validation

Every marker used by `-M` or a named scenario must be registered in
`[tool.pytest.ini_options].markers`:

```toml
[tool.pytest.ini_options]
markers = [
    "recovery_prepare: prepare the device recovery scenario",
    "recovery_check: verify device recovery",
]
```

Static registration preserves the protection provided by `--strict-markers`. Add the marker
registration, test annotation, and scenario entry in the same project change.

A scenario run fails with a pytest usage error when:

- a requested marker is not registered;
- the sequence is empty or contains an invalid marker name;
- the same marker occurs more than once;
- no collected test matches a required marker;
- one selected test belongs to multiple steps;
- `-M` and `-S` are supplied together.

A test may still combine one scenario step with ordinary property markers:

```python
import pytest


@pytest.mark.recovery_check
@pytest.mark.slow
@pytest.mark.destructive
def test_factory_reset() -> None:
    ...
```

## Failure and cleanup behavior

Ordered runs use pytest's fail-fast behavior. A failure during fixture setup, the test call, or
fixture teardown stops the remaining scenario items.

Do not rely on a final test step for mandatory hardware cleanup because fail-fast may prevent that
test from running. Put required restoration in a state-changing `yield` fixture with `try/finally`:

```python
from collections.abc import Iterator

import pytest

from hardware_test.stand import TestStand


@pytest.fixture
def prepared_device(stand: TestStand) -> Iterator[None]:
    prepare_test_state(stand.dut)
    try:
        yield
    finally:
        restore_test_state(stand.dut)
```

Here, `prepare_test_state` and `restore_test_state` represent project-specific helpers that use the
public DUT API. Connection ownership remains in the stand fixture.

If cleanup before and after a scenario is itself tested behavior, use two distinct step markers,
such as `clean_before` and `clean_after`. Repeating one marker in a scenario is not supported.

## Hardware runs

Scenario files must not contain stand names, inventory paths, topology, or credentials. Pass the
physical runtime selection separately:

```bash
uv run pytest -S hardware-recovery --stand stand-01
uv run pytest -M clean_before,recovery_check --stand stand-02
```

After scenario selection, a run containing any hardware test requires `--stand`. Unit-only and
integration-only scenarios do not require physical equipment.

## Pytest argument files

Use `test-runs/pytest-args/` for saved command-line selections that do not need ordered marker
groups. The included `framework.txt` contains:

```text
tests/unit
tests/integration
--strict-markers
```

Run it using pytest's built-in `@file` syntax:

```bash
uv run pytest @test-runs/pytest-args/framework.txt
```

Keep environment-specific values outside reusable argument files when possible. For example:

```bash
uv run pytest @test-runs/pytest-args/hardware-smoke.txt --stand stand-01
```
