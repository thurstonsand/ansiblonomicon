# macOS system configuration

Native mise owns the 27 typed user preferences and `/etc/pam.d/sudo_local`; the driver adds change-only application restarts and personal hostname reconciliation. Run `mise sysconfig` or `mise laptop -t sysconfig`, adding `--check` for a read-only preview. Section tags such as `dock,permissions` select only those resources; including `sysconfig` selects the whole unit.

Work owns Touch ID but leaves hostname and every pre-existing `pam_reattach` line untouched.

The driver checks all selected resources before writing and restarts affected applications after defaults changes, including partial native apply failures. PAM rendering preserves unrelated lines and their ordering. Credentials are needed only if a privileged write invokes sudo; the driver itself performs no credential lookup. Repository environment activation is separate and may authenticate before a root mise task starts.
