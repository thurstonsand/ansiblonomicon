# Plex: catalog app → plain compose

Research for [ticket 06](../tickets/06-plex-catalog-to-compose.md). Evidence gathered read-only from the live TrueNAS host on 2026-08-19, plus primary sources (`plexinc/pms-docker`, Docker Hub).

## Headline

There is no migration. The TrueNAS catalog app is already `plexinc/pms-docker:plexpass` in host networking with `/dev/dri` bound in, and every byte of server identity already lives on a pool dataset that survives the Proxmox import. The catalog app contributes nothing but a rendered compose file. Delete the app, write our own compose file pointing at the same paths, and the server comes back as itself.

Two things do have to change: the `PreferredNetworkInterface="br0"` preference (no `br0` on Proxmox), and the separate Logs bind mount (a TrueNAS-ism worth dropping).

## What the catalog app actually is

`docker inspect ix-plex-plex-1` on the live host:

| Field | Value |
| --- | --- |
| Image | `plexinc/pms-docker:plexpass` (digest `sha256:8aeb4a98…`, built 2021-04-14) |
| Compose project | `ix-plex`, rendered at `/mnt/.ix-apps/app_configs/plex/versions/1.3.12/templates/rendered/docker-compose.yaml` |
| Network | `host` |
| Container user | `0:0`, with `PLEX_UID=3001` / `PLEX_GID=3001` |
| Extra groups | `44` (video), `107` (render), `568` (apps) |
| Devices | `/dev/dri` → `/dev/dri`, `rwm` |
| Limits | `NanoCpus` 4e9, `Memory` 4 GiB, `MemorySwap` 8 GiB |
| Caps | drop `ALL`, add `CHOWN DAC_OVERRIDE FOWNER KILL SETGID SETUID`; `no-new-privileges` |
| Env | `TZ=America/New_York`, `UMASK=002`, `CHANGE_CONFIG_DIR_OWNERSHIP=true`, `NVIDIA_VISIBLE_DEVICES=void`, `PLEX_CLAIM=claim-…` |
| Restart | `unless-stopped` |
| Healthcheck | `/healthcheck.sh` (baked into the image) |

Binds:

```
/mnt/performance/apps/plex/config  → /config
/mnt/performance/apps/plex/logs    → /config/Library/Application Support/Plex Media Server/Logs
/mnt/capacity/watch/media          → /data
/mnt/capacity/watch/transcode      → /transcode
```

So the "ix-apps internals" question resolves to: `/mnt/.ix-apps` holds the docker graph driver (`overlay2`), container runtime metadata, and the rendered chart. All disposable. `performance/apps/plex` is its own ZFS dataset (`zfs list`), and it holds the entire server.

## Where identity lives

`/mnt/performance/apps/plex/config/Library/Application Support/Plex Media Server/` — 29 GB total, owned `appsvm` (uid 3001, gid 3001):

- `Preferences.xml` — `MachineIdentifier`, `ProcessedMachineIdentifier`, `PlexOnlineToken`, `CertificateUUID`. This file *is* the server's identity.
- `Plug-in Support/Databases/com.plexapp.plugins.library.db` (63 MB) — libraries, watch state, users. Plus `.blobs.db` (121 MB) and the rolling `-2026-08-NN` nightly backups Plex keeps itself. Note live `-wal` / `-shm` files: **stop the container before copying anything**, or the copy is a torn database.
- `Metadata/` (2.5 GB), `Media/` (25 GB — thumbnails/BIF), `Plug-in Support/`, `Scanners/`, `Codecs/`, `Drivers/` — regenerable but expensive; keep them.

Live server, for post-cutover comparison:

```
machineIdentifier  8d8336b217cd7836987429589cced6f7dd668608
friendlyName       truenas
myPlexSubscription 1   (Plex Pass)
library sections   /data/movies (id 1), /data/tv (id 2)
```

Library paths are `/data/...`, i.e. container-relative. As long as the new compose keeps `/mnt/capacity/watch/media → /data`, no library repathing is needed.

Preferences that encode the *old* host and need attention:

