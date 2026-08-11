#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PROJECT_ROOT
readonly ARTIFACTS_DIR="${PROJECT_ROOT}/artifacts"

mkdir -p "${ARTIFACTS_DIR}"
find "${ARTIFACTS_DIR}" -mindepth 1 ! -name .gitkeep -delete

echo "Artifacts cleared: ${ARTIFACTS_DIR}"
