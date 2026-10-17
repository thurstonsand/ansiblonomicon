-- See https://wiki.hypr.land/Configuring/Basics/Monitors/
-- List current monitors and supported resolutions with: hyprctl monitors all

local omarchy_gdk_scale = 1
local omarchy_monitor_scale = 1.6

hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })

-- Sonnet eGPU: native ultrawide resolution, 144 Hz with 10-bit color, 125% scale.
hl.monitor({ output = "DP-6", mode = "3440x1440@143.97", position = "0x0", scale = 1.25, vrr = 2, bitdepth = 10 })

-- Hyprland's auto setting draws the cursor in software whenever it renders on NVIDIA, which made it lag on the eGPU.
hl.config({ cursor = { no_hardware_cursors = 0 } })

-- The ultrawide is also cabled through the dock as DP-1; while the eGPU drives it, that input would be an invisible extra screen.
local function set_dock_output(disabled)
  hl.monitor({ output = "DP-1", mode = "preferred", position = "auto", scale = omarchy_monitor_scale, disabled = disabled })
end

set_dock_output(hl.get_monitor("DP-6") ~= nil)

hl.on("monitor.added", function(monitor)
  if monitor.name == "DP-6" then
    set_dock_output(true)
  end
end)

hl.on("monitor.removed", function(monitor)
  if monitor.name == "DP-6" then
    set_dock_output(false)
  end
end)

-- Configure a specific monitor.
-- hl.monitor({ output = "DP-2", mode = "2560x1440@144", position = "0x0", scale = 1 })

-- Portrait/rotated secondary monitor (transform: 1 = 90°, 3 = 270°).
-- hl.monitor({ output = "DP-2", mode = "preferred", position = "auto", scale = 1, transform = 1 })
