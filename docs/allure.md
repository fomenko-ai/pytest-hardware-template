# Optional Allure 3 reporting

The ordinary test workflow always produces `pytest.log`, JUnit XML, and a self-contained HTML
report. Allure reporting is optional and has three separate parts:

- `allure-pytest` records raw test results;
- Allure 3 generates an HTML report from those results;
- Allure Report Storage publishes reports, retains history, and provides shareable URLs.

The template pins `allure-pytest` through the repository-local `allure` dependency group. It is
not part of the future `hardware_test` library's published dependencies. The deployment helper
pins Allure 3 to 3.17.0 and the official `allure/allure-report-storage` image to v1.0.1.

## Report flow

```text
pytest --allure
      │
      ▼
artifacts/<pytest-run-id>/allure-results/
      │  raw Allure JSON and attachments
      ▼
disposable Allure 3 publisher
      │  generates HTML and publishes with repo + branch metadata
      ▼
Allure Report Storage named volume
      ├── SQLite report metadata and history
      └── immutable published report files
              │
              ├──► direct report URL
              └──► /reports/tree?repo=<repository>
```

The Test Runner coordinates the same path after pytest finishes:

```text
Run tests ──► preserve pytest status and local artifacts
    │
    └──► publish allure-results ──► save report_url in current operation
                                      │
                                      ├──► Open Allure report
                                      └──► All Allure reports
```

Publication failure is reported separately and never changes the pytest exit code.

## Collect results locally

Install the optional adapter and run non-hardware tests:

```bash
uv sync --locked --group allure
uv run --group allure pytest tests/unit tests/integration --allure
```

The project option puts raw results into the same unique directory as the standard artifacts:

```text
artifacts/<pytest-run-id>/
├── pytest.log
├── allure-results/
└── reports/
    ├── junit.xml
    └── report.html
```

Without `--allure`, the adapter is not required and no Allure results are created. Passing
`--allure` without installing the group fails immediately with an installation hint. The standard
adapter option `--alluredir PATH` remains available when a caller deliberately needs a custom path;
use one mode or the other, not both. Both `--allure` and its configuration live in
`tests/conftest.py`, keeping the installed `hardware_test` pytest plugin independent of Allure.

Hardware tests still require an explicitly prepared stand and `--stand`. Never run them merely to
validate reporting.

## Start and publish to Report Storage

Use the independently deployable helper under `helpers/allure/`:

```bash
cd helpers/allure
cp .env.example .env
# Set unique bootstrap and signing secrets in .env.
docker compose up --detach
docker build --tag local/allure-publisher:3.17.0 .
```

Follow the helper README to mint an `ars1...` report-access token and publish an existing result
directory. The bootstrap token must never be given to a test container or publisher.

For a server deployment, bind Storage to loopback behind a TLS reverse proxy or to a protected
internal interface. The report-access token embeds the Storage URL, so mint it through the URL
that publishers can reach. Back up the named volume and define an operational retention policy;
Storage does not expire report history automatically.

## Publish from the Test Runner

Build the publisher image on the Docker host, then enable the optional integration in the Test
Runner's untracked `.env`:

```dotenv
TEST_RUNNER_ALLURE_ENABLED=true
TEST_RUNNER_ALLURE_PUBLISHER_IMAGE=local/allure-publisher:3.17.0
TEST_RUNNER_ALLURE_ACCESS_TOKEN=ars1.replace-with-report-access-token
TEST_RUNNER_ALLURE_PUBLIC_URL=http://192.0.2.10:3000
TEST_RUNNER_ALLURE_REPOSITORY=pytest-hardware-template
```

When enabled, Test Runner builds framework images with `INSTALL_ALLURE=true`, adds `--allure` to
the hardware pytest command, and publishes the resulting directory with a disposable publisher
container. Remote framework images supplied to the runner must already contain the optional
adapter.
The repository setting gives Storage a stable project key independent of the publisher container's
working-directory name. Browse the completed reports at
`http://<storage-host>:3000/reports/tree?repo=pytest-hardware-template`.
The public URL must be reachable by the user's browser. It enables the Test Runner's **All Allure
reports** link; the report-access token remains server-side.

The Storage tree groups completed reports by Git branch:

![Allure Report Storage report tree](../helpers/test-runner-service/docs/images/allure-reports.png)

Selecting a report UUID opens the generated Allure 3 report:

![Published Allure 3 report](../helpers/test-runner-service/docs/images/allure-report.png)

Publication runs after both passing and failing tests. The operation keeps the original pytest
status and exit code. `report_status`, `report_url`, and `report_message` describe publication
separately, so an unavailable reporting service cannot turn passing tests into failed tests.

Tokens are injected into the publisher process environment and are never included in Docker
arguments, persisted operation state, UI configuration, or report messages. The browser receives
only `TEST_RUNNER_ALLURE_PUBLIC_URL` and the repository-tree link. Review test logs and attachments
for application secrets before publishing them.

Official references:

- [Allure pytest integration](https://allurereport.org/docs/pytest/)
- [Allure 3 report generation](https://allurereport.org/docs/v3/generate-report/)
- [Allure Report Storage](https://allurereport.org/docs/self-hosted-storage/)
- [Storage deployment with Docker](https://allurereport.org/docs/guides/self-hosted-storage-docker/)
