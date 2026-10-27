# macOS system configuration

Native mise owns the 34 typed user preferences and `/etc/pam.d/sudo_local`; the driver adds change-only application restarts and hotkey reloads and pod153's hostname reconciliation. Run `mise sysconfig` or `mise laptop -t sysconfig`, adding `--check` for a read-only preview. Section tags such as `dock,permissions` select only those resources; including `sysconfig` selects the whole unit.

Work owns Touch ID but leaves hostname and every pre-existing `pam_reattach` line untouched. pod153 has nobody to answer Touch ID, so its own `mise.permissions.toml` removes `sudo_local` and grants passwordless sudo instead.

The driver checks all selected resources before writing and restarts affected applications after defaults changes, including partial native apply failures. PAM rendering preserves unrelated lines and their ordering. Credentials are needed only if a privileged write invokes sudo; the driver itself performs no credential lookup. Repository environment activation is separate and may authenticate before a root mise task starts.
