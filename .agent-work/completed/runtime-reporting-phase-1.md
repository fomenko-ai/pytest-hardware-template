# Runtime/reporting separation: phase 1

Owner: /root
Status: complete

## Scope and authorization

User authorized phase 1 of .agent-work/completed/runtime-reporting-implementation-plan.md after the
ADR discussion. Reporting belongs in existing tests/conftest.py; no root conftest,
runner changes, or legacy compatibility. Existing staged changes from prior tasks
were inspected and must be preserved. No other active task file existed.

## Implementation decisions

- Optional --run-id and --artifacts-root inputs; root defaults to project artifacts.
- Runtime directly creates a new session directory, rejects reuse and unsafe IDs,
  and exposes it only after successful creation.
- Move report setup, presentation, logger policy and metadata adapters to tests/conftest.py.
- Put pytest-html in a reporting group enabled by default alongside dev.

## Plan and verification

Implement main runtime/configuration changes, verify with isolated runtime/reporting
probes, and present concrete main-code changes before editing tests as AGENTS.md requires.
Update lock/documentation, then run required CI. Phase 1 is not complete until
approved test updates and all relevant checks pass. No hardware tests may run.

Main code implemented and 11 existing reporting integration cases passed with both
optional groups installed. uv lock and uv sync --locked passed. User approved the
remaining implementation and requested using the actual module logger name; changed
the project policy logger to logging.getLogger(__name__). Test updates now authorized.

Focused runtime and reporting tests pass: 52 cases with the optional Allure and
ReportPortal groups installed. Documentation now describes the implemented
runtime/reporting boundary, explicit identity/root options, and the real policy location.

## Result

Phase 1 is complete. The runtime allocates and describes pytest sessions independently
of reporters. The template policy in tests/conftest.py preserves the existing log, JUnit,
HTML, Allure, and ReportPortal behavior. pytest-html is a project reporting dependency.

Verification:

- focused runtime/reporting set: 52 passed;
- Ruff and ty checks for changed Python files: passed;
- ./scripts/ci.sh: passed; hardware tests were not run.
