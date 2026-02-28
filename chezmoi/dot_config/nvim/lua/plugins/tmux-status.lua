local function set_tmux_status(value)
  if not vim.env.TMUX then return end
  vim.fn.system({ "tmux", "set-option", "-g", "status", value })
end

local function tmux_session()
  local lines = vim.fn.systemlist({ "tmux", "display-message", "-p", "#S" })
  if vim.v.shell_error ~= 0 or #lines == 0 then
    return vim.fn.fnamemodify(vim.fn.getcwd(), ":t")
  end
  return lines[1]:match("^ide%-(.+)%-%x+$") or lines[1]
end

return {
  {
    "nvim-lualine/lualine.nvim",
    opts = function(_, opts)
      if not vim.env.TMUX then return end

      set_tmux_status("off")

      local group = vim.api.nvim_create_augroup("tmux_lualine", { clear = true })
      vim.api.nvim_create_autocmd("VimEnter", { group = group, callback = function() set_tmux_status("off") end })
      vim.api.nvim_create_autocmd("VimLeavePre", { group = group, callback = function() set_tmux_status("on") end })
      vim.api.nvim_create_autocmd("FocusGained", {
        group = group,
        callback = function() require("lualine").refresh() end,
      })

      local orig_a = vim.deepcopy(opts.sections.lualine_a or {})
      local orig_b = vim.deepcopy(opts.sections.lualine_b or {})

      opts.sections.lualine_a = { tmux_session }
      opts.sections.lualine_b = { require("lib.tmux-windows") }

      for i = #orig_b, 1, -1 do table.insert(opts.sections.lualine_c, 1, orig_b[i]) end
      for i = #orig_a, 1, -1 do table.insert(opts.sections.lualine_c, 1, orig_a[i]) end

      opts.sections.lualine_z = {
        function() return vim.fn.hostname():match("^([^.]+)") or vim.fn.hostname() end,
      }
    end,
  },
}
