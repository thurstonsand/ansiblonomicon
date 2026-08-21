---
status: closed
type: research
claimed: subagent
blocked-by: []
---

# Plex off the catalog app

## Question

How does Plex move from the TrueNAS catalog app (`ix-apps`) to a plain compose stack without losing identity, watch state, or QuickSync?

Establish against primary sources (Plex docs, plexinc/pms-docker, the current host, `thurstonsand/nixonomicon` on GitHub):

- Prior art: `thurstonsand/nixonomicon` ran Plex outside a catalog app before — extract that config as a starting shape.
- Current state on the host: where the catalog app keeps `Library/Application Support` under `/mnt/performance/apps/plex/config` vs `ix-apps` internals; what must be copied for server identity (Preferences.xml, databases) to survive.
- Plex Pass image (`image_selector: plex_pass_image` today) → the equivalent official image/tag and claim behavior on an existing config dir.
- QuickSync in plain compose: `/dev/dri` device mapping, group perms (`render` gid), current `run_as` 3001/… mapping.
- Host networking equivalence for remote access/discovery.

Deliver a migration recipe: files to copy, compose skeleton, verification steps (server identity preserved, HW transcode confirmed via dashboard).

## Resolution

There is no migration. The catalog app already runs `plexinc/pms-docker:plexpass` in host networking with `/dev/dri` bound in, and the entire server lives on `performance/apps/plex` — its own dataset, which survives the pool import. `/mnt/.ix-apps` holds only the overlay2 graph and a rendered compose file; all disposable. Delete the app, write our own compose against the same paths, and the server comes back as itself: same `machineIdentifier`, same `/data/movies` + `/data/tv` sections, same watch state.

The compose is smaller than the chart. Drop `PLEX_CLAIM` (the image ignores it when `PlexOnlineToken` exists), drop the Logs bind mount (a TrueNAS graft), drop the cpu/memory limits and the capability set. Keep `PLEX_UID`/`PLEX_GID` at 3001 — it matches the on-disk ownership and skips a `chown -R` over 29 GB. `devices: - /dev/dri:/dev/dri` is the whole QuickSync story; the image's own init resolves the render gid at runtime, so no `group_add`, but the container must start as root. `:plexpass` stays: the tag self-updates PMS at every container start, which is why watchtower must keep excluding it.

Two things genuinely change. `PreferredNetworkInterface="br0"` in `Preferences.xml` names a bridge that will not exist on Proxmox and must be cleared while the container is stopped. And remote access runs on manual port mapping with relay disabled, so the router forward has to be rebuilt at the new house or remote access simply fails. (Corrected by the [UDMP network audit](14-udmp-network-audit.md): the live forward is 32400→32400 — `ManualPortMappingMode=1` with no `ManualPortMappingPort` means default 32400, confirmed in the router's DNAT table. Not 20460 as first recorded.)

One gap to close before teardown: the logs show no recent hardware video transcode, so capture a known-good `Transcode (hw)` baseline while the old host still runs — otherwise a post-cutover failure has nothing to compare against.

Negative result on the prior art: `thurstonsand/nixonomicon` never ran Plex outside the catalog app. The reusable pattern there is frigate's `/dev/dri` passthrough.

Full evidence, compose skeleton, and verification steps: [Plex catalog app to compose](../research/plex-catalog-to-compose.md).
