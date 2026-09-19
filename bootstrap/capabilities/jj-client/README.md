# Jujutsu client capability

This capability owns the native Jujutsu fragment `~/.config/jj/conf.d/00-ansiblonomicon.toml`. Jujutsu parses fragments independently and overlays them after `config.toml`, so capability-owned keys override old declarations while unknown user keys—including keys in the same table—remain effective. Cutover never parses or rewrites the old file. It requires Jujutsu v0.45 or newer for `conf.d` support.

It independently consumes the shared `vcs-identity` facts. Personal hosts use the public personal signing key—including pod042, intentionally differing from Git's private-key override—while work uses the required private `vcs_work_email` and `vcs_work_signing_key` inputs. Run `mise jj-client` or `mise jj-client --check`; the pre-write hook validates identity inputs before creating the fragment.
