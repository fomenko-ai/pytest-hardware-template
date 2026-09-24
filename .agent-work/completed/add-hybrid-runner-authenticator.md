---
id: add-hybrid-runner-authenticator
status: completed
owner: codex
branch: null
updated: 2026-09-24
issue: null
---

# Add hybrid runner authenticator

Restored the single `TEST_RUNNER_AUTH_MODE` design and added
`keycloak_ui_local_api` with a dedicated `KeycloakUILocalAPIAuthenticator`. HTML pages accept only
the Keycloak UI session. API routes use an explicitly supplied local Bearer token; without that
header, they accept the UI session so the browser can call `/v1/*`.

Verification:

- Focused authentication and OIDC tests: 20 passed; one upstream AnyIO deprecation warning.
- `./scripts/ci.sh`: passed.
