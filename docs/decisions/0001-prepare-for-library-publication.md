# 0001: Develop the template toward future library publication

Status: accepted
Date: 2026-08-11
Task: N/A

## Context

The project was created as a reusable template for hardware test automation. Developing and
maintaining that template is its primary purpose.

Projects created from a copied template otherwise have to receive shared fixes, updates, and new
features through repeated manual or AI-agent-assisted transfers. As their number grows, keeping
them aligned becomes increasingly expensive. A shared library can reduce that cost, but the
project's public Python API is still evolving. Publishing it before its boundaries and naming
conventions settle would create premature compatibility obligations.

## Decision

Develop the project primarily as a reusable template for hardware test automation. Its
architecture, documentation, and tooling must first support creating and maintaining projects
based on that template.

In the longer term, after the public API has been formed through real use, reviewed, and
stabilized, publish the reusable part of the project as a Python library. The library's primary
purpose will be to distribute shared fixes, updates, and new functionality to projects based on
the template with less manual transfer and maintenance effort.

Keep reusable production code in the `hardware_test` package, maintain explicit public boundaries,
and avoid coupling library candidates to repository-specific tests, inventory, credentials, or
deployment details. Until the API is deliberately reviewed and declared stable, continue treating
the project as a template and do not promise public library API compatibility.

The publication decision, package distribution details, versioning policy, and initial stable API
will be defined separately when there is enough usage experience to make those choices.

## Alternatives Considered

### Remain only a repository template

This avoids package compatibility and release-management concerns, but makes shared fixes, updates,
and features depend on copying changes and manually keeping template-based projects synchronized.

### Publish the library immediately

This would enable package-based reuse sooner, but would expose an unsettled API and either burden
the project with premature backward compatibility or require frequent breaking releases.

## Consequences

### Positive

- The project's immediate design remains driven by its primary role as a reusable template.
- Reusable code remains separated from project-specific configuration and hardware scenarios.
- A future library can reduce the cost of distributing shared updates and new functionality.
- Publication can follow a deliberate API review instead of requiring a large structural rewrite.

### Negative

- Some design choices must consider future library consumers before the library exists.
- The project must clearly distinguish internal interfaces from candidates for the public API.
- Library publication, semantic versioning, and compatibility guarantees remain future work.

## Documentation

- `AGENTS.md` defines the current architectural and dependency boundaries.
- Packaging and public API documentation will be added when publication is approved.
