---
status: closed
type: task
blocked-by: [28]
claimed: 01a06a50-6c47-7603-aa39-e536fbce070a
---

# Bring up pod042-kvm

## Question

Install the GL-RM1PE as the permanent `pod042-kvm` console from a known state. Unless the capability research exposes a recovery hazard, record the device identity and current firmware, factory-reset it, connect it to pod042, update and harden it, and verify console, keyboard, virtual media, and supported power controls.

OpenTofu owns only its UniFi network identity: a named Bunker access port and a stable client identity or reservation using an appropriate non-fast switch port. Device settings remain manual. Record concise recovery facts and evidence that the KVM remains reachable while pod042 is powered off.

## Progress

2026-09-04: live UniFi confirmed port 1 on the Pro Max 24 PoE, 1 Gb/s, PoE auto and healthy, MAC `94:83:c4:c0:d7:7b`, Bunker DHCP address `10.10.10.101`, and roughly 2–3 W draw. Pre-reset firmware was `V1.9.1 release1`; Tailscale was active as `glkvm.tail5f024.ts.net` with exit-node mode enabled, 2FA was disabled, and Wake-on-LAN still targeted the former TrueNAS address. The full persistent configuration was archived in the agent vault as `pod042-kvm pre-reset backup 2026-09-04`.

The vendor factory-reset script completed and the API returned `is_inited: false`. Reset removed the SSH authorized key, which the user restored once through the browser terminal. The confusing password mismatch came from 1Password CLI behavior: `op item get --fields password` returns a concealment notice unless passed `--reveal`, and that notice had been written to the KVM and then accepted by the agent's matching API test. The backend now contains the actual revealed 1Password value, and a fresh API login proves they agree. Future secret reads must use `--reveal` or the JSON field value deliberately; never treat default concealed output as a credential.

During pre-reset inventory, a diagnostic command printed the appliance's hardware cloud identity credential into the private agent-session transcript. Treat GL.iNet Cloud identity as exposed and keep the appliance unbound from GL.iNet Cloud; the intended permanent remote paths remain Cloudflare or Tailscale.

The user restored the dedicated public key through the browser terminal. Root SSH then set the KVM password backend from the current 1Password value; API login, key-only SSH, hostname, and credentials all survived a deliberate reboot. Firmware `V1.9.1 release1` matches the current stable release. OpenTofu now owns MAC `94:83:c4:c0:d7:7b` as `pod042-kvm`, fixed Bunker address and local DNS name `10.10.10.34`, and Pro Max 24 PoE port 1 as a Bunker access port with PoE auto. Apply converged after removing an invalid explicit network override for the native network, and the follow-up plan reported no changes. The managed SSH host is now `pod042-kvm` at `10.10.10.34`; the former `glkvm` alias and `192.168.1.34` address retire.

HDMI and USB are connected while the NAS remains powered off, and the KVM stays reachable solely through switch PoE. No GL-ATXPC board is installed. Manual power control is accepted for installation; configure and test WOL after pod042's NIC and BIOS are available. WOL cannot recover a hard freeze, so controlled-PDU cycling plus BIOS power-on-after-AC-loss remains the stronger fallback if later required.

With the NAS powered on, the KVM produced a 2560×1440 snapshot of the TrueNAS console. Browser keyboard input redrew the console prompt. `scripts/pod042_kvm.py` now exposes the same verified controls for agents and operators: `status`, `screenshot`, literal `text`, and named keys or chords such as `ctrl+alt+delete`. Its live smoke typed `x`, captured it, erased it with Backspace, and sent a modifier-only `ctrl+alt` chord without changing host state.

Virtual media now works through the same CLI. A factory reset left both mass-storage functions absent from the active USB composite gadget even though the lower-level media API could report enabled. The `media enable` command now uses the control panel's `/api/system/otg_functions` operation, which added both CD-ROM and flash functions. The verified Debian 13.6.0 amd64 netinst image, SHA-256 `65273beed27b2df543b68b65630ba525cfbad8df2b12035732b2dff87d6664e7`, uploaded in full, mounted read-only, and appeared in UEFI as `UEFI: Glinet Optical Drive 1.00 (755MB)`. The NAS then booted its existing TrueNAS SSD without altering data. The ISO remains stored but ejected. A final KVM reboot preserved both mass-storage functions, the image, media-online state, API access, and TrueNAS console video.

The reboot also exposed that this firmware starts uStreamer only while `/api/ws` has an active client. Snapshot polling alone therefore returned 503 forever, an admirably literal implementation of on-demand video. The CLI now opens that demand socket while taking a screenshot, then closes it. A live post-reboot invocation captured a valid 2560×1440 JPEG without an open browser.

Two-factor authentication remains disabled by design. CLI operation would require keeping its TOTP secret beside the password in the same 1Password item, so it would not create an independent factor, while clock or vault trouble could lock out the recovery console. Network access remains restricted to Bunker or the separately authenticated remote path chosen in ticket 30; the appliance adds a random password, and SSH remains key-only.

Nineteen focused tests cover response conformance, key names, binary framing, reverse-order release, failure cleanup, on-demand screenshots, media uploads and operations, and command dispatch. The full 245-test suite, Ruff, strict basedpyright, and `git diff --check` pass.

## Resolution

`pod042-kvm` is operational at `10.10.10.34` on Pro Max 24 PoE port 1. OpenTofu owns its stable Bunker identity and port declaration; appliance settings remain manual. Independent PoE, authenticated API and key-only SSH access, HDMI console, reversible USB HID, persistent virtual media, reboot persistence, and reachability while pod042 is off all passed live tests. Physical power remains manual until ticket 36 tests WOL and decides whether controlled-PDU recovery is warranted.
