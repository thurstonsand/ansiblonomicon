# VCS capability

This capability owns Git and Jujutsu client configuration and the identity facts both share. It owns the shared Git settings as a managed block in `~/.config/git/config`, so application-added and otherwise unmanaged settings in that file remain intact. Static attributes and ignore files are symlinked; signer and work-personal identity files are native Tera templates. Git's private signing-key override and SCM configuration remain Git-specific.

The target's shared `vars.host_profile` selects `personal` or `work` behavior; this is host context available to every capability, not a VCS-specific profile.

Run `mise vcs` from the repository for this capability alone, or add `--check` for a nonmutating preview. Regular laptop and pod042 reconciliation includes it. Check mode previews native dotfiles but does not execute hooks, so it does not validate raw corporate Git configuration.

Mise renders the configuration after a Python hook validates identity inputs and the corporate SCM fragment. Subsequent runs leave converged files untouched. Git keys declared in the block belong to this capability; edit their shared template or host variables rather than adding competing values outside it.

The work target requires an ignored `bootstrap/targets/ML-DFC6YK6VJQ/mise.local.toml`:

```toml
[vars]
vcs_work_email = "name@example.com"
vcs_work_signing_key = "ssh-ed25519 ..."
# Optional; omit when there are no corporate URL rewrites.
git_scm_config = '''
[url "ssh://git@git.example.com:2222"]
    insteadOf = "https://git.example.com/scm/"
'''
```

There are intentionally no blank or sample work identity defaults in the live target. Copy the identity and URL rewrites from the existing private work configuration before running this capability. Repositories under `~/code/personal/` retain the shared personal identity and signing key.

`git_scm_config` is optional and uses ordinary Git config syntax so it can express any number of hosts, ports, and path prefixes without another configuration schema. It is parsed and validated before dotfiles are written.

## Jujutsu

Jujutsu configuration is the native fragment `~/.config/jj/conf.d/00-ansiblonomicon.toml`. Jujutsu parses fragments independently and overlays them after `config.toml`, so capability-owned keys override `config.toml` while its other keys, including keys in the same table, remain effective. The capability never parses or rewrites `config.toml`. It requires Jujutsu v0.45 or newer for `conf.d` support.

Personal hosts sign Jujutsu commits with the public personal signing key, including pod042, intentionally differing from Git's private-key override; work uses the same `vcs_work_email` and `vcs_work_signing_key` inputs as Git.
