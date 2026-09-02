# Hardware test runner service

This optional helper exposes one trusted laboratory server through a small FastAPI application. It
can build the configured framework checkout, pull an allowed image, or run one named hardware
scenario. It intentionally has one global operation slot and no database, persistent queue, or
operation history.

The service is independently packaged from the main `hardware_test` project. It builds Docker CLI
argument arrays directly and does not import the framework package.

## Runtime contract

The service stores only the current or most recently completed operation:

```text
/opt/hardware-runner/state/
├── current.json
└── current.log
```

Hardware-test results keep the main project's standard layout:

```text
/opt/hardware-runner/artifacts/
├── latest.log
└── <pytest-run-id>/
    ├── pytest.log
    └── reports/
        ├── junit.xml
        └── report.html
```

Build, pull, and test execution are separate API operations. While any operation is active, another
request receives HTTP 409 instead of being queued.

## Host preparation

Create the runtime directories and place the framework checkout and physical inventory at the
configured locations:

```text
/opt/hardware-runner/
├── framework/
│   └── Dockerfile
├── inventory/
│   └── stands.yaml
├── artifacts/
└── state/
```

Inventory `device_files` remain relative to `stands.yaml`, so mount the complete inventory
directory. Credentials, trusted SSH host keys, networks, and physical devices are optional server
settings and are never accepted from an HTTP request.

Set the allowed registry/repository prefixes before pulling remote images. Comma-separated values
are supported:

```bash
export TEST_RUNNER_ALLOWED_IMAGE_PREFIXES='sha256:,registry.example.com/hardware-tests@sha256:'
```

The default permits only local image IDs returned by a successful build.

## Start with Docker Compose

From this directory, create the local configuration from the tracked example:

```bash
cp .env.example .env
```

Edit `.env` when the framework, inventory, artifacts, or state directories use different absolute
host paths. Do not add credentials or secrets to `.env.example`. Create all configured writable
directories before starting the service, then build and start its container:

```bash
docker compose up --build --detach
```

The UI is then available at `http://127.0.0.1:8080/` and OpenAPI documentation at `/docs`.
Set `TEST_RUNNER_PORT` in the helper's local `.env` file when the default host port is occupied;
the container port remains `8080`:

```dotenv
TEST_RUNNER_PORT=8081
```

### Authentication

Authentication is disabled by default. To protect the UI, API, event stream, artifacts, and API
documentation, set the following values in the untracked `.env` file:

```dotenv
TEST_RUNNER_AUTH_ENABLED=true
TEST_RUNNER_AUTH_USERNAME=operator
TEST_RUNNER_AUTH_PASSWORD=replace-with-a-strong-password
TEST_RUNNER_AUTH_SESSION_SECRET=replace-with-a-long-random-value
```

Generate the session secret independently from the password. The service refuses to start when
authentication is enabled without any required value. After a successful login, it stores a
signed `HttpOnly`, `SameSite=Strict` session cookie for seven days by default; neither the username
nor password is stored in the cookie. Configure the lifetime in seconds with
`TEST_RUNNER_AUTH_SESSION_TTL_SECONDS`. Changing the session secret invalidates all existing
sessions.

The default `TEST_RUNNER_AUTH_COOKIE_SECURE=false` supports the documented loopback HTTP setup.
Set it to `true` whenever TLS terminates at the service-facing URL. The `/health`, `/login`, and
login/logout endpoints remain public so health checks and authentication continue to work.

The Compose deployment mounts `/var/run/docker.sock`. Docker daemon access is equivalent to
privileged control of the laboratory host. Deploy only on a dedicated trusted server, bind the HTTP
port to loopback or a protected internal interface, and enable authentication together with TLS
before allowing remote access. The API never accepts arbitrary Docker arguments, build
contexts, host paths, network modes, devices, or credential files.

Docker bind paths are interpreted by the host daemon. Framework, inventory, and artifacts are
therefore mounted into the service at the same absolute paths that the service passes to Docker.

## API

