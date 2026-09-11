# Running hardware scenarios from a container

Use the provider-independent launcher to run one named hardware scenario from a pre-built image:

```bash
./scripts/run-hardware-tests.sh \
  --image registry.example.com/hardware-tests@sha256:0123456789abcdef \
  --inventory /opt/hardware-test/inventory/stands.yaml \
  --stand stand-01 \
  --scenario hardware-smoke \
  --artifacts artifacts
```

The registry address, digest, inventory path, stand, and scenario above are placeholders. A real
project supplies them at runtime. Prefer an immutable image digest or a commit-specific tag so a
result can always be associated with the exact test code and locked dependencies that produced it.

## Build and run are separate operations

Build and verify the image before reserving a physical stand:

```text
commit -> non-hardware quality gate -> build and publish image
                                                |
manual or scheduled request -> reserve stand -> run selected scenario
```

The launch script does not build an image, clone source code, reserve a stand, or decide whether a
destructive scenario is allowed. Those responsibilities belong to the project and its automation
environment. Keeping them separate avoids spending reserved stand time on builds and allows the
same image to be repeated on more than one compatible stand.

## Launcher contract

Required options are:

- `--image`: a pre-built image tag or digest;
- `--inventory`: the host path to `stands.yaml`;
- `--stand`: a logical stand key from that inventory;
- `--scenario`: a filename-safe name resolved inside the image from
  `test-runs/scenarios/<name>.yaml`.

Optional runtime access is explicit:

```bash
./scripts/run-hardware-tests.sh \
  --image "${TEST_IMAGE}" \
  --inventory "${INVENTORY_FILE}" \
  --stand "${TEST_STAND}" \
  --scenario "${TEST_SCENARIO}" \
  --artifacts artifacts \
  --env-file /secure/runtime.env \
  --known-hosts /secure/known_hosts \
  --network host \
  --device /dev/ttyUSB0 \
  --pull always
```

`--device` may be repeated. Use Docker's standard
`HOST_DEVICE[:CONTAINER_DEVICE[:PERMISSIONS]]` value when the two paths or permissions differ.
The pull policy defaults to `missing`. No network mode is selected by default.

The script validates filenames and required host files, creates the artifacts directory, and then
runs the equivalent of:

```bash
docker run --rm \
  --volume /host/inventory:/runtime/inventory:ro \
  --volume /host/artifacts:/app/artifacts \
  IMAGE \
  uv run pytest tests/hardware \
    --scenario SCENARIO \
    --inventory /runtime/inventory/stands.yaml \
    --stand STAND
```

The complete inventory directory is mounted read-only so every relative `device_files` entry can
be resolved. Scenario availability is validated by pytest inside the selected image, making that
image the source of truth. The script returns Docker's exit code unchanged.

Each run writes its normal project artifacts below the mounted host directory:

```text
artifacts/
├── latest.log
└── <run-id>/
    ├── pytest.log
    └── reports/
        ├── junit.xml
        └── report.html
```

Automation should publish the HTML and JUnit reports and diagnostic log even when the command
fails.

## Credentials and hardware access

Keep secrets, trusted host keys, physical inventory, and device access outside the image and
repository. Supply only what the selected scenario needs:

- create a temporary environment file from the automation system's secret store and pass it with
  `--env-file`;
- mount trusted host keys with `--known-hosts`;
- select a network only when the configured transports require it;
- expose individual host devices with `--device` instead of using a privileged container.

The launcher prints the selected image, stand, scenario, and artifacts path. It does not print the
contents of environment or host-key files. The caller remains responsible for removing temporary
secret files according to its own retention policy.

## Inactive automation examples

Executable templates are stored under `ci/hardware/`. They are deliberately inactive so creating
a repository from this template cannot reserve equipment or run hardware tests automatically:

- `ci/hardware/github-actions.yml` is a manually dispatched workflow for a self-hosted runner;
- `ci/hardware/gitlab-ci.yml` is a manual job for a runner tagged `hardware`;
- `ci/hardware/Jenkinsfile` is a parameterized declarative pipeline for an agent labeled
  `hardware`.

Activate only the provider used by the project:

```bash
# GitHub Actions
mkdir -p .github/workflows
cp ci/hardware/github-actions.yml .github/workflows/hardware.yml

# GitLab CI: include this file from the project's main configuration, or use it as a starting point
cp ci/hardware/gitlab-ci.yml .gitlab-ci.hardware.yml

# Jenkins
cp ci/hardware/Jenkinsfile Jenkinsfile.hardware
```

Before activation, adapt runner labels, permissions, secret injection, registry authentication,
and the inventory location. Use the provider's exclusive-resource mechanism to serialize each
physical stand. The GitHub example uses a stand-specific concurrency group, the GitLab example
uses a stand-specific resource group, and the Jenkins example conservatively disables concurrent
builds. Projects using the Jenkins Lockable Resources plugin can replace that global restriction
with a lock named from `TEST_STAND`.

The examples intentionally accept free-form strings because available images, stands, and
scenarios belong to the consuming project. Production automation should populate choices from an
approved catalog or validate them before invoking the launcher. Approval gates for destructive or
state-changing scenarios also remain project-specific.

## Optional single-server API runner

Projects that need a lightweight web interface on one trusted laboratory server can use the
independently packaged service under `helpers/test-runner-service/`. It provides separate image
build, image pull, and hardware-run operations, permits one active operation at a time, and exposes
live output and the normal pytest artifacts through HTTP. Its retained-run page lists artifacts
from earlier runs even after the current status and console view have reset, and its optional
Allure integration publishes a shareable report URL and links to the repository report tree.

The service is deployed by its own `compose.yaml` and talks directly to the host Docker daemon. It
does not replace this launcher for manual or CI-provider-driven runs, and it does not add FastAPI or
service dependencies to the main framework package. See the helper's README for its Docker socket
trust boundary and host-path requirements.
