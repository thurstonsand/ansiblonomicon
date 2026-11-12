---
name: operating-pod153
description: Operates pod153, the always-on headless MacBook server, through native mise, SSH, Cua Driver, and its independent KVM. Use before changing its host state, restarting it, recovering it after a reboot, or answering a macOS permission or authentication prompt on it.
---

# Operating pod153

pod153 is a MacBook Pro running as a server next to pod042. Nobody sits at it, so every prompt it raises is yours to answer. Treat this repository as its desired state: diagnose live state freely, make durable changes in `bootstrap/targets/pod153/` or the shared capability that owns them, and reconcile.

## Entry points

- SSH host: `pod153` (`10.10.10.53` on Bunker). Key login only after boot; pod042 and pod153 share the `id_ed25519_git` file key, the laptops use the operator key from 1Password.
- Tailnet: `pod153-ts` (`pod153.tail5f024.ts.net`, `tag:pod153`). The Homebrew `tailscaled` LaunchDaemon serves Tailscale SSH from the login window on, but not in FileVault pre-boot. The tailnet policy in `terraform/tailscale/policy.hujson` lets pod042 and pod153 reach each other, and Thurston's devices through a `check` re-authentication.
- Reconciliation: `mise reconcile [--check] [-t tags]` on pod153 itself. `mise run reconcile:tags` lists the tags. A LaunchAgent runs `scripts/reconcile-or-fix` daily at 04:30: it pulls main and reconciles, logging to `~/.local/state/ansiblonomicon/reconcile.log`. It commits and pushes the `lazy-lock.json` that the plugin sync rewrites. Uncommitted work rides along through an autostash and is deployed with main. On failure, including incoming commits that conflict with that work, it starts an Amp thread labeled `reconcile-failure` that sets aside any unfinished work behind the failure, fixes, finishes the reconcile, and pushes, notifying Thurston only for a true conflict or a decision he must make.
- Secrets: `scripts/fnox-host get NAME`. The `agent` provider uses the service-account token, so it never prompts. Resolve unattended credentials through fnox rather than depending on the 1Password app's unlock state or its SSH agent.
- Screen Sharing: `vnc://pod153` with the account name and password, through a client that speaks Apple's authentication (macOS Screen Sharing, Remmina, RealVNC, vncdotool). Only the System Settings → General → Sharing toggle grants it screen capture and input; started through `launchctl`, it authenticates but streams black and drops every key.
- T3 Code: the vendor LaunchAgent `com.t3tools.t3code.service` serves `*:3773` on the LAN and T3 Connect through its relay; `t3 connect status --json` reports reachability.
- Hardware console: `pod153-kvm` (`10.10.10.35`) locally or `pod153-kvm-ts` (`100.81.37.67`) through Tailscale. See recovery below when host SSH or Cua cannot reach the screen.

## Wiring and recovery console

The USW Pro Max 24 PoE connects pod153's USB Ethernet (`en10`, MAC `6c:6e:07:2a:90:e9`) on port 18 at 2.5 Gb/s. UniFi reserves `10.10.10.53` for that adapter; Wi-Fi (`en0`) stays off. The Mac's charger is on **PDU Pro AC outlet 18**, named `pod153 charger`. Its USB-C outlets are low-power accessory outputs, not a laptop supply. Check `pmset -g batt` for `AC Power`; a full battery can correctly report that it is not charging.

The GL-RM1PE KVM receives independent PoE on **switch port 7**, with HDMI and USB connected to the Mac. Tailscale terminates on the KVM, so neither Mac services nor pod042's tunnel are needed for console access. Browser access is `https://10.10.10.35` or `https://100.81.37.67`; its unique admin password is in the Agent-vault item `pod153-kvm`. Both SSH aliases use root with the operator or server automation key; password SSH is disabled. The pinned appliance key is in `bootstrap/capabilities/ssh-client/files/pod153.known_hosts`.

From the repository root, use the same client as pod042, selecting the host explicitly:

```sh
uv run scripts/kvm.py pod153 --insecure status
uv run scripts/kvm.py pod153 --insecure screenshot /tmp/pod153.jpg
uv run scripts/kvm.py pod153 --url https://100.81.37.67 --insecure screenshot /tmp/pod153-remote.jpg
uv run scripts/kvm.py pod153 --insecure key cmd+space
uv run scripts/kvm.py pod153 --insecure text 'literal text'
uv run scripts/kvm.py pod153 --insecure key esc
uv run scripts/kvm.py pod153 --insecure media status
```