- `PreferredNetworkInterface="br0"` — TrueNAS's bridge. Proxmox's is `vmbr0`. **Must be cleared or corrected**, or Plex binds/advertises against an interface that doesn't exist.
- `customConnections="http://192.168.1.68:32400"` — fine if the host keeps `.68`; otherwise update.
- `ManualPortMappingMode="1"` with remote access on external port 20460 (seen in the logs) — the router forward has to survive the house move. `RelayEnabled="0"`, so there is no fallback if it doesn't.
- `LanNetworksBandwidth="192.168.1.0/255.255.255.0"`, `HardwareAcceleratedCodecs="1"` — keep as-is.

## Prior art: nixonomicon

Negative result. The public `thurstonsand/nixonomicon` never ran Plex outside the catalog app — no `pms-docker`/`plexmediaserver` reference anywhere in the tree or in all 168 commits of history; the only mention is `nas/stacks/watchtower/compose.yaml`, which *excludes* `ix-plex-plex-1` from watchtower updates. That exclusion is itself the useful artifact: it confirms Plex has always been intentionally outside the auto-update path, because the `plexpass` image self-updates (below).

The reusable prior art is `nas/stacks/frigate/compose.yaml`, which does iGPU passthrough in plain compose the same way we need:

```yaml
    devices:
      - /dev/dri:/dev/dri # Intel iGPU acceleration
```

## The image, and how `plexpass` works

`plexinc/pms-docker:plexpass` is not a stale image to be replaced — it is the official image, and it is the correct target. Docker Hub shows the tag last pushed 2021-04-14, yet the running container reports PMS `v1.43.3.10896-cb3ebc72d`. The Dockerfile bakes `ARG TAG` into the install config, and `root/etc/cont-init.d/50-plex-update` reads that back on **every container start**, queries plex.tv with the `PlexOnlineToken` from `Preferences.xml`, and installs the current build of that channel before PMS launches. `plexpass` therefore means "latest Plex Pass build, refreshed at each start" — which is why watchtower is told to leave it alone, and why the base OS in the container is still Ubuntu 20.04 while the server binary is current.

Keep `:plexpass`. Restart to update; the update is a no-op when already current (`50-plex-update` short-circuits on version equality).

### Claim behavior on an existing config dir

From `root/etc/cont-init.d/40-plex-first-run`:

```bash
token="$(getPref "PlexOnlineToken")"
if [ ! -z "${PLEX_CLAIM}" ] && [ -z "${token}" ]; then
```

`PLEX_CLAIM` is only exchanged when there is **no** existing token. The README says the same ("If server is already logged in, this parameter is ignored"). Our `Preferences.xml` has a token, so **drop `PLEX_CLAIM` from the new compose entirely** — no `PLEX_CLAIM_TOKEN` env plumbing, no expired-claim-token failure mode. The current `truenas_apps.plex` value pulls it from the environment, which is dead weight.

The same script also generates `MachineIdentifier`/`ProcessedMachineIdentifier` only when absent, so an existing config is never re-identified.

### `CHANGE_CONFIG_DIR_OWNERSHIP`

Default `true`. The script only walks `/config` if `Preferences.xml` is *not* already owned by the plex uid:

```bash
if [ ! "$(stat -c %u "${prefFile}")" = "$(id -u plex)" ]; then
  find /config \! \( -uid … -gid … \) -print0 | xargs -0 chown -h plex:plex
```

Keep `PLEX_UID=3001` / `PLEX_GID=3001` and the check passes immediately — no `chown -R` across 29 GB. Change the uid and you buy a very long first start plus a permission mismatch against `/mnt/capacity/watch/media`, which is `3001:3001` on disk. **uid/gid 3001 is load-bearing; do not "normalize" it to the `950:544` the docker stacks use.** (The wider uid story — media is `3001:3001`, other stack dirs are `950:3001` — belongs to the storage-services ticket.)

## QuickSync in plain compose

`root/etc/cont-init.d/45-plex-hw-transcode-and-connected-tuner` handles device group membership itself: for every char device under `/dev/dri`, it stats the gid, creates a group for it if the container's OS has none, and adds `plex` to it. That is why the live container shows `groups=0(root),44(video),107(video2),568` — `107` had no name in Ubuntu 20.04 so it invented `video2`.

