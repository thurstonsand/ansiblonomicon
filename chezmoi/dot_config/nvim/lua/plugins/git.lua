local hunk_command = { "hunk", "diff" }

local function hunk_editor_env()
  local server = vim.v.servername
  if server == "" then
    server = vim.fn.serverstart()
  end

  return {
    -- hunk's `git diff` omits --no-optional-locks; without this, background
    -- sessions grab index.lock mid-commit and kill the commit hook's stash dance
    GIT_OPTIONAL_LOCKS = "0",
    EDITOR = vim.fn.expand("~/.local/libexec/hunk/nvim"),
    NVIM_OUTER_SERVER = server,
    NVIM_REAL_BIN = vim.v.progpath,
  }
end

local function hunk_terminal_opts(root)
  return {
    count = 1,
    cwd = root,
    env = hunk_editor_env(),
    win = {
      position = "float",
      width = 0.98,
      height = 0.98,
      wo = { winblend = 5 },
      keys = {
        hunk_hide = {
          "<c-q>",
          function(win)
            win:hide()
          end,
          mode = { "n", "t" },
          desc = "Hide Hunk",
        },
      },
    },
  }
end

local function open_hunk_diff()
  if vim.fn.executable("hunk") ~= 1 then
    vim.notify("hunk executable not found", vim.log.levels.ERROR)
    return
  end

  local root = LazyVim.root.git()
  Snacks.terminal.focus(hunk_command, hunk_terminal_opts(root))
end

return {
  -- inline blame toggle (persistent GitLens-style virtual text)
  {
    "lewis6991/gitsigns.nvim",
    opts = function(_, opts)
      local on_attach = opts.on_attach

      opts.current_line_blame = false
      opts.current_line_blame_opts = { delay = 0, virt_text_pos = "right_align" }
      opts.on_attach = function(buffer)
        if on_attach then
          on_attach(buffer)
        end

        pcall(vim.keymap.del, "n", "<leader>ghd", { buffer = buffer })
        pcall(vim.keymap.del, "n", "<leader>ghD", { buffer = buffer })
      end
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
        { "<leader>gV", open_hunk_diff, desc = "Hunk Diff" },
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
}
