return {
  {
    "neovim/nvim-lspconfig",
    opts = function(_, opts)
      local marksman = opts.servers and opts.servers.marksman
      if not marksman or marksman.enabled == false then
        return
      end

      marksman.root_dir = function(bufnr, on_dir)
        local name = vim.api.nvim_buf_get_name(bufnr)

        -- Marksman crashes on Diffview's Git object paths, so only attach to real files.
        if name == "" or not vim.uv.fs_stat(name) then
          return
        end

        local root_markers = vim.lsp.config.marksman.root_markers or { ".marksman.toml", ".git" }
        on_dir(vim.fs.root(name, root_markers) or vim.fs.dirname(name))
      end
    end,
  },
}
