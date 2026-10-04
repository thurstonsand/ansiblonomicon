---
name: using-pod042-desktop
description: Drives the shared Chromium and labwc desktop on pod042 that the user watches. Use when browsing, clicking through web UIs, launching GUI apps, or screenshotting on pod042.
---

# Using pod042's desktop

Run these commands on pod042 as `thurstonsand`. Amp's runner owns a persistent labwc Wayland session streamed through Waymote; the user sees the same windows you manipulate. The ChatGPT app's Xvfb `:42` is separate and must stay untouched. For service or configuration changes, use `operating-pod042` and read `bootstrap/targets/pod042/remote-development/README.md` in the ansiblonomicon checkout.

## Attach to Chromium

Probe the shared browser before issuing browser commands:

```sh
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:9222/json/version
```

Use the installed `agent-browser` CLI's `--cdp 9222` on every call. Pick a session name unique to your task and keep it for subsequent calls. A session isolates agent-browser's command state, not the shared browser. Inspect tabs before selecting one; create a task tab when the user's existing tab should be preserved.

```sh
agent-browser --session desktop-task --cdp 9222 tab
agent-browser --session desktop-task --cdp 9222 tab new about:blank
agent-browser --session desktop-task --cdp 9222 open https://example.com
agent-browser --session desktop-task --cdp 9222 snapshot
agent-browser --session desktop-task --cdp 9222 eval 'document.body.innerText'
agent-browser --session desktop-task --cdp 9222 screenshot /tmp/pod042-browser.png
```

Replace the example URL with the task's destination. Use snapshot refs for interaction and refresh them after navigation. Check `tab` again if the user changes tabs during your work. Close only your task's tab with `tab close` after confirming its selection; leave the shared browser running. Avoid `close`, which operates on the browser, and browser launch/install commands. CDP needs neither a new browser nor the desktop environment variables.

## Launch apps and capture the desktop

Source the runner's environment in the same shell that launches the GUI program or `grim`. Reload it after a runner restart; `WAYLAND_DISPLAY` can be an absolute socket path, so use the recorded value verbatim.

```sh
. "$HOME/.cache/amp/runner-desktop/pod042/environment"
foot
```

Use the harness's retained process facility for long-lived GUI commands. For a bounded smoke test, run `foot --title=desktop-proof sh -c 'printf "Shared labwc desktop\n"; sleep 120'`, then capture it from another command while the process is alive. A detached terminal command that reads from closed stdin exits immediately.

```sh
. "$HOME/.cache/amp/runner-desktop/pod042/environment"
grim /tmp/pod042-desktop.png
```

Inspect the image to verify the intended window is visible. CDP screenshots capture page content; `grim` captures the compositor, including terminal windows and browser chrome. Return the screenshot path with the observed result.

## Recover a missing browser

If the CDP probe fails, distinguish connection refusal from a permission denial. Check the environment file and its Wayland socket before launching anything:

```sh
. "$HOME/.cache/amp/runner-desktop/pod042/environment"
case "$WAYLAND_DISPLAY" in
  /*) test -S "$WAYLAND_DISPLAY" ;;
  *) test -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ;;
esac
pgrep -af 'chromium.*chromium-desktop'
```

When the compositor is available and Chromium is absent, run `~/.local/bin/desktop-chromium` with that environment using the harness's retained process facility. This launcher owns the dedicated `~/.config/chromium-desktop` profile, Wayland backend, and loopback DevTools port. Retry the CDP probe for up to 15 seconds, then attach again. If Chromium is already running but CDP is unavailable, inspect its launch arguments and logs before attempting recovery; do not kill the user's browser or remove profile locks. An absent environment file or socket requires runner diagnosis through `operating-pod042`.
