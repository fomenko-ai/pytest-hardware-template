# Runtime/reporting separation: phase 3

Owner: /root
Status: complete

## Scope and authorization

The user authorized continuing after phase 2. Implement phase 3 from
.agent-work/completed/runtime-reporting-implementation-plan.md: make the runner's supported report paths
optional and keep reporting failures separate from the launched process result.

## Implementation decisions

- Add optional configured paths for pytest log, JUnit, HTML, and Allure results, retaining
  current defaults.
- Validate configured paths as relative descendants of a session directory.
- Keep the existing public artifact names and map them to configured physical paths.
- Record JUnit availability/parsing diagnostics in a dedicated state field without changing
  pytest status or exit code.
- Configure Allure collection with the selected results path and publish only that directory.
- Do not add a generic artifact registry, manifest, or new lifecycle model.

## Plan and verification

Change production code first and present it for approval before changing runner tests. Then
update focused tests and documentation, run the helper suite, and run ./scripts/ci.sh. Never
execute hardware tests.

Main code approved by the user. Tests now cover default and custom paths, disabled report
capabilities, containment validation, malformed JUnit isolation, and continued Allure
publication. Helper Ruff, formatting, and ty pass; the complete helper suite passes 66 tests.

## Result

Phase 3 is complete. Supported report paths are explicit optional capabilities with existing
defaults. Public artifact names map to configured locations. JUnit reporting diagnostics no
longer replace the process outcome or block other reporting integrations.

Verification:

- helper Ruff and formatting: passed;
- helper ty: passed;
- helper test suite: 66 passed;
- ./scripts/ci.sh: passed; hardware tests were not run.
