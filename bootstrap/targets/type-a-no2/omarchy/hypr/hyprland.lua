-- Learn how to configure Hyprland: https://wiki.hypr.land/Configuring/Start/

-- Omarchy's bootstrap keeps path setup out of this user config.
dofile((os.getenv("OMARCHY_PATH") or "/usr/share/omarchy") .. "/default/hypr/bootstrap.lua")

-- Disable all Omarchy default bindings. Add your own in hypr/bindings.lua.
-- omarchy_default_bindings = false
--
-- Or disable only bindings for Omarchy's preinstalled apps/web apps while
-- keeping core window-manager bindings:
-- omarchy_preinstalled_bindings = false

-- Load Omarchy defaults.
require("default.hypr.omarchy")

-- Put your personal overrides in these files. They're loaded after Omarchy's
-- defaults so package updates can improve the defaults without rewriting your
-- ~/.config/hypr files.
require("hypr.monitors")
require("hypr.input")
require("hypr.mouse")
-- Superwhisper replaces bindings.lua whenever it saves its shortcuts, which would break a symlink, so personal bindings live beside it.
require("hypr.personal-bindings")
-- With Omarchy's `o` visible, Superwhisper's hook reports Right Alt to its daemon as Omarchy's push-to-talk key, and the
-- daemon then stops any recording started while Right Alt is down, which breaks the double-tap latch in personal-bindings.
local omarchy = o
o = nil
require("hypr.bindings")
o = omarchy
require("hypr.looknfeel")
require("hypr.autostart")

-- Toggle config flags dynamically.
require("default.hypr.toggles")

-- Add any other personal Hyprland configuration below.
-- o.window("qemu", { workspace = "5" })
