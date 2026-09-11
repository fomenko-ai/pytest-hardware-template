# Limit Pull image restoration

The Test Runner UI now restores `Pull image` only when the latest operation actually pulled a
remote image. Build and test-run references are restored only in the run form.

Verification:

- focused Test Runner API/UI tests passed: 3 tests;
- the full non-hardware quality gate passed.
