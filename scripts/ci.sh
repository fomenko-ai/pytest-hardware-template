#!/usr/bin/env bash
set -euo pipefail

# Disable ReportPortal usage analytics / Google Analytics.
# Security requirement: test execution must not send ReportPortal telemetry to third parties.
export AGENT_NO_ANALYTICS="${AGENT_NO_ANALYTICS:-1}"

uv sync --locked
uv run pre-commit run --all-files
git diff --exit-code
