-- prefer the repo root over LSP workspace roots (e.g. vtsls rooting at a nested package.json)
vim.g.root_spec = { ".git", "lsp", "cwd" }

-- use basedpyright instead of pyright
vim.g.lazyvim_python_lsp = "basedpyright"

-- ignore LSPs that root to a single file's directory, hijacking Root Dir pickers
vim.g.root_lsp_ignore = { "copilot", "marksman" }

-- allow project-local .nvim.lua
vim.o.exrc = true

-- faster CursorHold for agent file-change detection
vim.o.updatetime = 250

-- sync yank with system clipboard
vim.o.clipboard = "unnamedplus"

vim.o.title = true
vim.o.showtabline = 0

local function update_title()
  local ok, result = pcall(vim.fn.system, { vim.fn.expand("~/.local/libexec/tab-title.py"), "--nvim", vim.fn.getcwd() })
  if ok and vim.v.shell_error == 0 then
    vim.o.titlestring = vim.trim(result)
  else
    vim.o.titlestring = "nvim:" .. vim.fn.fnamemodify(vim.fn.getcwd(), ":t")
  end
end

update_title()
vim.api.nvim_create_autocmd("DirChanged", { callback = update_title })

-- readable soft wrapping for long lines
vim.o.wrap = true
vim.o.linebreak = true
vim.o.breakindent = true

-- keep Neovim background aligned with the persisted terminal background
local terminal_bg_path = vim.fn.expand("~/.terminal-bg")
local function apply_terminal_bg()
  local terminal_bg_file = io.open(terminal_bg_path, "r")
  if not terminal_bg_file then
    return
  end
  local terminal_bg = vim.trim(terminal_bg_file:read("*l") or "")
  terminal_bg_file:close()
  if (terminal_bg == "light" or terminal_bg == "dark") and terminal_bg ~= vim.o.background then
    vim.o.background = terminal_bg
  end
end

apply_terminal_bg()

local terminal_bg_watcher = vim.uv.new_fs_event()
if terminal_bg_watcher then
  local function watch_terminal_bg()
    terminal_bg_watcher:start(terminal_bg_path, {}, function(err)
      if err then
        return
      end
      vim.schedule(function()
        apply_terminal_bg()
        terminal_bg_watcher:stop()
        watch_terminal_bg()
      end)
    end)
  end
  watch_terminal_bg()
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
