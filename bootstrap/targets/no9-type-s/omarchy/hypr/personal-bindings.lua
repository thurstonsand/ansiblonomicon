-- Keep only your personal keybinding overrides here. Add new bindings or
-- unbind defaults before replacing them.

-- See current bindings and descriptions:
--   omarchy menu keybindings --print

-- To disable every Omarchy default binding, set this in
-- ~/.config/hypr/hyprland.lua before require("default.hypr.omarchy"), then add
-- only the bindings you want below:
--   omarchy_default_bindings = false

-- To disable all preinstalled app/webapp bindings, set:
--   omarchy_preinstalled_bindings = false

-- Add a new binding.
-- o.bind("SUPER + SHIFT + R", "SSH", "alacritty -e ssh your-server")

-- Change an existing binding by unbinding it first, then binding the key again.
-- This example changes SUPER+SPACE from the launcher to the Omarchy root menu.
-- hl.unbind("SUPER + SPACE")
-- o.bind("SUPER + SPACE", "Omarchy menu", "omarchy-menu toggle root")

-- Disable a default binding without replacing it.
-- hl.unbind("SUPER + SHIFT + B")

-- Logitech MX Keys examples:
-- o.bind("SUPER + SHIFT + S", nil, "omarchy-capture-screenshot")
-- o.bind("SUPER + H", nil, "voxtype record toggle")
-- o.bind("SUPER + PERIOD", nil, "omarchy-shell shell toggle omarchy.emojis")

-- A wake-time power-button event must not open the menu behind the lock screen.
o.rebind("XF86PowerOff", "Power menu", { menu = "system" })

-- Retired apps and web shortcuts; keep the other preinstalled bindings.
hl.unbind("SUPER + SHIFT + ALT + M") -- cliamp
hl.unbind("SUPER + SHIFT + O") -- Obsidian
hl.unbind("SUPER + SHIFT + A") -- ChatGPT
hl.unbind("SUPER + SHIFT + ALT + A") -- Grok
hl.unbind("SUPER + SHIFT + C") -- HEY Calendar
hl.unbind("SUPER + SHIFT + E") -- HEY
hl.unbind("SUPER + SHIFT + ALT + E") -- HEY compose
hl.unbind("SUPER + SHIFT + Y") -- YouTube
hl.unbind("SUPER + SHIFT + CTRL + G") -- Google Messages
hl.unbind("SUPER + SHIFT + P") -- Google Photos
hl.unbind("SUPER + SHIFT + S") -- Google Maps
hl.unbind("SUPER + SHIFT + X") -- X
hl.unbind("SUPER + SHIFT + ALT + X") -- X compose

-- macOS-style line deletion in any text field. Terminals get readline's
-- ctrl+u/ctrl+k; everything else selects to the line edge and deletes the
-- selection. Key injection mirrors Omarchy's universal clipboard
-- (default/hypr/bindings/clipboard.lua): explicit down/up to dodge stuck keys.
local function send_key(mods, key, delay)
	hl.timer(function()
		hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "down" }))
		hl.timer(function()
			hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "up" }))
		end, { timeout = 30, type = "oneshot" })
	end, { timeout = delay, type = "oneshot" })
end

-- Replay a tap through the input method. send_key_state bypasses Fcitx, and
-- forwarding the original press leaves Compose pending after the chord.
o.bind_hold("code:66", nil, hl.dsp.submap("caps-compose"), nil, function()
	if hl.get_current_submap() == "caps-compose" then
		hl.dispatch(hl.dsp.submap("reset"))
		hl.exec_cmd("wtype -P Multi_key -s 30 -p Multi_key")
	end
end)
hl.unbind("SUPER + CTRL + V")
hl.define_submap("caps-compose", "reset", function()
	o.bind("V", "Clipboard manager (hold Caps Lock)", { panel = "omarchy.clipboard" })
	o.bind("Alt_R", "Hex Annotate (hold Caps Lock)", hl.dsp.global("anomaly.hex:capture"), { ignore_mods = true })
	hl.bind("catchall", hl.dsp.no_op(), { non_consuming = true, ignore_mods = true })
end)
o.bind("Alt_R", "Hex dictation (hold or double-tap)", hl.dsp.global("anomaly.hex:dictation"), { ignore_mods = true })

local function active_window_is_terminal()
	local window = hl.get_active_window()
	for _, tag in ipairs(window and window.tags or {}) do
		if tag:gsub("%*$", "") == "terminal" then
			return true
		end
	end
	return false
end

local function delete_to_line_edge(edge, terminal_key, delete_key)
	return function()
		if active_window_is_terminal() then
			send_key("CTRL", terminal_key, 1)
		else
			send_key("SHIFT", edge, 1)
			send_key("", delete_key, 80)
		end
	end
end

-- Replaces Omarchy's "Toggle window transparency".
hl.unbind("SUPER + BACKSPACE")
o.bind("SUPER + BACKSPACE", "Delete to start of line", delete_to_line_edge("Home", "U", "BackSpace"))
o.bind("SUPER + Delete", "Delete to end of line", delete_to_line_edge("End", "K", "Delete"))
