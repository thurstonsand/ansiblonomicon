# pod042 Healthchecks metadata

`reconcile.py` is a Python 3.13 stdlib adapter for the Healthchecks v3 API. Native bootstrap owns host resources; it has no demonstrated REST metadata resource, so this adapter owns only the five checks in `checks.toml`.

Run inside `scripts/fnox-host exec`, with `HEALTHCHECKS_API_KEY` resolved into the process environment:

```sh
python3 bootstrap/targets/pod042/monitoring/api/reconcile.py [--check] -- CHILD ARGS
```

The adapter verifies the declared Hark integration's ID, name, and kind before writing anything, rejects duplicate managed slugs, and writes only missing or drifted managed checks. It never changes unrelated checks or sends pings, pauses, resumes, or deletes. Run one reconciliation at a time: the API does not provide an atomic create-if-slug-absent operation that rejects duplicates without updating existing checks.

The child receives these returned credentials in its environment:

| Check | Environment variable |
| --- | --- |
| `pod042-heartbeat` | `POD042_HEARTBEAT_PING_URL` |
| `pod042-scrub-ark` | `POD042_SCRUB_ARK_PING_URL` |
| `pod042-scrub-black-box` | `POD042_SCRUB_BLACK_BOX_PING_URL` |
| `pod042-sanoid` | `POD042_SANOID_PING_URL` |
| `pod042-sanoid-prune` | `POD042_SANOID_PRUNE_PING_URL` |

The adapter removes `HEALTHCHECKS_API_KEY`, `OP_*`, and `FNOX_*` before executing the child. Other host environment values remain available. It never stores credentials or provider responses on disk. The caller must keep child output secret-safe; native bootstrap persists only these scoped ping URLs in root-owned mode-0600 secret files.

`--check` performs GET requests only and reports proposed changes using local slugs and field names, never remote values or identifiers. Missing checks cause exit 1 before child execution because no real ping URLs exist yet. With all checks present, it passes their actual URLs to the child even if metadata drifts. **The caller must supply a read-only child command, such as native bootstrap's plan, when using `--check`.** The adapter does not translate child arguments or sandbox child actions.

HTTPS requests go directly to `healthchecks.io`, without environment proxies or redirects, with a 15-second socket timeout. API response errors suppress payloads, URLs, and exception details. A failed write can have succeeded remotely; rerun to discover actual state. There is no provider cache or automatic retry.

Full reconciliation and full `--check` require Healthchecks API availability, just as their declared secret set requires the provider. This is intentional: they must not silently skip remote desired state. An explicit `mise pod042 base` remains independent of Healthchecks for SSH/sudo repair.

All schedules use the physically verified `America/Los_Angeles` timezone. Ark's three-day grace covers the observed 45-hour scrub. Black-box's two-hour grace covers the packaged timer's one-hour jitter and its roughly six-minute scrub. Sanoid snapshot and prune checks each run every 15 minutes with 15 minutes of grace. Their finish-only hooks report each native unit's result independently; the Sanoid adapter treats stderr as failure because Sanoid can warn about failed ZFS operations and still exit zero. Creating checks does not arm monitoring: heartbeat, actual scrub runs, and Sanoid runs activate them after their jobs and scoped credentials are installed.
