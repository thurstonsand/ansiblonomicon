local wezterm = require("wezterm")
local config = wezterm.config_builder()

config.color_scheme = "City Ruins"
config.use_fancy_tab_bar = false

-- ConPTY answers kitty keyboard queries itself and encodes Shift+Enter as a
-- bare Enter, so send the newline Ctrl+J would.
config.keys = {
	{ key = "Enter", mods = "SHIFT", action = wezterm.action.SendString("\n") },
}

return config
