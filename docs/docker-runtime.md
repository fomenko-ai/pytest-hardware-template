# Running a built image on another host

Use a previously built image to run the same test package on a host connected to a different
physical stand. Keep host-specific inventory, credentials, trusted SSH keys, and device access
outside the image.

## Transfer the image

Push the image to a container registry from the build host and pull it on the target host:

```bash
docker tag pytest-hardware-template registry.example.com/pytest-hardware-template:1.0
docker push registry.example.com/pytest-hardware-template:1.0
```

```bash
docker pull registry.example.com/pytest-hardware-template:1.0
```

For a target host without registry access, transfer an archive instead:

```bash
docker save --output pytest-hardware-template.tar pytest-hardware-template
```

Copy `pytest-hardware-template.tar` to the target host, verify it using an out-of-band checksum,
and load it:

```bash
docker load --input pytest-hardware-template.tar
```

The image architecture must match the target host. Build a multi-platform image when build and
target machines use different architectures.

## Prepare runtime configuration

Create an inventory directory on the target host. The directory can describe different physical
equipment without rebuilding the image:

```text
inventory/
├── stands.yaml
└── devices/
    ├── analyzers.yaml
    ├── duts.yaml
    └── generators.yaml
```

List the device sources explicitly in `stands.yaml`:

```yaml
version: 1
device_files:
  - devices/duts.yaml
  - devices/analyzers.yaml
  - devices/generators.yaml
```

These paths are resolved relative to `stands.yaml`. Device IDs must be unique across all listed
files. Inventory may contain hosts, ports, topology, and credential references, but must not
contain passwords or other secrets.

Provide secrets through a target-host `.env` file and make trusted SSH host keys available at
runtime. Do not copy either file into the image.

## Run hardware tests

From the directory containing `.env`, `inventory/`, and optionally `artifacts/`, run:

```bash
mkdir -p artifacts

docker run --rm \
  --env-file .env \
  --network host \
  --volume "$PWD/inventory:/runtime/inventory:ro" \
  --volume "$HOME/.ssh/known_hosts:/root/.ssh/known_hosts:ro" \
  --volume "$PWD/artifacts:/app/artifacts" \
  pytest-hardware-template \
  uv run pytest tests/hardware \
    --inventory /runtime/inventory/stands.yaml \
    --stand stand-01
```

`--inventory` must refer to the path inside the container. `--stand` must name a stand defined in
that `stands.yaml`. The inventory mount is read-only, while the artifacts mount is writable so
logs and JUnit reports remain on the target host.

Host networking is appropriate for many Linux SSH stands. Other platforms or network layouts may
require explicit port routing instead. Add only the access required by the configured transports,
for example:

```bash
docker run --rm \
  --device /dev/ttyUSB0:/dev/ttyUSB0 \
  --volume "$PWD/inventory:/runtime/inventory:ro" \
  pytest-hardware-template \
  uv run pytest tests/hardware \
    --inventory /runtime/inventory/stands.yaml \
    --stand serial-stand
```

USB, Serial, and VISA access may also require target-host permissions, drivers, libraries, or
additional mounts. Grant devices individually; avoid privileged containers unless a concrete
hardware requirement justifies them.

## Verify the setup

Before running state-changing tests, confirm that:

- the image tag or image ID is the expected version;
- the selected stand exists in the mounted inventory;
- every `device_files` entry is present below the mounted directory;
- credentials referenced by inventory are present in the runtime environment;
- SSH host keys and network routes are available inside the container;
- required physical devices are mounted and accessible;
- the stand is ready and reserved for this test run.

The image's default command runs only unit and integration tests. Hardware tests run only when the
explicit `uv run pytest tests/hardware ...` command is supplied.
