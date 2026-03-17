local M = {}

local setup_done = false
local key_table_active = false

local FloatWinBehavior = {
  previous = "previous",
  mux = "mux",
}

local float_win_behavior = FloatWinBehavior.previous

local function in_ghostty()
  return vim.env.TERM_PROGRAM == "ghostty"
end

local function helper_path()
  return vim.fn.expand("~/.local/bin/ghostty-nav")
end

local function helper_available()
  return in_ghostty() and vim.fn.executable(helper_path()) == 1
end

local function tty_key()
  local tty = vim.env.TTY
  if not tty or tty == "" then
    return nil
  end
  return tty:gsub("/", "_")
end

local function sentinel_path()
  local key = tty_key()
  if not key then
    return nil
  end

  local state_home = vim.env.XDG_STATE_HOME or (vim.env.HOME .. "/.local/state")
  return state_home .. "/ghostty-nav/" .. key .. ".active"
end

local function touch_sentinel()
  local path = sentinel_path()
  if not path then
    return
  end

  vim.fn.mkdir(vim.fn.fnamemodify(path, ":h"), "p")
  local file = io.open(path, "w")
  if file then
    file:close()
  end
end

local function clear_sentinel()
  local path = sentinel_path()
  if path then
    vim.fn.delete(path)
  end
end

local function run(args)
  if not helper_available() then
    return false
  end

  local argv = vim.list_extend({ helper_path() }, args)
  local result = vim.system(argv, { text = true }):wait()
  if result.code ~= 0 then
    local stderr = vim.trim(result.stderr or "")
    if stderr ~= "" then
      vim.notify(stderr, vim.log.levels.WARN, { title = "ghostty-nav" })
    end
    return false
  end

  return true
end

local function activate_key_table()
  if key_table_active then
    return
  end

  if run({ "activate", "nvim" }) then
    touch_sentinel()
    key_table_active = true
  end
end

local function deactivate_key_table()
  if key_table_active then
    run({ "deactivate" })
  end
  clear_sentinel()
  key_table_active = false
end

local function is_floating_window(win)
  local cfg = vim.api.nvim_win_get_config(win or 0)
  return cfg and cfg.relative ~= ""
end

local function is_embedded_floating_window(win)
  if not is_floating_window(win) then
    return false
  end

  local cfg = vim.api.nvim_win_get_config(win or 0)
  return cfg.zindex ~= nil and cfg.zindex < 50
end

local function is_floating_window_at_screen_edge(win, dir)
  win = win or vim.api.nvim_get_current_win()
  if not is_floating_window(win) then
    return false
  end

  local cfg = vim.api.nvim_win_get_config(win)
  local col = type(cfg.col) == "number" and cfg.col or 0
  local row = type(cfg.row) == "number" and cfg.row or 0

  if dir == "left" then
    return col <= 0
  elseif dir == "right" then
    return col + cfg.width >= vim.o.columns
  elseif dir == "up" then
    return row <= 0
  elseif dir == "down" then
    return row + cfg.height >= vim.o.lines - vim.o.cmdheight
  end

  return false
end

local function handle_floating_window(mux_callback)
  if not is_floating_window() then
    return false
  end

  if float_win_behavior == FloatWinBehavior.previous then
    local prev_win = vim.fn.win_getid(vim.fn.winnr("#"))
    if prev_win == 0 or not vim.api.nvim_win_is_valid(prev_win) or is_floating_window(prev_win) then
      return true
    end
    vim.api.nvim_set_current_win(prev_win)
    return false
  elseif float_win_behavior == FloatWinBehavior.mux then
    if mux_callback then
      mux_callback()
    end
    return true
  end

  return false
end

function M.navigate(wincmd, dir)
  if is_embedded_floating_window() then
    if is_floating_window_at_screen_edge(nil, dir) then
      run({ "move", dir })
      return
    end

    vim.cmd("wincmd " .. wincmd)
    return
  end

  if handle_floating_window(function()
    run({ "move", dir })
  end) then
    return
  end

  local current_winnr = vim.fn.winnr()
  local target_winnr = vim.fn.winnr(wincmd)

  if target_winnr == current_winnr then
    run({ "move", dir })
    return
  end

  local target_win = vim.fn.win_getid(target_winnr)
  if target_win ~= 0 and vim.api.nvim_win_is_valid(target_win) then
    vim.api.nvim_set_current_win(target_win)
    return
  end

  run({ "move", dir })
end

function M.setup()
  if setup_done then
    return
  end
  setup_done = true

  if not in_ghostty() then
    return
  end

  local group = vim.api.nvim_create_augroup("ghostty_nav", { clear = true })

  vim.api.nvim_create_autocmd("VimEnter", {
    group = group,
    callback = activate_key_table,
  })

  vim.api.nvim_create_autocmd("VimResume", {
    group = group,
    callback = activate_key_table,
  })

  vim.api.nvim_create_autocmd({ "VimSuspend", "VimLeavePre" }, {
    group = group,
    callback = deactivate_key_table,
  })
end

return M
