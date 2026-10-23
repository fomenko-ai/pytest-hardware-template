---
name: add-custom-device
description: Add a project-owned hardware device domain API, strict inventory model, and factory dispatch using hardware_test extension contracts. Use for new device classes or device-specific construction fields; use add-inventory-device for physical equipment whose API is already supported.
---

# Add Custom Device

Read the repository `AGENTS.md`, applicable `.agent-work/active/` record, and
[custom entity guide](../../docs/custom-entities.md). The accepted construction boundary is in
[ADR 0003](../../docs/decisions/0003-explicit-custom-entity-factories.md); the complete typed
example is [docs/examples/custom_entities.py](../../docs/examples/custom_entities.py).

## Design and implement

- Find the consuming project's package, inventory unions, factory composition, and pytest fixture
  overrides. Implement the API outside `hardware_test`; the library must not import project code.
- Define a `DeviceConfig[ProjectTransportConfig]` subclass with a unique literal `type` and strict
  physical-device fields. Extend the project's explicit device union and its
  `TypeAdapter(DeviceInventory[ProjectDeviceConfig])`. Inherit strict extra-field validation.
- Keep scenario values and expectations out of the device model. Keep credential references in
  inventory and secret values in runtime settings.
- Build the device through constructor injection of `LockableTransport` and its configuration
  values. Inherit `Device`, or `Dut` when the API must satisfy `stand.dut`. Return domain values or
  `CommandResult`; do not assert test expectations, access client libraries, or own stand setup.
- Extend `ProjectDeviceFactory.create(config: DeviceConfig[ProjectTransportConfig], transport)`.
  Narrow the custom config with `isinstance`; delegate built-in types to `create_device`.
  Do not narrow the method's declared input to only the custom config or mutate `_DEVICE_TYPES`.
- Reuse the project's transport union so the new device can use either standard or custom
  transports. Add transport support only when actually required.
- Map physical IDs to logical roles. Tests resolve `stand.device(role, CustomDevice)` instead of
  depending on physical names or adding vendor properties to `TestStand`.

## Verify and hand off

Follow repository authorization for broad changes and test edits; existing user approval remains
valid. Verify custom fields survive real YAML loading, the factory selects the domain API, and
both standard/custom transports work with fake I/O. Connection lifecycle remains in fixtures.
Run the relevant checks and `./scripts/ci.sh`; never run hardware tests implicitly. Update the
project's guide, skill/example references if affected, and work record with actual results.
