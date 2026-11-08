---
name: using-pod042-desktop
description: Drives pod042's shared Desktop tab with browser automation, Wayland keyboard, mouse, clipboard, and screenshots. Use for GUI work or browsing on pod042.
---

# Using pod042's desktop

Run on pod042 as `thurstonsand`. Each Amp thread's Desktop tab streams the runner's labwc Wayland session: the windows you drive are the windows the user watches. Control it with Browse for pages, and `wlrctl`, `wtype`, `wl-clipboard`, and `grim` for everything else. For service changes, use `operating-pod042` and read `bootstrap/targets/pod042/remote-development/README.md` in ansiblonomicon. The ChatGPT app on Xvfb `:42` and 1Password on `:43` are separate persistent apps holding login state; touch them only when the task names them.

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

`wlrctl pointer move` is relative and works in logical pixels, while `grim` captures physical pixels. The user's viewer sets the output scale, so divide screenshot coordinates by `wlr-randr`'s `Scale:` and anchor at the top-left corner:

```sh
click() {   # x y in grim screenshot pixels
  s=$(wlr-randr | awk '/Scale:/{print $2}')
  wlrctl pointer move -100000 -100000
  wlrctl pointer move "$(awk "BEGIN{print int($1/$s)}")" "$(awk "BEGIN{print int($2/$s)}")"
  wlrctl pointer click "${3:-left}"
}
click 960 400
wlrctl pointer scroll 3 0            # dy dx
printf %s 'text' | wl-copy >/dev/null 2>&1   # wl-copy stays running to serve the clipboard
wl-paste -n
```

Drive input only through `wtype` and `wlrctl`; each adds its own virtual device. The Waymote gateway's `/control` socket belongs to the user's viewer, and connecting to it takes input away from them.

## Screenshots

```sh
grim /absolute/path/desktop.png
grim -g '400,0 400x720' /absolute/path/region.png   # -g takes logical pixels
```

The viewer can resize and rescale the output at any time, so check `wlr-randr` and a fresh capture before choosing points, and capture again after every input. A dispatched action is not success: verify the changed window, field, or file.

## Browser

Chromium runs a dedicated profile paired with Browse. Load `browsing`, then use one named session per task:

```sh
browse status --json
browse session new my-task
browse execute --session my-task 'await page.goto("https://example.com"); return await snapshot()'
```

Browse opens its own background tabs. Adopt a user's tab only after they lend it with the toolbar button. Read fields back after filling them and verify the resulting page state. For pairing or extension installation, follow the Browser automation section of `bootstrap/capabilities/agent-harness/README.md` in ansiblonomicon.

Browser chrome (address bar, bookmark dialogs, extension popups, permission prompts) sits outside the page; drive it with `grim` and the pointer, or Chromium's keyboard shortcuts. Typing into the address bar triggers inline autocomplete from history, so Return can land on a different page; paste the URL instead:

```sh
printf %s 'https://example.com/' | wl-copy >/dev/null 2>&1
wtype -M ctrl l -m ctrl -s 200 -M ctrl v -m ctrl -s 200 -k Return   # -s waits ms; without them a new tab drops the paste
```

Browse removes password-manager overlays from controlled pages and cannot operate 1Password's passkey UI. When authorized to perform a login with native desktop controls, use a fresh tab outside Browse's control, complete and verify the login there, then resume Browse in a new tab. Otherwise hand the login to the user.

Close only your task's tabs with `browse session delete my-task`; leave other sessions and the user's tabs alone. Do not run global tab cleanup on this shared browser.

If Browse reports no browser, run `browse doctor` and check `pgrep -af 'chromium.*chromium-desktop'`. With no browser running, start `setsid ~/.local/bin/desktop-chromium >/dev/null 2>&1 </dev/null &` and check status again. A running browser may need its extension paired or reconnected; leave its process and profile locks alone. A missing environment file or Wayland socket is a runner fault: diagnose it through `operating-pod042`. Restarting `dev.mise.amp-remote.service` interrupts every runner thread.
