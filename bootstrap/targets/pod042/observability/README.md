# Observability on pod042

The `observability` capability owns collection, Loki storage, the usage page, and Grafana. Native mise Compose resources deploy it; it does not own the inference services or change their requests. Netdata still owns host/service health monitoring.

```diagram
┌─────────────────────────┐
│ Doppelclaude HTTP daemon│──▶ records.jsonl ─────────────┐
└─────────────────────────┘                              │
                                                        ▼
┌─────────────────────────┐   ┌───────────────────┐  ┌───────┐   ┌──────┐   ┌─────────┐
│ CLIProxyAPI usage queue │──▶│ Sanitizing poller │─▶│ Alloy │──▶│ Loki │◀──│ Grafana │
└─────────────────────────┘   └───────────────────┘  └───────┘   └──────┘   └─────────┘
                                  records.jsonl       positions    WAL      Loopback
                                                                     ▲
                                                               ┌─────┴───────┐
                                                               │ Usage index │◀── Amp thread titles (CLI, every 15 min)
                                                               └─────────────┘ SQLite rollups, usage.thurstons.house
```

Only the CPA adapter and the usage index are custom code. Alloy tails JSONL, attaches structured metadata, and sends it to Loki. Loki's index labels are `host` and `service_name`; thread/request/runtime IDs remain structured metadata, not unbounded index labels. Other applications can join through another source in `config.alloy` without changing the inference services.

## Collected evidence

| Source | Evidence | What it can answer |
| --- | --- | --- |
| Bridge `request_complete` | Request/thread/runtime IDs, request kind, requested/served model, release version, duration, outcome, four usage buckets | Which identified threads or anonymous calls dominate observed tokens? Which models are actually served? Did a release change cache reuse? |
| Bridge nested `executions` and diagnostics | Existing query spawn/reuse/rebuild reasons, configuration fingerprints, SDK result observations | Does a cache-read drop coincide with a lifecycle or configuration change? A rebuild alone is not a cache miss. |
| CPA `usage` | Execution/request/session/parent IDs, provider/model, hashed client key, latency/TTFT, outcome, validated token breakdown | Which callers/models dominate proxy usage? Does an explicitly identified session cache well? |
| CPA collector notices | Starts, five-minute successful-poll heartbeat, errors/recovery, rejected record count | Was collection running? Is a quiet period trustworthy or potentially a gap? |

Both sources use `usage.input` (uncached), `usage.cache_read`, `usage.cache_creation`, and `usage.output`. CPA accepts its canonical schema-v2 non-overlapping buckets; reasoning is a subset of output, not another additive bucket. Unsupported/incomplete accounting keeps `usage: null`, not fabricated zeroes. Validated schema-v2 `token_breakdown` retains known buckets and unclassified remainder even when accounting is incomplete; this is supporting evidence, not another additive usage source.

The bridge source is the HTTP daemon's existing content-free record log, **not every Pi/Claude process on the host**. It includes failures/disconnects, but these often lack final token usage. Nested SDK results overlap response usage; never add the two. This collector preserves the current evidence, not a complete upstream-attempt ledger. Independent late SDK events, Pi-local events, quota sampling, API-price estimates, parent inference, and historical rotated-file backfill are not implemented here.

CPA client-key hashes distinguish applications only if they use different keys. Inbox Zero uses the dedicated `INBOX_ZERO_CLI_PROXY_API_KEY` secret; historical traffic on the shared key remains unattributed. CPA exports a normalized session identifier; it need not be the original Amp thread ID. Preserve unknown attribution rather than guessing from timing.

The dedicated key lives in the Agent vault's Inbox Zero item, field `cli proxy api key`. The containers capability supplies it as Inbox Zero's `ANTHROPIC_API_KEY`. CPA's application-managed access list must also contain it: read `/v8/management/config/access/api-keys`, then PUT the existing list plus the dedicated key with the returned ETag in `If-Match`. This preserves other clients and reloads CPA without restarting it. Recreating only Inbox Zero's application container picks up a changed key. Do not reuse this key in other applications or introduce a per-user key override in Inbox Zero if its traffic should remain attributable here.

## Deployment and access

Prerequisites: the Docker/ingress and doppelclaude capabilities, UID/GID 3456, mounted `/mnt/black-box/docker`, the bridge diagnostics directory, CPA usage statistics enabled, and **no other consumer draining CPA's usage queue**. The deployed CPA config currently enables usage statistics; this capability does not take ownership of its application-managed config.

