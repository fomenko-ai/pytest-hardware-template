# Runtime and reporting separation: staged implementation plan

Status: completed
Decision: [ADR 0002](../../docs/decisions/0002-separate-runtime-and-reporting.md)

## Scope and preserved behavior

Implement the agreed responsibility boundary while keeping the template's normal invocation and
default artifacts unchanged:

```text
artifacts/<run-id>/pytest.log
artifacts/<run-id>/reports/junit.xml
artifacts/<run-id>/reports/report.html
artifacts/latest.log
```

Preserve header spacing, step logging, summaries, metadata values, optional Allure/ReportPortal,
hardware selection and cleanup, and the non-hardware default Docker command. Preserve current
artifact download routes and the runner's process log. No migration of existing reports is part
of this plan.

Use the existing `tests/conftest.py` for project reporting policy; do not create a root
`conftest.py`. The project is new: compatibility with old test images or old runner versions
is not required. Update the runner and test images together without a compatibility layer.

The phases below are implementation work, not authorization to change code in this documentation
task. For each phase, follow AGENTS.md: obtain any required architectural approval, present main
code before changing tests, run the narrowest relevant verification, then run `./scripts/ci.sh`.
Run helper-specific checks when changing helpers; the repository gate does not substitute for
the runner's own test suite. Never use hardware to verify reporting.

## Phase 1: Separate runtime allocation from template reporting

Likely scope: `src/hardware_test/pytest_plugin.py`, existing `tests/conftest.py`, dependency
configuration, and their focused tests.

- Keep identity, direct session-directory creation, metadata collection, and the two accessors
  in the library candidate. Reject directory reuse and expose only successfully created paths.
- Permit an optional caller-supplied identity and artifacts root; choose their concrete transport
  during implementation. Preserve existing generated IDs and `artifacts/` defaults for manual
  runs. Validate supplied IDs and root containment.
- Move log/JUnit/HTML paths, `latest.log`, report presentation, and metadata publication to
  `tests/conftest.py`. Consolidate optional reporter setup there; leave settings/inventory/stand
  fixtures in their existing test layers. Do not introduce a root `conftest.py`. Preserve hook
  ordering before reporters consume their settings.
- Keep reusable logging helpers and execution behavior such as `stop_on_fail` in the package.
- Make pytest-html a project reporting dependency rather than a required library dependency.
  Select the smallest dependency-group arrangement that keeps current development, CI, and Docker
  commands functional. Regenerate `uv.lock` if dependency metadata changes.

Acceptance: unchanged default artifacts and presentation; library-only use does not require HTML
or publish metadata to reporters; allocation works without reporters; invalid/conflicting IDs
fail without reusing another session's directory; metadata is collected once. Existing Allure
and ReportPortal fake-client tests continue to pass. For invocations under `tests/`, including
the runner's `tests/hardware` target, project options load and reports remain available when
collection fails. No backward-compatibility requirement is imposed on the old runner.

## Phase 2: Give the runner explicit session correlation

Likely scope: runner Docker command construction, worker/state handling, artifact discovery, and
their tests. Adjust deployment/script arguments only where the selected transport requires it.

- Supply the identity/root supported by phase 1 and determine the expected host directory before
  launching the command. Keep operation and session identity conceptually separate; equal values
  are sufficient for the current single-session operation.
- Replace discovery based on new-directory snapshots, JUnit presence, and directory modification
  time with the known directory. The runner prepares the root, not the session directory.
- Check actual directory existence independently of process completion. Preserve process result
  and operation diagnostics when pytest never creates it, is cancelled, or times out.
- Preserve current operation logs, cancellation behavior, and report URLs. Do not add a second
  lifecycle state machine or change detailed exit-code classification in this phase.

Acceptance: default runs behave as before; a run without JUnit still has correctly correlated
artifacts; an early startup failure records its result without inventing artifacts; unrelated
directories cannot be attributed to the operation.

Rollout: update the runner and test images to the new contract together, then rebuild the images.
Do not implement support for old images, image-version detection, a transitional mode, or
fallback to JUnit-based discovery. Default report paths remain unchanged; this does not require
deleting or migrating existing artifacts.

## Phase 3: Make existing report capabilities optional and isolate failures

Likely scope: runner settings, artifact helpers, worker, API/UI, publisher command construction,
and their tests.

- Replace fixed local report paths with optional configured relative paths, preserving current
  defaults. Keep the supported capability set small; do not introduce a generic artifact model.
- Decouple JUnit summary parsing, HTML/log availability, and Allure publication. A missing or
  disabled report must not disable other capabilities.
- Preserve the obtained command exit code through reporting failures. Record missing/malformed
  JUnit diagnostics separately; retain existing Allure/ReportPortal reporting status separation.
- Resolve configured paths inside the session directory. Keep existing public download names
  while mapping them to configured physical paths; determine HTML presentation by capability.
- Preserve the default historical layout. Document that customized paths need coordinated
  configuration for historical access; do not build a history migration subsystem.

Acceptance: default policy, log-only, and log-plus-Allure without JUnit/HTML all work. Malformed
JUnit does not replace the process result or prevent Allure publication. Disabled reports do
not produce misleading links; configured paths cannot escape the session directory.

## Phase 4: Verify the complete migration and update operational documentation

Likely scope: documentation and existing deployment examples; no virtual-DUT behavior changes.

- Run focused runtime/reporting tests and the runner's own tests using local files and fake
  process/reporting clients. Exercise successful runs, test failures, collection errors, missing
  Git, early command failures, cancellation, and reporting failures.
- Install the optional reporting groups for adapter checks so those cases actually execute.
  Run Allure alone, ReportPortal alone, and both together without external service connections.
- Verify standard Docker/script paths and virtual-stand Compose configuration. Keep existing
  defaults; change mounts or inputs only if required by the implemented correlation transport.
- Update AGENTS.md, README, runner/reporting guides, and deployment instructions to describe
  implemented behavior, the current runner contract, reporting policy in `tests/conftest.py`,
  and required image rebuilds. Do not add an old-image compatibility matrix or migration mode.
- Run `uv lock`/`uv sync --locked` for dependency changes, relevant helper checks, and the full
  `./scripts/ci.sh` gate. Apply the repository approval workflow before marking the ADR accepted.

## Explicitly deferred

No manifest, artifact registry, generic artifact schema, shared lifecycle API, multi-session
operations, retries, arbitrary artifact browsing, or redesign of the virtual DUT. Revisit these
only when a concrete consumer cannot use the minimal contract.
