-- See https://wiki.hypr.land/Configuring/Basics/Monitors/
-- List current monitors and supported resolutions with: hyprctl monitors all

local omarchy_gdk_scale = 2
local omarchy_monitor_scale = "auto"

hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })

hl.monitor({ output = "eDP-1", mode = "2880x1920@120", position = "auto", scale = 2 })

-- Configure a specific monitor.
-- hl.monitor({ output = "DP-2", mode = "2560x1440@144", position = "0x0", scale = 1 })

-- Portrait/rotated secondary monitor (transform: 1 = 90°, 3 = 270°).
-- hl.monitor({ output = "DP-2", mode = "preferred", position = "auto", scale = 1, transform = 1 })

-- AW3423DW: DisplayPort from the eGPU carries 175 Hz, while the hub/HDMI path tops out at 100 Hz.
-- uwsm/egpu sets AQ_DRM_DEVICES only when the eGPU is attached at login.
if os.getenv("AQ_DRM_DEVICES") then
  hl.monitor({ output = "desc:Dell Inc. Dell AW3423DW", mode = "3440x1440@175", position = "auto", scale = 1 })
else
  hl.monitor({ output = "desc:Dell Inc. Dell AW3423DW", mode = "3440x1440@100", position = "auto", scale = 1 })
end