From the repository root, `mise pod042 observability --check` previews only this capability. After approval, `mise pod042 observability` installs `/etc/ansiblonomicon/observability/` and the Compose project. The driver resolves only `CLI_PROXY_API_MANAGEMENT_KEY` from fnox; its rendered file is private to UID 3456. It does not restart doppelclaude or CPA.

State lives under `/mnt/black-box/docker/observability/{loki,alloy,cpa,grafana,usage}`. The files and state use the bridge's service UID so Alloy can read its private rotating log without relaxing permissions. Alloy mounts the diagnostics directory read-only but selects **only `records.jsonl`**, never `prompts.jsonl`. CPA uses an allowlist: no prompts, email bodies, response bodies/headers, IP addresses, OAuth tokens, or raw API keys. Client keys become SHA-256 fingerprints. Do not add broad Docker stdout collection without reviewing each service's log contents.

Grafana listens on pod042 loopback port **3030**, with anonymous **Editor** access for Explore and saved dashboards. It is trusted-local access, not an authentication boundary: any local user can query the data and edit dashboards. There is no initial admin, public listener, Caddy route, or Cloudflare route. Reach it with `ssh -N -L 3030:127.0.0.1:3030 pod042`, then open `http://localhost:3030/explore`. Add authentication before exposing it beyond loopback. Loki and Alloy have no host ports. Grafana's bundled plugins are used without background plugin upgrades.

The usage page is at `https://usage.thurstons.house/`, a Caddy `local_only` route like the other pod042 services, and on pod042 loopback port **3031**. It has the same trusted-local model: anyone who reaches it can read the data and add or delete notes.

## Usage page

`usage_index.py` reads both services from Loki every 15 seconds, re-reading the last hour each poll and the last two days hourly and after a Loki error, so a late Alloy delivery still lands; a backlog older than two days needs a rebuild. It keeps a SQLite index in the `usage` state directory. For each bridge thread it records the idle gap since the previous request with usage, whether the request went cold (read less than half of the prefix that request left), and which runtime close or bridge restart fell between them; a late record recomputes the rest of its thread. It then rebuilds day and hour rollups for the days it touched. The page loads one `/api/view` response computed from those rollups, plus one conversation's requests when you drill in, so its cost follows the number of days and conversations, not requests.

Each request has one cause: a changed configuration fingerprint first, then the bridge's sync reason. **Rewrites** are cache writes caused by a reopened runtime, a configuration change, diverged history, or a retry after failure; writes for new turns and first requests are expected. CLIProxyAPI cannot know why it wrote to the cache, so its requests have no cause and the page leaves their rewritten share blank. Requests without usage count as unknown, never zero. Requests without a thread pool by request kind, as `anonymous` or `opencode_one_shot`.

Bridge records carry the daemon's release `version` from the first release after 0.14.15; earlier records have none. Each release is a marker on the timeline, and clicking it compares that release with the one before it. The `amp-titles` user timer sends every Amp thread title from `amp threads list` to `POST /api/titles` every 15 minutes, because only the signed-in CLI can list them. OpenCode titles stay on the machine that ran OpenCode, and derived conversations have none.

The indexer validates records at ingestion and exits on anything it cannot classify, such as a new bridge reason or request kind; Compose restarts it into the same error until the classification is added here. Except for notes and titles, the index is derived from Loki. Bump `SCHEMA_VERSION` when a change alters what it derives; the next start drops the derived tables and rebuilds them from `--since`, which takes seconds, and keeps notes and titles. Inbox Zero is attributed by the key fingerprint in `compose.yaml`; on rotation, add the new fingerprint as another `--inbox-zero-key-hash` and keep the old one.

## Reading cache behavior

In Grafana Explore, select Loki. Successful HTTP-response cache reads by thread over one hour:

```logql
sum by (thread_id) (
  sum_over_time({service_name="doppelclaude"}
    | json
    | event="request_complete" | outcome="success"
    | unwrap usage_cache_read | __error__="" [1h])
)
```

Filter with `| thread_id="T-..."` for a particular thread, or inspect `requestKind` for keyed versus anonymous traffic. Grouping on an extracted field is query-time work; it does not make the field an index label. Missing thread IDs do not imply a known parent.

CPA execution events, including failed executions and incomplete accounting:

```logql
{service_name="cli-proxy-api"} | json | event="usage"
```

Inbox Zero executions on its dedicated key:

```logql
{service_name="cli-proxy-api"} | json | event="usage"
  | client_key_hash="81d13a717ce9067b297422704526f6c3daf0cd566f4626fc84e43716a1f22729"
```

