# Rename Test Runner Compose service

Both the standalone and virtual-stand Compose deployments now use the consistent `test-runner`
service key. Service-specific documentation commands use the same name.

Verification:

- both Compose configurations parsed and reported `test-runner`;
- the full non-hardware quality gate passed.
