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
  {
    "HakonHarnes/img-clip.nvim",
    ft = { "markdown" },
    cmd = { "PasteImage", "ImgClipConfig", "ImgClipDebug" },
    keys = {
      {
        "<leader>mi",
        function() require("img-clip").paste_image() end,
        desc = "Paste Image",
        mode = { "n" },
      },
    },
    cond = function()
      return vim.fn.has("win32") == 1
        or vim.fn.executable("pngpaste") == 1
        or vim.fn.executable("wl-paste") == 1
        or vim.fn.executable("xclip") == 1
    end,
    opts = {
      default = {
        dir_path = "images",
        relative_to_current_file = true,
        use_absolute_path = false,
        embed_image_as_base64 = false,
        prompt_for_file_name = true,
        drag_and_drop = {
          insert_mode = true,
        },
      },
      filetypes = {
        markdown = {
          template = "![$CURSOR]($FILE_PATH)",
          download_images = false,
        },
      },
    },
  },
}
