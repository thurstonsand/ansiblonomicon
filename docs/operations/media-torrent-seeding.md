# Media torrent seeding policy

This repository manages the TrueNAS media stack: qBittorrent, Prowlarr, Sonarr, and Radarr. The cleanup behavior depends on all four. Do not treat qBittorrent as the single source of truth for seeding policy.

## Intended behavior

- Public tracker downloads may be removed after Sonarr/Radarr successfully import them.
- Private tracker downloads should remain seedable for ratio and account health.
- Sonarr/Radarr imports are hardlinks into `/watch/media`, so removing the original download path after a successful import does not remove the library file.

## Responsibilities

### qBittorrent

qBittorrent should not enforce global seed limits.

Expected global qBittorrent preferences:

```text
max_ratio_enabled = false
max_ratio = -1
max_seeding_time_enabled = false
max_seeding_time = -1
```

Do **not** set global qBittorrent limits such as:

```text
max_ratio_enabled = true
max_ratio = 0
max_seeding_time_enabled = true
max_seeding_time = 0
```

That makes qBittorrent stop every completed torrent, including private tracker torrents. Sonarr/Radarr may then remove private tracker seeds. This has caused data loss before. Annoying, but instructive.

qBittorrent categories seen in use:

- `sonarr`
- `radarr`
- `manual`
- `myanonamouse`
- `prowlarr`

The `myanonamouse` category is private-tracker material and should not be treated like disposable public Arr downloads.

### Prowlarr, Sonarr, and Radarr

The public/private distinction belongs in indexer seed criteria, not qBittorrent global preferences.

Public indexers should have blank/null seed criteria so completed imported downloads can be removed by Arr cleanup behavior.

Private trackers should keep explicit seed criteria. Known private trackers:

- AnimeBytes
- Blutopia
- MyAnonamouse / MAM

Previously used private tracker seed criteria:

| Tracker | Seed ratio | Seed time | Pack seed time |
| --- | ---: | ---: | ---: |
| AnimeBytes | `1` | `262800` | `262800` |
| Blutopia | `1` | unset | unset |

Private trackers have also been configured through a Prowlarr private app profile with RSS and automatic search disabled, interactive search enabled. Verify current live settings before changing this; do not assume.

## Removal rules

Safe automatic/manual cleanup criteria for Arr downloads:

1. qBittorrent torrent is complete.
2. Category is `sonarr` or `radarr`.
3. Sonarr/Radarr history has a `downloadFolderImported` event for the same qBittorrent info hash/download ID.
4. Torrent is not private.
5. Tracker/category/name does not match private markers such as:
   - `animebytes`
   - `blutopia`
   - `myanonamouse`
   - `mam`
6. If removing torrent content manually, only delete source paths under:
   - `/mnt/capacity/watch/downloads/sonarr/`
   - `/mnt/capacity/watch/downloads/radarr/`

Prefer qBittorrent deletion with `deleteFiles=false` first, then delete source download paths only after import/hardlink verification.

## Important qBittorrent state

`stalledUP` is a valid seed state. It means the torrent is complete and available to upload, but no peers currently need data. For a private tracker seed, `stalledUP` is normal and should not be treated as failed or disposable.

## Recovery notes

If a private tracker torrent is accidentally removed but the imported media files remain:

1. Find the original qBittorrent info hash in Sonarr/Radarr history (`DownloadId` / `torrentInfoHash`).
2. Find the original Prowlarr download URL in the grab history event.
3. Recreate the original download folder under `/mnt/capacity/watch/downloads/sonarr` or `/mnt/capacity/watch/downloads/radarr` using hardlinks from the imported media files.
4. Re-add the torrent file to qBittorrent with the original category and save path.
5. Let qBittorrent recheck. It should return to `stalledUP` or another seeding state when complete.

This was used to recover a Blutopia seed:

```text
The.Tale.of.Lady.Ok.S01.1080p.NF.WEB-DL.AAC2.0.H.264-MrHulk
hash: b7f65f035befaf2658b7be71449f7b9d7393d278
tracker: blutopia.cc
```
