# XGS-PON stick firmware upgrade — human runbook

For when `scripts/upgrade-xgs-pon.sh` fails or the house stays offline. The stick is a WAS-110 running 8311 community firmware (basic), upgrading v2.8.0 → v2.8.3 via the supplementary (`local-upgrade.tar`) path — the one pon.wiki calls safe. The Azores *web* upgrader is the soft-brick one; we do not use it.

Facts you need:

- Stick management: `https://192.168.11.1` / `ssh root@192.168.11.1` — creds in 1Password item **XGS PON** (agent vault). LAN reachability survives internet loss.
- ssh needs legacy options: `ssh -oHostKeyAlgorithms=+ssh-rsa -oPubkeyAcceptedKeyTypes=+ssh-rsa root@192.168.11.1`
- A/B banks: the stick keeps two firmware images. We were on **bank B (v2.8.0)**; the upgrade writes bank A and switches to it. The old B image stays intact as fallback.
- Baseline captures (config, env, temps) are in `/tmp/xgs-pon-upgrade/` on the laptop.

## Expected timeline

Flash ≈1–2 min, reboot ≈2–3 min, PON reauth ≈1–2 min. **Total internet loss ~3–5 minutes.** Don't intervene before 15 minutes have passed.

## Failure cases, in escalating order

### 1. Script died mid-run but you changed nothing

Re-run with `--resume` — it skips straight to waiting/verification:

```sh
docs/wayfinding/bunker-rebuild/scripts/upgrade-xgs-pon.sh --resume
```

### 2. Stick pingable but version still 2.8.0 (bank didn't switch)

The flash didn't take. Nothing is lost — you're on the old firmware. Check `dmesg`/`logread` on the stick for flash errors, then simply re-run the whole script.

### 3. Stick up, v2.8.3 active, but PON won't reach O5 / no internet after 15 min

The new image boots but won't sync. Revert to the known-good bank:

1. Browse to `https://192.168.11.1/cgi-bin/luci/admin/8311/firmware` (root password).
2. Switch the active bank back to the previous one (B) and reboot.
3. Internet should return on v2.8.0. Report the failure; we stay on 2.8.0.

### 4. Stick not pingable at all after 15 min

Power-cycle ritual (the one you already know): pull the stick from the UDMP SFP+ cage for ~10 seconds, reseat, wait 5 minutes. If it returns on v2.8.0, the new bank failed boot and it fell back — we stay on 2.8.0, report it. If it returns on v2.8.3, all good — run `--resume` to verify.

### 5. Still dead after power-cycle

Two independent paths home:

- **AT&T gateway**: plug the original AT&T gateway back into the fiber in place of the stick. House is online while the stick is debugged at leisure.
- **Stick recovery**: pon.wiki "Multicast Upgrade and Community Firmware Recovery" guide. Worst case needs a serial breakout on SFP pins 2/7 — that's a bench job, not a tonight job.

## Verification of success

- `ssh root@192.168.11.1 'cat /etc/8311_version'` → shows 2.8.3
- PON state O5.x: `ssh root@192.168.11.1 'pontop -b -g s'`
- Internet works
- New in v2.8.2+: metrics at `https://192.168.11.1/cgi-bin/luci/8311/metrics` (unauthenticated JSON: cpu/optic temps, PLOAM state, optical power) — this is the observability the upgrade was for (temperature trending, per ticket 16's thermal hypothesis)
