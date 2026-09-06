---
id: virtual-docker-stand
status: completed
owner: codex
branch: null
updated: 2026-09-06
issue: null
---

# Docker virtual hardware stand

## Result

Added `helpers/virtual-stand/`, containing a disposable SSH DUT, runtime-only credential setup,
dedicated inventory, and a Compose deployment integrated with the optional test-runner service.
Added the tracked `virtual-smoke` hardware scenario and command-path test. The standalone runner
Compose deployment now forwards its existing optional Docker network setting.

The emulator stays outside the production package and uses the existing inventory, factories,
device API, lifecycle, and Paramiko transport. Its regenerating SSH key uses the explicitly
documented `warn` policy only on the isolated virtual network.

## Verification

- Settings credential resolution and virtual Compose parsing passed.
- Runner Docker-command tests passed (`4 passed`).
- Local runner API E2E built the main image and ran `virtual-smoke`: `1 passed`, with `pytest.log`,
  `junit.xml`, and `report.html` published. The temporary Compose stack and networks were removed.
- `./scripts/ci.sh` passed through formatting, linting, ShellCheck, ty, and unit/integration tests;
  its first post-format run requested staging before the final worktree check.
