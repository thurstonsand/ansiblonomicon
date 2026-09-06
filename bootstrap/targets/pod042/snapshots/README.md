# pod042 snapshots

Native bootstrap installs Debian's Sanoid package and enables its timer every 15 minutes. Only `black-box/docker` and `black-box/agents`, without recursion, use the active policy: 24 hourly, 7 daily, and 1 monthly snapshot. All other periods are disabled. Legacy datasets are outside the configuration.

Reconcile datasets before snapshots so both active dataset roots exist when the timer starts. Before either snapshot or prune execution, the adapter verifies black-box's pinned pool GUID and requires local `org.ansiblonomicon:layout=fresh-v1` and `org.ansiblonomicon:migration=verified` properties on both roots and rejects any filesystem or volume descendants. AnyPod and Plex are ordinary directories within Docker, not separate snapshot boundaries. A premature timer activation fails before Sanoid can touch legacy data. This guard does not depend on ark or the quarantine's mount state. Monitoring owns `/etc/alerting/checks` and `hc-ping`; snapshots owns its two root-only URL files.

Debian's snapshot and prune services remain separate. Their drop-ins preserve the packaged arguments but run them through `sanoid-run.py`: stdout passes through, stderr is captured and relayed, and any stderr makes an otherwise successful command fail. Sanoid can return zero after ZFS errors, so a quiet exit zero is the success criterion. Keep the configuration warning-free rather than filtering warnings.

Each service sends an ignored-failure, finish-only Healthchecks ping. Notification failure cannot change the producer's result. The snapshot and prune checks each expect a completion every 15 minutes with 15 minutes of grace; no start ping is needed.

Run the adapter regression test locally without ZFS or root:

```sh
python3 -m unittest discover -s bootstrap/targets/pod042/snapshots
```
