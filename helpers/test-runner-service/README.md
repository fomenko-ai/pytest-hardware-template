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
    └── reports/junit.xml
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

From this directory:

```bash
docker compose up --build --detach
```

The UI is then available at `http://127.0.0.1:8080/` and OpenAPI documentation at `/docs`.
Set `TEST_RUNNER_PORT` in the helper's local `.env` file when the default host port is occupied;
the container port remains `8080`:

```dotenv
TEST_RUNNER_PORT=8081
```

The Compose deployment mounts `/var/run/docker.sock`. Docker daemon access is equivalent to
privileged control of the laboratory host. Deploy only on a dedicated trusted server, bind the HTTP
port to loopback or a protected internal interface, and put authentication and TLS in front of the
service before allowing remote access. The API never accepts arbitrary Docker arguments, build
contexts, host paths, network modes, devices, or credential files.

Docker bind paths are interpreted by the host daemon. Framework, inventory, and artifacts are
therefore mounted into the service at the same absolute paths that the service passes to Docker.

## API

```text
GET    /                         lightweight HTML UI
GET    /health
GET    /v1/current
GET    /v1/current/events       live Server-Sent Events
POST   /v1/current/cancel
POST   /v1/images/build
POST   /v1/images/pull
POST   /v1/runs
GET    /v1/current/artifacts
GET    /v1/current/artifacts/{pytest.log|junit.xml}
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
