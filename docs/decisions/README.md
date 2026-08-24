# Architecture decision records

This directory records significant, long-lived architectural choices when their context,
alternatives, and consequences would not be clear from the code alone.

Create a record only when a decision affects multiple architectural components, establishes a
lasting convention, chooses between meaningful alternatives, or would be costly to reverse. Do not
create records for routine implementation details.

## Workflow

1. Copy `template.md` and assign the next four-digit number.
2. Use the filename `<number>-<short-title>.md`.
3. Start with status `proposed` and obtain the approval required by `AGENTS.md`.
4. Change the status to `accepted` when the decision is approved.
5. Update regular project documentation to describe the resulting current behavior.
6. If a later decision replaces it, mark the old record `superseded` and link both records.

Decision records explain why a choice was made. Regular documentation remains the source for how
the project currently works.

## Samples for template-based projects

The files in `examples/` are starting points for projects created from this template. They are not
decisions made by this repository. Copy a relevant sample into the downstream project's own
`docs/decisions/` directory, adapt it to the project's actual context, assign its local decision
number, and approve it through that project's workflow.

- `examples/0001-adopt-template-before-library-publication.md` covers using the copied template now,
  reviewing upstream changes explicitly, and evaluating migration after a shared library is
  published.
