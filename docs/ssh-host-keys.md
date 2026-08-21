# SSH host-key policies

Both `SSHTransport` and `PicocomOverSshTransport` verify the identity of their remote SSH host.
The global policy is a runtime setting and defaults to `reject`:

```dotenv
HARDWARE_TEST_SSH_HOST_KEY_POLICY=reject
# HARDWARE_TEST_SSH_KNOWN_HOSTS_PATH=/etc/hardware-test/known_hosts
```

The supported policies are:

- `reject`: reject hosts whose keys are absent from the loaded known-hosts files;
- `accept_new`: accept a previously unknown key and persist it in the configured known-hosts file;
- `warn`: accept an unknown key for the current connection and emit a warning.

Changed keys for already known hosts remain errors. Use `reject` as the normal CI and hardware-test
default, including in closed networks. Populate the trusted file through the environment's normal
provisioning process and verify new fingerprints through a separate trusted channel.

## Known-hosts sources

The transports always load the account's system SSH host keys through Paramiko. When
`HARDWARE_TEST_SSH_KNOWN_HOSTS_PATH` is set, that file is loaded in addition to the system sources.
The file must already exist and be readable.

`accept_new` requires `HARDWARE_TEST_SSH_KNOWN_HOSTS_PATH`. The file must also be writable so the
new key survives later test runs. Failing instead of accepting a key only in memory prevents every
session from silently trusting a different unknown host.

## Per-device override

An individual SSH-based transport may override the global policy in inventory:

```yaml
transport:
  type: ssh
  ssh:
    host: 192.0.2.21
    credentials: analyzer-default
    host_key_policy: accept_new
```

The same field is available for `picocom_over_ssh`. Resolution follows this order:

```text
transport.ssh.host_key_policy
    -> HARDWARE_TEST_SSH_HOST_KEY_POLICY
    -> reject
```

Keep overrides exceptional and visible in code review. Inventory stores no host keys or secrets;
it only selects behavior for that physical connection.
