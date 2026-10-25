---
name: operating-pod153
description: Operates pod153, the always-on headless MacBook server, through native mise, SSH, and Cua Driver. Use before changing its host state, restarting it, recovering it after a reboot, or answering a macOS permission prompt on it.
---

# Operating pod153

pod153 is a MacBook Pro running as a server next to pod042. Nobody sits at it, so every prompt it raises is yours to answer. Treat this repository as its desired state: diagnose live state freely, make durable changes in `bootstrap/targets/pod153/` or the shared capability that owns them, and reconcile.

## Entry points

- SSH host: `pod153` (`10.10.10.53` on Bunker). Key login only after boot; pod042 and pod153 share the `id_ed25519_git` file key, the laptops use the operator key from 1Password.
- Reconciliation: `mise reconcile [--check] [-t tags]` on pod153 itself. `mise run reconcile:tags` lists the tags. A LaunchAgent runs `scripts/reconcile-or-fix` daily at 04:30: it pulls main and reconciles, logging to `~/.local/state/ansiblonomicon/reconcile.log`. On failure it starts an Amp thread labeled `reconcile-failure` that fixes and pushes, or notifies Thurston.
- Secrets: `scripts/fnox-host get NAME`. The `agent` provider uses the service-account token, so it never prompts. Never route unattended work through the 1Password app or its SSH agent; it is locked whenever nobody is at the Mac.
- Screen Sharing: `vnc://pod153` with the account name and password. It offers only Apple's authentication (RFB security type 30 and newer), which macOS Screen Sharing, Remmina, and RealVNC speak; plain VNC-password clients cannot connect.
- Hardware console: none. `pod042-kvm` is wired to pod042, so a hard freeze or a pre-boot that SSH cannot reach needs someone at the Mac.

## Boot states

`scripts/pod153-wake status` reports one of:

| State | Meaning | Next step |
| --- | --- | --- |
| `down` | Nothing answers SSH. | Wait; a Mac does not power on over the network. After a restart, see the Wi-Fi note below. |
| `unverified` | No pinned host key for `pod153`. | Check `~/.ssh/pod153.known_hosts`, which `ssh-client` links from the repo. |
| `denied` | The booted sshd refused the key. | Check `authorized_keys`; the watcher never sends the password here. |
| `preboot` | FileVault is locked; only password SSH answers. | `pod153-wake wake` sends the password once. |
| `login-window` | Unlocked, nobody logged in. LaunchAgents and the Amp runner are not running. | Log in through Screen Sharing. |
| `desktop` | Logged in. | Nothing. |

pod042 runs `pod153-wake watch` as the `dev.mise.pod153-wake` user service, so an unplanned restart unlocks itself, but it stops at `login-window`: an SSH unlock mounts the data volume without logging anyone in. `wake` and `watch` need `POD153_LOGIN_PASSWORD`: run them as `fnox-host exec --secret POD153_LOGIN_PASSWORD -- scripts/pod153-wake wake`. Check `journalctl --user -u dev.mise.pod153-wake` on pod042 when pod153 stays in `preboot`; the watcher waits an hour after an unlock that did not take, so a wrong password cannot turn into a lockout.

Pre-boot joins only an open or WPA2-PSK Wi-Fi network the Mac has joined before, or unauthenticated Ethernet, which is why the temporary Bunker SSID is WPA2. Keep Bunker first in `networksetup -listpreferredwirelessnetworks en0`: a boot that picks YoRHa stays `down` from pod042, which UniFi blocks from YoRHa's SSH. After changing Wi-Fi, refresh pre-boot's copy with `sudo diskutil apfs updatePreboot /`.

## Restarting

Plan restarts with `fnox-host exec --secret HOMEBREW_SUDO_ASKPASS_PASS -- scripts/pod153-restart`. It runs `fdesetup authrestart`, which skips pre-boot and logs straight back in. A plain `sudo shutdown -r` lands in pre-boot, depends on the watcher, and still needs a login. Restarting ends every session on pod153, including the agent's own runner, so finish and report first.

## Answering prompts

Cua Driver runs as the `dev.mise.house.thurstons.cua-driver` LaunchAgent and holds Accessibility and Screen Recording. Use it to answer prompts:

- TCC consent alerts ("would like to access", "would like to administer your computer") belong to `UserNotificationCenter`. Find them with `list_windows` on its pid, read each with `get_window_state`, and press the button by role and name. Alerts stack; only the frontmost one takes a press, so answer them one at a time and list again.
- A sudo authorization sheet from `SecurityAgent` means something bypassed the passwordless sudoers rule. Press Escape to dismiss it and fix the caller, rather than typing the password into it.
- Grant a privacy permission in System Settings → Privacy & Security. Some grants then offer "Quit & Reopen" for the app. Choose "Later" for Amp, because quitting Amp kills the runner you are working through. The grant applies at Amp's next launch.
- Prefer `run_script` for multi-step flows; element tokens do not survive between separate `cua-driver call` processes.

Codex and the ChatGPT app use their own computer use. Claude Code, Amp, and Pi use Cua.

## Renewing Claude's login

Claude Remote Control needs the full-scope login in the keychain, which lapses after about 28 days; `setup-token` credentials cannot run it. `env -u CLAUDE_CODE_OAUTH_TOKEN claude auth status` shows which login is in use. To renew it with nobody present:

1. Start `tail -f FILE | env -u CLAUDE_CODE_OAUTH_TOKEN BROWSER=true claude auth login --claudeai` in the background, with output to a log, and open the printed authorize URL with `open -a "Google Chrome"`. Chrome holds the Google session; the default browser does not.
2. With Cua, press "Continue with Google", choose `thurstonsand@gmail.com`, press "Continue", then "Authorize".
3. Read the code under "Paste this into Claude Code:" from the page's accessibility tree and append it to FILE. Never print it. The log reports "Login successful".
4. Kill the `tail`, then `launchctl kickstart -k gui/$(id -u)/dev.mise.house.thurstons.claude-remote-control` so the server stops refreshing the replaced token.

## Services

| Service | Declared in |
| --- | --- |
| Cua Driver daemon, Claude Remote Control rooted at `~/Develop`, daily reconcile | `bootstrap/targets/pod153/mise.server.toml` |
| Power (no sleep, lid-closed awake, restart after freeze), Remote Login, Screen Sharing, Automation Mode | `bootstrap/targets/pod153/server/reconcile.py` |
| Amp runner | `bootstrap/targets/pod153/mise.amp-cli.toml` |
| Apps | `bootstrap/capabilities/mac-apps/Brewfile.pod153` |

## Safety boundaries

- Restarts, network changes, and anything touching Remote Login or Screen Sharing can strand pod153. Keep one working path (SSH or Screen Sharing) while changing another.
- Do not disable FileVault or enable auto-login to make boots easier; pre-boot unlock over SSH is the supported path.
- Do not arm `fdesetup authrestart -delayminutes -1` as a standing setting: it keeps an unlock key in memory until the next restart.
