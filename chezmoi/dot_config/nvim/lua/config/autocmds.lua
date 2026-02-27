-- auto-save when focus is lost or cursor is idle
vim.api.nvim_create_autocmd({ "FocusLost", "CursorHold", "CursorHoldI" }, {
  group = vim.api.nvim_create_augroup("auto_save", { clear = true }),
  callback = function()
    if vim.bo.modified and vim.bo.buftype == "" and vim.fn.expand("%") ~= "" then
      vim.cmd("silent! write")
    end
  end,
})

-- check for external file changes on CursorHold (supplements LazyVim's
-- FocusGained/BufEnter checktime). Catches changes made by AI agents
-- while the cursor is idle inside nvim.
vim.api.nvim_create_autocmd({ "CursorHold", "CursorHoldI" }, {
  group = vim.api.nvim_create_augroup("agent_checktime", { clear = true }),
  command = "checktime",
})

-- LazyVim's lazyvim_wrap_spell enables spell+wrap for text filetypes; keep wrap, disable spell
vim.api.nvim_create_augroup("lazyvim_wrap_spell", { clear = true })
vim.api.nvim_create_autocmd("FileType", {
  group = vim.api.nvim_create_augroup("wrap_nospell", { clear = true }),
  pattern = { "text", "plaintex", "typst", "gitcommit", "markdown" },
  callback = function()
    vim.opt_local.wrap = true
    vim.opt_local.spell = false
  end,
})

-- watch ~/.terminal-bg for light/dark changes (written by shell's _detect_terminal_bg)
if vim.env.SSH_TTY or vim.env.SSH_CONNECTION then
  local bg_file = vim.fn.expand("~/.terminal-bg")

  local function apply_terminal_bg()
    local f = io.open(bg_file, "r")
    if not f then
      return
    end
    local bg = vim.trim(f:read("*l") or "")
    f:close()
    if (bg == "light" or bg == "dark") and bg ~= vim.o.background then
      vim.o.background = bg
    end
  end

  apply_terminal_bg()

  local bg_watcher = vim.uv.new_fs_event()
  if bg_watcher then
    local function watch_bg()
      bg_watcher:start(bg_file, {}, function(err)
        if err then
          return
        end
        vim.schedule(apply_terminal_bg)
        bg_watcher:stop()
        watch_bg()
      end)
    end
    watch_bg()
  end
end
