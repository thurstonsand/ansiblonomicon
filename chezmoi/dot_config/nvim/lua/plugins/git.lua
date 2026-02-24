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
    keys = {
      { "<leader>gv", "<cmd>DiffviewOpen<cr>", desc = "Diff View (All Changes)" },
      { "<leader>gV", "<cmd>DiffviewClose<cr>", desc = "Close Diff View" },
      { "<leader>gH", "<cmd>DiffviewFileHistory %<cr>", desc = "File History (Current)" },
    },
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
            { "n", "u", function() Snacks.notifier.show_history() end, { desc = "Notification history (undo info)" } },
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
