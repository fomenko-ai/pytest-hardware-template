# Agent work records

This directory keeps short, resumable state for work that may continue in another agent session or
be handed to another contributor. It is operational memory, not the authoritative project
documentation or issue tracker.

## Workflow

1. Copy `template.md` to `active/<issue-id>-<short-name>.md`.
2. Fill in the owner, branch, goal, acceptance criteria, and next action.
3. Keep the record current at significant checkpoints and before ending an unfinished session.
4. Verify recorded claims against Git and the source tree whenever work resumes.
5. Move lasting knowledge into the appropriate project documentation.
6. On completion, reduce the record to its result and verification summary, then move it to
   `completed/`.

Completed records may be deleted after the team-agreed retention period when their outcome is
already preserved in documentation, the issue or pull request, and Git history. Never put secrets,
raw logs, or private reasoning in these records.
