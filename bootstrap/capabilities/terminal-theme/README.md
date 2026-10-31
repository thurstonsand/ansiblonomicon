# Terminal theme capability

This native mise capability installs the shared Python runtime and zsh helper as source symlinks, renders Hunk's runtime-mutated config as a real native dotfile, and manages the macOS appearance watcher as a LaunchAgent. The detector seeds a missing `.terminal-bg` from macOS appearance; mirrors default a missing state to dark. Runtime state and SSH leases remain outside the repository. Both native rendering and Python runtime switching read the same light/dark TOML palettes.

## City Ruins and Copied City

City Ruins is the dark theme and Copied City the light one. Both start from Omarchy's Solitude: `city-ruins/solitude.toml` is its terminal palette verbatim, paired with ashen.nvim's accents as Omarchy pairs them. Copied City mirrors each color's OKLCH lightness while keeping its hue and chroma, giving up chroma only where sRGB cannot hold it. Over those cool greys, `SIGNALS` in `city-ruins/render.py` places a steel accent and one hue per meaning, per mode rather than mirrored: ember (Solitude's own `bright_red`) for errors and removals, amber for changes, warnings, and lit lamps, and green for additions and locks. They take the ANSI red, yellow, green, and blue slots; Solitude's greys keep the rest, and its keyword grey keeps syntax highlighting as it was. The script writes every theme file from both modes: Ghostty, tmux, Hunk, Neovim's light ashen palette and the diff colors it lays over ashen, Codex's `.tmTheme` files and desktop chrome, Pi's interview CSS, Claude's statusline colors, both Omarchy themes, and Home Assistant's House Atlas theme. Edit the palette, the signals, or the mirror there and rerun it; never hand-edit its outputs.

On Omarchy, everything follows the active Omarchy theme instead. City Ruins and Copied City are user themes whose `colors.toml` the script writes into `bootstrap/capabilities/omarchy/files/themes/`, beside Neovim specs for the matching colorschemes, so Omarchy renders Ghostty, tmux, Hyprland, and the rest of its apps from them. City Ruins also keeps Solitude's icon theme and wallpapers, which `omarchy-config` copies from the Omarchy install. The same renderers, fed Omarchy `{{ key }}` placeholders instead of hex values, write `omarchy/themed/*.tpl`, which Omarchy fills from whichever theme is active; City Ruins and Copied City carry exact copies that take precedence. Claude's statusline, Pi's interview, and a Hunk extension read the rendered files in place; `theme-set` hooks copy Codex's theme and chrome into `~/.codex` and cache the same `.tmTheme` as bat's `omarchy` theme, which bat and the delta wrapper select. Codex desktop's code blocks stay on its built-in `vercel`, the only kind of theme it accepts, and an open Hunk reads the new theme on restart. Omarchy renders only on a theme switch, so `omarchy-config` refreshes the current theme when any of these sources changed or a consumer's copy is missing.

Run the focused reconciliation on a registered host:

```sh
mise terminal-theme
mise terminal-theme --check
```

`--check` uses mise's dry run to preview files, dotfiles, and the LaunchAgent; it does not initialize state, execute the theme runtime, fetch from the network, or update mise. Regular host reconciliation also includes this capability. The macOS target requires mise 2026.9.6; normal reconciliation runs mise maintenance before invoking this capability.

Shared declarations and assets are linked into each host target. The Macs keep only absolute private-file destinations and ownership in `mise.terminal-theme-files.toml`: mise does not template those keys. macOS apply resolves the host's scoped sudo credential before invoking askpass, then executes native mise in the authenticated process; no terminal is required.

The watcher plist contains a hash of its repository runtime inputs. Native LaunchAgent apply therefore reloads it when those inputs or the plist declaration change, while a no-op reconcile leaves the running watcher untouched. Mise prefixes the label with `dev.mise.`.

Laptop reconciliation calls this capability after the agent harness and before the other configuration capabilities. `mise laptop -t terminal-theme` and `mise reconcile -t terminal-theme` run it alone. Check mode follows the same routing without updates or native writes.
