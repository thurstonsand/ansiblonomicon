# pod042 operator and remote-agent verification

Verified on the physical Debian host on 2026-09-06, deployed revision `6c7ebff` before the final Amp directory-permission correction. No reboot or storage operation was performed.

## Installed and reconciled

Native mise owns runtimes, utilities and OS resources. Amp, Claude, Codex and OpenCode use their official native installers; Pi and T3 use Node's npm. Nurb uses uv. The shared harness catalogue and resolver produce 223 managed files, without copying laptop-generated resources or running the retired Ansible playbook.

Observed versions: Node 24.20.0, npm 12.0.2, Neovim 0.12.5, zsh 5.9, tmux 3.5a, Pi 0.85.1, T3 0.0.38, Herdr 0.8.2 and Nurb 0.26.0. Sessions and TPM are installed. A fresh operator login through sudo and a PTY selected `/usr/bin/zsh`, loaded the shell configuration without the non-PTY ZLE warnings, and resolved the operator tools.

Native check reported 49 unchanged resources. The only later chezmoi drift was Amp changing its configuration directory from 0755 to 0700. The final source directory uses chezmoi's `private_` attribute to agree with Amp rather than repeatedly broadening those permissions.

## Remote paths

- **Amp:** `pod042-ansiblonomicon` registered with hostname `pod042` and working directory `/home/thurstonsand/code/ansiblonomicon`. A disposable cloud-created thread targeted that runner and returned exactly one assistant response, `READY`. This proves a cloud-to-NAS-to-cloud agent roundtrip. Thread: `T-01a078cb-6415-7730-b57a-6afab8378821`.
- **Amp terminal:** the authenticated actor connection reached terminal authorization and returned `Terminal requires sudo passkey authentication`. This is Amp's account passkey gate, not a NAS sudo-password request. No terminal commands ran and no security policy was weakened. The user must complete the normal passkey assertion when connecting.
- **T3:** saved setup reports desired, authenticated and linked. The advertised managed Cloudflare endpoint returned the correct environment descriptor and server version. A supported five-minute local auth session then authenticated over that public endpoint, opened a WebSocket and retrieved live `server.getConfig`. This verifies the managed tunnel and authenticated remote RPC. The separate Clerk-specific web broker flow was not tested with a browser session.
- **T3 providers:** Claude and Codex are enabled and installed. Live RPC reported 25 enabled Claude skills and 29 enabled Codex skills, including Nurb in both. Other T3 providers remain disabled; the user selected Claude and Codex.
- **Amp skills:** the CLI in the checkout reported 34 available skills, including the hosted user catalogue, machine-local skills, repository-local skills and built-ins.
- **Pi:** its own package updater installed declared packages. RPC command discovery with extensions disabled reported 26 skills before the Nurb addition, without starting MCP integrations. The final harness adds Nurb to Pi as well.

## Runtime repair and persistence

T3's global CLI and vendor service have separate dependency installations. A successful global PTY test did not establish that the service's native module existed. npm 12 had blocked the service runtime's `node-pty` build; a T3-only npmrc now permits that build for future vendor updates. The existing runtime was repaired once through npm's supported rebuild command. A real PTY in that exact runtime emitted `T3_VENDOR_PTY_OK` and exited zero.

Debian's stock `polkitd` now authorizes T3's own-user linger request. No custom policy or root T3 process was added. Vendor install/update and unprivileged self-linger both succeeded.

Both services are enabled, run inside `user@1000.service/app.slice`, and have linger enabled. T3 remained active with zero restarts after its repair; Amp retained its original start time and zero restarts. Both remained active after the verification SSH session closed. The shared SSH transport was retained, and an actual reboot test remains deferred to an attended window.

No credentials, endpoint bearer URLs or websocket tickets are recorded here. The disposable T3 token was held in process memory and expires after five minutes. The Amp test thread remains available for attended terminal confirmation.
