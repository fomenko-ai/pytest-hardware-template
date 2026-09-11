# Allure Report Storage integration

Implemented optional `allure-pytest` collection in each standard run directory, an independently
deployable Allure Report Storage helper, a pinned Allure 3 publisher image, and automatic Test
Runner publication that preserves the original pytest result.

Verification:

- `uv lock` resolved allure-pytest 2.16.0.
- A real `pytest --allure` invocation created result JSON in the per-run artifact directory.
- The publisher image built successfully and reported Allure CLI 3.9.0.
- Storage `docker compose config --quiet` passed.
- Test Runner tests passed: 26 tests.
- Test Runner `ty check` passed.
- The final `./scripts/ci.sh` run passed without changes.
- A live Test Runner publication completed and produced a working Storage URL.
- Publisher checkout mounting now supplies the stable repository key
  `pytest-hardware-template`; the Allure 3 detector was verified to return that repo and `main`.

The first live report was published under the old inferred `workspace` key and remains available
there; subsequent reports use the configured stable repository key.