`--insecure` is the explicit exception for the appliance's self-signed certificate. The host selection chooses its password item even when `--url` overrides the network path. `status` can report `video_online: false` while the demand-started streamer is idle; capture and inspect a screenshot before diagnosing lost HDMI. Inspect the screen before sending input, and pass passwords through stdin rather than command arguments. For virtual media, run `media enable` before `upload` and `mount`, then `eject` when finished; attachment is not permission to install an OS. `reboot` restarts the KVM, not the Mac.

OpenTofu owns the UniFi identity, switch port, Tailscale tag, disabled key expiry, and approved emergency subnet routes. Appliance settings remain manual, as for pod042. The KVM advertises Bunker, Lunar Tear, Scanners, and The Village, excludes YoRHa, and accepts neither DNS nor routes; it is not an exit node. Amp orbs can use the `operating-pod042` skill's `scripts/with-pod042-access lan -- <command>` wrapper to reach the LAN address; the wrapper's `ssh` mode still targets pod042.

After firmware changes, verify hostname, password login to the API, key-only SSH, Tailscale membership, and video/HID again. Initial setup required Tailscale re-enrollment with a one-use key tagged `tag:pod153-kvm`; the appliance already reported `NeedsLogin` before the firmware upgrade. A subsequent ordinary KVM reboot preserved all settings and the node address. Check `/etc/kvmd/user/tailscale.json` and the native `/api/tailscale/config` API rather than changing only CLI preferences.

This supplies console access, not a Mac power button: there is no ATX control, and cycling its charger does not reset a battery-powered laptop. Use the KVM to inspect or unlock a visible screen before considering a host restart. A normal restart on 2026-11-02 verified automatic FileVault unlock over Ethernet at `10.10.10.53` and Screen Sharing login, returning to the desktop in about 96 seconds with Wi-Fi still off. KVM boot-progress video and desktop video/HID are verified; manual KVM input at the FileVault screen remains untested.

## Boot states

`scripts/pod153-wake status` reports one of:

| State | Meaning | Next step |
| --- | --- | --- |
| `down` | Nothing answers SSH. | Inspect `pod153-kvm`; distinguish a visible pre-boot or hung screen from loss of power. A shut-down Mac does not power on over the network. |
| `unverified` | No pinned host key for `pod153`. | Check `~/.ssh/pod153.known_hosts`, which `ssh-client` links from the repo. |
| `denied` | The booted sshd refused the key. | Check `authorized_keys`; the watcher never sends the password here. |
| `preboot` | FileVault is locked; only password SSH answers. | `pod153-wake wake` sends the password once. |
| `login-window` | Unlocked, nobody logged in. LaunchAgents and the Amp runner are not running. | The watcher logs in over Screen Sharing; `pod153-wake login` does it once by hand. |
| `desktop` | Logged in. | Nothing. |

pod042 runs `pod153-wake watch` as the `dev.mise.pod153-wake` user service to return the Mac to its desktop after a restart, provided pre-boot networking is reachable. Neither an SSH unlock nor `fdesetup authrestart` logs anyone in, so after either the watcher types the password into the login window through vncdotool (a `pod042` operator tool) and waits for the console to belong to `thurstonsand`. Each login leaves before and after captures in `~/.local/state/pod153-wake/` on pod042. `wake`, `login`, and `watch` need `POD153_LOGIN_PASSWORD`: run them as `fnox-host exec --secret POD153_LOGIN_PASSWORD -- scripts/pod153-wake login`. Check `journalctl --user -u dev.mise.pod153-wake` on pod042 when pod153 stays in `preboot` or `login-window`; the watcher waits an hour after an attempt that did not reach the desktop, so a wrong password cannot turn into a lockout, and alerts through Hark each time it starts that wait.

Pre-boot supports unauthenticated Ethernet or an open/WPA2-PSK Wi-Fi network the Mac has joined before. Normal operation now uses Ethernet with Wi-Fi off; do not assume the old Wi-Fi recovery route remains available. If deliberately restoring Wi-Fi recovery, keep Bunker first in `networksetup -listpreferredwirelessnetworks en0`, since UniFi blocks pod042 from YoRHa's SSH, and refresh pre-boot's copy with `sudo diskutil apfs updatePreboot /` after the change.

## Restarting

