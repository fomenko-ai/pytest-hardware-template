---
id: fix-helper-test-order
status: completed
owner: codex
branch: null
updated: 2026-10-13
issue: null
---

# Fix helper environment assertion

## Result

The ReportPortal test now verifies the adjacent `--env RP_API_KEY` option/value pair without
assuming it is Docker's first environment argument. The production command retains its natural
ordering, including the common analytics opt-out. Repository instructions require helper-local
pytest runs after changes when the helper provides internal tests.

## Verification

- `helpers/test-runner-service`: `uv run pytest` passed (82 tests, one third-party deprecation
  warning).
- `./scripts/ci.sh`: passed with the final changes staged for its clean-diff guard.
