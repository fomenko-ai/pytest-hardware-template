# Docker in a closed network

Hardware tests are often built and run inside an organization network that requires a VPN,
HTTPS proxy, internal package index, or private certificate authority (CA). Configure trust at
each boundary instead of disabling TLS verification.

Use organization-specific hostnames, certificates, and credentials only at runtime. Do not add
them to this repository or bake credentials and private keys into an image.

## Trust boundaries

Containerized tests can require configuration at three independent levels:

1. The Docker daemon must reach and trust the registry used by `FROM`.
2. The image build must reach and trust package indexes and source repositories used by
   `uv sync`.
3. The running container must trust internal HTTPS services contacted by tests.

Installing a CA inside an image cannot fix a failure while pulling its base image because Docker
resolves `FROM` before executing any Dockerfile instruction.

## Docker daemon and registries

Install the organization CA according to the host operating system and Docker deployment. For a
private registry on a Linux Docker Engine host, administrators commonly provide its CA at:

```text
/etc/docker/certs.d/registry.example.org/ca.crt
```

Include the port in the directory name when the registry uses a non-default port:

```text
/etc/docker/certs.d/registry.example.org:5000/ca.crt
```

Restart or reload Docker as required by the host after changing its trust configuration. This is
a machine-administration operation and is intentionally not automated by this repository.

If the closed network cannot reach `ghcr.io`, mirror the pinned base image into an approved
internal registry and maintain a corporate derivative of the Dockerfile that uses it:

```dockerfile
FROM registry.example.org/base/uv-python:3.14
```

Keep the upstream image version and provenance in the internal image metadata or maintenance
documentation.

## Build proxy

Pass proxy settings as Docker's predefined build arguments. Do not declare or copy them into the
Dockerfile:

```bash
docker build \
  --build-arg HTTPS_PROXY=http://proxy.example.org:3128 \
  --build-arg HTTP_PROXY=http://proxy.example.org:3128 \
  --build-arg NO_PROXY=localhost,127.0.0.1,.example.org \
  -t pytest-hardware-template .
```

Set only the variables required by the organization. Avoid embedding proxy credentials in shell
history; use the credential mechanism approved for the local Docker installation.

## Corporate CA during the build

The path in `src` is a local path on the machine executing `docker build`:

```bash
docker build \
  --secret id=corporate_ca,src=/secure/path/corporate-ca.crt \
  -t pytest-hardware-template .
```

BuildKit exposes the file to a matching Dockerfile instruction as
`/run/secrets/corporate_ca`. A corporate derivative of the Dockerfile can install the CA and ask
`uv` to use the operating system trust store:

```dockerfile
ENV UV_SYSTEM_CERTS=true

RUN --mount=type=secret,id=corporate_ca,required=true \
    cp /run/secrets/corporate_ca /usr/local/share/ca-certificates/corporate-ca.crt \
    && update-ca-certificates
```

The secret mount itself is temporary, but the explicit `cp` makes the CA part of the resulting
image. This is appropriate only when organizational policy permits distributing that CA with the
image. Never use this pattern for a client private key, access token, or password.

When the CA must not persist in the image, mount a PEM certificate bundle when the container
runs and point software to it, for example:

```bash
docker run --rm \
  --volume /secure/path/corporate-ca-bundle.pem:/run/certs/corporate-ca-bundle.pem:ro \
  --env SSL_CERT_FILE=/run/certs/corporate-ca-bundle.pem \
  pytest-hardware-template
```

`SSL_CERT_FILE` replaces the default certificate source for `uv`, so the supplied PEM file must
contain every CA that the process needs to trust. Prefer `UV_SYSTEM_CERTS=true` when the system
trust store is correctly configured.

## Private Python package index

Define an internal index without credentials in project configuration. Supply its credentials at
build or runtime through environment variables or an approved secret store. For an index named
`internal-proxy`, `uv` recognizes:

```text
UV_INDEX_INTERNAL_PROXY_USERNAME
UV_INDEX_INTERNAL_PROXY_PASSWORD
```

Do not put credentials in `pyproject.toml`, `uv.lock`, a Dockerfile, an image tag, or a committed
environment file. Use BuildKit secret mounts when a credential is required only while building.

## Runtime access to hardware

VPN routing and firewall access must be available from the Docker host and compatible with the
container network mode. Inject runtime credentials, trusted SSH host keys, and physical-device
mounts explicitly as described in the Docker section of the project README.

Do not work around certificate errors with `--insecure`, `allow-insecure-host`, disabled SSH host
key verification, or an unverified HTTP index. Diagnose which trust boundary is missing the CA
and configure that boundary instead.

## Operational checklist

- Confirm that the host is connected to the required VPN.
- Confirm that Docker can pull the base image or its approved internal mirror.
- Confirm that the Docker daemon trusts the registry certificate.
- Pass required proxy variables without persisting credentials.
- Make the corporate CA available to the build and runtime where required.
- Keep tokens, passwords, client private keys, and real organization addresses out of Git.
- Verify that `uv sync --locked` uses the intended package index.
- Run unit and integration tests before enabling access to physical equipment.
