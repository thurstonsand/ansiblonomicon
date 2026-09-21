# Shell capability

Native mise owns `.zshenv`, `.zprofile`, `.zshrc`, the static Starship configuration, and work's `cleanh` helper. It preserves the existing `~/.zshenv.local` and `~/.zshrc.local` extension points and does not own those private work templates.

Run `mise run shell` (or `mise run shell --check`) on a registered host. Check mode uses no credentials and substitutes an inert value while previewing the private work `.zshenv`; it never prints a token. Apply on work resolves `SOURCEGRAPH_TOKEN` and the work-scoped sudo credential through `fnox-host`, validates sudo, then renders the mode-0600 `.zshenv` atomically. Personal and pod042 runs do not resolve work credentials.

Shell software remains owned by the existing Brewfile/base/operator capabilities. This capability only renders configuration.

Project environments use mise. Direnv remains installed for external projects, but the shared shell does not activate it; use `direnv exec . <command>` explicitly where needed. Reconciliation removes the retired `~/.config/direnv/direnv.toml`. The tmux wrapper clears mise's project environment before starting tmux.
