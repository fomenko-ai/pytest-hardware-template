---
id: custom-entities
status: complete
owner: codex
branch: current
updated: 2026-10-23
issue: null
---

# Explicit custom devices and transports

## Result

Implemented the user-approved explicit composition architecture in
[ADR 0003](../../docs/decisions/0003-explicit-custom-entity-factories.md): generic strict inventory
models, a typed loader adapter, factory protocols, built-in adapters, and injected StandFactory.
Existing YAML and create_* functions remain supported. Template fixtures now accept stand_factory.

Added the [custom entity guide](../../docs/custom-entities.md), diagrams, settings/YAML examples,
a typed project-owned example, README links, and add-custom-device/add-custom-transport skills.
Updated inventory skill discovery to include project factories. Implementation details and the
extension workflow are maintained in the guide and ADR rather than this completed work record.

Added 22 fake-only integration cases covering all four built-in/custom device/transport
combinations, custom field preservation, credentials, invalid schemas, cross-file IDs, identity
reuse, timeout selection, unsupported commands, failure cleanup, and isolated pytest fixture
injection on test success and failure. No hardware tests or real connections were run.

## Verification

- Existing focused inventory/factory checks: 35 passed before test-layer changes.
- Extended inventory/factory checks: 53 passed; complete new extension suite: 22 passed.
- Both new skill-creator validators and local documentation/skill links: passed.
- ./scripts/ci.sh: passed after accepting Ruff formatting and fixing test regex/literal findings;
  locked sync, all pre-commit hooks, Ruff, ShellCheck, ty (including examples), and both suites pass.
- Final staged diff whitespace check: passed. Intended changes staged; no commit created.
