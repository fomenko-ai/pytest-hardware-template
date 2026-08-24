#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Run one named hardware-test scenario from a pre-built Docker image.

Usage:
  ./scripts/run-hardware-tests.sh \
    --image IMAGE \
    --inventory PATH/TO/STANDS.YAML \
    --stand STAND \
    --scenario SCENARIO \
    [--artifacts DIRECTORY] \
    [--env-file FILE] \
    [--known-hosts FILE] \
    [--network NETWORK] \
    [--device HOST_DEVICE[:CONTAINER_DEVICE[:PERMISSIONS]]]... \
    [--pull always|missing|never]

The selected image must contain this project and the named scenario under
test-runs/scenarios/. Inventory paths referenced by stands.yaml are resolved from the
mounted inventory directory. Credentials and host access are supplied only at runtime.
EOF
}

fail() {
    echo "Error: $*" >&2
    exit 2
}

require_value() {
    local option="$1"
    local value="${2-}"

    [[ -n "${value}" ]] || fail "${option} requires a value"
}

absolute_directory() {
    local directory="$1"

    (cd "${directory}" && pwd -P)
}

absolute_file() {
    local file="$1"
    local directory
    local filename

    directory="$(dirname "${file}")"
    filename="$(basename "${file}")"
    printf '%s/%s\n' "$(absolute_directory "${directory}")" "${filename}"
}

IMAGE=""
INVENTORY=""
STAND=""
SCENARIO=""
ARTIFACTS="artifacts"
ENV_FILE=""
KNOWN_HOSTS=""
NETWORK=""
PULL_POLICY="missing"
declare -a DEVICES=()

while (($# > 0)); do
    case "$1" in
        --image)
            require_value "$1" "${2-}"
            IMAGE="$2"
            shift 2
            ;;
        --inventory)
            require_value "$1" "${2-}"
            INVENTORY="$2"
            shift 2
            ;;
        --stand)
            require_value "$1" "${2-}"
            STAND="$2"
            shift 2
            ;;
        --scenario)
            require_value "$1" "${2-}"
            SCENARIO="$2"
            shift 2
            ;;
        --artifacts)
            require_value "$1" "${2-}"
            ARTIFACTS="$2"
            shift 2
            ;;
        --env-file)
            require_value "$1" "${2-}"
            ENV_FILE="$2"
            shift 2
            ;;
        --known-hosts)
            require_value "$1" "${2-}"
            KNOWN_HOSTS="$2"
            shift 2
            ;;
        --network)
            require_value "$1" "${2-}"
            NETWORK="$2"
            shift 2
            ;;
        --device)
            require_value "$1" "${2-}"
            DEVICES+=("$2")
            shift 2
            ;;
        --pull)
            require_value "$1" "${2-}"
            PULL_POLICY="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            fail "unknown option '$1'"
            ;;
    esac
done

[[ -n "${IMAGE}" ]] || fail "--image is required"
[[ -n "${INVENTORY}" ]] || fail "--inventory is required"
[[ -n "${STAND}" ]] || fail "--stand is required"
[[ -n "${SCENARIO}" ]] || fail "--scenario is required"
[[ "${IMAGE}" != -* ]] || fail "invalid image reference: ${IMAGE}"
[[ -f "${INVENTORY}" ]] || fail "inventory file does not exist: ${INVENTORY}"
[[ "${STAND}" =~ ^[[:alnum:]][[:alnum:]_.-]*$ ]] || fail "invalid stand name: ${STAND}"
[[ "${SCENARIO}" =~ ^[[:alnum:]][[:alnum:]_-]*$ ]] || fail "invalid scenario name: ${SCENARIO}"
[[ "${PULL_POLICY}" =~ ^(always|missing|never)$ ]] || fail "invalid pull policy: ${PULL_POLICY}"

if [[ -n "${ENV_FILE}" ]]; then
    [[ -f "${ENV_FILE}" ]] || fail "environment file does not exist: ${ENV_FILE}"
fi
if [[ -n "${KNOWN_HOSTS}" ]]; then
    [[ -f "${KNOWN_HOSTS}" ]] || fail "known-hosts file does not exist: ${KNOWN_HOSTS}"
fi

command -v docker >/dev/null 2>&1 || fail "docker is not available"

mkdir -p "${ARTIFACTS}"
ARTIFACTS="$(absolute_directory "${ARTIFACTS}")"
INVENTORY="$(absolute_file "${INVENTORY}")"
INVENTORY_DIRECTORY="$(dirname "${INVENTORY}")"
readonly INVENTORY_DIRECTORY
INVENTORY_FILENAME="$(basename "${INVENTORY}")"
readonly INVENTORY_FILENAME

declare -a DOCKER_ARGS=(
    run
    --rm
    --pull "${PULL_POLICY}"
    --volume "${INVENTORY_DIRECTORY}:/runtime/inventory:ro"
    --volume "${ARTIFACTS}:/app/artifacts"
)

if [[ -n "${ENV_FILE}" ]]; then
    ENV_FILE="$(absolute_file "${ENV_FILE}")"
    DOCKER_ARGS+=(--env-file "${ENV_FILE}")
fi
if [[ -n "${KNOWN_HOSTS}" ]]; then
    KNOWN_HOSTS="$(absolute_file "${KNOWN_HOSTS}")"
    DOCKER_ARGS+=(--volume "${KNOWN_HOSTS}:/root/.ssh/known_hosts:ro")
fi
if [[ -n "${NETWORK}" ]]; then
    DOCKER_ARGS+=(--network "${NETWORK}")
fi
for device in "${DEVICES[@]}"; do
    DOCKER_ARGS+=(--device "${device}")
done

DOCKER_ARGS+=(
    "${IMAGE}"
    uv run pytest tests/hardware
    --scenario "${SCENARIO}"
    --inventory "/runtime/inventory/${INVENTORY_FILENAME}"
    --stand "${STAND}"
)

echo "Running hardware scenario '${SCENARIO}' on stand '${STAND}' from image '${IMAGE}'"
echo "Artifacts directory: ${ARTIFACTS}"
exec docker "${DOCKER_ARGS[@]}"
