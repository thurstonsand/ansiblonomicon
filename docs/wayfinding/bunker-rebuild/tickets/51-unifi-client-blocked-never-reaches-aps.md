---
status: closed
type: task
blocked-by: []
---

# Make `unifi_client.blocked` reach the access points

## Problem

Flipping `blocked` on a `unifi_client` changes the controller's record and nothing else. The access points keep enforcing whatever they last heard, so OpenTofu reports success, the controller reports the client unblocked, and the radio still refuses it.

Found on 2026-09-14 with the two Whisker robots (then "Unidentified Espressif": the Feeder-Robot `3c:61:05:6a:d0:7c` and the Litter-Robot `c8:c9:a3:c2:36:90`). They were blocked from the controller UI on 2026-09-03; `blocked = true` was declared in `terraform/unifi/clients.tf` on 2026-09-12 to match. On 2026-09-13 an apply set both to `false` and completed cleanly. More than 24 hours later the AP was still refusing the Litter-Robot's retries of its saved network, and onboarding the Feeder-Robot failed with the Whisker app blaming the passphrase.

## Evidence

- Controller: `/rest/user` and `/stat/alluser` both returned `blocked=False` for both MACs. The v2 system log held no client events for either, only the two admin edits from the apply.
- U7 Pro Max `logread`, 2026-09-14 14:56, on `wifi0ap8` (Lunar Tear): 53 lines of `auth: disallowed by ACL` / `rejected, reason=37` for `c8:c9:a3:c2:36:90`, and a `STA_ASSOC_TRACKER` `deny` event with `auth_failures: 6`. The AP rejected the open-system auth frame, before any WPA handshake, so the passphrase was never evaluated.
- AP config: neither MAC appears in `/tmp/system.cfg` or `/tmp/running.cfg`. The deny is runtime ACL state, not provisioned config. The AP's `provisioned_at` predated the apply, and its `cfgversion` matched the controller, so nothing marked it stale.
- Fix, 14:56:40: `POST /api/s/default/cmd/stamgr {"cmd": "unblock-sta", "mac": ...}` for both MACs. At 14:57:14 the same AP logged a complete 4-way handshake, `AP-STA-CONNECTED`, and a DHCP lease of `10.10.30.236`.

## Cause

In the fork, `unifi/client_resource.go` carries `blocked` like any other field: `planToClient` sets `Blocked`, `mergeClient` copies it onto the current client, and both `Update` and the adopt-existing path in `Create` send the result through `UpdateClient`, a `PUT` to `rest/user/{id}`. The controller stores the flag and does not tell the APs.

The UI does not block that way. It issues station-manager commands, which update the AP ACL immediately. The go-unifi fork already wraps them in `unifi/client.go`: `BlockClientByMAC` (`block-sta`) and `UnblockClientByMAC` (`unblock-sta`). The provider never calls either.

## Verification

The provider and SDK patches passed their focused unit suites, the full SDK suite, provider compilation, and provider vet. The SDK now rejects a non-`ok` station-manager `rc` even when the response contains one client record.

Both directions then passed live on the Whisker Feeder-Robot using a development provider built from those exact patches. Applying `blocked = true` changed both controller APIs to `blocked=true`, removed the client from `/stat/sta`, and made the U7 Pro Max immediately log repeated `auth: disallowed by ACL` and reason 37. Applying `blocked = false` changed the controller back and, within seconds, the AP logged authentication, association, a complete four-way handshake, `AP-STA-CONNECTED`, and DHCP address `10.10.50.112`. A full refreshed follow-up plan returned **No changes**. The client was left online and unblocked.

## Work

- In `Update`, when `blocked` differs between state and plan, call `BlockClientByMAC` or `UnblockClientByMAC` after `UpdateClient` succeeds. Do the same in `Create` when adopting an existing client whose current `blocked` differs from the plan.
- Decide whether `blocked` still belongs in the `PUT` body. Keeping it keeps the stored record consistent with the command; dropping it leaves one writer for the flag. Either way, read back afterwards so state reflects the controller.
- Surface a non-`ok` `rc` from `stamgr` as an apply error, not a warning.
- Test the conversion with fixtures, then live against a disposable client in both directions: after `blocked = true` the AP log shows `disallowed by ACL`, and after `false` the client associates without a manual command.
- Cut a fork release, bump `provider.toml` and `versions.tf`, and note the behavior under decision 1 or the edge cases in [design 23](../../../designs/23-unifi-provider-fork.md).

## Completion

Changing `blocked` in HCL and applying changes what the AP enforces within one apply, in both directions, proven from the AP's own log, with a clean follow-up plan.

## Resolution

The SDK rejects failed station-manager responses, and the provider persists the controller record, issues the matching runtime ACL command whenever declared blocked state changes, then reads the controller record back. Both release branches carry the fix in provider release `v0.56.0-ansiblonomicon.6`; ansiblonomicon pins its verified Darwin ARM64, Linux AMD64, and Linux ARM64 artifacts. The live Feeder-Robot block/unblock cycle proved both AP enforcement directions, and the released provider produced a clean full plan.
