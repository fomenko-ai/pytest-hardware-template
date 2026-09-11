# Allure Report Storage

This helper runs the official Allure Report Storage service and builds a disposable Allure 3
publisher image. Storage keeps published HTML reports and cross-run history in a named Docker
volume. The publisher converts `allure-pytest` result files and uploads the generated report.

```text
pytest with allure-pytest
        │
        ▼
artifacts/<run-id>/allure-results/
        │
        ▼
Allure 3 publisher container
        │ generate + upload
        ▼
Allure Report Storage
        ├──► named volume: SQLite metadata, history, and report files
        ├──► /<report-uuid>/awesome/index.html
        └──► /reports/tree?repo=<repository>
```

## Start locally

Create an untracked configuration and replace both secret values with independently generated,
long random strings:

```bash
cp .env.example .env
docker compose up --detach
curl --fail http://127.0.0.1:3000/api/ping
```

Mint the narrower report-access token used by publishers:

```bash
curl --silent --show-error --request POST http://127.0.0.1:3000/api/token \
  --header "Authorization: Bearer $ALLURE_STORAGE_BOOTSTRAP_TOKEN"
```

The returned `ars1...` value is not the bootstrap token. Export it as `ALLURE_ACCESS_TOKEN` for a
manual publisher invocation, or store it as `TEST_RUNNER_ALLURE_ACCESS_TOKEN` in the Test Runner's
untracked `.env`.

Build the pinned Allure 3 publisher image:

```bash
docker build --tag local/allure-publisher:3.17.0 .
```

After collecting results with the root project's `--allure` option, publish one run manually:

```bash
docker run --rm \
  --env ALLURE_ACCESS_TOKEN \
  --env GIT_CONFIG_COUNT=1 \
  --env GIT_CONFIG_KEY_0=safe.directory \
  --env GIT_CONFIG_VALUE_0=/workspace/pytest-hardware-template \
  --volume "$PWD/../..:/workspace/pytest-hardware-template:ro" \
  --volume "/absolute/path/to/run/allure-results:/results:ro" \
  --workdir /workspace/pytest-hardware-template \
  local/allure-publisher:3.17.0 \
  generate /results --config /opt/allure/allurerc.mjs
```

Allure 3 derives the repository from the checkout directory name and the branch from Git. Keep the
mount target's final component equal to the intended repository key; downstream projects replace
`pytest-hardware-template` in all three places above. The command prints the direct published
report URL. Browse the repository history at
`http://127.0.0.1:3000/reports/tree?repo=pytest-hardware-template`.

![Allure Report Storage report tree](../test-runner-service/docs/images/allure-reports.png)

Each UUID in the tree opens one immutable generated report:

![Published Allure 3 report](../test-runner-service/docs/images/allure-report.png)

## Run on a server

Keep `ALLURE_BIND_ADDRESS=127.0.0.1` when a TLS reverse proxy runs on the same host. Otherwise bind
only to a protected internal interface. Do not expose plain HTTP or the bootstrap token publicly.
Back up the `hardware-allure_report-data` volume; it contains both SQLite metadata and report
files. Report Storage does not remove old history automatically.

The access token embeds the Storage URL at the time it is minted. Mint publisher tokens through
the externally reachable HTTPS URL when Test Runners connect from other hosts.
