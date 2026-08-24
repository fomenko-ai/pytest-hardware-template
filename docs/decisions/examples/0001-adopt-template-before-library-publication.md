# 0001: Adopt the hardware test template before library publication

Status: proposed
Date: YYYY-MM-DD
Task: PROJECT-000

> This is a sample decision for a project created from `pytest-hardware-template`. Copy it into
> that project's `docs/decisions/` directory, replace the placeholders, adapt the text to the
> project's actual constraints, and obtain project-specific approval. It is not a decision record
> of the template repository itself.

## Context

This project uses `pytest-hardware-template` as the starting point for its hardware test
automation. The template provides reusable architecture, tooling, and examples, but its shared
Python API is still evolving and has not yet been published as a compatibility-guaranteed library.

The project needs to develop its product-specific tests, devices, inventory, and configuration
now. Waiting for a future library would delay that work. At the same time, copying the template
creates a maintenance cost: useful fixes and features from the template must be reviewed and
adapted explicitly, while local changes can make later updates or migration more difficult.

## Decision

Use the current repository template as the foundation of this project. Keep project-specific
hardware scenarios, inventory, credentials, deployment details, and device behavior in this
project; do not assume that they will become part of the future shared library.

Until a library is published, adopt relevant template fixes and features through deliberate,
reviewed changes. Do not automatically merge or copy template changes. Preserve the template's
documented architectural boundaries where they remain suitable, and record intentional
project-specific deviations when they are significant and long-lived.

Avoid depending on undocumented internals merely to make a future migration easier. Keep imports
and extensions aligned with explicit package boundaries, and isolate project-specific integration
code from reusable framework code where practical.

When the shared library is published with a defined public API and compatibility policy, evaluate
migration in a separate decision. That evaluation must compare the published API with the
project's actual usage, identify local deviations, and define versioning, rollout, and rollback.
This decision does not commit the project to migrating before that assessment.

## Alternatives Considered

### Wait for the shared library

This could avoid some temporary copying and later migration work, but it would block project
delivery on an unpublished library whose API and release date are not yet defined.

### Copy the template and stop following its development

This gives the project complete independence and avoids ongoing update reviews, but the project
would have to maintain all shared fixes and improvements itself and would likely become more
expensive to migrate later.

### Build a separate project-specific framework immediately

This gives full control over the API, but duplicates framework design and maintenance before the
project has demonstrated requirements that justify a separate solution.

## Consequences

### Positive

- Product-specific hardware testing can begin without waiting for library publication.
- Template updates are adopted only after their relevance and compatibility are reviewed.
- Clear boundaries reduce accidental coupling and make a future library evaluation more
  manageable.
- The project retains the option to migrate, remain independent, or adopt only part of the future
  library.

### Negative

- Relevant template fixes and features require manual review and adaptation until a library is
  available.
- Local deviations can increase the cost of accepting template updates and migrating later.
- The project may temporarily retain code that a future dependency will replace.
- A separate decision and migration plan will still be required after library publication.

## Documentation

- `<link to the project's architecture or contributor guide>` describes the boundaries retained
  from the template and the approved local deviations.
- `<link to the project's update procedure>` describes how template changes are reviewed and
  adapted.
- `<link to the template source or pinned baseline>` identifies the template version or commit
  from which this project was created.
