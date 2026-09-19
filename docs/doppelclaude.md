# Doppelclaude hosting

Status: edge and isolated host configuration prepared locally; not deployed. The `pi-doppelclaude` repository owns the daemon-only Dockerfile and GitHub Actions build, test and publication workflow. Ansiblonomicon only consumes its published image and configures the service. Installation is gated by the empty `vars.doppelclaude_image` in `bootstrap/targets/pod042/mise.doppelclaude.toml`; set it to the reviewed registry image with an `@sha256:` digest, never a moving tag. Both focused and full reconciliation fail before host commands or secret resolution until it is set.

## Route and authentication

`https://doppelclaude.thurstons.house/v1/messages` and `/v1/models` terminate at the dedicated Worker. The Worker accepts `Authorization: Bearer` or `x-api-key`, using the existing `CLI_PROXY_API_KEY`. This intentionally gives existing personal proxy-key holders access to both services; a separate client key would require a new 1Password item and fnox reference before deployment.

The Worker forwards directly to `https://doppelclaude-origin.thurstons.house`, adding the existing `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET`. A dedicated Access application allows only the existing service-auth policy: no home-network bypass, WARP bypass, or interactive browser login. Terraform owns the origin DNS, tunnel ingress and Access application; Wrangler owns the public Worker custom domain. Neither hostname is active from these local edits alone.

The `home` tunnel forwards directly to `http://doppelclaude:3456` on pod042's private Docker `ingress` network. Compose sets `DOPPELCLAUDE_HTTP_HOST=0.0.0.0` and `PORT=3456`, matching the image's container binding; standalone daemon use defaults to loopback. No host port is published. The daemon retains its API-key check. There is no extra proxy or supervisor; Docker supplies an init process and a 25-second stop grace for the daemon's 15-second shutdown bound, including prebind authentication probes.

Unlike `aig`, this Worker does not route through AI Gateway. It does not read, rewrite, cache or log request bodies. Only `POST /v1/messages` and `GET /v1/models` are forwarded. The daemon owns validation of the required `Amp Thread URL` system marker; the proxy leaves its body untouched. Redirects are not followed and requests are not automatically retried.

## Host and subscription credentials

The dedicated `doppelclaude` capability owns definitions under `/etc/ansiblonomicon/containers/doppelclaude` and mode-0700 durable state under `/mnt/black-box/docker/doppelclaude`. User/group `doppelclaude` has UID/GID 3456 and no login shell. The container uses that identity, a read-only root, dropped capabilities and no-new-privileges, with writable state and temporary storage only. No Docker socket, user home or repository is mounted. Its state volume supplies `HOME=/var/lib/doppelclaude`, `DOPPELCLAUDE_STATE_DIR=/var/lib/doppelclaude` and `CLAUDE_CONFIG_DIR=/var/lib/doppelclaude/.claude`.

The host already has unattended 1Password access through its retained service-account token. `fnox.toml` declares `CLAUDE_CODE_OAUTH_TOKEN`; the confirmed daemon contract inherits this subscription credential into Claude's SDK child. It is not an Anthropic API key. Confirm token validity, renewal and vault access without displaying the value. Do not install the 1Password service-account token in the daemon or the Worker.

The capability selects only `CLI_PROXY_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN`. Native mise renders a root-owned mode-0600 Compose environment file, mapping the former to `DOPPELCLAUDE_HTTP_API_KEY`; the mutually exclusive `_FILE` setting is not used. The Worker receives the proxy key and Access credentials only, never Claude's subscription token. Rotating its key also requires reconciling the daemon and clients.

The requester selects the model through `body.model`, using a stable Claude ID, bare or provider-qualified. The server operator does not set a model or default. `/v1/models` advertises the SDK's startup `supportedModels` result for discovery, not as an allowlist.

The declaration sets 32 runtimes, a one-hour idle TTL, 2 MiB maximum request body, ten-minute request timeout, 15-second shutdown timeout and two application retry attempts. The Worker never retries a request. The authenticated `/v1/models` healthcheck calls the daemon on loopback port 3456 without sending a Claude request.

## Streaming

