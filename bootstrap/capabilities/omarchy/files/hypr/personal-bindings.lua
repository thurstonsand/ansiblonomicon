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

-- MiniWhisper's dictation gesture on Right Alt: hold to talk, double-tap to
-- latch until the next press, and a lone tap discards. Recording starts on the
-- first press so no speech is lost while the gesture is still ambiguous.
-- Superwhisper's own shortcuts have no double-tap latch, so this drives its CLI.
local dictation_hold_ms = 200
local dictation_double_tap_ms = 300
local dictation = { state = "idle", held = false, generation = 0 }

local function dictation_send(command)
	hl.exec_cmd("superwhisper " .. command)
end

local function dictation_after(ms, callback)
	dictation.generation = dictation.generation + 1
	local generation = dictation.generation
	hl.timer(function()
		if generation == dictation.generation then
			callback()
		end
	end, { timeout = ms, type = "oneshot" })
end

local function dictation_press()
	if dictation.state == "idle" then
		dictation_send("start")
		dictation.state = "first_press"
	elseif dictation.state == "awaiting_second" then
		dictation.state = "second_press"
	elseif dictation.state == "latched" then
		dictation_send("stop")
		dictation.state = "stopping"
		return
	else
		return
	end
	dictation.held = false
	dictation_after(dictation_hold_ms, function()
		dictation.held = true
	end)
end

local function dictation_release()
	local state = dictation.state
	if state == "stopping" then
		dictation.state = "idle"
	elseif state ~= "first_press" and state ~= "second_press" then
		return
	elseif dictation.held then
		dictation_send("stop")
		dictation.state = "idle"
	elseif state == "second_press" then
		dictation.state = "latched"
	else
		dictation.state = "awaiting_second"
		dictation_after(dictation_double_tap_ms, function()
			dictation_send("cancel")
			dictation.state = "idle"
		end)
	end
end

o.bind("Alt_R", "Dictation (hold, or double-tap to latch)", dictation_press)
-- Alt may or may not still count as held when Alt_R comes up.
o.bind("Alt_R", nil, dictation_release, { release = true })
o.bind("ALT + Alt_R", nil, dictation_release, { release = true })
