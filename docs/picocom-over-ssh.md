# Picocom over SSH

Use `picocom_over_ssh` when a Linux board is connected by USB to a remote test stand. The
transport opens SSH to the stand, starts a persistent `picocom` process in a PTY, and executes
commands in the board's serial console.

```text
test -> device API -> PicocomOverSshTransport -> SSH -> picocom -> USB serial -> board
```

## Inventory

Define the physical connection in a device inventory:

```yaml
devices:
  serial_dut:
    type: dut
    model: example-linux-board
    transport:
      type: picocom_over_ssh
      ssh:
        host: 192.0.2.13
        port: 22
        credentials: default-ssh
      serial_device: /dev/serial/by-path/platform-example-usb-0:1:1.0-port0
      baudrate: 115200
      console:
        prompt: "__HARDWARE_TEST_PROMPT__# "
        initial_prompt_suffix: "# "
        login_prompt: "login:"
        password_prompt: "Password:"
        credentials: dut-console
```

The fields have the following meanings:

- `ssh` contains the host, port, credential reference, and optional host-key policy for the stand.
- `serial_device` is one explicit absolute device path below `/dev`.
- `baudrate` is the serial line speed and defaults to `115200`.
- `console.prompt` is the unique shell prompt installed for the active test session.
- `console.initial_prompt_suffix` recognizes an authenticated shell and defaults to `# `.
- `console.login_prompt` and `console.password_prompt` recognize authentication requests.
- `console.credentials` optionally references the board login profile in runtime settings.

The transport does not discover devices automatically. Prefer stable `/dev/serial/by-path/...` or
`/dev/serial/by-id/...` paths. Direct `/dev/ttyUSB0`, `/dev/ttyACM0`, and custom udev aliases are
also accepted, but numbered tty names may change after reconnecting hardware.

## Stand requirements

The remote stand must have `picocom` installed. Its SSH user must be able to read and write the
configured serial device. On Linux this commonly requires membership in the group that owns the
device, such as `dialout`.

SSH uses strict known-host verification. Add the stand's real host key to the account's known
hosts file rather than disabling verification.

Only one test session should own a serial device at a time. A second `picocom` process may fail to
open a device that is already locked or produce interleaved console traffic.

## Console credentials

SSH credentials authenticate on the stand. Console credentials authenticate in the board shell;
keep these profiles separate.

Inventory contains only the reference:

```yaml
console:
  prompt: "__HARDWARE_TEST_PROMPT__# "
  credentials: dut-console
```

Store the profile in `.env` or inject the equivalent environment variable at runtime:

```dotenv
HARDWARE_TEST_CREDENTIALS__CONSOLE='{"dut-console":{"username":"root","password":"change-me"}}'
```

The password is loaded as `SecretStr`. It is sent only after the configured `password_prompt` is
recognized and is not included in timeout or authentication errors. Never commit `.env` or real
credentials.

## Connection sequence

After starting `picocom`, the transport sends Enter and examines the end of the console output:

1. If the unique `prompt` is present, the console is ready.
2. If `initial_prompt_suffix` is present, login is skipped.
3. If `login_prompt` is present, the configured username is sent.
4. The password is sent only after `password_prompt` appears.
5. A repeated login or password prompt reports failed authentication.
6. Unrecognized output reports an error instead of guessing the console state.

After reaching a shell, the transport sets `PS1` to the configured unique `prompt`. The change
applies only to the current board shell session and disappears when that session closes.

If the board requests login but `console.credentials` is omitted, connection fails without
submitting credentials. Boards using a non-root shell commonly need `initial_prompt_suffix: "$ "`.

## Command results

Commands execute in the board shell, not in the stand's SSH shell. The transport appends a unique
marker to each command to recover its shell exit status and returns a `CommandResult`.

Serial consoles do not provide separate stdout and stderr streams. All console output is returned
in `CommandResult.stdout`; `CommandResult.stderr` remains empty. Assertions should use
`exit_code` and the combined console output accordingly.

Closing the transport sends the standard `picocom` exit sequence, closes the PTY channel, and
then closes SSH. Pytest fixtures remain responsible for calling `close()` in `try/finally`.

## Connection failures

Typical failures indicate one of these conditions:

- the serial device path does not exist or is not a character device;
- the SSH user lacks read or write permission for the device;
- `picocom` is absent, exits early, or cannot acquire the serial device;
- console prompts differ from the configured markers;
- console credentials are missing or rejected;
- the board is still booting and does not reach a recognized prompt before the timeout.

Use the exact prompt text emitted by the board. Keep marker values on one line and avoid values
that may commonly occur at the end of ordinary boot or command output.
