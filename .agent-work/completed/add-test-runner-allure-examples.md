# Add Test Runner Allure examples

State: complete.

Result:

- the Test Runner README shows the Allure repository branch/report list;
- the README also shows an opened interactive Allure report;
- both examples use the existing helper screenshots.

Verification:

- image references exist;
- `git diff --check` passed;
- `./scripts/ci.sh` passed (including Ruff, ShellCheck, ty, and unit/integration tests).
