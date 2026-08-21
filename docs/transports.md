# Transports

Transports isolate device APIs from concrete communication libraries and physical connection
details. A device receives an already constructed transport through its constructor and uses only
the transport contract. It does not read inventory, resolve credentials, or create connections.

```text
inventory + settings
        ↓
  TransportFactory
        ↓
concrete Transport
  SSH / serial / remote serial
        ↓
SynchronizedTransport
        ↓
   DeviceFactory
        ↓
     Device API
        ↓
     TestStand
```

## Contracts and implementations

`Transport` is the minimal synchronous protocol implemented structurally by concrete transports:

```python
class Transport(Protocol):
    def connect(self) -> None: ...
    def close(self) -> None: ...
    def execute(self, command: Command[str] | Command[bytes]) -> CommandResult: ...
```

Concrete implementations do not need to inherit from `Transport`. Matching method signatures are
enough for static type checking. This keeps Paramiko, pyserial, and other client libraries inside
their respective transport modules.

`LockableTransport` extends that contract with exclusive access:

```python
class LockableTransport(Transport, Protocol):
    def exclusive(self) -> AbstractContextManager[None]: ...
```

`SynchronizedTransport` implements `LockableTransport` by composing a concrete `Transport` with a
reentrant lock. `TransportFactory` always applies this wrapper before returning a transport to
`DeviceFactory`.

```text
SSHTransport ──────────────┐
PicocomOverSshTransport ───┼── Transport
PySerialTransport ─────────┤        ↓
PySerialOverSshTransport ──┘  SynchronizedTransport
                                      ↓
                               LockableTransport
                                      ↓
                                    Device
```

## Connection lifecycle

The session-scoped `TestStand` fixture owns the connection lifecycle. `TestStand.connect()` asks
each device to connect before a hardware test uses it, and `TestStand.close()` closes connected
devices during fixture teardown. A device delegates both operations to its injected transport.

`SynchronizedTransport` uses the same lock for `connect()`, `execute()`, and `close()`. A connection
therefore cannot be closed by another thread while a command is using that transport instance.
Concrete transports remain responsible for making repeated `connect()` and `close()` calls safe.

## Command execution

Tests call public device APIs. Direct commands are appropriate only when the DUT command-line
interface is itself under test:

```python
result = stand.dut.execute_command(UnixCommand("example service status", timeout=10.0))
```

```text
test -> Device API -> LockableTransport -> SynchronizedTransport
                                              ↓
                                      concrete Transport
                                              ↓
                                     physical equipment
```

The device passes the typed command to the transport, and the transport returns a
`CommandResult` containing `stdout`, `stderr`, and `exit_code`. Each concrete transport validates
the command types it supports and raises `UnsupportedCommandError` for an incompatible command.

The included implementations have these boundaries:

- `SSHTransport` executes text commands through Paramiko;
- `PicocomOverSshTransport` executes Unix commands in a persistent remote serial console;
- `PySerialTransport` executes Unix commands over a locally attached serial console;
- `PySerialOverSshTransport` executes Unix commands through the remote serial agent.

Serial console transports use `LinuxConsoleSession` to submit one command, identify its complete
response, and obtain its exit status. Tests must not access console channels or SSH clients
directly.

## Exclusive command sequences

Individual lifecycle operations and commands are serialized automatically. Reserve the connection
explicitly when several commands must execute without another thread inserting work between them:

```python
with stand.dut.exclusive_connection():
    stand.dut.execute_command(UnixCommand("example configure"))
    stand.dut.execute_command(UnixCommand("example restart"))
    result = stand.dut.execute_command(UnixCommand("example service status"))
```

The reentrant lock allows the owning thread to call `execute()` while it holds the exclusive
context. The lock is released even when a command or assertion raises an exception.

This guarantee applies only to one `SynchronizedTransport` instance in one process. It does not
coordinate separate pytest workers, containers, test runs, or external terminal programs. Those
cases require resource allocation or a shared inter-process lock outside the transport. A local
serial port additionally uses the operating system's exclusive-open support where available.

## Adding a transport

Add a concrete transport only for a current connection requirement:

1. Implement the `Transport` methods without depending on device classes.
2. Keep the concrete client library private to the transport module.
3. Accept typed commands and reject unsupported command types explicitly.
4. Translate client-library failures into project transport exceptions.
5. Make `connect()` and `close()` safe when called repeatedly.
6. Add construction and configuration mapping to `TransportFactory`.
7. Return it through `SynchronizedTransport`; do not implement a separate device-side lock.
8. Unit-test it with fake clients or channels and without network or physical equipment.

For implementation-specific configuration, see the
[picocom-over-SSH guide](picocom-over-ssh.md), the
[pyserial transport guide](pyserial-transports.md), and
[SSH host-key policies](ssh-host-keys.md).
