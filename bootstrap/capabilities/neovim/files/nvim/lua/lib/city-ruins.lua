-- City Ruins and Copied City: ashen.nvim as Omarchy pairs it with Solitude in dark, its OKLCH
-- mirror in light, and City Ruins' diff colors over both.
local M = {}

local light_palette = require("lib.ashen-copied-city")
local signals = require("lib.city-ruins-signals")
local names = { dark = "city-ruins", light = "copied-city" }
local dark_palette
local group = vim.api.nvim_create_augroup("city-ruins", { clear = true })

function M.apply(mode)
  vim.api.nvim_clear_autocmds({ group = group })
  -- ashen overrides its palette in place, so keep the defaults to restore dark.
  dark_palette = dark_palette or vim.deepcopy(require("ashen.colors"))
  require("ashen").setup({ colors = mode == "light" and light_palette or dark_palette })
  -- ashen hardcodes `set background=dark` on every load, which would undo light mode
  -- and leave the groups it does not define with dark defaults. Skip only that command.
  local nvim_command = vim.api.nvim_command
  vim.api.nvim_command = function(command)
    if command ~= "set background=dark" then
      nvim_command(command)
    end
  end
  local ok, err = pcall(function()
    vim.o.background = mode
    -- Not `:colorscheme ashen`: this runs inside the City Ruins colorschemes, and Neovim
    -- silently ignores a colorscheme loaded from another.
    require("ashen").load()
  end)
  vim.api.nvim_command = nvim_command
  assert(ok, err)
  for name, spec in pairs(signals[mode]) do
    vim.api.nvim_set_hl(0, name, spec)
  end
  -- ashen records itself; reloading that name would run the dark restore below.
  vim.g.colors_name = names[mode]

  if mode == "light" then
    -- ashen keeps the override for every later load, so a plain `:colorscheme ashen`,
    -- such as Omarchy switching to its own Solitude, would otherwise stay light.
    vim.api.nvim_create_autocmd("ColorSchemePre", {
      group = group,
      pattern = "ashen",
      once = true,
      callback = function()
        require("ashen").setup({ colors = dark_palette })
      end,
    })
  end
end

return M
