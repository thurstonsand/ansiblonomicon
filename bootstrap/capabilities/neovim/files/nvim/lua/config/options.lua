require("config.remote_clipboard").setup()

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
