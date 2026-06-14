vim.keymap.set("n", "<leader>dc", function()
  local diagnostics = vim.diagnostic.get(0, { lnum = vim.fn.line(".") - 1 })
  if #diagnostics == 0 then
    vim.notify("No diagnostics on current line", vim.log.levels.WARN)
    return
  end
  local messages = vim.tbl_map(function(d)
    return d.message
  end, diagnostics)
  vim.fn.setreg("+", table.concat(messages, "\n"))
  vim.notify("Copied " .. #diagnostics .. " diagnostic(s)", vim.log.levels.INFO)
end, { desc = "Copy Diagnostics to Clipboard" })

vim.keymap.set("n", "gb", "<Cmd>bnext<CR>", { desc = "Next Buffer" })
vim.keymap.set("n", "gB", "<Cmd>bprevious<CR>", { desc = "Prev Buffer" })

pcall(vim.keymap.del, "n", "<leader>ub")
Snacks.toggle.option("background", { off = "light", on = "dark", name = "Dark Background" }):map("<leader>uB")
vim.keymap.set("n", "<leader>ub", function()
  require("lazy").load({ plugins = { "gitsigns.nvim" } })
  local enabled = require("gitsigns").toggle_current_line_blame()
  require("gitsigns.current_line_blame").refresh()
  vim.notify("Inline blame " .. (enabled and "enabled" or "disabled"), vim.log.levels.INFO)
end, { desc = "Toggle Inline Blame" })

pcall(function()
  require("which-key").add({ { "<leader>ub", desc = "Toggle Inline Blame", icon = "󰊢" } })
end)
