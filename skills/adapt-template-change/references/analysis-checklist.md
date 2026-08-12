# Migration Analysis Checklist

Use this checklist selectively. Report material findings; do not turn every item into ceremony.

## Source identity

- Record the repository or local path.
- Resolve the tag, commit, pull request head, or snapshot date.
- Identify the exact change or behavior requested.
- Inspect the change diff when history is available.
- Note predecessor changes required by the selected change.

## Target state

- Read repository instructions and the current worktree status.
- Find the local component that owns the same responsibility.
- Identify renames, moved modules, replaced dependencies, and local extension points.
- Check whether the behavior is absent, partial, equivalent, or intentionally rejected.
- Preserve unrelated modified and untracked files.

## Behavioral slice

Trace only applicable layers:

- public API and user workflow;
- domain models and validation;
- settings, inventory, and scenario configuration;
- factories and dependency injection;
- device APIs and transport boundaries;
- pytest options, fixtures, markers, and plugin hooks;
- state changes, teardown, timeouts, and error handling;
- runtime and development dependencies;
- unit, integration, and hardware tests;
- CI, Docker, scripts, documentation, and generated artifacts.

Distinguish required behavior from incidental cleanup in the upstream diff.

## Ownership and risk

Classify each affected target file:

- **template-owned**: infrastructure normally inherited from the template;
- **project-owned**: local devices, inventory, scenarios, and domain behavior;
- **shared**: files such as project metadata, fixtures, and factories that commonly diverge.

For shared and project-owned files, explain how local behavior will be preserved. Flag:

- secret or credential exposure;
- vendor- or organization-specific assumptions;
- public API or configuration incompatibility;
- new runtime dependencies;
- data migrations or destructive changes;
- network or physical-device access;
- cleanup paths that can fail after an exception;
- upstream tests that assert structure rather than required behavior.

## Option comparison

For each viable option, describe:

- behavior delivered;
- production files and dependencies affected;
- compatibility with local architecture;
- expected conflict and maintenance cost;
- test and verification scope;
- deliberate deviations from upstream.

Recommend the smallest option that fully satisfies the requested behavior. Prefer local patterns
over copying an upstream abstraction solely for structural similarity.

## Approval boundary

Before editing, state:

- exact approved behavior;
- expected production files;
- whether dependencies or configuration change;
- whether test changes require a separate approval;
- conditions that would force a revised proposal.

Do not interpret permission to analyze as permission to edit.

## Completion review

- Compare final behavior with the request and relevant upstream behavior.
- Confirm no unresolved conflict markers or rejected patches remain.
- Confirm no secrets or environment-specific values were introduced.
- Run required checks in the order specified by the target repository.
- Record skipped or failed checks exactly.
- Describe partial adoption accurately; do not advance a whole-template revision for a selective
  migration.
