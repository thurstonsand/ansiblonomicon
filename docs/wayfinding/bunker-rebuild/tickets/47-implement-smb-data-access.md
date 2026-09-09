---
status: closed
type: implementation
blocked-by: [35]
claimed: T-01a0790a-aa41-7258-b0fd-c559a15e473a
---

# Implement SMB data access

## Objective

Implement the accepted [SMB data access](35-smb-data-access.md) contract through a native `sharing` capability: one authenticated SMB3 `media` share, group-compatible writes, no discovery or legacy exports, and no Lunar Tear access.

## Completion evidence

- [x] Native reconciliation installs and validates Samba, converges the declared account without exposing its credential, enables `smbd`, disables `nmbd`, and becomes a no-op.
- [x] Authenticated share listing plus create/read/delete through `smbclient` works as `thurstonsand`; an incorrect password and guest access fail.
- [x] New files and directories carry the expected owner, `media` group, write bits, and setgid directory behavior without changing imported content.
- [x] The host listens only on TCP 445 for SMB. The existing UniFi declaration permits YoRHa and does not add 445 to Lunar Tear.
- [x] Focused tests, Ruff, shell syntax, `testparm`, and repository whitespace checks pass.

## Resolution

Implemented live on pod042 through the native `sharing` capability. Samba 4.22.10 and `smbclient` are installed; `smbd` is active and enabled, while package-enabled `nmbd`, Winbind, and Samba AD DC are stopped and disabled. The validated configuration binds only loopback and `10.10.10.42` on TCP 445, advertises only `media` plus Samba's implicit IPC service, requires SMB3 and user authentication, and retains the prior macOS fruit/streams behavior.

The root-only rendered credential authenticated the existing `thurstonsand` system identity into Samba's independent account database. A live `smbclient` smoke created, read back, and removed both a file and directory through `//localhost/media`; the file landed `thurstonsand:media 0664` and the directory `thurstonsand:media 2775`. Guest and incorrect-password access to the share were rejected. No imported media ownership changed and no smoke artifact remains.

The final native check reports 29 unchanged resources, including all four Samba service states and the mounted dataset policy. UniFi now resolves `pod042.thurstons.house` locally to `10.10.10.42`, giving Finder and Files the stable `smb://pod042.thurstons.house/media` address without publishing SMB through Cloudflare. All 104 focused sharing, reconciliation, harness, and skill tests pass with Ruff, formatting, shell syntax, `testparm`, and whitespace checks. A workstation Finder mount remains a convenient later usability check, not a host-side correctness blocker.
