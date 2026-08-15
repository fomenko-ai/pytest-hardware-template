# Serial agent

`hardware-serial-agent` is a small standalone package installed on a remote test stand. It opens a
local serial device through pyserial and exposes byte-oriented operations to
`PySerialOverSshTransport` over an existing SSH channel.

See [pyserial transports](pyserial-transports.md) for runner-side inventory configuration and
console behavior.

```text
pytest
    -> PySerialOverSshTransport
    -> SSH stdin/stdout
    -> hardware-serial-helper
    -> pyserial
    -> /dev/serial/...
    -> board
```

The helper lives in `helpers/serial-agent/` and is packaged independently from the main
`hardware_test` framework. Installing it on a stand does not install pytest, Paramiko, inventory
models, or test code.

## Responsibilities

The helper is responsible only for remote serial I/O:

- validate and open one explicitly requested device below `/dev`;
- configure baud rate and supported serial line parameters;
- read and write arbitrary bytes;
- reset input and output buffers;
- report serial timeouts and I/O failures as structured responses;
- close the device when requested or when the SSH channel ends;
- allow only one helper process to own a serial device at a time;
- report its package and protocol versions before opening hardware.

Linux console behavior remains in the test framework. The helper does not interpret `login:`,
send credentials, set `PS1`, find command prompts, or evaluate shell commands. This keeps board
credentials out of the stand-side component and gives local and remote pyserial transports the
same console behavior.

## Protocol

The process reads one JSON object per line from stdin and writes one JSON response per line to
stdout. Binary fields use Base64. Diagnostic logging goes to stderr so it cannot corrupt protocol
responses.

Example session:

```json
{"version":1,"operation":"hello"}
{"version":1,"ok":true,"agent_version":"0.1.0"}
{"version":1,"operation":"open","device":"/dev/serial/by-path/platform-example-port0","baudrate":115200}
{"version":1,"ok":true}
{"version":1,"operation":"write","data":"dW5hbWUgLWEK"}
{"version":1,"ok":true,"written":9}
{"version":1,"operation":"read","size":65535,"timeout":0.2}
{"version":1,"ok":true,"data":"TGludXggYm9hcmQtZGV2Cg=="}
{"version":1,"operation":"close"}
{"version":1,"ok":true}
```

Supported operations are:

- `hello`: negotiate the protocol version and report the installed agent version;
- `open`: open and configure one serial device;
- `write`: decode and write one Base64 payload;
- `read`: read up to the requested byte count within the timeout;
- `reset_input`: discard buffered input received before the next operation;
- `reset_output`: discard buffered output where supported by the platform;
- `close`: close the serial device and terminate normally.

Requests with unknown versions, operations, fields, invalid Base64, oversized payloads, or paths
outside `/dev` fail without opening hardware. Error responses contain a stable error code and a
diagnostic message, but never console credentials.

## Stand requirements

The stand requires:

- Linux with Python 3.14;
- an SSH server available to the test runner;
- a user allowed to execute `hardware-serial-helper`;
- read and write access to the configured `/dev/serial/...` device;
- enough local storage for an isolated uv tool environment.

Serial devices commonly belong to the `dialout` group. Add the SSH account through the stand's
normal provisioning process, then start a new login session so the group membership takes effect:

```bash
sudo usermod --append --groups dialout hardware-test
```

Do not run the helper as root merely to bypass serial-device permissions.

## Build

Build the agent independently from the repository root:

```bash
uv build --wheel helpers/serial-agent
```

The wheel is written to:

```text
helpers/serial-agent/dist/
```

The helper has its own `pyproject.toml` and `uv.lock`. Build and deploy from the locked helper
environment rather than adding stand-only dependencies to the main test runner.

## Install from source

For development on a stand that has access to the repository and configured package index:

```bash
uv tool install ./helpers/serial-agent
```

Use an editable installation only while developing the helper:

```bash
uv tool install --editable ./helpers/serial-agent
```

The production command installed on `PATH` is:

```bash
hardware-serial-helper --version
```

The SSH account used by tests must resolve this command in a non-interactive SSH session. Use the
absolute installed executable path in stand provisioning when the account has a restricted PATH.

## Install in a closed network

Prepare a wheelhouse on a machine that can access the approved package source. It must contain:

- the `hardware_serial_agent` wheel built from this repository;
- the exact pyserial wheel selected by the helper lockfile;
- any build or runtime dependency wheels required by the selected installation method.

Transfer the wheelhouse into the closed network through the approved artifact process. On the
stand, install without consulting an external index:

```bash
uv tool install \
  --offline \
  --no-index \
  --find-links /opt/hardware-test/wheelhouse \
  /opt/hardware-test/wheelhouse/hardware_serial_agent-0.1.0-py3-none-any.whl
```

Pin and verify artifact checksums before transfer. Do not copy a development virtual environment
between machines; install the wheel into a fresh tool environment on the target stand.

## Verify the installation

First verify the executable without accessing hardware:

```bash
hardware-serial-helper --version
printf '{"version":1,"operation":"hello"}\n' | hardware-serial-helper
```

Then verify permissions for one configured device:

```bash
test -c /dev/serial/by-path/platform-example-port0
test -r /dev/serial/by-path/platform-example-port0
test -w /dev/serial/by-path/platform-example-port0
```

Do not run an open/read/write smoke test while another process, including `picocom`, owns the same
serial device.

## Upgrade and remove

Install an approved newer wheel with a forced replacement:

```bash
uv tool install --force /path/to/hardware_serial_agent-NEW_VERSION-py3-none-any.whl
```

Verify the reported agent and protocol versions before enabling hardware tests. Protocol version
incompatibility must fail during the `hello` exchange, before the helper opens a device.

Remove the tool with:

```bash
uv tool uninstall hardware-serial-agent
```

## Operational constraints

- Run one helper process per serial device and test session.
- Keep `/dev/serial/by-id/...`, `/dev/serial/by-path/...`, or managed udev aliases in inventory.
- Do not discover a device with wildcards or select the first available tty.
- Keep agent stdout reserved for protocol messages and route diagnostics to stderr.
- Bound JSON line length, decoded payload size, read size, and timeout values.
- Terminate the helper and close the serial port when its SSH channel closes unexpectedly.
- Never place passwords, tokens, or other secrets in helper arguments or logs.
