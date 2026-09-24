---
id: allow-http-runner-public-url
status: completed
owner: codex
branch: null
updated: 2026-09-24
issue: null
---

# Allow HTTP runner public URL

`TEST_RUNNER_PUBLIC_URL` now accepts HTTP for trusted internal stand networks while still rejecting
credentials, query strings, and fragments. `TEST_RUNNER_OIDC_ISSUER` remains HTTPS-only.

Verification:

- Focused authentication tests: 18 passed; one upstream AnyIO deprecation warning.
- `./scripts/ci.sh`: passed.
