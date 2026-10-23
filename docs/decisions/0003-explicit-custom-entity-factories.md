# 0003: Extend inventory and factories through explicit project composition

Status: accepted
Date: 2026-10-23
Task: custom-entities

## Context

The device constructor table, transport configuration union, inventory loader, and stand factory
currently form a closed construction chain. A downstream project cannot add a device or transport
without editing reusable code. Registering constructors alone would still leave custom transport
types rejected during inventory validation.

[ADR 0001](0001-prepare-for-library-publication.md) requires preparing reusable boundaries while
the project remains a template. Project implementations must depend on `hardware_test`, without
requiring the future library to import project code. [ADR 0002](0002-separate-runtime-and-reporting.md)
keeps pytest runtime and reporting concerns independent of equipment construction.

## Decision

### Typed inventory schemas

Make `DeviceConfig` generic over its transport configuration, and `DeviceInventory` and `Inventory`
generic over their device configuration. Default type parameters preserve the existing YAML and
ordinary Python entry points.

Projects define explicit unions of supported transport and device models. Device-specific models
inherit `DeviceConfig[ProjectTransportConfig]` and retain strict extra-field validation. The
loader accepts a typed Pydantic adapter for the physical-device inventory schema; that adapter
validates each explicitly listed source. The loader preserves concrete model instances and
custom fields when building the combined inventory.

The shared loader continues to own relative `device_files`, global duplicate-ID detection with
both source paths, and stand-reference validation. It does not import factories or create objects.

### Constructor injection and composition

Provide typed `DeviceFactory` and `TransportFactory` protocols and built-in adapters around the
existing `create_device` and `create_transport` functions. `StandFactory` receives these factories
through its constructor. It creates one object per physical device ID and assigns it to logical
roles in `TestStand`.

The factory protocols share a transport-configuration type. A project device factory accepts
`DeviceConfig[ProjectTransportConfig]`, narrows custom model subclasses explicitly, and delegates
ordinary types to `create_device`. It receives the complete configuration, including custom
fields, and an already constructed `LockableTransport`.

A small read-only inventory protocol exposes the device mapping to `StandFactory`. This lets
typed inventories containing different device-model subclasses use the same assembly mechanism
without weakening types with `Any` or mutating the inventory.

Project transport factories receive settings through their constructors. Their `create` method
accepts the project's transport union, resolves credential references, and returns a
`LockableTransport`. Custom `Transport` implementations are wrapped in `SynchronizedTransport`;
built-in transports delegated to `create_transport` are already wrapped.

Keep `create_stand(inventory, config, settings)` as the standard convenience composition.
Built-in device creation depends only on device type and model, allowing built-in devices to
use custom transports. Built-in transport dispatch explicitly rejects unsupported configuration
models instead of treating them as SSH.

### Project ownership and pytest integration

Custom devices, transports, configuration models, settings, and composition live in a project
package outside `hardware_test`. New runtime dependencies belong to the consuming project.
Settings load defaults and secrets; inventory contains physical parameters and credential
references; scenario configs contain test data.

The project overrides the `settings`, `inventory`, and `stand_factory` fixtures as needed. The
standard `stand` fixture selects a stand, asks the injected factory to create it, and coordinates
connection cleanup. Factories do not open connections. `TestStand` retains its lifecycle and
logical-role APIs and does not read files, settings, or environment variables.

Both device and transport selection are independent: built-in/custom devices work with either
built-in or custom transports. Example implementations and integration tests use fakes, never
physical equipment.

This decision introduces no global registration API, automatic package discovery, dynamic
imports from YAML, or stable-library compatibility guarantee.

## Alternatives Considered

### Instance registries pairing models and builders

This can simplify distributing many independent extensions, but adds heterogeneous registration,
schema assembly, and conflict handling. Explicit project schemas and small factory methods meet
the current requirement with less mechanism. Reconsider when extension distribution requires it.

### Installed plugins discovered through entry points

Useful for independently released driver packages, but still requires extensible schemas and
factory contracts. Discovery, selection, and compatibility management are deferred.

### Modify global constructor tables or import classes from YAML

Global mutation creates ordering and test-isolation problems and does not solve closed transport
schemas. YAML class imports couple inventory to Python packaging. Both weaken explicit composition.

## Consequences

### Positive

- Projects extend equipment support without modifying reusable modules.
- Typed validation covers all four built-in/custom device and transport combinations.
- Inventory validation, role mapping, synchronization, and cleanup stay reusable.
- Existing inventory and convenience functions remain usable.

### Negative

- Projects maintain their supported model unions and matching factory dispatch.
- Factory inputs use the shared device-config base; custom fields require explicit narrowing.
- New generic interfaces require type-checking examples alongside runtime tests.
- API stability remains subject to the future publication review under ADR 0001.

## Documentation

- [Custom entity guide](../custom-entities.md): schemas, settings, factory composition, pytest, and
  examples.
- [README](../../README.md): overview and skill discovery.
- [Transport guide](../transports.md): transport and synchronization contracts.
- `skills/add-custom-device/` and `skills/add-custom-transport/`: focused AI workflows.