Consequences:

- **No `group_add:` needed.** Host gids differ between TrueNAS (`render` = 107) and Debian/Proxmox (typically 104), and the script resolves whatever gid is actually there at runtime. Adding `group_add` is harmless but redundant.
- **The container must start as root.** Do not set `user:` in compose — the init scripts need root to `usermod`/`groupadd` and to chown. Privilege drop to `plex` happens inside via s6. This matches the catalog app, which runs `0:0` despite the app's `run_as: 3001`.
- `devices: - /dev/dri:/dev/dri` is the whole ask. Host devices today: `card0` `0:44`, `renderD128` `0:107`, driver `i915` on `pci-0000:00:02.0`.
- Hardware transcoding also requires Plex Pass (`myPlexSubscription=1`, current) and `HardwareAcceleratedCodecs="1"` (already set).

Caveat worth naming: current logs show `TPU: hardware transcoding: final decoder: , final encoder:` — empty — on the few recent transcode requests, which are audio-only/VAD work. **There is no recent evidence in the logs of a real hardware video transcode.** Capture a known-good baseline *before* teardown (step 1 below), otherwise a post-cutover failure is unattributable.

## Host networking

The catalog app already uses `network_mode: host`; `ss -ltn` confirms `*:32400` on the host. Plain compose `network_mode: host` is exactly equivalent — no port list, no `ADVERTISE_IP` (bridge-only, and it would overwrite `customConnections`), and GDM/DLNA discovery broadcasts keep working. Nothing to redesign.

The one caveat is `PreferredNetworkInterface="br0"` above: host networking means Plex sees the host's interfaces directly, and Proxmox will present `vmbr0`. Clear the pref and let Plex re-detect.

## Migration recipe

Assumes the pools import intact, so paths are unchanged. If they are, **no file copying is required at all** — steps 2–3 are the belt-and-braces backup, not the migration.

**1. Baseline, before touching anything (old host, still TrueNAS).**

- Force a video transcode from a client (e.g. set quality to 4 Mbps on a 1080p H.264 file) and confirm Plex Dashboard shows `Transcode (hw)` on the video stream. Screenshot it.
- Record `machineIdentifier`, `friendlyName`, section ids/paths, and a couple of known watch positions:
  ```bash
  curl -s "http://127.0.0.1:32400/?X-Plex-Token=$TOKEN" | head -c 400
  curl -s "http://127.0.0.1:32400/library/sections?X-Plex-Token=$TOKEN" | grep -o '<Location[^>]*>'
  ```

**2. Quiesce.** `docker stop ix-plex-plex-1` (or delete the app from the TrueNAS UI). The WAL must be checkpointed before any copy.

**3. Safety copy of the small, irreplaceable subset** — off-box, since the whole point is that the pool is about to be re-imported by a new OS:

```
Library/Application Support/Plex Media Server/Preferences.xml
Library/Application Support/Plex Media Server/Plug-in Support/Databases/   (~700 MB with the nightly backups)
```

`Metadata/`, `Media/`, `Cache/` can be left to the pool; they regenerate if lost. This subset alone restores identity, libraries, and watch state onto a bare config dir.

**4. Rebuild the host, `zpool import capacity performance`.** Verify `/mnt/performance/apps/plex/config` is present with `3001:3001` ownership intact and `/dev/dri/renderD128` exists.

**5. Fix the interface preference** before first start (Plex rewrites `Preferences.xml` on shutdown, so edit it while stopped):

```bash
# drop the stale TrueNAS bridge binding; Plex re-detects
sed -i 's/ PreferredNetworkInterface="br0"//' \
  "/mnt/performance/apps/plex/config/Library/Application Support/Plex Media Server/Preferences.xml"
```

**6. Deploy the stack** via the existing `docker_stack` role — `ansible/stacks/plex/compose.yaml.j2`, landing at `/mnt/performance/docker/stacks/plex/compose.yaml`:

