return {
  -- inline blame toggle (persistent GitLens-style virtual text)
  {
    "lewis6991/gitsigns.nvim",
    opts = {
      current_line_blame = false,
      current_line_blame_opts = { delay = 300 },
    },
    keys = {
      {
        "<leader>ub",
        function()
          require("gitsigns").toggle_current_line_blame()
        end,
        desc = "Toggle Inline Blame",
      },
    },
    -- disable <leader>ghd / ghD — diffview covers this use case
    init = function()
      vim.api.nvim_create_autocmd("User", {
        pattern = "VeryLazy",
        once = true,
        callback = function()
          pcall(vim.keymap.del, "n", "<leader>ghd")
          pcall(vim.keymap.del, "n", "<leader>ghD")
        end,
      })
    end,
  },

  -- side-by-side diff viewer (VSCode-style)
  {
    "sindrets/diffview.nvim",
    cmd = { "DiffviewOpen", "DiffviewClose", "DiffviewFileHistory" },
    keys = function()
      local function focus_or_open_diffview()
        local api = vim.api
        local lib = require("diffview.lib")
        local DiffView = require("diffview.scene.views.diff.diff_view").DiffView

        lib.dispose_stray_views()

        local current_tab = api.nvim_get_current_tabpage()
        local previous_tabnr = vim.fn.tabpagenr("#")
        local fallback_tab

        for _, view in ipairs(lib.views) do
          if api.nvim_tabpage_is_valid(view.tabpage) and view:instanceof(DiffView) then
            if view.tabpage == current_tab then
              return
            end

            if previous_tabnr > 0 and api.nvim_tabpage_get_number(view.tabpage) == previous_tabnr then
              api.nvim_set_current_tabpage(view.tabpage)
              return
            end

            fallback_tab = fallback_tab or view.tabpage
          end
        end

        if fallback_tab then
          api.nvim_set_current_tabpage(fallback_tab)
          return
        end

        vim.cmd("DiffviewOpen")
      end

      return {
        { "<leader>gv", focus_or_open_diffview, desc = "Diff View (Open or Focus)" },
        { "<leader>gV", "<cmd>DiffviewClose<cr>", desc = "Close Diff View" },
        { "<leader>gH", "<cmd>DiffviewFileHistory %<cr>", desc = "File History (Current)" },
      }
    end,
    opts = function()
      local actions = require("diffview.actions")
      return {
        enhanced_diff_hl = true,
        view = {
          default = { layout = "diff2_horizontal" },
          merge_tool = { layout = "diff3_mixed" },
        },
        hooks = {
          diff_buf_read = function()
            vim.wo.wrap = true
          end,
        },
        default_args = {
          DiffviewOpen = { "--imply-local" },
        },
        file_panel = {
          listing_style = "tree",
          win_config = { width = 35 },
        },
        keymaps = {
          view = {
            { "n", "q", "<cmd>DiffviewClose<cr>", { desc = "Close Diff View" } },
            { "n", "<leader>e", actions.focus_files, { desc = "Focus file panel" } },
          },
          file_panel = {
            { "n", "q", "<cmd>DiffviewClose<cr>", { desc = "Close Diff View" } },
            { "n", "x", actions.restore_entry, { desc = "Restore entry (discard changes)" } },
            {
              "n",
              "u",
              function()
                Snacks.notifier.show_history()
              end,
              { desc = "Notification history (undo info)" },
            },
          },
          file_history_panel = {
            { "n", "q", "<cmd>DiffviewClose<cr>", { desc = "Close Diff View" } },
          },
        },
      }
    end,
  },

  -- native nvim git status (Magit-style)
  {
    "NeogitOrg/neogit",
    dependencies = {
      "nvim-lua/plenary.nvim",
      "sindrets/diffview.nvim",
    },
    cmd = "Neogit",
    keys = {
      { "<leader>gn", "<cmd>Neogit<cr>", desc = "Neogit Status" },
    },
    opts = {
      integrations = { diffview = true },
      signs = {
        section = { "", "" },
        item = { "", "" },
      },
    },
  },
}