```text
GET    /                         lightweight HTML UI
GET    /login                    login page when authentication is enabled
GET    /auth/status              whether authentication is enabled
POST   /auth/login
POST   /auth/logout
GET    /health
GET    /v1/current
GET    /v1/current/events       live Server-Sent Events
POST   /v1/current/cancel
POST   /v1/images/build
POST   /v1/images/pull
POST   /v1/runs
GET    /v1/current/artifacts
GET    /v1/current/artifacts/{pytest.log|junit.xml|report.html}
```

Build the configured checkout:

```bash
curl --request POST http://127.0.0.1:8080/v1/images/build \
  --header 'Content-Type: application/json' \
  --data '{"revision":"working-tree"}'
```

Run a prepared immutable image:

```bash
curl --request POST http://127.0.0.1:8080/v1/runs \
  --header 'Content-Type: application/json' \
  --data '{
    "image":"sha256:0123456789abcdef",
    "stand":"stand-01",
    "scenario":"hardware-smoke"
  }'
```

Follow current output:

```bash
curl --no-buffer http://127.0.0.1:8080/v1/current/events
```

## End-to-end verification

This procedure verifies the runner service, its Docker access, the main framework image, one
prepared hardware scenario, and publication of all test artifacts. Run the test operation only
when the selected physical stand is ready.

1. Verify the required host paths from `.env`. The framework directory must contain `Dockerfile`,
   and the inventory directory must contain `stands.yaml` plus every relative file listed in its
   `device_files` field. The selected stand must reference device IDs defined by those files.

2. Recreate the service container from the current helper source and check its health:

   ```bash
   docker compose up --build --force-recreate --detach
   docker compose ps
   curl --fail http://127.0.0.1:8080/health
   ```

3. Build a new main framework image. This is separate from building the service image:

   ```bash
   curl --fail --request POST http://127.0.0.1:8080/v1/images/build \
     --header 'Content-Type: application/json' \
     --data '{"revision":"working-tree"}'
   ```

4. Follow the operation until it finishes, or inspect it periodically:

   ```bash
   curl --no-buffer http://127.0.0.1:8080/v1/current/events
   curl --fail http://127.0.0.1:8080/v1/current
   ```

   A successful build has status `succeeded`. Copy its complete `image_digest` value, including
   the `sha256:` prefix.

5. Confirm that the selected image contains a hardware scenario under
   `test-runs/scenarios/<scenario>.yaml` and matching tests under `tests/hardware`. Start the run
   with the new digest, a configured stand, and that scenario:

   ```bash
   curl --fail --request POST http://127.0.0.1:8080/v1/runs \
     --header 'Content-Type: application/json' \
     --data '{
       "image":"sha256:replace-with-the-built-digest",
       "stand":"stand-01",
       "scenario":"hardware-smoke"
     }'
   ```

6. Follow `/v1/current/events` again. After completion, `/v1/current` has status `passed` or
   `failed`, an `artifact_directory`, and a JUnit-derived `summary` when pytest produced its normal
   reports.

7. Verify the published artifact list:

   ```bash
   curl --fail http://127.0.0.1:8080/v1/current/artifacts
   ```

   A completed pytest run normally lists `pytest.log`, `junit.xml`, and `report.html`. Check each
   endpoint directly:

   ```bash
   curl --fail http://127.0.0.1:8080/v1/current/artifacts/pytest.log
   curl --fail http://127.0.0.1:8080/v1/current/artifacts/junit.xml
   curl --fail --output /tmp/hardware-test-report.html \
     http://127.0.0.1:8080/v1/current/artifacts/report.html
   ```

   The HTML report can also be opened from the `Open HTML report` link at
   `http://127.0.0.1:8080/`. Run-specific files remain below the configured artifacts directory.

8. Inspect service diagnostics when an operation fails, then stop the service when finished:

   ```bash
   docker compose logs runner
   docker compose down
   ```

## Recovery and retention

If the service restarts while an operation is active, it marks the snapshot `interrupted`; it does
not delete an unknown container automatically. An operator must inspect Docker and the physical
stand before starting another operation.

Starting a new operation replaces `current.json` and `current.log`. Run-specific pytest artifacts
remain under the configured artifacts directory and are cleaned through the main project's normal
artifact retention procedure.

## Development verification

All tests use fake process runners and never access Docker, networks, or physical equipment:

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
```