Return `Content-Type: text/event-stream`, flush headers immediately, and send SSE comments every 15 seconds during silent Claude work. The Worker forwards the response stream without buffering it. Propagate disconnects to Claude and test cancellation through the full path.

[Workers have no HTTP wall-time limit while the client remains connected](https://developers.cloudflare.com/workers/platform/limits/#duration), but runtime updates can terminate long requests. [Tunnel connection settings](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/origin-parameters/) such as `connectTimeout` and `keepAliveTimeout` are not SSE lifetime extensions. Heartbeats and a real multi-minute smoke test are required; no local test proves Cloudflare or Claude will keep a particular session alive. An interrupted POST must not be replayed automatically.

## Installation and activation gates

1. Obtain the successful application GitHub Actions run and its published `linux/amd64` image digest. The intended registry package is `ghcr.io/thurstonsand/http-doppelclaude`. Image building, base-image selection, tests, tagging and publication belong to that application repository, not this host or repo.
2. Record the reviewed registry reference in `vars.doppelclaude_image`. There is no local image assembly or runtime-tarball handoff. Do not substitute a candidate package or unbuilt source branch for the published image.
3. Confirm pod042 already has the Docker `ingress` network and mounted `/mnt/black-box/docker`. The driver checks these prerequisites without reconciling the shared containers capability. The focused apply also skips mise binary maintenance. Review UID/GID 3456 availability before creating the service account.
4. Obtain approval to push the reviewed infrastructure changes, create the new host stack, apply Cloudflare changes, and deploy the Worker and its secret bindings. Run the host commands on pod042's reviewed checkout; they reject any other hostname. Application workflow execution/publication has its own approval boundary.
5. On pod042, run `mise pod042 doppelclaude --check`, then `mise pod042 doppelclaude` after approval. These select only the new capability, not existing stacks. Run `mise run edge:plan`, review the plan, and apply with `mise run edge:apply` after approval. The tunnel configuration depends on the origin Access application so protection is created before the route.
6. Deploy the public endpoint with `mise run edge:deploy:doppelclaude`. Its script reads only the named fnox secrets, deploys the Worker, then reconciles secrets through Wrangler stdin. Missing bindings return 503, not unauthenticated access. This task is intentionally excluded from aggregate `edge:deploy` until host commissioning is complete.
7. Check public requests without/wrong keys return 401; origin requests without service credentials are denied; valid `/v1/models` returns the expected models; missing/invalid thread markers are rejected by the daemon; valid SSE delivers incremental events and 15-second heartbeats through several minutes of silence; cancellation stops upstream work. Repeat after restart to verify durable state and subscription credential handling. Never print credentials or persist full prompts in smoke-test output.

Read-only checks on 2026-09-19 confirmed pod042 reports `x86_64`, Debian `amd64`, Docker 29.8.1, the mounted `black-box/docker` filesystem and existing `ingress` network. UID/GID 3456 were available. Compose explicitly selects `linux/amd64`.

The commissioning scope here is: commit/push the reviewed infrastructure and published runtime digest; run only `mise pod042 doppelclaude --check` and `mise pod042 doppelclaude`; apply the new origin DNS/Access application, additive home-tunnel ingress and HSTS host entries; deploy the dedicated Worker/custom domain and its existing secret bindings. Reject unrelated Cloudflare drift. Full pod042 reconciliation, changes to `aig`, restarting existing stacks and image/npm publication are outside this scope.

## Local checks

```sh
mise run workers:typecheck:doppelclaude
uv run pytest -q tests/test_doppelclaude_deploy.py tests/test_pod042_doppelclaude.py tests/test_pod042_reconcile.py
uv run ruff check scripts/doppelclaude_deploy.py scripts/worker_secrets.py scripts/pod042_reconcile.py
tofu fmt -check terraform/cloudflare
tofu -chdir=terraform/cloudflare validate
git diff --check
```

The Worker task executes Node contract tests and Wrangler's offline bundle dry run, not a TypeScript semantic typecheck. The Python tests require the Docker Compose CLI but not a running Docker daemon. Terraform validation requires an initialized provider cache; formatting does not validate provider schemas. None of these operations applies infrastructure. Live subscription authentication, public-route SSE and Amp UI fork/compaction checks remain commissioning work after a published image and deployment approval are available.
