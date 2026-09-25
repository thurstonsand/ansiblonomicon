# Shell capability

Native mise owns `.zshenv`, `.zprofile`, `.zshrc`, the static Starship configuration, and work's `cleanh` helper. It preserves the existing `~/.zshenv.local` and `~/.zshrc.local` extension points and does not own those private work templates.

Run `mise run shell` (or `mise run shell --check`) on a registered host. Check mode uses no credentials and substitutes an inert value while previewing the private work `.zshenv`; it never prints a token. Apply on work resolves `SOURCEGRAPH_TOKEN`, `ANTHROPIC_AUTH_TOKEN` (exported as `GENAIHUB_API_KEY` for Codex), and the work-scoped sudo credential through `fnox-host`, then renders the mode-0600 `.zshenv` atomically, authenticating each sudo call through askpass. Personal and pod042 runs do not resolve work credentials.

Shell software remains owned by the existing Brewfile/base/operator capabilities. This capability only renders configuration.

This repo's environment uses mise. Direnv remains installed and its shell hook activates environments for external projects that use it. The tmux wrapper clears both mise and direnv project environments before starting tmux.
