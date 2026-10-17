# Terminal theme capability

This native mise capability installs the shared Python runtime and zsh helper as source symlinks, renders Hunk's runtime-mutated config as a real native dotfile, and manages the macOS appearance watcher as a LaunchAgent. The detector seeds a missing `.terminal-bg` from macOS appearance; mirrors default a missing state to dark. Runtime state and SSH leases remain outside the repository. Both native rendering and Python runtime switching read the same light/dark TOML palettes.

## Solitude

The palette is Omarchy's Solitude: `solitude/colors.toml` is its terminal palette verbatim, paired with ashen.nvim's accents as Omarchy pairs them. The light variant mirrors each color's OKLCH lightness while keeping its hue and chroma, giving up chroma only where sRGB cannot hold it. `solitude/render.py` derives both modes and writes every theme file from them: Ghostty, tmux, Hunk, Neovim's light ashen palette, Codex's `.tmTheme` files and desktop chrome, Pi's interview CSS, and Claude's statusline colors. Edit the palette or the mirror there and rerun it; never hand-edit its outputs.

On Omarchy, everything follows the active Omarchy theme instead. Ghostty, tmux, and Neovim are Omarchy's own; the light variant is the user theme `solitude-light`, whose `colors.toml` the script writes into type-a-no2's `omarchy/themes/` beside a Neovim spec for the `solitude-light` colorscheme. The same renderers, fed Omarchy `{{ key }}` placeholders instead of hex values, write `omarchy/themed/*.tpl`, which Omarchy fills from whichever theme is active; Solitude and Solitude Light carry exact copies that take precedence. Claude's statusline, Pi's interview, and a Hunk extension read the rendered files in place; `theme-set` hooks copy Codex's theme and chrome into `~/.codex` and cache the same `.tmTheme` as bat's `omarchy` theme, which bat and the delta wrapper select. Codex desktop's code blocks stay on its built-in `vercel`, the only kind of theme it accepts, and an open Hunk reads the new theme on restart. Omarchy renders only on a theme switch, so `omarchy-config` refreshes the current theme when any of these sources changed or a consumer's copy is missing.

Run the focused reconciliation on a registered host:

```sh
mise terminal-theme
mise terminal-theme --check
```

`--check` uses mise's dry run to preview files, dotfiles, and the LaunchAgent; it does not initialize state, execute the theme runtime, fetch from the network, or update mise. Regular host reconciliation also includes this capability. The macOS target requires mise 2026.9.6; normal reconciliation runs mise maintenance before invoking this capability.

Shared declarations and assets are linked into each host target. The Macs keep only absolute private-file destinations and ownership in `mise.terminal-theme-files.toml`: mise does not template those keys. macOS apply resolves the host's scoped sudo credential before invoking askpass, then executes native mise in the authenticated process; no terminal is required.

The watcher plist contains a hash of its repository runtime inputs. Native LaunchAgent apply therefore reloads it when those inputs or the plist declaration change, while a no-op reconcile leaves the running watcher untouched. Mise prefixes the label with `dev.mise.`.

Laptop reconciliation calls this capability after the agent harness and before the other configuration capabilities. `mise laptop -t terminal-theme` and `mise reconcile -t terminal-theme` run it alone. Check mode follows the same routing without updates or native writes.
