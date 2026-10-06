-- Run as: nvim -u ~/.config/nvim/init.lua -l reconcile.lua <step> [mode]
-- `-l` exits 1 on a Lua error and terminates echoed output with a newline.
local step, mode = _G.arg[1], _G.arg[2]

local function plugins()
  local Config = require("lazy.core.config")
  local lazy = require("lazy")
  Config.options.headless = { process = false, log = false, task = false, colors = false }

  local cleaned = vim.tbl_map(function(plugin)
    return plugin.name
  end, mode == "sync" and Config.to_clean or {})
  if mode == "restore" then
    lazy.restore({ wait = true, show = false })
  elseif mode == "sync" then
    lazy.sync({ wait = true, show = false })
  else
    error("unknown plugins mode: " .. tostring(mode))
  end

  local failed = false
  local changes = 0
  local names = vim.tbl_keys(Config.plugins)
  table.sort(names)
  for _, name in ipairs(names) do
    local plugin = Config.plugins[name]
    local updated = plugin._.updated
    if plugin._.cloned then
      changes = changes + 1
      print(("lazy: installed %s"):format(name))
    elseif updated and updated.from ~= updated.to then
      changes = changes + 1
      print(("lazy: updated %s %s..%s"):format(name, updated.from:sub(1, 7), updated.to:sub(1, 7)))
    end
    for _, task in ipairs(plugin._.tasks or {}) do
      if task:has_errors() then
        failed = true
        print(("lazy: %s %s failed:\n%s"):format(name, task.name, task:output()))
      end
    end
  end
  for _, name in ipairs(cleaned) do
    changes = changes + 1
    print(("lazy: removed %s"):format(name))
  end
  if changes == 0 and not failed then
    print(("lazy: %d plugins unchanged"):format(#names))
  end
  if failed then
    os.exit(1)
  end
end

local function tools()
  vim.cmd("MasonToolsUpdateSync")
end

local function parsers()
  if not require("nvim-treesitter").update(nil, { summary = true }):wait(600000) then
    print("treesitter: parser update failed")
    os.exit(1)
  end
end

local steps = { plugins = plugins, tools = tools, parsers = parsers }
local run = steps[step]
if not run then
  error("unknown step: " .. tostring(step))
end
run()
