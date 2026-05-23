# Pi Paste File

## Status

Accepted

## Decision Summary

Replace the BetterTouchTool-driven Alt-v image paste flow with a Pi extension named `pi-paste-file` that calls `ghostty-nav paste` over the existing local or SSH-forwarded `ghostty-navd` Unix socket. The design generalizes paste handling from images to clipboard text and file-like non-text content: text is pasted directly into Pi's editor, while non-text content is materialized under `/tmp/pi-paste-file` and its path is pasted into the editor.

## Problem Statement

The current Alt-v image paste path lives outside Pi in `chezmoi/dot_local/bin/executable_btt-paste-image.sh`. BetterTouchTool detects SSH targets by process name, extracts a macOS clipboard image with `pngpaste`, creates a remote temp file, copies it with `scp`, briefly mutates the local clipboard, sends Cmd-v through AppleScript, then restores the clipboard.

That works, but it is brittle and too detached from the terminal session that needs the paste. Recent `ghostty-nav` work added a portable Go client, a macOS `ghostty-navd` daemon, SSH Unix socket forwarding to OpenClaw, and `GHOSTTY_NAV_TTY` propagation. Pi can now own the keybinding and ask the local macOS daemon for clipboard content through the same forwarded socket instead of relying on BetterTouchTool and process-list heuristics.

## Goals

- Bind a configurable shortcut inside Pi through a package-style extension named `pi-paste-file`. The extension default is Alt-v; this repo configures Alt-p to avoid colliding with other paste behavior.
- Replace the BTT Alt-v flow for Pi sessions without changing ordinary Cmd-v terminal paste behavior.
- Use the existing `ghostty-navd` socket locally and the existing SSH `RemoteForward` on OpenClaw.
- Generalize beyond images: support text, screenshots/images, copied Finder files, PDFs, and other file-like pasteboard content where practical.
- Preserve Pi's current visible behavior for image paste: insert a local path into the editor, not a hidden attachment.
- Keep extension settings narrow and TypeBox-validated, following the `../pi-sessions` settings pattern.

## Non-Goals

- Do not send hidden Pi image attachments through `input` transforms for the first implementation.
- Do not keep BetterTouchTool in the main Pi paste path.
- Do not add clipboard auth tokens or per-host trust controls; this environment is fully trusted by the operator.
- Do not implement arbitrary text/file upload through SSH side channels such as `scp`; the forwarded `ghostty-navd` socket is the transport.
- Do not add `--max-bytes`; trust the personal environment unless real failures appear.
- Do not add `--output PATH`; only support `--output-dir`.

## Design Decisions

### 1. Name the extension and temp directory `pi-paste-file`

The extension will live at:

```text
chezmoi/private_dot_pi/agent/extensions/pi-paste-file/
```

The default output directory is:

```text
/tmp/pi-paste-file
```

This name is deliberately broader than `pi-paste-image`. Images are only one pasteboard content type; the command's job is to paste clipboard content into Pi, using files when the content is not plain text.

### 2. Add a general `ghostty-nav paste` command

The Go client will add:

```sh
ghostty-nav paste --output-dir /tmp/pi-paste-file
ghostty-nav paste --output-dir /tmp/pi-paste-file --json
```

Without `--json`, the command prints the text to paste:

- `kind=text`: raw clipboard text
- `kind=files`: space-separated saved paths; a single file is represented as a one-item file list

With `--json`, the command prints structured metadata for the Pi extension. Text results include the text and remain silent in the UI. File results include enough metadata for a small notification, primarily file count and byte size.

Example text result:

```json
{ "kind": "text", "text": "clipboard text" }
```

Example single-file result:

```json
{
  "kind": "files",
  "files": [
    {
      "path": "/tmp/pi-paste-file/pi-paste-a8F3.png",
      "fileName": "clipboard.png",
      "mediaType": "image/png",
      "bytes": 421099,
      "source": "pasteboard-image"
    }
  ],
  "bytes": 421099
}
```

Example multi-file result:

```json
{
  "kind": "files",
  "files": [
    {
      "path": "/tmp/pi-paste-file/a.png",
      "fileName": "a.png",
      "mediaType": "image/png",
      "bytes": 1234,
      "source": "pasteboard-file"
    },
    {
      "path": "/tmp/pi-paste-file/b.pdf",
      "fileName": "b.pdf",
      "mediaType": "application/pdf",
      "bytes": 9999,
      "source": "pasteboard-file"
    }
  ],
  "bytes": 11233
}
```

