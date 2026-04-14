-- prevent LSP from attaching to non-file buffers (e.g. diffview://)
vim.api.nvim_create_autocmd("LspAttach", {
  group = vim.api.nvim_create_augroup("detach_lsp_from_non_file", { clear = true }),
  callback = function(args)
    local uri = vim.uri_from_bufnr(args.buf)
    if uri and not vim.startswith(uri, "file://") then
      vim.schedule(function()
        vim.lsp.buf_detach_client(args.buf, args.data.client_id)
      end)
    end
  end,
})

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

-- theme sync: watch ~/.terminal-bg for changes (written by tmux hooks or bgdark/bglight)
local bg_file = vim.fn.expand("~/.terminal-bg")
local bg_watcher = vim.uv.new_fs_event()
if bg_watcher then
  local function watch_bg()
    bg_watcher:start(bg_file, {}, function(err)
      if err then
        return
      end
      vim.schedule(function()
        local f = io.open(bg_file, "r")
        if not f then
          return
        end
        local bg = vim.trim(f:read("*l") or "")
        f:close()
        if (bg == "light" or bg == "dark") and bg ~= vim.o.background then
          vim.o.background = bg
        end
      end)
      bg_watcher:stop()
      watch_bg()
    end)
  end
  watch_bg()
end
