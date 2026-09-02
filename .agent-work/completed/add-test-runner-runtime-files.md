# Add test-runner runtime files

Added `TEST_RUNNER_ENV_FILE` and `TEST_RUNNER_KNOWN_HOSTS_FILE` to the Compose service environment,
mounted the test environment file read-only for the nested Docker CLI, and documented both paths
in `.env.example`.

Verification passed:

- `docker compose config --quiet`
- `./scripts/ci.sh`
