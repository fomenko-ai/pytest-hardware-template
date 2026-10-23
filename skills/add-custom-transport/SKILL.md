---
name: add-custom-transport
description: Add a project-owned hardware transport, strict inventory configuration, credential settings, and injectable factory mapping. Use for new connection methods or wire protocols; existing SSH or serial endpoint configuration belongs to inventory instead.
---

# Add Custom Transport

Read the repository `AGENTS.md`, applicable `.agent-work/active/` record, and
[custom entity guide](../../docs/custom-entities.md). Consult
[transport contracts](../../docs/transports.md) and
[ADR 0003](../../docs/decisions/0003-explicit-custom-entity-factories.md).
[docs/examples/custom_entities.py](../../docs/examples/custom_entities.py) demonstrates typed factory and
credential composition; its client is a protocol adapter, not a complete TCP implementation.

## Design and implement

- Locate the project's package, supported transport union, settings model, and factory fixtures.
  Keep the transport and its client-library dependency outside `hardware_test` for project-specific
  protocols. Runtime client dependencies belong in the consuming project's runtime metadata.
- Define an ordinary strict Pydantic model with a unique literal `type`, physical connection
  fields, and credential references. Extend `ProjectTransportConfig` and use that union in every
  project device model, including models for built-in device APIs.
- Extend settings for any new secret profile using `SecretStr`. Document nested environment names
  and commit only empty `.env.example` placeholders. Do not put secrets in YAML or source code.
- Implement `Transport.connect`, `close`, and `execute` with the chosen client library encapsulated
  inside the transport module. Accept typed commands and reject unsupported command types.
  Translate client errors without leaking secrets; respect configured and per-command timeouts.
  Map timeouts to `TransportTimeoutError`. Make lifecycle operations repeatable, release partial
  resources when connection fails, and preserve the connection error if cleanup also fails.
- Extend `ProjectTransportFactory`, receiving settings and client constructors through its
  constructor. Resolve credentials before client construction, return a `SynchronizedTransport`
  around the custom implementation, and delegate built-in models to `create_transport` without
  wrapping its already synchronized result again. Construction must not open connections.
- Pass the matching transport union to `StandFactory` and its device factory. Ensure pytest uses
  the project's source/final schema adapters and `stand_factory`; changing dispatch alone cannot
  enable a new inventory type. Do not add global registration or Python class imports from YAML.

## Verify and hand off

Follow repository authorization for broad changes and test edits; existing user approval remains
valid. Fake the client, covering credentials and settings mapping, unsupported commands, timeout
selection, partial setup cleanup, and domain-device use. Exercise both built-in and custom devices
through the project loader and `StandFactory`, without sockets or physical equipment.
Run relevant checks, dependency locking when metadata changes, and `./scripts/ci.sh`. Update the
project guide and work record with actual results. Hardware execution requires a separate explicit
request and a prepared stand.