Plan restarts with `fnox-host exec --secret HOMEBREW_SUDO_ASKPASS_PASS -- scripts/pod153-restart`. It runs `fdesetup authrestart`, which skips pre-boot and its Wi-Fi requirement and lands at the login window for the watcher. A plain `sudo shutdown -r` lands in pre-boot, and the watcher unlocks and then logs in. Restarting ends every session on pod153, including the agent's own runner, so finish and report first.

## Answering prompts

pod153 is unattended, so treat it as a machine without prompts. Thurston's standing authorization: allow every prompt macOS raises, on your own, whoever raised it. Origin is often unclear; an alert can belong to an earlier thread, a background job, or another app. Press Allow, OK, or Continue without tracing it first, then carry on with the task.

The server capability keeps display sleep, the screen saver, and the screen lock off because a locked screen hides every window from Cua and drops Screen Sharing's keys. If pod153 is found locked, inspect and unlock it through the hardware KVM. `pod153-restart` remains the fallback when console recovery fails.

Cua Driver runs as the `dev.mise.house.thurstons.cua-driver` LaunchAgent, set up to answer consent alerts and password sheets. It holds Accessibility and Screen Recording, and the server reconcile restarts it once when the running daemon reports either missing, since a daemon restarted under a reconcile can come up without grants TCC still holds.

Answer prompts through Cua. The hardware KVM only bootstraps it: when Cua cannot act, because it lacks Accessibility or Screen Recording or the screen is locked, use the KVM just far enough to restore that, then go back to Cua. The KVM sends keys only; `key return` presses an alert's default button, which is Allow on the consent alerts seen so far, so confirm it on a screenshot first. Its browser console at `https://10.10.10.35` adds a mouse for anything keys cannot reach, such as System Settings switches. With Cua working:

- TCC consent alerts ("would like to access", "would like to administer your computer") belong to `UserNotificationCenter`. Find them with `list_windows` on its pid, read each with `get_window_state`, and press Allow by role and name. Alerts stack; only the frontmost one takes a press, so answer them one at a time and list again.
- A sudo authorization sheet from `SecurityAgent` means something bypassed the passwordless sudoers rule. Authenticate it with the login password from fnox (`HOMEBREW_SUDO_ASKPASS_PASS`), filled with `set_value` as below, so the work goes on; when the caller is one this repository owns, fix it too so it stops asking.
- Grant a privacy permission in System Settings → Privacy & Security. Some grants then offer "Quit & Reopen" for the app; choose it, Amp included. Amp and its runner threads recover on their own after it relaunches.
- Prefer `run_script` for multi-step flows; element tokens do not survive between separate `cua-driver call` processes.

Background jobs never raise a TCC prompt; a denied check hangs or fails with "Operation not permitted". pod153's only system Python is python.org's, which `server/mac_mcp.py` keeps current; mise and uv keep their own for development. The reconcile LaunchAgent's `python3` runs on it, so everything it starts, including `op` reading the 1Password app's settings, is checked against `/Library/Frameworks/Python.framework/Versions/3.X/bin/python3.X` with the PSF's Developer ID. That binary holds Full Disk Access, Automation → Messages, and Local Network, which the reconcile's SSH to cupertino needs. The grants survive patch releases; a new minor moves the path and needs all three again.

To restore a grant, unlock with the login password from fnox (`HOMEBREW_SUDO_ASKPASS_PASS`); fill the sheet's password field with `set_value` on its element rather than typed keys. A binary that was denied Full Disk Access usually already appears in Privacy & Security → Full Disk Access, switched off; otherwise add its path with **+** and Go to Folder (⌘⇧G). Automation has no **+**, but a job started with `launchctl submit` raises its alert: `launchctl submit -l tcc-probe -- <python> -c 'import subprocess; subprocess.run(["osascript", "-e", "tell application \"Messages\" to count chats"])'`, press Allow on the `UserNotificationCenter` alert, then `launchctl remove tcc-probe`. Only a command Messages must answer prompts; AppleScript resolves `get name` without asking it. `sudo log show --predicate 'process == "tccd"' --info` names the denied identity as its `responsible_path`.

An app running without a window, such as a headless server started by a LaunchAgent, gets its prompts held: the log shows tccd `Delaying prompt`, and the app's request never returns. Run the app with a window, bring it to the front, and make the request again from inside the app. Some alerts never show up in `list_windows`. Find them in a `get_desktop_state` screenshot and click them with a desktop target and `delivery_mode: "foreground"`. Desktop pixels are screen points × 2.