This is the key's SHA-256 fingerprint, not the credential. On rotation, preserve the old fingerprint for historical queries and add the new one; do not relabel older shared-key traffic as Inbox Zero.

For CPA numeric totals, additionally filter `accounting_quality="complete"`. Always show incomplete/error counts alongside totals. To investigate collection coverage:

```logql
{service_name="cli-proxy-api"} | json | event=~"collector_.*"
```

Compute cache hit ratio as **sum(cache_read) / sum(input + cache_read + cache_creation)** over the same rows, not the mean of per-request percentages. Keep writes and reads visible separately: a warm rebuild can hit cache, and a reused process can still miss it. These are observed token statistics, **not subscription quota percentages**. Two clients using the same subscription do not provide a token-to-quota conversion.

## Durability and gaps

- The poller drains up to 1,000 CPA records every five seconds and fsyncs each sanitized batch and its parent directory before its next fetch. Errors back off to 60 seconds; auth errors and invalid records exit nonzero. Valid peers in a malformed batch are persisted. Write failures are fatal. Compose restarts the process after exits.
- CPA pops records before replying, has in-memory retention (default 60 seconds, maximum 3,600), and loses pending events on restart. A lost HTTP response, collector crash between fetch and fsync, or a second poller can lose events. Notices expose known/possible gaps; an empty response cannot prove no upstream loss.
- Both spools retain a 64 MiB active file plus eight rotations. Alloy persists file positions and follows rotation while running. It watches active filenames only to avoid re-ingesting renamed archives. Rotation while Alloy is stopped can strand unread lines in archives; they are **not automatically backfilled**. Keep those archives for a separate recovery pass.
- Alloy retries transient Loki failures indefinitely while running. Its position checkpoint is **not** a durable delivery acknowledgement, and this setup does not enable Alloy's experimental write WAL. An Alloy crash can lose buffered entries even though the original spool survives. Loki's own WAL protects accepted records; that does not provide end-to-end exactly-once delivery. Permanent rejections (for example oversized/too-far-out-of-order entries) still require operator attention in Alloy logs.
- Loki disables old-sample age rejection, but its per-stream out-of-order window still applies. Don't replay old archives into an already-current stream and assume they were accepted. No replay tool is included yet.
- Historical queries include unflushed ingester data. Single-binary filesystem mode needs both `querier.query_ingesters_within: 0s` and `ingester.query_store_max_look_back_period: -1ns`; Loki tests the latter against exactly minus one nanosecond, not any negative duration. Without these, freshly ingested old records can stay invisible until chunks flush. After changing mounted Loki configuration, reconcile the capability and restart only `observability-loki-1` to load it.
- Loki intentionally retains data indefinitely while growth remains modest. Watch disk usage as traffic grows; the bounded source spools are not permanent backups.

## Verification

These commands use no Claude quota and never contact production CPA:

```sh
mise -C bootstrap/targets/pod042 -E observability run observability:test
mise -C bootstrap/targets/pod042 -E observability run observability:smoke
```

The unit tests invoke the collector CLI against a fake destructive HTTP queue, asserting token values, privacy, failure behavior, and unknown accounting. The index tests check rewrite classification, unknown usage, that late records re-annotate their thread, release comparison, and that a schema rebuild keeps notes and titles. The smoke test runs the actual Compose stack with separate temporary state, a fake CPA endpoint, and synthetic bridge records, including a six-hour-old record that must be immediately queryable. It queries Loki through Grafana, restarts the collectors and Loki, rotates the bridge log, checks exact record/token counts and index-label privacy, and checks that the usage index rolls up the same tokens by day and by release and serves the page. By default it removes its containers/state; run `python3 bootstrap/targets/pod042/observability/smoke.py --keep` to retain an isolated preview. Its randomly assigned ports are loopback-only and it prints the cleanup command.

## Upstream contracts

- [CLIProxyAPI usage queue and schema](https://github.com/router-for-me/CLIProxyAPI/blob/ad8bdd3f20bef44f0684b8a6096a216b2c76040d/internal/redisqueue/plugin.go)
- [CLIProxyAPI canonical token accounting](https://github.com/router-for-me/CLIProxyAPI/blob/ad8bdd3f20bef44f0684b8a6096a216b2c76040d/sdk/cliproxy/usage/accounting.go)
- [Alloy file source](https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.file/)
- [Alloy Loki writer](https://grafana.com/docs/alloy/latest/reference/components/loki/loki.write/)
