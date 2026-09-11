# Allure adapter integration check

User requested independent verification of the real Allure pytest adapter.
Added a subprocess integration test using the repository reporting hook, generated local
tests, and blocked socket connections. Checks passed/failed/skipped JSON results, failure
details, native Allure steps and attachments, StepLogger output, and local artifacts.
ReportPortal is explicitly disabled. No production code changes or hardware runs required.

The isolated test passed with both groups present and with only Allure installed.
The initial quality gate found a filename collision with unit/test_allure_reporting.py;
renamed the integration module to test_allure_adapter.py. Accepted Ruff formatting.
Final ./scripts/ci.sh passed. Combined adapter checks passed: 3 tests with the Allure and
ReportPortal groups installed. The Allure test skips explicitly when its optional group is
absent. No hardware or live service used.
