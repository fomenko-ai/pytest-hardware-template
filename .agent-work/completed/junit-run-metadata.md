# Run metadata across test reports

Status: complete
Owner: /root

Shared run metadata is collected once and reused in the pytest.log header, JUnit
suite properties, pytest-html Environment, Allure environment.properties, and
ReportPortal launch attributes. User-selected header spacing is preserved.
Optional adapter integration stays in tests/conftest.py; custom RP attributes are
preserved, with actual run values replacing conflicting shared keys.

Verification: 32 targeted tests passed with both optional reporting groups installed,
using a fake RP client and no hardware or network connections. Coverage includes
cross-report equality, collection errors, Git absence/timeouts, properties escaping,
INI/CLI/environment attributes, and JUnit failure capture. Final scripts/ci.sh passed
without changes after accepting Ruff formatting. The ordinary gate omits optional
adapter cases when their groups are absent; they were verified separately above.

README and reporting guides document UI locations, image rebuild requirements, and
pytest 9.1.1's setup-capture limitation with junit_log_passing_tests=false. Existing
published reports and remote launches were not modified. No hardware tests ran.
