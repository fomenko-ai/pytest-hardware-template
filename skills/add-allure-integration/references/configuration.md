# Allure publication configuration

Use this reference when a user needs help filling configuration for Report Storage, a publisher,
Test Runner, or a stand. Derive values from the actual repository and deployment; names below are
the current pytest hardware template convention, not universal Allure settings.

## Configuration roles

| Role | Typical settings | Purpose |
| --- | --- | --- |
| Report Storage | Bind address, port, main branch, bootstrap token, signing secret | Run persistent storage and authorize administrative token creation. |
| Publisher | Pinned image and `ars1...` report-access token | Convert one run's raw results and upload the generated report. |
| Test Runner | Enabled flag, publisher image, report token, public URL, repository | Collect and publish results and expose browser links for a stable project key. |

The bootstrap token and the `ars1...` report-access token are different credentials. Keep the
bootstrap token with Storage and use it only to mint narrower publisher tokens. Pass the report
token only to the disposable publisher through the runner environment. Never put either token in
inventory, scenario data, a tracked env file, a command argument, a task record, or logs.

`TEST_RUNNER_ALLURE_PUBLIC_URL` is the browser-facing Storage origin used for UI links. It does not
override the Storage endpoint encoded into `TEST_RUNNER_ALLURE_ACCESS_TOKEN`.

## Resolve the publisher endpoint

Choose the publisher-reachable Storage URL before minting the report token. A token minted through
`http://127.0.0.1:<port>` later directs the publisher to its own container, not to the Docker host.
For a Linux Docker host, use one of these as appropriate:

- an HTTPS reverse-proxy name resolvable from the publisher container;
- a protected server or LAN address reachable from the publisher container;
- an explicitly configured Docker-network hostname when Storage and publisher share that network.

Do not recommend exposing the service or credentials over public plain HTTP. The browser-facing URL
may equal the token endpoint, but validate both consumers independently.

## Configure this template

Start from tracked examples and write real values only to ignored files:

- `helpers/allure/.env` configures the Storage bind address, port, main branch, bootstrap token, and
  signing secret;
- `helpers/test-runner-service/.env` configures production runner paths, authentication, and Allure
  publication;
- `helpers/virtual-stand/.env` configures absolute Docker-host paths, the disposable DUT password,
  and optional Allure publication for the local end-to-end example.

Guide the user through these Test Runner values:

```dotenv
TEST_RUNNER_ALLURE_ENABLED=true
TEST_RUNNER_ALLURE_PUBLISHER_IMAGE=local/allure-publisher:<pinned-version>
TEST_RUNNER_ALLURE_ACCESS_TOKEN=ars1.<report-access-token>
TEST_RUNNER_ALLURE_PUBLIC_URL=https://allure.example
TEST_RUNNER_ALLURE_REPOSITORY=pytest-hardware-template
```

Derive `<pinned-version>` from `helpers/allure/Dockerfile` or the current project equivalent; do not
copy a remembered latest version. Set the public URL to an origin reachable by the user's browser.
Use one stable repository value across runs. It selects
`/reports/tree?repo=<repository>`, while Git metadata determines the branches within that tree.

Confirm that the publisher image exists on the Docker host used by Test Runner. Remote framework
images must already contain the optional pytest adapter. In this template, enabling Allure causes
locally built framework images to install the `allure` dependency group automatically.

## Verify without leaking secrets

Where access and authorization permit:

1. Render the Storage and runner Compose configurations and check required variables. Avoid output
   that expands real secrets into logs or chat.
2. Start Storage and check `/api/ping` through the address intended for token creation.
3. Mint a report-access token through that address and save it only in the runner's ignored env
   file or secret store.
4. Build the pinned publisher image and check its reported version.
5. Start Test Runner, check `/health`, and verify its public repository-tree URL.
6. Publish non-sensitive existing results or run non-hardware tests first.
7. Run a virtual or physical hardware scenario only with explicit authorization and a ready stand.

Configuration preparation does not authorize deployment, token creation, report upload, or a
hardware run. Obtain any authority required by the project or execution environment.

## Diagnose publication failures

Check the layers separately:

1. Confirm that pytest created `artifacts/<run-id>/allure-results/`.
2. Confirm that the pinned publisher image exists and starts.
3. Confirm that the endpoint embedded in the report token is reachable from the publisher.
4. Confirm that Storage is healthy and accepts the report token rather than the bootstrap token.
5. Confirm that repository and Git branch metadata produce the expected history grouping.
6. Confirm that the public URL works from the user's browser.

Keep the pytest outcome independent from publication status and report upload errors separately.
