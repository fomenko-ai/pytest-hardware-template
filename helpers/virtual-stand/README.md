# Docker virtual hardware stand

This helper runs a disposable SSH DUT beside the hardware test runner service. The runner starts
the main framework image on the shared `hardware-virtual-stand` Docker network, so the framework
uses its production inventory, factories, device API, lifecycle, and Paramiko transport to reach
the emulator at `virtual-dut:22`.

It is intended for local end-to-end verification of `tests/hardware/` and
`helpers/test-runner-service/`. It does not emulate USB, serial timing, power control, or faults of
real equipment, and it is not part of the ordinary non-hardware CI gate.

The Compose deployment shares one artifact root between the runner and test containers. The
runner passes an explicit pytest session identity, while pytest creates the individual run
directory. Rebuild both the runner and framework images after changing this runtime contract;
there is no compatibility mode for older images.

## Container scripts

`src/entrypoint.sh` validates the runtime password, assigns it to the `tester` account, generates
the disposable SSH host keys, and starts `sshd` as the container's main process.

`src/virtual-device` is the deterministic DUT command-line interface invoked through SSH. It
supports `status`, `model`, `echo TEXT`, and `fail CODE`; the last command makes it possible to
verify propagation of nonzero exit codes.

## Prepare the local configuration

Docker bind paths are resolved by the host daemon and must be absolute. From this directory, copy
the ignored configuration and replace both example paths with paths on the Docker host:

```bash
cp .env.example .env
```

Set `VIRTUAL_STAND_PASSWORD` to a local disposable value containing only letters, numbers, `.`,
`_`, and `-`. Compose passes it to the DUT and a one-shot setup container writes the matching
framework settings to the ignored `runtime/test.env` with mode `0600`. The password and generated
test artifacts are not committed.

Create the runtime root before starting Compose so it is owned by the current user:

```bash
mkdir -p runtime
docker compose up --build --detach
docker compose ps
curl --fail http://127.0.0.1:8080/health
```

The runner UI is available at `http://127.0.0.1:8080/`. The virtual DUT publishes no host port; it
is reachable only by containers attached to `hardware-virtual-stand`.

To publish the virtual run to an already deployed Allure Report Storage instance, first build the
publisher from `helpers/allure/`, mint its `ars1...` report-access token, and add these values to
this helper's ignored `.env`:

```dotenv
TEST_RUNNER_ALLURE_ENABLED=true
TEST_RUNNER_ALLURE_PUBLISHER_IMAGE=local/allure-publisher:3.17.0
TEST_RUNNER_ALLURE_ACCESS_TOKEN=ars1.replace-with-report-access-token
TEST_RUNNER_ALLURE_PUBLIC_URL=http://127.0.0.1:3000
TEST_RUNNER_ALLURE_REPOSITORY=pytest-hardware-template
```

Use a browser-reachable server address instead of loopback when Storage runs on another host.

The disposable DUT generates a new SSH host key when its container is recreated. Its dedicated
inventory therefore uses the framework's `warn` policy. Do not copy that policy into a physical
stand: real equipment should use a persistent trusted `known_hosts` file and `reject` or
`accept_new` according to the laboratory policy.

## Run the end-to-end scenario

