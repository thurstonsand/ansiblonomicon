local lualine_require = require("lualine_require")
local M = lualine_require.require("lualine.component"):extend()

local function active_color()
  local dark = vim.o.background ~= "light"
  return { fg = dark and "#fabd2f" or "#b57614" }
end

local function inactive_color()
  return { fg = "#928374" }
end

function M:init(options)
  M.super.init(self, options)
  self.hl_active = self:create_hl(active_color, "active")
  self.hl_inactive = self:create_hl(inactive_color, "inactive")
end

function M:update_status()
  local lines = vim.fn.systemlist({ "tmux", "list-windows", "-F", "#{window_active}\t#{window_name}" })
  if vim.v.shell_error ~= 0 then return "" end

  local parts = {}
  for _, line in ipairs(lines) do
    local active, name = line:match("^(%d)\t(.+)$")
    if name then
      local hl = self:format_hl(active == "1" and self.hl_active or self.hl_inactive)
      parts[#parts + 1] = hl .. name
    end
  end

  if #parts == 0 then return "" end
  return table.concat(parts, "  ") .. self:get_default_hl()
end

return M
