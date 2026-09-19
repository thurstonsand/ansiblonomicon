# Terminal tools

Owns shared tmux configuration and the macOS-only Ghostty configuration and helpers. Host manifests select platform resources. TPM checkout and plugin installation are enabled on personal hosts only; work retains its configuration-only behavior. Personal Mac reconciliation updates TPM; pod042 keeps its existing checkout unless explicitly updated.

Run `mise terminal-tools` (alias `mise tmux`) or add `--check`. Check mode renders and resolves resources without cloning or running plugin hooks. Software prerequisites remain in the Brewfiles and pod042 operator capability; full reconciliation installs them before this capability runs.
