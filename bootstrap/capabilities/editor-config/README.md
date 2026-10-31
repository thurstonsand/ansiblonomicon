# Editor configuration capability

This capability renders Zed on every laptop. `bootstrap/capabilities/agent-harness/models.yml` is the canonical model catalogue; a small read-only renderer materializes only the application structures that need that YAML, then native mise performs all destination writes.

Run `mise editor-config`, or the `editor-config` tag of `mise laptop` or `mise omarchy`; add `--check` for a nonmutating preview. Native dotfiles link static baselines to the checkout and render settings as regular files. The renderer writes only to stdout; Tera templates call it with the repository interpreter and model catalogue paths supplied by the root task.

`editor_monospace_font`, `editor_proportional_font`, and `editor_font_size` are host scalar variables.

On Omarchy, Zed comes from the loadout and is set up once by `omarchy-install-editor-zed`. The `omarchy` profile gives Zed omazed's generated `Omazed` theme with Zed's default icons.
