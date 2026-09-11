---
id: reportportal-integration
status: completed
owner: codex
branch: main
updated: 2026-09-11
---

# Optional ReportPortal integration

Implemented the optional pytest-reportportal group, Docker image selection, runner settings,
separate report status and links, and independent ReportPortal deployment documentation.
All 12 image versions match official ReportPortal 26.0.5, as requested. Library production code
remains independent of ReportPortal. The README includes local/server setup and an explicit
virtual-stand walkthrough with network attachment and API/report checks.

Verification:
- Final ./scripts/ci.sh passed (default optional-agent cases skip when groups are absent).
- With ReportPortal and Allure groups installed: 166 unit/integration tests passed.
- Runner: ty passed and 55 tests passed with strict markers and a 120-second timeout.
- Real pytest agent lifecycle, StepLogger messages, local artifacts and secret-log protection
  checked with a fake client; network connections prohibited in those integration tests.
- Official image-version equality and Compose configuration checks passed, including the
  documented virtual-stand override with dummy settings.
- No hardware tests, live reporting, user .env edits or full service deployment performed.

User approved implementation after reviewing ADR boundaries and image policy, then requested
continuation with test changes. No commit created; changes staged for review.

Follow-up: corrected the documented API probe to use `uv run --no-sync python`, matching
the runner Dockerfile's virtual environment, and clarified its working directory.
The user reported ModuleNotFoundError with system Python. Follow-up ./scripts/ci.sh passed;
the live API probe remains for the user to run against their configured deployment.

The user confirmed live reporting works after changing the reporting user's project role
from OPERATOR to MEMBER. Simplified the successful UI status to "ReportPortal: report generated";
incomplete/unavailable statuses retain their diagnostic messages. This also applies to saved
operations without rerunning tests. Follow-up git diff --check and ./scripts/ci.sh passed.

Added the four user-provided ReportPortal screenshots to the runner README's UI preview,
following the Allure examples: launch list, test results, logs, and dashboard statistics.
Screenshot captions were checked against the images. git diff --check and ./scripts/ci.sh passed.

At the user's request, the UI now shows ReportPortal status text only for incomplete or
unavailable reports. Finished launches retain their report link without a success message.
Verification: git diff --check and ./scripts/ci.sh passed.