For file paste, the extension inserts space-separated paths. That matches the intended shell-friendly use better than newline separation.

### 3. Keep the existing `Response` type separate

`protocol.Response` remains the response for existing `ghostty-nav` commands:

```go
type Response struct {
    Value string `json:"value,omitempty"`
    Error string `json:"error,omitempty"`
}
```

Clipboard paste uses a separate framed response contract. The daemon first sends a JSON `PasteHeader`, then streams raw file bytes for `kind=files`. The Go client converts that wire header into distinct materialized response types such as `PasteTextResponse` and `PasteFilesResponse` after writing files locally.

```go
type PasteKind string

const (
    PasteKindText  PasteKind = "text"
    PasteKindFiles PasteKind = "files"
)

type PasteHeader struct {
    Response
    Kind  PasteKind   `json:"kind,omitempty"`
    Text  string      `json:"text,omitempty"`
    Files []PasteFile `json:"files,omitempty"`
    Bytes int64       `json:"bytes,omitempty"`
}

type PasteResponse interface {
    PasteKind() PasteKind
}

type PasteTextResponse struct {
    Text string
}

type PasteFilesResponse struct {
    Files []PasteFile
    Bytes int64
}
```

Existing navigation commands keep their current JSON-only response contract and are not polluted by paste-specific fields.

### 4. The daemon reads clipboard content; the remote client writes files

The macOS `ghostty-navd` daemon owns clipboard access because it is the process with access to the local macOS pasteboard. The remote Go client owns writing files because only it can write to the remote filesystem.

Flow for OpenClaw:

```text
Pi extension on OpenClaw
  -> ghostty-nav paste --json --output-dir /tmp/pi-paste-file
  -> forwarded Unix socket
  -> macOS ghostty-navd reads pasteboard
  -> response carries a JSON header followed by raw file bytes when needed
  -> OpenClaw ghostty-nav writes /tmp/pi-paste-file/*
  -> extension pastes text or space-separated paths into editor
```

This avoids SSH target guessing, `scp`, AppleScript keystrokes, and clipboard mutation.

### 5. Text stays text and is pasted silently

If the clipboard contains text, `ghostty-nav paste --json` returns `kind=text`. The extension calls `ctx.ui.pasteToEditor(text)` and shows no notification.

A user should usually use ordinary Cmd-v for text, but supporting text makes the configured shortcut harmless when pressed against a text clipboard. Pi already handles large pasted text through its editor paste behavior, so the extension does not need a separate large-text summary path.

### 6. File-like content is materialized under `--output-dir`

If the clipboard contains non-text file-like content, the daemon returns metadata and streams raw bytes. The client creates `--output-dir` if needed, writes generated names under that directory, and prints either paths or JSON metadata.

Expected first-class cases:

- macOS screenshot/image pasteboard data, normalized to a portable image file when needed
- copied Finder files
- PDFs or other pasteboard file data where the UTI/MIME type provides a stable extension

Image-specific processing is allowed only where it makes clipboard data usable as a file. For example, screenshots may exist as image data rather than a filesystem path, and converting `NSImage`/TIFF pasteboard data to PNG makes the result portable. The command remains conceptually file paste, not image paste.

### 7. Follow `pi-sessions` extension packaging and settings patterns

`pi-paste-file` will be a package-style extension with strict TypeScript and local package metadata:

```text
chezmoi/private_dot_pi/agent/extensions/pi-paste-file/
  package.json
  tsconfig.json
  index.ts
  ghostty-nav.ts
  settings.ts
  typebox.ts
```

The structure should follow existing package extensions such as `amp-style-permission-gate` and `parallel-web-tools`, and the settings implementation should follow `../pi-sessions/extensions/shared/settings.ts`:

- `SettingsManager.create(process.cwd()).getGlobalSettings()`
- TypeBox schemas and `Static` types
- explicit runtime parsing helper
- defaults applied after validation
- `~` expansion
- absolute path validation for configured directories

Settings namespace:

