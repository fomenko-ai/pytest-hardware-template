# Add native runner token authentication

## Result

Added optional Bearer-token authentication for CI API clients while preserving the existing UI
login and signed-cookie flow. Documented secure GitLab/Jenkins usage and added focused coverage for
valid, invalid, missing, unsupported, and empty-token cases.

## Verification

- `uv run --project helpers/test-runner-service pytest helpers/test-runner-service/tests/test_auth.py -q`: 11 passed.
- `./scripts/ci.sh`: passed after the intended files were staged.