```yaml
services:
  plex:
    image: plexinc/pms-docker:plexpass
    container_name: plex
    restart: unless-stopped
    network_mode: host
    devices:
      - /dev/dri:/dev/dri # Intel UHD 770 QuickSync
    volumes:
      - /mnt/performance/apps/plex/config:/config
      - /mnt/capacity/watch/media:/data
      - /mnt/capacity/watch/transcode:/transcode
      - /etc/localtime:/etc/localtime:ro
    environment:
      TZ: America/New_York
      PLEX_UID: 3001
      PLEX_GID: 3001
      UMASK: "002"
    labels:
      com.centurylinklabs.watchtower.enable: "false"
```

Deliberate departures from the catalog app:

- **No `PLEX_CLAIM`** — ignored with an existing token; removes a secret and a stale-token trap.
- **No Logs bind mount.** The catalog app grafted `/mnt/performance/apps/plex/logs` over the Logs subdirectory (owner `950`, mismatched with everything else). Logs belong inside `/config`; drop the mount. Existing logs are archaeology — copy them in if wanted, or let Plex recreate the directory.
- **No cpu/memory limits.** 4 cores / 4 GiB was iX's default on a 10-core, 96 GB box. Add `deploy.resources.limits` back only if something demonstrates a need.
- **No cap drop/add set.** The image needs root at init to manage the render group and ownership; reproducing iX's exact capability list is unnecessary complexity for a homelab. Revisit if a hardening ticket wants it.
- Consider relocating `/transcode` off the raidz1 to the NVMe pool or tmpfs — `TranscoderTempDirectory` is `/transcode` inside the container, so it's a compose-side change only. Out of scope here; noted for the topology ticket.

**7. Watchtower** must keep excluding Plex. The label above covers it; the nixonomicon-era name-based exclusion (`ix-plex-plex-1`) is now wrong and should become `plex`.

## Verification

1. `docker logs -f plex` — expect `Plex Media Server first run setup complete` with **no** "Attempting to obtain server token from claim token" line (proof the existing token was honored) and an update line from `50-plex-update`.
2. `curl -s "http://127.0.0.1:32400/?X-Plex-Token=$TOKEN"` → `machineIdentifier` matches `8d8336b217cd7836987429589cced6f7dd668608`. Identity preserved; this is the single most important check.
3. `curl -s "http://127.0.0.1:32400/library/sections?X-Plex-Token=$TOKEN"` → `/data/movies` and `/data/tv`, item counts unchanged, no "unavailable" libraries.
4. Watch state: pick a partially-watched episode recorded in step 1 and confirm the resume offset survived. Confirms the database, not just the preferences file.
5. `docker exec plex ls -l /dev/dri` → `card0`/`renderD128` visible; `docker exec plex id plex` → member of the group owning `renderD128`.
6. Force the same transcode as step 1; Plex Dashboard must show `Transcode (hw)`. Cross-check `intel_gpu_top` on the host showing Video engine load.
7. Remote access: Settings → Remote Access reports "fully accessible" (needs the router forward to 20460 rebuilt at the new house), and a client on another network plays.
8. Clients rediscover the server without re-pairing — the machine identifier being unchanged means no "new server" appears in anyone's list.

## Sources

- Live host, 2026-08-19: `docker ps`, `docker inspect ix-plex-plex-1`, `zfs list`, `ls -ln /dev/dri`, `docker exec` reads of `Preferences.xml` / `Plug-in Support/Databases` / logs, `curl` against the local PMS API.
- `plexinc/pms-docker` @ master: `README.md`, `Dockerfile`, `root/etc/cont-init.d/40-plex-first-run`, `45-plex-hw-transcode-and-connected-tuner`, `50-plex-update`, `docker-compose-host.yml.template`.
- Docker Hub tag metadata for `plexinc/pms-docker` (`plexpass` last pushed 2021-04-14).
- `thurstonsand/nixonomicon` @ main + full history: `nas/stacks/watchtower/compose.yaml`, `nas/stacks/frigate/compose.yaml`.
- This repo: `ansible/inventory/targets/group_vars/truenas.yml` (`truenas_apps.plex`), `ansible/roles/docker_stack/`, `ansible/stacks/*/compose.yaml.j2`.
