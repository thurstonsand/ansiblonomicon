# Windows system configuration

Native mise has no Windows settings resource, so this capability owns registry values and the time zone. A target declares them in `windows-system.toml`: `timezone` takes a Windows ID from `tzutil /l`, and registry values are keyed by `HKLM\…` or `HKCU\…` path; integers become `REG_DWORD` and strings `REG_SZ`. Run `mise windows-system`, or `mise windows -t windows-system`, adding `--check` for a read-only preview.

The driver reads every declared value before writing and changes only the ones that differ. Machine (`HKLM`) changes need elevation: an unelevated run relaunches itself once through UAC, which a person approves at the keyboard, then re-reads every value to confirm it converged. Check mode never elevates. A change under `HKCU\Environment` is announced to running programs; terminals opened before it still need restarting.

Hibernation and Fast Startup settings take effect at the next restart.
