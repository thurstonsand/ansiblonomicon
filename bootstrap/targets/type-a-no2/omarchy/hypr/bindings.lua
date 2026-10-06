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

o.bind("Alt_R", "Start dictation (push-to-talk)", "hyprwhspr record start")
o.bind("ALT + Alt_R", "Stop dictation (push-to-talk)", "hyprwhspr record stop", { release = true })
