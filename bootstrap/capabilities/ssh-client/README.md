# SSH client

Native mise owns the pod153, Omarchy laptop, and pod042 SSH client config and smart proxy. The executable proxy is rendered as a native dotfile. The ordinary config remains a `bootstrap.files` template so its required `0644` mode is explicit, while pod042's private and public GitHub keys remain permission-controlled bootstrap files. The laptops receive home-lab aliases and the 1Password agent; their `pod042` aliases need 1Password's "sync SSH bookmarks to filesystem" setting, which writes `~/.ssh/1Password/`. Other files below `~/.ssh`, including `config.d`, `known_hosts`, and unrelated private keys, are preserved.

pod153 runs unattended, so like pod042 it uses the shared `id_ed25519_git` file key for GitHub, pod042, and commit signing, never the 1Password agent. `authorized_keys` here lists who may log in to both servers: the operator key and that shared key.

Run `mise ssh-client` or `mise laptop -t ssh-client`. On pod042 and pod153 it resolves only `POD042_GIT_SSH_PRIVATE_KEY` and `POD042_GIT_SSH_PUBLIC_KEY`.
