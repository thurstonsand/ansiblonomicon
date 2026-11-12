# eve

`eve` is the Framework laptop's Windows side, dual-booting with Omarchy, reconciled natively by `mise windows`; `-t windows-system` and friends narrow it. Tasks run under Git Bash, selected by the global mise config the `mise` tag links, so the target never assumes WSL. `windows-apps` declares winget packages in `[bootstrap.packages]`, and `windows-system` owns the registry values in the target's `windows-system.toml`, asking UAC once when a machine-wide value differs. `vcs` turns off Git for Windows' CRLF conversion and turns on symlinks. `amp-cli` runs the Amp runner as the `mise\amp-runner` Scheduled Task at logon, windowless under a headless conhost, with `amp-runner.ps1` restarting it and taking it down with the task.

`windows-apps` also installs the latest stable Microsoft-signed MagicTrackpad2ForWindows driver through its post-packages hook, verifying the release checksum and catalog signature before requesting UAC for an install or upgrade. The hook downloads the release to inspect its version on each apply, but skips installation when that version is already in the driver store, even with the trackpad disconnected. SteelSeries GG is a normal winget package. Keyboard repeat and trackpad preferences belong to [windows-system](../../capabilities/windows-system/README.md).

A fresh Windows host needs Git for Windows and Developer Mode first, because the repo and its dotfiles are symlinks. Then:

```powershell
git clone -c core.symlinks=true -c core.autocrlf=false git@github.com:thurstonsand/ansiblonomicon.git
cd ansiblonomicon
irm https://mise.run/powershell | iex      # official build at ~\.local\bin, so self-update works
mise -C bootstrap/targets/eve bootstrap --only dotfiles --force-dotfiles --yes
mise trust; mise run bootstrap; mise windows
mise --no-env exec -- python3 scripts/automation_identity.py
```

The identity is the laptops' shared automation token, kept readable only by its owner through the file's access list instead of mode 0600.
