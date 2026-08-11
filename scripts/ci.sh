#!/usr/bin/env bash
set -euo pipefail

uv sync --locked
uv run pre-commit run --all-files
git diff --exit-code
