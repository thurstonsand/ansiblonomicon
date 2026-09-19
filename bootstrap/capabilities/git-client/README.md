# Git client capability

This capability owns the shared Git settings as a managed block in `~/.config/git/config`, so application-added and otherwise unmanaged settings in that file remain intact. Static attributes and ignore files are symlinked; signer and work-personal identity files are native Tera templates. Git and Jujutsu independently consume defaults from the `vcs-identity` environment; Git's private signing-key override and SCM configuration remain Git-specific.

The target's shared `vars.host_profile` selects `personal` or `work` behavior; this is host context available to every capability, not a Git-specific profile. Temporary adoption code and its removal conditions are tracked in the [migration cleanup ledger](../../../docs/operations/mise-migration-cleanup.md).

Run `mise git-client` from the repository for this capability alone, or add `--check` for a nonmutating preview. Regular laptop and pod042 reconciliation includes it. Check mode previews native dotfiles but does not execute hooks, so it does not validate raw corporate Git configuration or preview legacy-key cleanup.

Mise renders the configuration. The Python hook validates inputs before writes and removes legacy copies of managed keys outside the block afterward, preserving other settings and repeated values. On work it also removes the old Ansible-owned personal-directory include from `~/.gitconfig`; the managed block owns that include instead. Subsequent runs leave converged files untouched. Git keys declared in the block belong to this capability; edit their shared template or host variables rather than adding competing values outside it.

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
