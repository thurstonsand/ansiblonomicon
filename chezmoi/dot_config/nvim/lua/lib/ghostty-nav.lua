local M = {}

local setup_done = false
local cached_tty = nil

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

local function tui_pid()
  for _, ui in ipairs(vim.api.nvim_list_uis()) do
    local ok, info = pcall(vim.api.nvim_get_chan_info, ui.chan)
    local client = ok and info.client or nil
    local attrs = client and client.attributes or nil
    local pid = attrs and tonumber(attrs.pid) or nil
    if client and client.name == "nvim-tui" and pid then
      return pid
    end
  end
  return nil
end

local function tty_for_pid(pid)
  local result = vim
    .system({
      "ps",
      "-p",
      tostring(pid),
      "-o",
      "tty=",
    }, { text = true })
    :wait()

  if result.code ~= 0 then
    return nil
  end

  local tty = vim.trim(result.stdout or "")
  if tty == "" or tty == "?" or tty == "??" then
    return nil
  end

  if not tty:match("^/") then
    tty = "/dev/" .. tty
  end

  return tty
end

local function current_tty()
  if cached_tty then
    return cached_tty
  end

  local pid = tui_pid()
  if not pid then
    return nil
  end

  local tty = tty_for_pid(pid)
  if not tty then
    return nil
  end

  cached_tty = tty
  return cached_tty
end

local function run(args)
  if not helper_available() then
    return false
  end

  local argv = { helper_path() }
  local tty = current_tty()
  if tty then
    vim.list_extend(argv, { "--tty", tty })
  end
  vim.list_extend(argv, args)

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
  run({ "activate", "nvim" })
end

local function deactivate_key_table()
  run({ "deactivate" })
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

  vim.api.nvim_create_autocmd({ "VimEnter", "VimResume", "FocusGained" }, {
    group = group,
    callback = activate_key_table,
  })

  vim.api.nvim_create_autocmd({ "VimSuspend", "VimLeavePre" }, {
    group = group,
    callback = deactivate_key_table,
  })
end

return M