A service that needs local network access may need its Local Network prompt approved, even when it runs in the background. Until then its connections to LAN addresses fail with `no route to host`, including cupertino's `192.168.64.x`. Its alert, "Allow “Python” to find devices on local networks?", is a `UserNotificationCenter` window; a `launchctl submit` probe that runs `/usr/bin/ssh admin@cupertino true` under the reconcile's Python raises it.

Codex and the ChatGPT app use their own computer use. Claude Code, Amp, and Pi use Cua.

### Passkeys with the lid closed

macOS can verify a passkey with the Mac account password when Touch ID is unavailable. A 1Password spinner or a clamshell Touch ID warning is not proof that physical presence is required: password dialogs can belong to `coreautha`, be missing from app-name window discovery, and sit behind `UserNotificationCenter` alerts.

1. Find `coreautha` and its executable identity with `ps -axo pid,comm`, then call `cua-driver list_windows` with its explicit `pid`. Read each candidate with `get_window_state` using both `pid` and `window_id`; inspect the desktop screenshot for obscuring alerts. Verify the requesting app, site, and account before entering a credential. Allow any other alerts in the way, as above.
2. For an authorized Mac-password prompt, resolve `HOMEBREW_SUDO_ASKPASS_PASS` through `scripts/fnox-host` in process memory. Confirm recording is disabled with `cua-driver recording status` before entry. Pass the secret as JSON on stdin to `cua-driver call set_value`, targeting the exact dialog and a fresh password-field `element_token`; suppress captured output and keep the value out of command arguments, the clipboard, logs, and screenshots. This password is not the 1Password account password.
3. Submit that dialog's **OK** button with `run_steps`, using its own `pid` and `window_id`. Rediscover windows and tokens after UI changes rather than reusing old identifiers. Exact-window AX targeting can work without foreground typing; parent-app targeting can fail with `element_outside_target_window`.
4. Confirm the dialog closes and check `coreauthd` logs for successful completion. Then verify the requesting app separately: local password acceptance, website sign-in, Desktop authorization, and rendered frames/input are distinct outcomes. If a completed sign-in exposes a decoder error, investigate codec compatibility rather than repeating authentication.

## Renewing Claude's login

Claude Remote Control needs the full-scope login in the keychain, which lapses after about 28 days; `setup-token` credentials cannot run it. `env -u CLAUDE_CODE_OAUTH_TOKEN claude auth status` shows which login is in use. To renew it with nobody present:

1. Start `tail -f FILE | env -u CLAUDE_CODE_OAUTH_TOKEN BROWSER=true claude auth login --claudeai` in the background, with output to a log, and open the printed authorize URL with `open -a "Google Chrome"`. Chrome holds the Google session; the default browser does not.
2. With Cua, press "Continue with Google", choose `thurstonsand@gmail.com`, press "Continue", then "Authorize".
3. Read the code under "Paste this into Claude Code:" from the page's accessibility tree and append it to FILE. Never print it. The log reports "Login successful".
4. Kill the `tail`, then `launchctl kickstart -k gui/$(id -u)/dev.mise.house.thurstons.claude-remote-control` so the server stops refreshing the replaced token.

## Services

| Service | Declared in |
| --- | --- |
| Cua Driver daemon, Claude Remote Control rooted at `~/Develop`, daily reconcile, the `tailscaled` LaunchDaemon and its `tailscale up` settings | `bootstrap/targets/pod153/mise.server.toml` |
| Power (no sleep, lid-closed awake, restart after freeze), Wi-Fi off after verifying Ethernet, display and screen lock, Remote Login, Screen Sharing, Automation Mode, restarting services whose executable was replaced while they ran, Time Machine to pod042's `timemachine` share and its exclusions | `bootstrap/targets/pod153/server/reconcile.py` |
| Amp runner, its portal and desktop settings, and the `amp-app-update` LaunchAgent, which restarts Amp.app to install a Sparkle update once no runner thread is working and 12 hours have passed since its last start; the reconcile fails when an update has waited over a day, and `~/Library/Logs/amp-app-update.log` says why | `bootstrap/targets/pod153/mise.amp-cli.toml` |
| Apps | `bootstrap/capabilities/mac-apps/Brewfile.pod153` |

## Safety boundaries

- Restarts, network changes, and anything touching Remote Login or Screen Sharing can strand pod153. Keep one working path (SSH or Screen Sharing) while changing another.
- Do not disable FileVault or enable auto-login to make boots easier; pre-boot unlock over SSH is the supported path.
- Do not arm `fdesetup authrestart -delayminutes -1` as a standing setting: it keeps an unlock key in memory until the next restart.
