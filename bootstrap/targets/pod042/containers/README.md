# Containers

Docker plus one compose project per stack under `/etc/ansiblonomicon/containers/<stack>`, each declared as a `[bootstrap.compose.*]` resource in `mise.containers.toml` and ordered after `service:docker`. `finalize.py` fixes up the group memberships that package installation creates. Netdata reaches Docker only through the read-only socket proxy.

## Subtitles

Bazarr runs in `arr-apps`, with a LAN-only interface at <https://bazarr.thurstons.house>. It reads the TV library from Sonarr at `http://sonarr:8989`, shares its `/media` paths, and refreshes Plex through `http://host.docker.internal:32400` after subtitle changes. Settings, credentials, language profiles and history live under `/mnt/black-box/docker/arr-apps/bazarr/config`; subtitles live beside the videos and appear in Plex's subtitle selector. It does not change anyone's Plex language preferences.

Sonarr's `Anime` automatic-tagging rule adds the `anime` tag to shows with series type Anime, regardless of requester; existing anime are tagged too. Bazarr's tag-based profile assignment maps `anime` to the Japanese language profile during Sonarr sync. The default profile for other TV remains None. These rules live in the applications' persistent state, alongside their other library settings; configure them through Sonarr Settings → Tags and Bazarr Settings → Languages.

[Jimaku](https://jimaku.cc) is connected for Japanese subtitles; Gestdown is also enabled without an account. Jimaku limits API requests to 25 per minute per IP, and Bazarr's provider waits and retries on HTTP 429. Missing-subtitle searches run every 24 hours, with adaptive searching reducing unsuccessful searches to weekly after three weeks. Existing Japanese tracks satisfy the profile, and subtitle upgrades are disabled. A large backlog takes time, and availability and timing depend on the source files. Provider credentials stay in Bazarr's private configuration, never in the repository.

The series match-score cutoff is 85%; Jimaku's series/season/episode/year matches can score 86% without release-specific metadata, below Bazarr's default 90% cutoff. Automatic timing synchronization is enabled for matches below 90%, but different cuts of an episode may still need manual correction.

Nichijou S01E01–E26 use Jimaku's [BD-timed Japanese subtitles](https://jimaku.cc/entry/704), aligned against the existing English tracks and uploaded through Bazarr. The Netflix-timed files do not match these releases' mid-episode breaks and extended episodes. Check timing when replacing the videos; matching episode numbers alone is insufficient.

## DNS assertion

Docker writes each container's `/etc/resolv.conf` on the host at container **start** and bind-mounts it in; it never revisits the file afterwards. If the host had no nameserver at that moment, the container gets `nameserver 127.0.0.11` with `# NO EXTERNAL NAMESERVERS DEFINED`, the embedded resolver has nothing to forward to, and every external lookup returns SERVFAIL until someone restarts the container. Host-network containers get the same file with no nameserver line at all.

`check.py` asserts the outcome. For each running container it reads that host-side file, then queries its nameservers for `api.github.com` over UDP from inside the container's network namespace until one succeeds. It enters only the network namespace, so the host's Python does the asking and images without a shell or a resolver binary are still covered. Containers on `network_mode: none` are skipped; containers sharing a VPN namespace pass through that namespace's own resolver.

It runs on `mise pod042 containers --check`, at the end of a containers reconciliation, and on demand as `containers:check`.

The ordering that makes this hold at boot belongs to the network capability, not here: see `../network/README.md`.
