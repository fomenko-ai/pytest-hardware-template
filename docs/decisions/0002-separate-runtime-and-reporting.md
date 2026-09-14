# 0002: Separate runtime, reporting policy, and the runner contract

Status: accepted
Date: 2026-09-13
Task: N/A

## Context

The project is a reusable hardware test automation template whose shared functionality may
eventually be published as a Python library.

[ADR 0001](0001-prepare-for-library-publication.md) requires separating reusable mechanisms from
project-specific configuration without introducing premature API compatibility guarantees.

The pytest plugin currently allocates the run directory, collects shared context, and forces
local report configuration. The external runner discovers a completed session's directory by
looking for `reports/junit.xml`.

This makes reporting conventions an implicit integration contract. Disabling JUnit can prevent
directory discovery and Allure publication even when the process completes and produces other
results. A JUnit parsing error can also replace the operation outcome and discard an exit code
that has already been obtained.

The runtime mechanism should remain shared while projects choose independent reporting policies
and the runner no longer requires a particular report file.

## Decision

### Pytest session identity

The reusable runtime owns pytest session identity.

The runtime generates a `run_id` when the caller does not supply one. It may accept an external
identifier when a caller needs to correlate a session with an external operation in advance.

A supplied identifier is validated and used unchanged. An invalid or conflicting external
identifier causes an explicit error; the runtime must not silently replace it.

The transport used to supply `run_id`, the format of generated identifiers, and collision
handling during automatic generation remain implementation details.

### Runner operations and pytest sessions

`operation_id` identifies a runner operation; `run_id` identifies a pytest session. They remain
distinct concepts.

With the current one-test-operation-to-one-session relationship, their values may be equal.
Equality is an implementation detail, not a required contract.

This decision does not introduce multiple sessions per operation or retry support.

### Session directory

The project or caller specifies the artifacts root. The runtime owns creation of the individual
pytest session directory within that root.

The runtime:

- creates a new session directory directly, independently of report creation;
- does not reuse an existing session directory;
- validates externally supplied identifiers;
- prevents the session directory from escaping the artifacts root;
- exposes the directory through its API only after successful creation.

The caller may prepare the artifacts root but must not pre-create the individual session
directory.

The caller must be able to determine the expected session location unambiguously from the agreed
root and identity. The mechanism for communicating these inputs remains an implementation detail.

An expected path provides correlation; it does not prove that pytest initialized its runtime.
Under exclusive runtime ownership of session-directory creation, existence of the new directory
confirms allocation, not test execution or successful collection.

If the process exits before creating the directory, the runner still records its result and
operation diagnostics. No additional runtime marker is introduced for this purpose.

### Shared context and metadata

The runtime collects common run context once and exposes it to consumers. The candidate API is:

```python
get_run_directory(config)
get_run_metadata(config)
```

Context may include the run identifier, Python and pytest versions, an available Git revision,
the selected stand and scenario, and the resolved marker sequence.

Git revision denotes HEAD of the checkout where tests execute. It does not automatically identify
the library version, DUT firmware, or the verified source revision of a Docker image.

Metadata collection:

- does not depend on reporting plugins being installed;
- does not create reports;
- does not configure reporters;
- does not publish data to external systems.

The API's scope and stability guarantees will be defined separately under ADR 0001.

### Project reporting policy

The consuming project decides:

- which reporting plugins are enabled;
- which report formats are produced;
- where results are stored within the session directory;
- how logs and reports are presented;
- how shared context is published to JUnit, HTML, Allure, ReportPortal, or other systems.

Automatic configuration of these pytest options belongs to project policy:

```python
config.option.log_file
config.option.xmlpath
config.option.htmlpath
config.option.self_contained_html
```

Project integrations convert runtime context into JUnit properties, pytest-html metadata,
Allure `environment.properties`, ReportPortal attributes, and other representations.

The template retains its default reporting policy:

```text
pytest.log
reports/junit.xml
reports/report.html
```

These paths are template conventions, not public library API. Projects may change or disable
the corresponding reports.

### Library logging

Library code may emit diagnostic messages through standard logging and provide reusable helpers
such as `StepLogger`. Library logging does not require consumers to create a particular file or
use a particular reporter.

Project log/report policy owns:

- destination files and handlers;
- configuration of third-party loggers;
- creation of `pytest.log` and `latest.log`;
- run-header and summary presentation;
- automatic presentation of test outcomes in logs.

Diagnostics of the library's own mechanisms stay in the library. Execution mechanisms such as
`stop_on_fail` do not become reporting policy merely because they emit log messages.

### External runner contract

The runner explicitly correlates a test operation with a pytest session and knows its expected
artifact location before execution.

Session-directory discovery does not depend on JUnit, HTML, Allure, or another specific result.
A policy with only `pytest.log` and Allure must still let the runner:

- identify the session;
- locate its directory;
- obtain the launched command's result;
- persist operation state;
- publish Allure when that capability is enabled.

The required filesystem contract defines session correlation and directory location relative
to the agreed artifacts root. Deployment configuration supplies concrete host/container paths.
Report filenames are not constants of the required protocol.

