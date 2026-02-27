-- use basedpyright instead of pyright
vim.g.lazyvim_python_lsp = "basedpyright"

-- faster CursorHold for agent file-change detection
vim.o.updatetime = 250

-- sync yank with system clipboard
vim.o.clipboard = "unnamedplus"

-- honor pre-detected terminal background
local terminal_bg = os.getenv("TERMINAL_BG")
if terminal_bg == "light" or terminal_bg == "dark" then
  vim.o.background = terminal_bg
end

-- OSC 52 clipboard for remote/SSH sessions
if os.getenv("SSH_TTY") or os.getenv("SSH_CONNECTION") then
  vim.g.clipboard = {
    name = "OSC 52",
    copy = {
      ["+"] = require("vim.ui.clipboard.osc52").copy("+"),
      ["*"] = require("vim.ui.clipboard.osc52").copy("*"),
    },
    paste = {
      ["+"] = require("vim.ui.clipboard.osc52").paste("+"),
      ["*"] = require("vim.ui.clipboard.osc52").paste("*"),
    },
  }
end
