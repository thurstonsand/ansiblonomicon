# pod042 agent harness

`mise.agent-harness.toml` runs the native adapter as the operator after the operator capability installs Python 3.14, uv and Git. The adapter imports the existing role's Python resolver and transformers, and reads its source catalogue, pod042 profile, platform layouts and public models. It does not run Ansible or copy another machine's generated files.

The adapter owns catalogue skills, supported subagent files and the hook fragment cache. Chezmoi still owns user instructions, models, settings, extensions and platform packages. The capability reapplies chezmoi after the adapter to incorporate refreshed hook fragments. Amp receives only explicitly targeted machine-local skills; hosted catalogue publishing remains separate.

The command refuses execution outside pod042 or outside the operator's UID/GID 1000 and Linux home. Git sources use the existing harness cache and fast-forward updates. Jinja templates render with pod042 facts; file lookups stay inside the checkout and unsupported lookup plugins fail rather than requesting credentials.

Reconciliation records its owned files in `.cache/ansiblonomicon-harness/pod042-managed-files.json`. Later runs remove only previously recorded files, preserving skills installed independently by Codex, Pi packages or the operator. Run the script with `--check` to compare already cached sources without writes or network updates. A first-run check requires the source cache to exist. Native bootstrap check mode previews the hook but does not execute it.
