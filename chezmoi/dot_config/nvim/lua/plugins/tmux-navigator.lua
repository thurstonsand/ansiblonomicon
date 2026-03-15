local function navigate(dir, key)
  local cur_win = vim.api.nvim_get_current_win()
  vim.cmd("wincmd " .. key)
  if vim.api.nvim_get_current_win() == cur_win then
    vim.fn.jobstart({ vim.fn.expand("~/.local/bin/ghostty-nav"), "--ghostty-only", dir })
  end
end

return {
  -- disable vim-tmux-navigator (no longer needed)
  { "christoomey/vim-tmux-navigator", enabled = false },
  -- ghostty split navigation with edge fallback
  {
    dir = ".",
    name = "ghostty-navigator",
    keys = {
      { "<C-h>", function() navigate("left", "h") end, desc = "Navigate Left" },
      { "<C-j>", function() navigate("down", "j") end, desc = "Navigate Down" },
      { "<C-k>", function() navigate("up", "k") end, desc = "Navigate Up" },
      { "<C-l>", function() navigate("right", "l") end, desc = "Navigate Right" },
    },
  },
}
