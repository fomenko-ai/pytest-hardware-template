---
id: move-examples-to-docs
status: complete
owner: codex
branch: current
updated: 2026-10-23
issue: null
---

# Move custom entity examples into documentation

## Result

Moved the example package from examples/ into docs/examples/ at the user's request. Updated
test imports (including isolated pytest scripts), README/guide/skill links, and ty's include
path. The executable example stays outside the hardware_test wheel; library behavior is unchanged.

## Verification

- Focused custom-entity suite: 22 passed after the move, including isolated pytest imports.
- Changed guide and skill links: all resolve.
- Full ./scripts/ci.sh: passed, including locked sync, Ruff, ShellCheck, ty, and both test suites.
- Changes staged; no commit created. No hardware tests or real connections were run.
