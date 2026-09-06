# Maintenance activation gates

The registered maintenance capability configures pool properties and SMART/ZED event monitoring. Selecting it includes storage and alerting. Daily short and staggered monthly long self-tests run through smartd 7.5. The monitoring capability owns Healthchecks-backed heartbeat and monthly scrub timers. The final hook changes only the three named pool properties after checking both pool GUIDs; running `python3 maintenance/zed/pool-policy.py` without `--apply` is read-only and also runs during `mise pod042 --check`.

## Registered spares are not manual spares

Physical pod042 runs Debian `zfs-zed` 2.3.9-0+deb13u1 with `/usr/sbin/zed -F`, already enabled and running. Its retire agent can activate ark's registered spare independently of `autoreplace=off`. Removing shell handlers does not disable the compiled retire agent. The operator accepted automatic spare activation on 2026-09-06. Ark keeps its registered spare, WD serial `7LG2VNYK`, WWN `0x5000cca2dbc14ce1`; no pool membership changes are required.

OpenZFS 2.3.9 [`fmd_prop_get_int32`](https://github.com/openzfs/zfs/blob/zfs-2.3.9/cmd/zed/agents/fmd_api.c#L223-L237) hardcodes `spare_on_remove` to 1. [`zfs_retire_recv`](https://github.com/openzfs/zfs/blob/zfs-2.3.9/cmd/zed/agents/zfs_retire.c#L472-L475) replaces removed devices with spares; its [fault path](https://github.com/openzfs/zfs/blob/zfs-2.3.9/cmd/zed/agents/zfs_retire.c#L624-L626) also calls `replace_with_spare`. No configuration override was found. The physical binary contains `spare_on_remove`, `zfs-retire`, and `ZFS Retire Agent`; its SHA256 during inspection was `d4d1277aadcc912b04cb67a76e0ac6521d7a15c607f5803083266323a046163c`.

This supersedes the earlier manual-only policy. `autoreplace=off` still prevents replacement by physical location; it does not prohibit ZED from activating a registered spare. No patched binary or fictional configuration switch is needed.

## Shipped handlers

The declarations remove built-in mail notifications for data errors, state changes, scrub finishes, and resilver finishes. `zed.rc` disables mail, automatic post-resilver scrubs, and enclosure slot power-off. The slot-off and post-resilver scrub symlinks are also retired. Their switches were already disabled in the inspected configuration; the compiled spare retirement behavior remains enabled by operator choice. Existing syslog, LED, and dataset mount-list caching handlers remain intact. ZED's normal event cursor remains intact; no `-Z` replay is requested.

The custom handler accepts device and pool error subclasses listed in `FAULTS`, fault state changes, scrub completion or cancellation, and resilver completion. It ignores unrelated events, including history events. Only ONLINE state changes and scrubs whose structured status has ONLINE vdevs, zero error counters, zero repair bytes, and a FINISHED scan are suppressed. Unsupported-feature advice does not masquerade as a storage failure. Resilver outcomes always notify. Repeated faults are throttled per pool, subclass, vdev GUID, and state for one hour; unsuccessful alert delivery does not consume the throttle. Scrub and resilver outcomes are not throttled.

All notifications call `/usr/local/bin/storage-alert`, not the checkout or a credential resolver. Sender exit status propagates. SMART likewise forwards `SMARTD_FULLMESSAGE` and preserves the sender's exit status.

## SMART schedule and probe

All eight devices receive health monitoring and scheduled self-tests through whole-device `/dev/disk/by-id` paths. No device scan, KVM device, optical device, or partition is declared. Times use the physical host's America/Los_Angeles timezone. Smartd polls within the scheduled hour rather than guaranteeing the exact minute, and long tests take precedence over same-hour short tests.

| Serial | Daily short hour | Monthly long day and hour |
| --- | --- | --- |
| 9LKV5DUG | 02 | 04 at 02 |
| Y6GRJ1YD | 03 | 07 at 03 |
| Y6GTBAUC | 04 | 10 at 04 |
| 7LG2VNYK | 05 | 13 at 05 |
| ZTM0M2V7 | 06 | 16 at 06 |
| S6P6NL0W307869J | 07 | 19 at 07 |
| S6S1NS0T644144F | 08 | 22 at 08 |
| S59ANM0W427759V | 09 | 25 at 09 |

Physical probes confirmed self-test support on all eight drives. One NVMe rejected smartctl 7.4's namespace-specific self-test log request; the broadcast namespace succeeded. The official 7.5 backport fixed that lookup and added NVMe scheduling to smartd. Both logs read successfully with unmodified commands after the upgrade. Long tests supersede the same-hour short, and smartd skips a scheduled test while another remains in progress.

Package installation may start packaged services. Deploying the capability also installs event monitoring and runs the pool-property hook; it is not a package-only operation. The capability enables SMART/ZED services and restarts them when their configuration changes. The file-change notifications reload the declared schedule.

## Read-only physical checks

The pool-policy helper ran on physical pod042 through Python stdin without `--apply`. It reported exactly ark `failmode: continue -> wait`, black-box `failmode: continue -> wait`, and black-box `autotrim: off -> on`. Both GUID guards passed. The custom handler processed synthetic `scrub_finish` environments against each pool's real `zpool status -jp`; both clean scrubs exited zero without alert delivery despite unsupported-feature advice. No remote file, package, property, service, timer, or provider value was changed.
