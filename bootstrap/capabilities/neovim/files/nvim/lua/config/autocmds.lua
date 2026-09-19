rawset(_G, "HunkOpenInNvim", function(file, line)
  line = math.max(1, tonumber(line) or 1)

  if vim.bo.buftype == "terminal" then
    pcall(function()
      vim.cmd("silent! hide")
    end)
  end

  local edit_win = vim.api.nvim_get_current_win()
  local explorer = _G.Snacks and Snacks.picker and Snacks.picker.get({ source = "explorer" })[1]
  if
    explorer
    and vim.api.nvim_win_is_valid(explorer.main)
    and vim.api.nvim_win_get_config(explorer.main).relative == ""
  then
    edit_win = explorer.main
  end

  if explorer and _G.Snacks and Snacks.explorer then
    pcall(function()
      Snacks.explorer.reveal({ file = file })
    end)
  end

  if vim.api.nvim_win_is_valid(edit_win) then
    vim.api.nvim_set_current_win(edit_win)
  end

  local buffer = vim.fn.bufadd(file)
  vim.bo[buffer].buflisted = true
  vim.cmd("buffer " .. buffer)
  vim.api.nvim_win_set_cursor(0, { line, 0 })
  vim.cmd("normal! zvzz")

  return ""
end)

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

vim.api.nvim_create_autocmd("FileType", {
  group = vim.api.nvim_create_augroup("help_format", { clear = true }),
  pattern = "help",
  callback = function()
    vim.opt_local.formatexpr = ""
    vim.opt_local.textwidth = 78
  end,
})
