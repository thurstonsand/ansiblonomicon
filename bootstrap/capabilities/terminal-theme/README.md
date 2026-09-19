# Terminal theme capability

This native mise capability installs the shared Python runtime and zsh helper as source symlinks, renders Hunk's runtime-mutated config as a real native dotfile, and manages the macOS appearance watcher as a LaunchAgent. The detector seeds a missing `.terminal-bg` from macOS appearance; mirrors default a missing state to dark. Runtime state and SSH leases remain outside the repository. Both native rendering and Python runtime switching read the same light/dark TOML palettes.

Run the focused reconciliation on a registered host:

```sh
mise terminal-theme
mise terminal-theme --check
```

`--check` uses mise's dry run to preview files, dotfiles, and the LaunchAgent; it does not initialize state, execute the theme runtime, fetch from the network, or update mise. Regular host reconciliation also includes this capability. The macOS target requires mise 2026.9.6; normal reconciliation runs mise maintenance before invoking this capability. Work-host live application is intentionally deferred until that laptop is available.

Shared declarations and assets are linked into each host target. The Macs keep only absolute private-file destinations and ownership in `mise.terminal-theme-files.toml`: mise does not template those keys. macOS apply resolves the host's scoped sudo credential before invoking askpass, then executes native mise in the authenticated process; no terminal is required.

The watcher plist contains a hash of its repository runtime inputs. Native LaunchAgent apply therefore reloads it when those inputs or the plist declaration change, while a no-op reconcile leaves the running watcher untouched. Mise prefixes the label with `dev.mise.`; migration unloads the legacy `house.thurstons.terminal-theme-watch` job in the post-dotfiles hook before loading the replacement, and declares the old plist absent.

Laptop reconciliation calls this capability directly after the remaining Ansible work. `mise laptop -t terminal-theme` and `mise reconcile -t terminal-theme` skip Ansible entirely; mixed tag selections pass only non-theme tags to Ansible. Check mode follows the same routing without updates or native writes. The legacy watcher cleanup remains until both Macs have migrated.
