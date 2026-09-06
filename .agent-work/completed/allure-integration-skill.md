# Allure integration skill and guide

Owner: Codex
Status: complete

User approved moving the guide to docs/allure.md, shortening README, and adding
skills/add-allure-integration with UI metadata. No Allure runtime integration is requested.

Reviewed AGENTS.md, existing skills, README, and the completed Allure documentation record.
Existing staged documentation is preserved. The unrelated unstaged change to
helpers/test-runner-service/docs/images/html-report-example.png is outside this task.

Moved the guide to docs/allure.md and added a short README link and skill listing.
Added add-allure-integration with project inspection, workflow questions, implementation,
verification, and UI metadata. No runtime code, dependencies, or tests changed.

Verification: skill-creator quick_validate.py and git diff --cached --check passed.
All ./scripts/ci.sh hooks, including non-hardware tests, passed. The script's final Git diff
check failed solely on the pre-existing unstaged image change noted above. It was not staged
or modified by this task. The skill was reviewed for local, server, and existing-service paths;
no live Allure integration or hardware test was executed.
