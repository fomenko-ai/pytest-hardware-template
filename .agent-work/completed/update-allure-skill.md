# Update Allure integration skill

State: complete.

Result:

- added routed configuration guidance for Storage, Publisher, Test Runner, and stands;
- documented token roles, endpoint reachability, repository/branch grouping, and diagnostics;
- aligned remaining `.env.example` publisher references with Allure 3.17.0.

Verification:

- skill-creator `quick_validate.py` passed;
- Allure, Test Runner, and virtual-stand Compose configurations rendered successfully;
- no Allure Publisher 3.9.0 references remain;
- `./scripts/ci.sh` passed, including Ruff, ShellCheck, ty, and unit/integration tests.
