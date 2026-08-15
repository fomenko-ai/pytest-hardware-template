# Pyserial transports

The project provides two pyserial-based transports for Linux console devices:

- `pyserial` opens a serial device attached directly to the pytest runner;
- `pyserial_over_ssh` starts `hardware-serial-helper` on a remote SSH stand and accesses the
  stand's serial device through its versioned protocol.

Both transports use the same `LinuxConsoleSession` for optional login, deterministic `PS1`, command
execution, timeouts, output normalization, and shell exit status. Tests continue to use device APIs
such as `stand.dut`; they do not access pyserial or the helper directly.

## Direct pyserial

Define a device connected to the machine running pytest:

```yaml
devices:
  local_serial_dut:
    type: dut
    model: example-linux-board
    transport:
      type: pyserial
      serial_device: /dev/serial/by-id/usb-example-board-port0
      baudrate: 115200
      prompt: "__HARDWARE_TEST_PROMPT__# "
      console_credentials: dut-console
```

The pytest account must have read and write access to `serial_device`. The port is opened with
exclusive ownership and non-blocking reads. No SSH credentials or host-key policy apply to this
transport.

## Pyserial over SSH

Define a board connected to a remote stand:

```yaml
devices:
  remote_serial_dut:
    type: dut
    model: example-linux-board
    transport:
      type: pyserial_over_ssh
      host: 192.0.2.14
      port: 22
      credentials: default-ssh
      host_key_policy: reject
      serial_device: /dev/serial/by-path/platform-example-port0
      baudrate: 115200
      prompt: "__HARDWARE_TEST_PROMPT__# "
      console_credentials: dut-console
```

Install `hardware-serial-agent` on the stand before running hardware tests. See the
[serial-agent guide](serial-agent.md) for build, offline installation, permissions, protocol, and
verification.

The executable defaults to `hardware-serial-helper`. Override its absolute path globally when a
non-interactive SSH account has a restricted PATH:

```dotenv
HARDWARE_TEST_SERIAL_AGENT_COMMAND=/opt/hardware-test/bin/hardware-serial-helper
```

The command is a runtime setting rather than inventory data, so an inventory file cannot inject an
arbitrary remote shell command. SSH host-key verification follows the global setting and optional
per-device override described in [SSH host-key policies](ssh-host-keys.md).

## Console login

Both transports accept the same optional console settings:

```yaml
initial_prompt_suffix: "# "
login_prompt: "login:"
password_prompt: "Password:"
console_credentials: dut-console
```

Console credentials remain in `.env` as `SecretStr` values. If the shell is already authenticated,
login is skipped. If `login_prompt` appears without configured console credentials, connection
fails without submitting a username or password.

## Command results

Serial consoles combine stdout and stderr into one byte stream. `CommandResult.stdout` contains
the normalized console output, `stderr` remains empty, and `exit_code` comes from the marker added
by `LinuxConsoleSession`.

Only one process may own a configured serial device. Close `picocom`, another helper, or any manual
terminal session before starting a pyserial-based hardware test.
