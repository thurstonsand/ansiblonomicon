vim.keymap.set("n", "<leader>dc", function()
  local diagnostics = vim.diagnostic.get(0, { lnum = vim.fn.line(".") - 1 })
  if #diagnostics == 0 then
    vim.notify("No diagnostics on current line", vim.log.levels.WARN)
    return
  end
  local messages = vim.tbl_map(function(d) return d.message end, diagnostics)
  vim.fn.setreg("+", table.concat(messages, "\n"))
  vim.notify("Copied " .. #diagnostics .. " diagnostic(s)", vim.log.levels.INFO)
end, { desc = "Copy Diagnostics to Clipboard" })

-- remap background toggle from <leader>ub to <leader>uB so blame can use <leader>ub
-- runs after VeryLazy to ensure Snacks keymaps are already registered
vim.api.nvim_create_autocmd("User", {
  pattern = "VeryLazy",
  once = true,
  callback = function()
    pcall(vim.keymap.del, "n", "<leader>ub")
    Snacks.toggle
      .option("background", { off = "light", on = "dark", name = "Dark Background" })
      :map("<leader>uB")
  end,
})