### Optional runner reporting capabilities

The runner remains aware of the reporting types it supports. It may parse JUnit, serve local
logs and HTML, publish Allure, and retrieve information from ReportPortal. These are optional
service capabilities.

Local report paths are explicitly configured relative to the session directory and must not
escape it. The template's default configuration corresponds to:

```text
pytest log:      pytest.log
JUnit:           reports/junit.xml
HTML:            reports/report.html
Allure results:  allure-results
```

A disabled report has no configured path. Its absence does not prevent processing other results
or recording operation state. Configuration names and their transport remain implementation
details.

This decision does not introduce universal artifact discovery or arbitrary-format processing.

### Process results and reporting errors

The runner preserves the original exit code of the launched command and owns its interpretation.
When the command executes pytest, that code represents pytest termination, including collection,
configuration, and internal errors, rather than only individual test outcomes. Container or
command startup errors are distinct from pytest results.

Once obtained, the command's exit code is preserved independently of subsequent report handling.
JUnit parsing failures, Allure publication failures, and ReportPortal lookup failures are
recorded separately. They do not by themselves turn a completed execution into
`infrastructure_error` or discard its exit code.

A missing or malformed JUnit report may make the summary unavailable but must not prevent
recording the process result or handling other reports.

If a reporting plugin disrupts pytest execution itself, the runner preserves the actual result
it receives. Reconstructing a hypothetical test outcome is not its responsibility.

The runner continues to own process control, cancellation, timeouts, and recovery of its state.
Runtime metadata does not become a second source of operation state. Detailed exit-code
classification and UI presentation remain separate implementation concerns.

### Virtual stand and deployment configuration

The virtual DUT depends only on the hardware/environment contract. It has no knowledge of JUnit,
HTML, Allure, or report-directory layout.

`virtual-stand/compose.yaml` remains the deployment configuration for the template's standard
scenario. It may configure mounts, networking, the runner, publisher containers, and other
components.

Deployment configuration implements the agreed helper protocol in a particular environment;
it does not define library API.

### Responsibility categories

| Category | Responsibility |
| --- | --- |
| Library mechanisms | Session identity, directory allocation, shared context, reusable logging |
| Template conventions | Default reporters, filenames, presentation, publication |
| Helper-service protocol | Operation/session correlation, output location, process result, configured optional reporting capabilities |
| Deployment configuration | Concrete paths, mounts, networks, images, runner and publisher deployment |

These categories describe responsibility boundaries; they do not require additional software
layers.

### Deferred mechanisms

This decision does not introduce:

- a universal artifact registry;
- a mandatory `run.json` manifest;
- a generic model of every possible artifact;
- a shared lifecycle API or state machine for pytest, the runner, and reporting systems.

Explicit identity, a known session directory, the process result, and configured optional report
paths meet current requirements.

Without a manifest, historical-result access depends on agreed path configuration. Changes to
that configuration must account separately for previously created artifacts.

Revisit deferred mechanisms only when demonstrated requirements exceed this minimal contract.

## Alternatives Considered

### Keep reporting in the library plugin

This simplifies distribution of standard configuration across projects, but makes selected
reporters and their configuration mandatory for consumers and retains the runner's dependency
on a particular reporting policy.

### Move all run context into the project

This gives projects full control, but duplicates identity, directory, and metadata handling.
It makes common integrations and distribution of shared fixes harder to maintain.

### Introduce a manifest and artifact registry immediately

This lets each run describe arbitrary artifacts and retain historical paths. However, it adds a
schema, registration rules, and handling of incomplete records. No current reporting capability
requires a problem to be solved this way instead of using explicit correlation and configured
paths.

## Consequences

### Positive

- Projects can change reporting policy without changing the library.
- The runner supports sessions without JUnit or HTML.
- The shared session directory is independent of enabled reporters.
- Report-processing errors do not hide a completed process result.
- Metadata is collected once and reused.
- The template retains convenient default reporting.
- Reporting-plugin dependencies are localized to project integrations.
- Deployment-specific settings remain separate from library API.

### Negative

- Runner report paths must match project policy.
- Path changes must account for historical-artifact access.
- Reporting integrations remain maintained template code.
- The runner remains aware of supported report types.
- Helper-protocol changes require coordinated runner and test-image updates.
- Arbitrary and dynamic artifact sets have no generic discovery mechanism.
- Directory existence does not provide detailed pytest execution-stage information.

## Documentation

After implementation, update:

- [AGENTS.md](../../AGENTS.md): runtime, logging, and reporting boundaries;
- [README.md](../../README.md): template defaults and runtime API;
- [runner guide](../../helpers/test-runner-service/README.md): session correlation, process results,
  and optional report paths;
- [Allure guide](../../helpers/allure/README.md) and
  [ReportPortal guide](../../helpers/reportportal/README.md);
- [virtual-stand guide](../../helpers/virtual-stand/README.md): the standard deployment scenario.

The migration described by this decision is complete. This ADR supplements ADR 0001 and does not
establish future library API stability guarantees.
