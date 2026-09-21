# SSH client

Native mise owns the personal Mac and pod042 SSH client config and smart proxy. The Mac receives home-lab aliases and the 1Password agent; pod042 receives its GitHub identity from the two scoped fnox secrets. Other files below `~/.ssh`, including `config.d`, `known_hosts`, and unrelated private keys, are preserved.

Run `mise ssh-client` or `mise laptop -t ssh-client`. `--check` uses explicit non-secret placeholders on pod042 so preview never fetches credentials; key files can appear changed even when their real values are already converged. Apply resolves only `POD042_GIT_SSH_PRIVATE_KEY` and `POD042_GIT_SSH_PUBLIC_KEY`.
