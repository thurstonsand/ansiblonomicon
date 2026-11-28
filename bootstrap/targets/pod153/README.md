# pod153

## Apple Library betas

NotesCTL, MailCTL, and PhotoCTL come from [Club MacStories downloads](https://www.macstories.net/club/macstories-weekly-issue-539/introducing-two-more-apple-clis-in-beta-for-plus-and-premier-members-mailctl-and-photoctl/). These member builds do not auto-update. Run a new signed DMG installer over the existing installation, keeping the existing permission grants and MCP credentials. Check the build date in the download; multiple builds can report the same CLI version. After upgrading an active MCP, restart its `dev.mise.house.thurstons.<cli>-mcp` GUI LaunchAgent and check its `doctor` command and one MCP read.

PhotoCTL and its private endpoint setup are prerequisites for `mise server`. NotesCTL and MailCTL are paused; their installers, permissions, and private configuration stay in place for a later restart.

| CLI | Private `mcp-http.json` on pod153 | Loopback port | Executor status |
| --- | --- | --- | --- |
| NotesCTL | `~/Library/Application Support/NotesCTL/mcp-http.json` | 7363 | Paused |
| MailCTL | `~/.config/mailctl/mcp-http.json` | 7365 | Paused |
| PhotoCTL | `~/.config/photoctl/mcp-http.json` | 7366 | `photos` |

Keep these files when reinstalling. If recreating an endpoint, use the vendor's `ensure_http_config(port=…)` with the port above. Run PhotoCTL's setup in the logged-in GUI session so it can store its token in the login Keychain; leave Beeper Images on 7364. Grant protected access only to the signed Capability Host apps.

[The Apple Library Executor app](../../../executor/apple-library/) exposes Photos and Reminders. The `library` requirement uses a per-user account; Reminders uses an app account. The **pod153 MCP** item in 1Password's Agent vault holds the Cloudflare Access credentials and `notes_token`, `mail_token`, and `photos_token`. The pod153 tunnel requires Cloudflare Access in addition to each server's own bearer. App policy marks raw Photos CLI calls, non-read-only tools, and Photos requests that opt in to iCloud downloads for approval; MCP connections in Automatic mode accept those without prompting. PhotoCTL does not edit the Photos library.

To resume NotesCTL or MailCTL, replace its absent plist declaration in `mise.server.toml` with a LaunchAgent like PhotoCTL's, using `~/.local/bin/notesctl` or `~/bin/mailctl`. Restore its route in `terraform/cloudflare/pod153.tf` and its tool group in the Executor app. For MailCTL, also replace the absent Mail opener with a LaunchAgent that runs `/usr/bin/open -g -a Mail` at login; Mail must be open for store updates and writes. NotesCTL needs `notesctl config set mcp.run-writes true` for its approved export commands. No new credentials are needed while the saved accounts and local configurations are unchanged.
