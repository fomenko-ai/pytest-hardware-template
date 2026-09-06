# Optional Allure reporting

The template already creates an HTML report, JUnit XML, and a diagnostic log. Use those outputs
when they meet your needs. Allure is an optional downstream integration for projects that need
its report UI or already publish results to an Allure system. The template does not install
`allure-pytest`, provide an `allure` extra or `--allure` flag, generate Allure reports, or publish
them from the Test Runner UI.

## Try Allure locally

From the repository root, collect results with the standard adapter option `--alluredir`:

```bash
mkdir -p artifacts/allure
allure_run_dir=$(mktemp -d "$PWD/artifacts/allure/run-XXXXXXXX")
uv run --with allure-pytest pytest tests/unit tests/integration \
  --alluredir "$allure_run_dir/allure-results"
```

`uv run --with` makes the adapter available for this invocation without changing project dependency
metadata. Choose and pin a compatible adapter version for repeatable use. The example runs only
non-hardware tests. Hardware runs still require explicit stand preparation and `--stand`.

Each invocation uses a fresh directory under `artifacts/allure/`; pytest continues creating its
normal timestamped directory independently. This documentation-only integration does not place
Allure results automatically inside that timestamped directory. Do not infer a run's directory
from `latest.log` during concurrent sessions. If a downstream project requires one shared run
directory, integrate path selection into its pytest plugin before the Allure adapter initializes.

The adapter produces result files, not a browser report. Install an Allure CLI separately using
the instructions for the selected major version: [Allure 2](https://allurereport.org/docs/install/)
uses Java; [Allure 3](https://allurereport.org/docs/v3/install/) uses Node.js. Pin the generator
version in the consuming project's tooling or a separately maintained container image.

For example, with an installed **Allure 2** CLI, view the saved results locally:

```bash
allure serve "$allure_run_dir/allure-results"
```

Or generate a persistent report and open it through the CLI's local server:

```bash
allure generate "$allure_run_dir/allure-results" -o "$allure_run_dir/report"
allure open "$allure_run_dir/report"
```

Run report generation even if pytest returned a test-failure exit code; a failed test run is often
the most useful report. Generation does not rerun tests. Use the selected version's documentation
for CLI options rather than mixing Allure 2 and Allure 3 commands.

## Keep the integration optional

For a lasting integration in a project created from this template, an optional dependency group
can be declared with `uv add --optional allure allure-pytest`. Commit the resulting dependency
metadata and lockfile in that project, and run with `uv run --extra allure pytest ... --alluredir
PATH`. This extra is a downstream choice, not an existing feature of this template.

Omit `--with allure-pytest` (or the downstream extra) and `--alluredir` to use the ordinary template
workflow. Avoid unconditional `import allure` statements in tests that must also run without the
adapter. Existing `StepLogger` messages remain logs; they do not automatically become structured
Allure steps. Keep reporting concerns in the test layer and keep device APIs independent of Allure.

## Publish for a team

Start with a CI publication step or a web server serving generated reports. Preserve a separate URL
for each run, publish after test failures too, and retain the original pytest exit status if report
generation or upload fails. Archive raw results when reports may need to be regenerated.

Projects needing central storage can evaluate
[Allure Report Storage](https://allurereport.org/docs/self-hosted-storage/) for Allure 3.
Projects already using TestOps can upload through
[`allurectl`](https://docs.qameta.io/reference/ecosystem/allurectl/) with their server URL, project
ID, and token. These are external deployment choices; neither service is required for local use.
The current Test Runner only exposes the standard template artifacts. Adding an Allure link or
automatic publication requires a separate downstream change.

Keep endpoint settings and tokens in runtime configuration or CI secrets, never in inventory or
scenario YAML. Review captured logs and attachments for secrets before publication. Define history
grouping for compatible stands and software configurations, and configure server retention
separately. Local Allure files under `artifacts/` are ignored by Git and are removed by
`./scripts/clean-artifacts.sh` along with other run artifacts.

See the [Allure pytest guide](https://allurereport.org/docs/pytest/) for adapter usage, parameters,
and optional report annotations.
