local function set_tmux_status(value)
  if not vim.env.TMUX then
    return
  end
  vim.fn.system({ "tmux", "set-option", "-g", "status", value })
end

local function gruvbox_colors()
  local dark = vim.o.background ~= "light"
  -- bg matches lualine section b (gruvbox bg2)
  local bg = dark and "#504945" or "#d5c4a1"
  return {
    window_active          = { fg = dark and "#fabd2f" or "#b57614", bg = bg },
    window_inactive        = { fg = "#928374", bg = bg },
    window_inactive_recent = { fg = dark and "#665c54" or "#bdae93", bg = bg },
    session                = { fg = dark and "#b8bb26" or "#79740e", bg = bg },
    datetime               = { fg = "#928374", bg = bg },
    battery                = { fg = "#928374", bg = bg },
  }
end

local function apply_gruvbox_highlights()
  for name, val in pairs(gruvbox_colors()) do
    vim.api.nvim_set_hl(0, "tmux_status_" .. name, { fg = val.fg, bg = val.bg })
  end
end

local function tmux_session_sync()
  local lines = vim.fn.systemlist({ "tmux", "display-message", "-p", "#S" })
  if vim.v.shell_error ~= 0 or #lines == 0 then
    return vim.fn.fnamemodify(vim.fn.getcwd(), ":t")
  end
  local session = lines[1]
  local simplified = session:match("^ide%-(.+)%-%x+$")
  return simplified or session
end

return {
  {
    "christopher-francisco/tmux-status.nvim",
    lazy = true,
    config = function()
      require("tmux-status").setup({
        window = { text = "name" },
        colors = gruvbox_colors(),
        manage_tmux_status = false,
      })

      apply_gruvbox_highlights()
      set_tmux_status("off")

      vim.api.nvim_create_autocmd("VimEnter", {
        group = vim.api.nvim_create_augroup("tmux_status_initial_sync", { clear = true }),
        callback = function()
          set_tmux_status("off")
        end,
      })

      vim.api.nvim_create_autocmd("VimLeavePre", {
        group = vim.api.nvim_create_augroup("tmux_status_leave_sync", { clear = true }),
        callback = function()
          set_tmux_status("on")
        end,
      })

      vim.api.nvim_create_autocmd("ColorScheme", {
        group = vim.api.nvim_create_augroup("tmux_status_gruvbox", { clear = true }),
        callback = apply_gruvbox_highlights,
      })
    end,
  },

  {
    "nvim-lualine/lualine.nvim",
    opts = function(_, opts)
      -- Only restructure lualine when inside tmux; outside tmux, LazyVim defaults are unchanged
      if not vim.env.TMUX then
        return
      end

      local ts = require("tmux-status")

      -- Save original a/b content (mode, branch, etc.) to relocate into c
      local orig_a = vim.deepcopy(opts.sections.lualine_a or {})
      local orig_b = vim.deepcopy(opts.sections.lualine_b or {})

      -- Left: tmux at the edges (a, b), nvim toward center (c)
      opts.sections.lualine_a = {
        {
          tmux_session_sync,
          cond = function()
            return true
          end,
        },
      }

      opts.sections.lualine_b = {
        {
          ts.tmux_windows,
          cond = function()
            return true
          end,
        },
      }

      -- Prepend original mode + branch into section c (nvim content together)
      for i = #orig_b, 1, -1 do
        table.insert(opts.sections.lualine_c, 1, orig_b[i])
      end
      for i = #orig_a, 1, -1 do
        table.insert(opts.sections.lualine_c, 1, orig_a[i])
      end

      -- Right: replace LazyVim's clock with hostname (tmux at far right)
      opts.sections.lualine_z = {
        {
          function()
            return (vim.fn.hostname():match("^([^.]+)") or vim.fn.hostname())
          end,
          cond = function()
            return true
          end,
        },
      }
    end,
  },
}
