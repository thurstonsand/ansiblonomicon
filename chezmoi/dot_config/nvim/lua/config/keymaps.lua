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
