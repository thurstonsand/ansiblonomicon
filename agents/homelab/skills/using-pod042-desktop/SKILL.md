---
name: using-pod042-desktop
description: Drives pod042's shared Desktop tab with browser automation, Wayland keyboard, mouse, clipboard, and screenshots. Use for GUI work or browsing on pod042.
---

# Using pod042's desktop

Run on pod042 as `thurstonsand`. Each Amp thread's Desktop tab streams the runner's labwc Wayland session: the windows you drive are the windows the user watches. Control it with agent-browser on CDP 9222 for pages, and `wlrctl`, `wtype`, `wl-clipboard`, and `grim` for everything else. For service changes, use `operating-pod042` and read `bootstrap/targets/pod042/remote-development/README.md` in ansiblonomicon. The ChatGPT app on Xvfb `:42` and 1Password on `:43` are separate persistent apps holding login state; touch them only when the task names them.

Runner restarts, including Amp's self-updates, recreate the Desktop tab's compositor: Chromium reopens its tabs and every other app on it closes.

## Wayland environment

Source the runner's environment in the same shell as every GUI command, and again after a runner restart:

```sh
. "$HOME/.cache/amp/runner-desktop/pod042/environment"
```

## Windows

```sh
setsid foot --title=my-task-term >/dev/null 2>&1 </dev/null &
wlrctl toplevel waitfor title:my-task-term
wlrctl toplevel list
wlrctl toplevel focus title:my-task-term
wtype -M logo -k Left -m logo        # snap the focused window to the left half; -k Right for the right
wlrctl toplevel close title:my-task-term
```

`wlrctl` has no `--help`; `man wlrctl` lists its actions and match syntax. Give each window you launch a unique title. `title:` and `app_id:` match whole values; `wlrctl toplevel list` prints the current ones, which shells and pages can change. Native Wayland apps (`foot`, Chromium, Thunar) and X11 apps under Xwayland all take this input.

## Keyboard, pointer, and clipboard

`wtype` types into the focused window. Focus your target, confirm it with `wlrctl toplevel find title:my-task-term state:active`, then type:

```sh
wtype 'ls -la'; wtype -k Return
wtype -M ctrl c -m ctrl              # hold, press, release
wtype -M ctrl -M shift v -m shift -m ctrl   # paste in foot
```

`wlrctl pointer move` is relative. Anchor it at the top-left corner and the coordinates match a full `grim` screenshot pixel for pixel:

```sh
click() { wlrctl pointer move -100000 -100000; wlrctl pointer move "$1" "$2"; wlrctl pointer click "${3:-left}"; }
click 960 400
wlrctl pointer scroll 3 0            # dy dx
printf %s 'text' | wl-copy
wl-paste -n
```

Drive input only through `wtype` and `wlrctl`; each adds its own virtual device. The Waymote gateway's `/control` socket belongs to the user's viewer, and connecting to it takes input away from them.

## Screenshots

```sh
grim /absolute/path/desktop.png
grim -g '640,0 640x720' /absolute/path/right-half.png
```

The viewer can resize the output, so read the size of a fresh capture before choosing points, and capture again after every input. A dispatched action is not success: verify the changed window, field, or file.

## Browser

Chromium runs a dedicated profile with DevTools on CDP 9222. Use the `agent-browser` skill for page commands, with one session name per task and `--cdp 9222` on every call:

```sh
curl -fsS --max-time 5 http://127.0.0.1:9222/json/version
S="agent-browser --session my-task --cdp 9222"
$S --pin-tab open https://example.com   # first call: opens your own tab and waits for the page
$S snapshot -i
$S open https://example.org          # later navigation stays in that tab
```

Make the pinned `open` the session's first call; starting with `tab` or `tab new` leaves an extra blank tab, and `tab new <url>` returns while the page is still `about:blank`. Read a field back after `fill`: on time, date, and other native pickers it reports success and sets nothing. Type those natively instead, in the field's display segments:

```sh
$S focus 'input[type=time]'
wlrctl toplevel focus app_id:chromium
wtype 0745P                          # 19:45
```

Browser chrome (address bar, bookmark dialogs, extension popups, permission prompts) sits outside the page; drive it with `grim` and the pointer, or Chromium's keyboard shortcuts. Close only the tabs you opened (`$S tab close`) and leave the user's. `agent-browser --session my-task close`, without `--cdp`, disconnects your session and leaves Chromium running.

If the CDP probe fails while the environment's Wayland socket exists, check `pgrep -af 'chromium.*chromium-desktop'`. With no browser running, start `setsid ~/.local/bin/desktop-chromium >/dev/null 2>&1 </dev/null &` and retry the probe for 15 seconds. A running browser without CDP needs its launch arguments and logs inspected before anything else; leave its process and profile locks alone. A missing environment file or socket is a runner fault: diagnose it through `operating-pod042`. Restarting `amp-remote.service` interrupts every runner thread.
