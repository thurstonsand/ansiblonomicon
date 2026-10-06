# Editor configuration capability

This capability renders Zed on every laptop and VS Code on the personal Mac and the Omarchy laptop. `bootstrap/capabilities/agent-harness/models.yml` is the canonical model catalogue; a small read-only renderer materializes only the application structures that need that YAML, then native mise performs all destination writes.

Run `mise editor-config`, or the `editor-config` tag of `mise laptop` or `mise omarchy`; add `--check` for a nonmutating preview. Native dotfiles link static baselines to the checkout and render settings as regular files. The renderer writes only to stdout; Tera templates call it with the repository interpreter and model catalogue paths supplied by the root task.

`editor_monospace_font`, `editor_proportional_font`, and `editor_font_size` are host scalar variables. `go_local_imports` and `gopls_build_flags` affect only VS Code output.

On Omarchy, the editors come from the loadout and are set up once by `omarchy-install-editor-vscode` and `omarchy-install-editor-zed`. The `omarchy` profile settles the overlap with Omarchy's theme sync: the rendered VS Code settings leave `workbench.colorTheme` to Omarchy, and the target reruns `omarchy-theme-set-vscode` after each render to put it back. VS Code also gets `"update.mode": "none"` because pacman owns updates. Zed uses omazed's generated `Omazed` theme with Zed's default icons.
