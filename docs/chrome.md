# Chrome

Chrome's shortcut editor rejects Ctrl-Tab, so the recent-tab switchers that take it over are bound through Chrome's internal extension-management API instead, once per profile. Each host that relies on them declares the bindings in its `bootstrap/targets/<host>/chrome-shortcuts.toml`. `mise browser`, also run as the `browser` tag of that host's full reconcile, reads the declared profile's `Preferences` and fails with a link to this guide if any shortcut has a missing or incorrect extension ID, command, or scope. Other profiles and unrelated shortcuts are left alone. This checks saved bindings, not whether the extensions are enabled or working, and never edits the profile or opens Chrome.

When it fails, it prints the console block that saves the declared shortcuts. Run that block in the profile's `chrome://extensions/shortcuts` DevTools console, not an ordinary website's. It first checks that each extension is installed, then updates only the named commands, replacing any existing assignment for the same key combination. It can be repeated. Chrome can lag in saving the result to `Preferences`; if the check still fails afterwards, fully exit Chrome, including web apps, and rerun it. There is no profile-file patching or system-wide key remapping. The API is private and may change with Chrome updates. Bindings are per platform and don't sync between operating systems.

## Omarchy

Chrome is no9-type-s's default browser. `loadout.toml` declares its package; `omarchy-config` selects it through `omarchy default browser chrome`, installs Omarchy's native Copy URL clipboard helper, and enables the accessibility flag used by Superwhisper. Chrome Sync owns supported browser preferences and Web Store extensions. Browser profiles, cookies, and credentials stay out of the repo.

### Restore a profile

Run `mise omarchy -t omarchy-loadout,omarchy-config,browser` to reconcile the host. The `browser` step fails until the `Default` Chrome profile has the three shortcuts below; on a fresh install, that failure is expected. Open Chrome and sign into the personal Google account to restore synced extensions, or install [Tab Flick Lite](https://chromewebstore.google.com/detail/kdddoanokjocdkbkmgnkkcemjepknlgm) directly. The remaining steps apply to each Chrome profile that needs these shortcuts; they are not unattended reconciliation.

#### Load Omarchy's Copy URL extension

1. Open `chrome://extensions/` in Chrome and enable **Developer mode**.
2. Choose **Load unpacked**, then select `/usr/share/omarchy/default/chromium/extensions/copy-url`. In the folder picker, choose **Home** first if it opens in **Recent**, then use Ctrl-L to enter the path and click **Select**.
3. Check that **Copy URL** is enabled, with ID `bgpiichlckmfanooecilcjemknkcpngb`.

Use the installed Omarchy directory directly rather than copying or vendoring the extension. Chrome ignores the `--load-extension` flag Omarchy uses for Chromium, and unpacked extensions do not restore through Chrome Sync. The native helper is already registered for Chrome by reconciliation. After an Omarchy extension update, use its **Reload** button or restart Chrome to load the updated code. Download Video is not required.

#### Apply the shortcuts

Run `mise omarchy -t browser --check`, open `chrome://extensions/shortcuts`, press F12, select the **Console** tab, and paste the block it printed. Its Ctrl-Shift-C belongs to Copy URL rather than the DevTools element picker.

Close DevTools before testing:

- On a normal web page, Ctrl-Shift-C should put its exact URL in the clipboard and show Omarchy's confirmation notification. Paste into a text field to verify it.
- With several ordinary web tabs open, hold Ctrl and press Tab twice, then Shift-Tab. Tab Flick should open, advance, and move back one card. Release Ctrl to select it.
- Ctrl-PageUp / Ctrl-PageDown still navigate tabs in tab-strip order.

Then rerun `mise omarchy -t browser --check`.

### Web apps follow the default browser

`Amp.desktop`, `WhatsApp.desktop`, and the other Omarchy web-app launchers call `omarchy-launch-webapp`, which selects Chrome when it is the default. WhatsApp is `https://web.whatsapp.com/` in an app window, not a separate native client. No per-launcher browser override is necessary.

Check the resolved browser with `omarchy default browser` (expected: `chrome`). Close old Chromium app windows and reopen their launchers; already-running windows do not migrate. Chrome has separate cookies, so Amp and WhatsApp may need a fresh sign-in or device pairing. Neither Chrome Sync nor this setup copies Chromium sessions. Omarchy's optional WhatsApp Slim extension is separate from the WhatsApp launcher and is not part of this setup.

## Work Mac

The Crowdstrike profile, `Profile 1`, switches recent tabs with [Popup Tab Switcher](https://chromewebstore.google.com/detail/cehdjppppegalmaffcdffkkpmoflfhkc); work policy blocks Tab Flick Lite. Install it, run `mise laptop -t browser --check`, open `chrome://extensions/shortcuts` in that profile, press ⌥⌘J for the console, and paste the block it printed. The API reads `Ctrl` as the Control key on macOS too, unlike a manifest's suggested keys; `Command` names ⌘.

Hold Control and press Tab to open the switcher on the most recent tab; release Control to select. Then rerun `mise laptop -t browser --check`.

## Lucky

The `browser` task renders the config for Lucky, the address-bar "I'm Feeling Lucky" extension, on no9-type-s and pod042. Make Kagi the default search engine and load it unpacked as [its README](../bootstrap/capabilities/browser/README.md) describes.

## Agent browsing

Browse drives the signed-in Chrome profile for coding agents. Mise installs its CLI, while Chrome Sync owns its Web Store extension. Pair each profile with the local relay once, following [Browser automation](../bootstrap/capabilities/agent-harness/README.md#browser-automation). The `browsing` skill supplies the agent workflow; passkey prompts still need native desktop interaction or a user handoff.
