local function sync_tmux_theme(mode)
  local tmux_env = vim.env.TMUX
  if not tmux_env or tmux_env == "" then
    return
  end

  local bg_file = vim.fn.expand("~/.terminal-bg")
  local f = io.open(bg_file, "w")
  if f then
    f:write(mode)
    f:close()
  end

  vim.fn.system({ "tmux", "set-environment", "-g", "TERMINAL_BG", mode })
  vim.system({ "zsh", "-lc", "source ~/.config/zsh/tmux-theme.zsh 2>/dev/null || :; _apply_tmux_gruvbox " .. mode }, {}, function() end)
end

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
  {
    "f-person/auto-dark-mode.nvim",
    lazy = false,
    cond = function()
      return not (vim.env.SSH_TTY or vim.env.SSH_CONNECTION)
    end,
    opts = {
      update_interval = 1000,
      set_dark_mode = function()
        vim.o.background = "dark"
        sync_tmux_theme("dark")
      end,
      set_light_mode = function()
        vim.o.background = "light"
        sync_tmux_theme("light")
      end,
    },
  },
}
