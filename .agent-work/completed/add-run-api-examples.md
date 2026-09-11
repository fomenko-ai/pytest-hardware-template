# Add readable run API examples

State: complete.

Result:

- added explicit OpenAPI examples for the image, stand, and scenario request fields;
- used the repository's virtual stand and smoke scenario in the examples;
- added API schema coverage for the documented values.

Verification:

- focused API test module passed: 5 tests;
- `./scripts/ci.sh` passed, including Ruff, ShellCheck, ty, and unit/integration tests.
