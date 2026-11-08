# Chrome on Omarchy

Chrome is no9-type-s's default browser. `loadout.toml` declares its package; `omarchy-config` selects it through `omarchy default browser chrome`, installs Omarchy's native Copy URL clipboard helper, and enables the accessibility flag used by Superwhisper. Chrome Sync owns supported browser preferences and Web Store extensions. Browser profiles, cookies, and credentials stay out of the repo.

## Restore a profile

Run `mise omarchy -t omarchy-loadout,omarchy-config` to reconcile the host. The `omarchy-config` step fails until the `Default` Chrome profile has the three shortcuts below; on a fresh install, that failure is expected. Open Chrome and sign into the personal Google account to restore synced extensions, or install [Tab Flick Lite](https://chromewebstore.google.com/detail/kdddoanokjocdkbkmgnkkcemjepknlgm) directly. The remaining steps apply to each Chrome profile that needs these shortcuts; they are not unattended reconciliation.

Both regular reconciliation and `mise omarchy -t omarchy-config --check` read `~/.config/google-chrome/Default/Preferences` and fail with a link to this guide if any required shortcut has a missing or incorrect extension ID, command, or scope. Other profiles and unrelated shortcuts are left alone. This checks saved bindings, not whether the extensions are enabled or working, and never edits the profile or opens Chrome.

### Load Omarchy's Copy URL extension

1. Open `chrome://extensions/` in Chrome and enable **Developer mode**.
2. Choose **Load unpacked**, then select `/usr/share/omarchy/default/chromium/extensions/copy-url`. In the folder picker, choose **Home** first if it opens in **Recent**, then use Ctrl-L to enter the path and click **Select**.
3. Check that **Copy URL** is enabled, with ID `bgpiichlckmfanooecilcjemknkcpngb`.

Use the installed Omarchy directory directly rather than copying or vendoring the extension. Chrome ignores the `--load-extension` flag Omarchy uses for Chromium, and unpacked extensions do not restore through Chrome Sync. The native helper is already registered for Chrome by reconciliation. After an Omarchy extension update, use its **Reload** button or restart Chrome to load the updated code. Download Video is not required.

### Apply the shortcuts

Open `chrome://extensions/shortcuts`, press F12, and select the **Console** tab in DevTools. Run this block there, not in an ordinary website's console. These calls update only the named commands and can be repeated. They replace any existing assignment for the same key combination in this profile. In particular, Ctrl-Shift-C belongs to Copy URL rather than the DevTools element picker.

```javascript
await chrome.developerPrivate.getExtensionInfo("bgpiichlckmfanooecilcjemknkcpngb");
await chrome.developerPrivate.getExtensionInfo("kdddoanokjocdkbkmgnkkcemjepknlgm");

await chrome.developerPrivate.updateExtensionCommand({
  extensionId: "bgpiichlckmfanooecilcjemknkcpngb",
  commandName: "copy-url",
  keybinding: "Ctrl+Shift+C",
  scope: "CHROME",
});
await chrome.developerPrivate.updateExtensionCommand({
  extensionId: "kdddoanokjocdkbkmgnkkcemjepknlgm",
  commandName: "next-tab",
  keybinding: "Ctrl+Tab",
  scope: "CHROME",
});
await chrome.developerPrivate.updateExtensionCommand({
  extensionId: "kdddoanokjocdkbkmgnkkcemjepknlgm",
  commandName: "prev-tab",
  keybinding: "Ctrl+Shift+Tab",
  scope: "CHROME",
});
```

The first two calls check that both extensions are installed before changing bindings. This uses Chrome's internal extension-management API because the shortcut editor rejects Ctrl-Tab. There is no profile-file patching or system-wide key remapping. The API is private and may change with Chrome updates; do not assume that these Linux bindings sync to other operating systems.

Close DevTools before testing:

- On a normal web page, Ctrl-Shift-C should put its exact URL in the clipboard and show Omarchy's confirmation notification. Paste into a text field to verify it.
- With several ordinary web tabs open, hold Ctrl and press Tab twice, then Shift-Tab. Tab Flick should open, advance, and move back one card. Release Ctrl to select it.
- Ctrl-PageUp / Ctrl-PageDown still navigate tabs in tab-strip order.

Fully exit Chrome, including its web-app windows, so it saves the changed preferences. Then rerun `mise omarchy -t omarchy-config --check`. While Chrome is running, the file may lag behind its current shortcuts.

## Lucky

The `browser` tag renders the keys for Lucky, the address-bar "I'm Feeling Lucky" extension. Make Kagi the default search engine and load it unpacked as [its README](../bootstrap/capabilities/browser/README.md) describes.

## Agent browsing

Browse drives the signed-in Chrome profile for coding agents. Mise installs its CLI, while Chrome Sync owns its Web Store extension. Pair each profile with the local relay once, following [Browser automation](../bootstrap/capabilities/agent-harness/README.md#browser-automation). The `browsing` skill supplies the agent workflow; passkey prompts still need native desktop interaction or a user handoff.

## Web apps follow the default browser

`Amp.desktop`, `WhatsApp.desktop`, and the other Omarchy web-app launchers call `omarchy-launch-webapp`, which selects Chrome when it is the default. WhatsApp is `https://web.whatsapp.com/` in an app window, not a separate native client. No per-launcher browser override is necessary.

Check the resolved browser with `omarchy default browser` (expected: `chrome`). Close old Chromium app windows and reopen their launchers; already-running windows do not migrate. Chrome has separate cookies, so Amp and WhatsApp may need a fresh sign-in or device pairing. Neither Chrome Sync nor this setup copies Chromium sessions. Omarchy's optional WhatsApp Slim extension is separate from the WhatsApp launcher and is not part of this setup.
