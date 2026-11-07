# Windows system configuration

Native mise has no Windows settings resource, so this capability owns appearance, registry values and the time zone. A target declares them in `windows-system.toml`: `timezone` takes a Windows ID from `tzutil /l`, and registry values are keyed by `HKLM\…` or `HKCU\…` path; integers become `REG_DWORD` and strings `REG_SZ`. Run `mise windows-system`, or `mise windows -t windows-system`, adding `--check` for a read-only preview.

The driver reads every declared value before writing and changes only the ones that differ. Machine (`HKLM`) changes need elevation: an unelevated run relaunches itself once through UAC, which a person approves at the keyboard, then re-reads every value to confirm it converged. Check mode never elevates. A change under `HKCU\Environment` is announced to running programs; terminals opened before it still need restarting.

The optional `[theme]` table selects a generated Windows `.theme` `source`, a `wallpaper`, and the installed theme filename in `name`. Source and wallpaper paths are relative to the target's declarations. The driver writes the resolved theme under `%LOCALAPPDATA%\Microsoft\Windows\Themes` and opens it through Windows, which derives the accent shades and notifies applications. This requires the logged-in desktop session and may open Personalization settings. It verifies the app and system modes, accent, picture background and wallpaper fit; a converged run does not reopen the theme, and `--check` neither writes nor applies it.

Eve selects City Ruins permanently dark, with the rainy 2B wallpaper and a steel-blue accent. `terminal-theme/city-ruins/render.py` generates the source from the shared palette. `windows-apps` links its generated WezTerm scheme and configuration; apply both with `mise windows -t windows-system,windows-apps`. There is no automatic switching. Apps that ignore Windows appearance keep their own styling.

Keyboard repeat changes apply to the live session through Windows' system-parameters API. Eve uses RepeatKeys for a 250 ms initial delay and a 15 ms repeat interval, with acceptance delays, bounce filtering, sounds, and the right-Shift toggle disabled.

Eve also declares the Magic Trackpad driver's USB and Bluetooth settings: one-finger click-and-drag and Light haptic feedback. Changes to those registry values take effect when the driver reloads its settings or the device reconnects; the driver's control panel Apply button reloads them without reconnecting.

Hibernation and Fast Startup settings take effect at the next restart.
