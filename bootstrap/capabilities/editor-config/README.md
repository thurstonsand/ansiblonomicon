# Editor configuration capability

This capability renders Zed on both Macs and the Cursor, Windsurf, Antigravity, and Datasette LLM configurations declared only by the personal target. `bootstrap/capabilities/agent-harness/models.yml` is the canonical model catalogue; a small read-only renderer materializes only the application structures that need that YAML, then native mise performs all destination writes.

Run `mise editor-config` or `mise laptop -t editor-config`; add `--check` for a nonmutating preview. Native dotfiles link static baselines to the checkout and render nonsecret settings as regular files. The two secret Datasette templates remain permission-controlled bootstrap files. Personal apply resolves only `CLI_PROXY_API_KEY`, `CF_ACCESS_CLIENT_ID`, and `CF_ACCESS_CLIENT_SECRET`. The renderer writes only to stdout; Tera templates call it with the repository interpreter and model catalogue paths supplied by the root task.

`editor_monospace_font`, `editor_proportional_font`, and `editor_font_size` are host scalar variables. `go_local_imports` and `gopls_build_flags` affect only the personal VSCode-family outputs; work currently installs only Zed files.
