# Docker env-file JSON quoting

## Result

Removed shell-style single quotes around the console-credentials JSON in `.env.example`, because
Docker `--env-file` passes those quote characters through as part of the value.

## Verification

`./scripts/ci.sh` passed, including pre-commit, Ruff, ShellCheck, ty, and all non-hardware tests.
