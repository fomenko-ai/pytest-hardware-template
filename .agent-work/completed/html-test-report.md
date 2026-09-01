# HTML test report

Implemented self-contained `reports/report.html` generation with `pytest-html`. The runner service
lists the report, serves it inline from `/v1/current/artifacts/report.html`, and links to it from the
web UI. Artifact documentation was updated.

Verification:

- focused pytest-plugin tests: 12 passed;
- focused runner-service tests: 5 passed (one existing Starlette deprecation warning);
- `./scripts/ci.sh`: passed.
