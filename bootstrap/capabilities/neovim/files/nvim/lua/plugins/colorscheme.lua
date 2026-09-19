local function apply_highlights()
  vim.api.nvim_set_hl(0, "GitSignsCurrentLineBlame", {
    link = "Comment",
  })
end

vim.api.nvim_create_autocmd("ColorScheme", {
  group = vim.api.nvim_create_augroup("custom_highlights", { clear = true }),
  callback = apply_highlights,
})

apply_highlights()

return {
  {
    "ellisonleao/gruvbox.nvim",
    lazy = false,
    priority = 1000,
    opts = {
      contrast = "hard",
    },
  },
  {
    "LazyVim/LazyVim",
    opts = {
      colorscheme = "gruvbox",
    },
  },
}
