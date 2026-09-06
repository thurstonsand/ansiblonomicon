# Package repositories and storage tools

The `repositories` capability owns the APT source and preference files. `storage` includes it, and `maintenance` includes both. The first-access environment also includes `repositories`; it remains secret-free.

Storage's pre-package phase uses native mise commands, in order:

1. Apply only the repository files with the explicit `repositories` environment.
2. Refresh package metadata and install the selected capabilities' missing packages.
3. Upgrade smartmontools to the current APT candidate.

The normal bootstrap package step then finds those packages installed. No script copies repository files or shells out directly to APT. The explicit repository-only environment prevents this early file phase from installing service configurations before their packages. Repository resources remain in the full selected environment, so the regular plan reports their drift. Full reconciliation still resolves required secrets before bootstrap can mutate the host.

Debian stable's smartmontools 7.4 cannot schedule NVMe self-tests. Official `trixie-backports` supplies 7.5 with that support and the broadcast-namespace self-test log fix. The APT preference selects backports for **smartmontools only**; it does not pin a version or promote unrelated backports packages. The declaration remains `latest`, with upgrades explicit on storage reconciliation. Native package plans treat any installed version as satisfying `latest`; they do not preview available upgrades.

The existing OrbStack Debian VM proved repository installation before package installation, a real backports smartmontools install, an already-current upgrade, and detection/repair of induced repository-file mode drift. This refactor has not yet been deployed to physical pod042.