```json
{
  "pasteFile": {
    "shortcut": "alt+p",
    "outputDir": "/tmp/pi-paste-file"
  }
}
```

Resolved settings:

```ts
interface PasteFileSettings {
  shortcut: KeyId;
  outputDir: string;
}
```

Defaults:

- `shortcut`: `alt+v`
- `outputDir`: `/tmp/pi-paste-file`

The checked-in Pi settings template overrides the shortcut to `alt+p`.

TypeBox is the schema choice because Pi and `pi-sessions` are TypeBox-oriented. Zod appears only as transitive dependency noise in this environment and was explicitly rejected by `pi-sessions` for package-owned runtime boundaries.

### 8. Use `ctx.ui.pasteToEditor`, not hidden input transforms

The extension should paste visible text into the editor:

- text clipboard: paste text
- one or more files: paste space-separated paths

It should not queue pending image attachments or modify the next submitted prompt through an `input` transform. Pi's current built-in `app.clipboard.pasteImage` writes one image to `os.tmpdir()` and inserts that path into the editor. This design preserves that visible, inspectable behavior while broadening the content types and making it work remotely.

### 9. Notifications are metadata-only

For `kind=text`, stay silent.

For `kind=files`, show a compact notification based on the JSON metadata:

```text
Pasted 1 file · image/png · 411 KiB
Pasted 2 files · 10.9 KiB
```

The notification must not include streamed bytes or large content. It exists only to confirm that the shortcut did something and to give a quick size/type snapshot.

## Edge Cases & Failure Modes

- **No usable clipboard content:** `ghostty-nav paste` exits with a distinct no-content status; the extension shows a small warning or silently no-ops if that proves less annoying in practice.
- **Text clipboard:** Paste text directly into the editor and show no notification.
- **Multiple files:** Save all supported files and paste space-separated paths.
- **Unsupported pasteboard type:** Return a clear error from `ghostty-nav paste`; the extension notifies with the error text.
- **Missing remote socket:** The extension reports that `ghostty-navd` is unavailable and suggests refreshing the SSH session or socket forward.
- **Missing `ghostty-nav` binary:** The extension reports that `ghostty-nav` is not installed on this host.
- **Daemon clipboard permission failure:** Return an error response and notify; do not fall back to BetterTouchTool.
- **Filename collisions:** The client generates unique names under `--output-dir`, using a random suffix.
- **Spaces in saved paths:** Multi-file editor insertion is space-separated by design. The first implementation may paste raw paths; shell-escaping can be added if actual use shows that copied filenames commonly contain spaces.

## Rejected Alternatives

### Keep BetterTouchTool as the main path

Rejected because BTT is outside Pi, guesses SSH targets by process list, depends on AppleScript keystroke injection, mutates the clipboard, and cannot use the already-working `ghostty-navd` socket identity.

### Use hidden Pi image attachments through `input` transforms

Rejected for the first implementation. Hidden attachments are useful for model-bound image prompts, but current Pi image paste behavior inserts a file path into the editor. Visible paths are easier to inspect, edit, pass to tools, and use in shell-like prompts.

### Name the feature `pi-paste-image`

Rejected because the desired primitive is now broader than images. The extension pastes text directly and materializes arbitrary file-like clipboard contents.

### Add `--output PATH`

Rejected because the remote client should own safe unique filename generation. `--output-dir` is enough for Pi's use case and avoids user-supplied filename collision and extension mismatch behavior.

### Add `--max-bytes`

Rejected for now because the deployment is a trusted personal environment and ordinary clipboard payloads are expected to be reasonable. If real failures occur, size limits can be added with concrete thresholds.

### Add Zod for settings validation

Rejected because Pi extension tools and local extension settings already use TypeBox. Adding Zod would create a second runtime schema language with no matching benefit.

## Integration Points

