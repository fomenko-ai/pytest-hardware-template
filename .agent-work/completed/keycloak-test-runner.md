# Keycloak authentication for test runner

Implemented optional `disabled`, `local`, and `keycloak` authentication modes. Keycloak mode uses
OIDC Authorization Code with PKCE for browser SSO, locally validated JWTs with cached JWKS for API
clients, and viewer/operator authorization. Detailed flows and configuration are documented in
`helpers/test-runner-service/docs/authentication.md`.

Verification:

- `./scripts/ci.sh`: passed.
- Full test-runner-service suite: 79 passed.
- Focused auth/OIDC suite: 18 passed.
- Ruff and ty checks: passed.

The Starlette TestClient suite emits one upstream AnyIO deprecation warning.
