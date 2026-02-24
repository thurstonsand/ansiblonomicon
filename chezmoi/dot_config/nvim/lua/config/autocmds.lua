-- check for external file changes on CursorHold (supplements LazyVim's
-- FocusGained/BufEnter checktime). Catches changes made by AI agents
-- while the cursor is idle inside nvim.
vim.api.nvim_create_autocmd({ "CursorHold", "CursorHoldI" }, {
  group = vim.api.nvim_create_augroup("agent_checktime", { clear = true }),
  command = "checktime",
})