For an already running ReportPortal service, follow the
[ReportPortal virtual-stand walkthrough](../reportportal/README.md#verify-reporting-on-the-virtual-stand).
It covers this helper's separate `.env`, forwarding the reporting settings, connecting the
ReportPortal gateway to the virtual network, and verifying the launch and local artifacts.
The standalone runner's `.env` does not configure this helper automatically.

### Through the UI

1. Open `http://127.0.0.1:8080/` and confirm that the runner status is `idle`.
2. Select **Build image** under **Build configured framework checkout**. Follow **Live output**
   until the status becomes `succeeded`; the UI then fills **Image digest** in the run form with
   the resulting `sha256:...` value.
3. Under **Run hardware scenario**, keep the populated image digest and enter:

   ```text
   Stand: virtual-stand
   Scenario: virtual-smoke
   ```

4. Select **Run tests** and follow **Live output** until the status becomes `passed`. The expected
   summary reports one passed test.
5. Open **Download pytest.log**, **Download JUnit XML**, and **Open HTML report** to verify that all
   three run artifacts are available and contain the `TestVirtualDut.test_command_path` result.
6. Open **All test artifacts** to find this and earlier retained local runs. When Allure is enabled,
   open **Open Allure report** before reloading for the current publication, or use persistent
   **All Allure reports** to browse the repository tree afterward.

### Through the API

First build the main framework image through the runner:

```bash
curl --fail --request POST http://127.0.0.1:8080/v1/images/build \
  --header 'Content-Type: application/json' \
  --data '{"revision":"working-tree"}'
curl --no-buffer http://127.0.0.1:8080/v1/current/events
curl --fail http://127.0.0.1:8080/v1/current
```

Copy the complete `image_digest` from the completed operation, then start the tracked
`virtual-smoke` scenario on `virtual-stand`:

```bash
curl --fail --request POST http://127.0.0.1:8080/v1/runs \
  --header 'Content-Type: application/json' \
  --data '{
    "image":"sha256:replace-with-built-image-digest",
    "stand":"virtual-stand",
    "scenario":"virtual-smoke"
  }'
curl --no-buffer http://127.0.0.1:8080/v1/current/events
curl --fail http://127.0.0.1:8080/v1/current/artifacts
```

A successful run verifies the runner API and worker, Docker command construction, image runtime,
inventory loading, credential resolution, stand/device/transport factories, SSH connection and
cleanup, hardware test execution, and publication of pytest log, JUnit XML, and HTML reports.

Stop and remove the helper containers when finished:

```bash
docker compose down
```

The ignored `runtime/` directory retains artifacts until removed explicitly.

## Trust boundary

Like the standalone runner deployment, this Compose stack mounts `/var/run/docker.sock` into the
runner. Docker daemon access is equivalent to privileged control of the host. Use the helper only
on a trusted development machine, keep the runner bound to loopback, and never reuse production
credentials for the emulator.

## Verify Allure and ReportPortal together

This combined check assumes that Allure Report Storage and ReportPortal are already running,
the Allure publisher image is built, and the ReportPortal gateway is connected to
`hardware-virtual-stand` as described in the linked walkthrough.

1. Enable both integrations in this directory's ignored `.env`. Set the Allure access token and
   browser-reachable URL, then set the ReportPortal endpoint, public URL, project, and API key.
   Keep `TEST_RUNNER_ALLURE_RESULTS_PATH=allure-results` unless the test image uses another path.
2. Create the ignored Compose override that forwards ReportPortal settings to the runner:

   ```bash
   cat > runtime/reportportal.compose.yaml <<'YAML'
   services:
     test-runner:
       environment:
         TEST_RUNNER_REPORTPORTAL_ENABLED: ${TEST_RUNNER_REPORTPORTAL_ENABLED:-false}
         TEST_RUNNER_REPORTPORTAL_ENDPOINT: ${TEST_RUNNER_REPORTPORTAL_ENDPOINT:?set endpoint}
         TEST_RUNNER_REPORTPORTAL_PUBLIC_URL: ${TEST_RUNNER_REPORTPORTAL_PUBLIC_URL:?set public URL}
         TEST_RUNNER_REPORTPORTAL_PROJECT: ${TEST_RUNNER_REPORTPORTAL_PROJECT:?set project}
         TEST_RUNNER_REPORTPORTAL_API_KEY: ${TEST_RUNNER_REPORTPORTAL_API_KEY:?set API key}
   YAML
   ```

3. Validate the merged configuration:

   ```bash
   docker compose --env-file .env -f compose.yaml -f runtime/reportportal.compose.yaml \
     config --quiet
   ```

4. Rebuild and restart the runner with both reporting configurations:

   ```bash
   docker compose --env-file .env -f compose.yaml -f runtime/reportportal.compose.yaml up --build --detach test-runner
   ```

5. Open the runner UI, build a new framework image, and wait for `succeeded`. The new image must
   be built after both integrations are enabled so it contains `allure-pytest` and
   `pytest-reportportal`.
6. Run `virtual-smoke` on `virtual-stand` with the new image. Expect the operation status
   `passed`, exit code `0`, and one passed test.
7. Open **Open Allure report**. Confirm that the report contains
   `TestVirtualDut.test_command_path` and that **Metadata** includes `run_id`, `stand`, and
   `scenario`. Use **All Allure reports** to confirm that the publication is retained.
8. Open **Open ReportPortal launch**. Confirm the same test and its INFO logs, then check the
   launch attributes `run_id`, `stand:virtual-stand`, and `scenario:virtual-smoke`. Use
   **All ReportPortal launches** to confirm that the launch is retained.
9. Inspect the machine-readable runner result:

   ```bash
   curl --fail http://127.0.0.1:${TEST_RUNNER_PORT:-8080}/v1/current
   ```

   A successful combined check has `status: passed`, `exit_code: 0`,
   `report_status: published`, a nonempty `report_url`, `reportportal_status: finished`, and a
   nonempty `reportportal_url`. Also open the local pytest log, JUnit, and HTML links to confirm
   that reporting integrations did not replace the standard artifacts.

If pytest passes but either reporting status is `failed`, `unavailable`, or `incomplete`, inspect
the runner live output and the run-specific `pytest.log`. A reporting failure must leave the
pytest status and exit code unchanged.