- `chezmoi/dot_local/bin/executable_btt-paste-image.sh`: Existing BTT flow to delete once `pi-paste-file` is implemented.
- `ansible/roles/ghostty_nav/files/ghostty-nav/main.go`: Add the `paste` Cobra command and client-side file materialization.
- `ansible/roles/ghostty_nav/files/ghostty-nav/internal/protocol/protocol.go`: Add paste request/response types without changing existing `Response`.
- `ansible/roles/ghostty_nav/files/ghostty-nav/internal/client/client.go`: Preserve `Send` for normal JSON-only commands and expose lower-level connection/request writing helpers for streamed paste responses.
- `ansible/roles/ghostty_nav/files/ghostty-navd/Sources/Requests.swift`: Decode and handle the new `paste` command.
- `ansible/roles/ghostty_nav/files/ghostty-navd/Sources/NetworkServer.swift`: Send JSON-only responses for normal commands and framed JSON-header-plus-byte-stream responses for paste.
- `chezmoi/private_dot_pi/agent/extensions/pi-paste-file/`: New Pi extension package.
- `chezmoi/private_dot_ssh/private_config.tmpl`: Existing OpenClaw `RemoteForward` provides the remote socket path.
- `chezmoi/dot_zshenv.tmpl` and `ansible/roles/sshd/templates/99-openclaw.conf.j2`: Existing `GHOSTTY_NAV_TTY` export/forwarding remains available for terminal identity.

## Implementation Plan

- [ ] Phase 1: Add `ghostty-nav paste` protocol and CLI skeleton
  - Goal: Introduce the command and wire contract without changing Pi or daemon clipboard behavior yet.
  - Files: `protocol.go`, `main.go`, Go client command files if split out, Swift request decoder stubs.
  - Work: Add `PasteRequest`, `PasteResponse`, `PasteFile`, Cobra command parsing for `paste --output-dir --json`, and unsupported-command handling from daemon until implementation lands.
  - Validation: Build the Go client on macOS/Linux; confirm existing `ghostty-nav ping`, `move`, `split`, `resize`, and `title` still behave.

- [ ] Phase 2: Implement macOS daemon pasteboard extraction
  - Goal: Let `ghostty-navd` return text, single file/image data, or multiple file entries from the macOS pasteboard.
  - Files: `Requests.swift`, new Swift pasteboard helper file if useful, daemon tests/helpers if present.
  - Work: Read `NSPasteboard.general`; prefer copied files before text; detect image/screenshot data and normalize to PNG when needed; send a JSON header and stream raw file bytes.
  - Validation: Local manual tests for text, screenshot, copied PNG, copied PDF/Finder file, and multiple Finder files.

- [ ] Phase 3: Implement client-side materialization
  - Goal: Write daemon-returned file data under `--output-dir` on the machine where `ghostty-nav` runs.
  - Files: Go client paste command and supporting helpers.
  - Work: Create output directory, generate unique filenames, copy streamed bytes according to `files[].bytes`, emit plain output or JSON output according to `--json`, and use distinct exit behavior for no-content vs errors.
  - Validation: Local macOS `ghostty-nav paste`; remote `ssh openclaw '~/.local/bin/ghostty-nav paste --output-dir /tmp/pi-paste-file --json'`; verify files exist on the remote host.

- [ ] Phase 4: Add `pi-paste-file` extension package
  - Goal: Bind the configured shortcut inside Pi and paste text or paths into the editor.
  - Files: `chezmoi/private_dot_pi/agent/extensions/pi-paste-file/package.json`, `tsconfig.json`, `index.ts`, `settings.ts`, `ghostty-nav.ts`, `typebox.ts`.
  - Work: Load settings with the `pi-sessions` pattern; register configured shortcut; run `ghostty-nav paste --json --output-dir <dir>`; parse JSON with TypeBox; call `ctx.ui.pasteToEditor`; notify only for file results.
  - Validation: `uv run poe lint:pi`; manual Pi tests for text, image, and multiple files locally and over OpenClaw.

- [ ] Phase 5: Delete the old BetterTouchTool path and verify migration
  - Goal: Make the new path the only repo-managed Pi paste flow.
  - Files: `chezmoi/dot_local/bin/executable_btt-paste-image.sh`, Ansible/chezmoi deployment files as needed, BTT documentation or local configuration notes.
  - Work: Remove the old script, apply macOS and OpenClaw roles, verify forwarded socket behavior, and bind the desired Pi shortcut.
  - Validation: End-to-end shortcut use in a remote OpenClaw Pi session inserts `/tmp/pi-paste-file/...`; text paste stays silent; multi-file paste inserts space-separated paths; no repo references still rely on `btt-paste-image.sh`.
