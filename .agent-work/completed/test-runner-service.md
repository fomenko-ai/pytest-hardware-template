---
id: test-runner-service
status: completed
owner: codex
updated: 2026-08-26
---

# Minimal laboratory test runner service

## Result

Added an independently packaged FastAPI service under `helpers/test-runner-service/`. It deploys
with its own `compose.yaml`, permits one build, pull, or hardware-run operation at a time, stores an
atomic current-state snapshot and console log without a database, streams output through SSE, and
provides a lightweight HTML interface and standard pytest artifact downloads.

The service builds Docker argument arrays directly, restricts images through configured prefixes,
and accepts no host paths, networks, devices, credentials, or arbitrary Docker arguments from HTTP
callers. Unit tests use a fake process runner and do not access Docker, networks, or hardware.

## Verification

- Helper Ruff, ty, and 14 unit tests passed.
- `docker compose config` passed.
- `docker compose build` passed.
- `./scripts/ci.sh` passed without hardware tests.
