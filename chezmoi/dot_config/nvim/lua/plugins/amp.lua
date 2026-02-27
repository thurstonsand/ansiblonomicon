local function focus_agent_window()
  if not vim.env.TMUX then
    return
  end

  local cwd = vim.fn.getcwd()
  local hash = vim.fn.system("printf '%s' " .. vim.fn.shellescape(cwd) .. " | shasum | cut -c1-8"):gsub("%s+$", "")

  local windows = vim.fn.system("tmux list-windows -F '#{window_index} #{@cwd_hash}'"):gsub("%s+$", "")
  for line in windows:gmatch("[^\n]+") do
    local idx, wh = line:match("^(%d+)%s+(.+)$")
    if wh == hash then
      vim.fn.system("tmux select-window -t :" .. idx)
      return
    end
  end
end

local function send_file_ref()
  local bufname = vim.api.nvim_buf_get_name(0)
  if bufname == "" then
    return
  end

  local ref = "@" .. vim.fn.fnamemodify(bufname, ":.")
  local mode = vim.fn.mode()

  if mode == "v" or mode == "V" or mode == "\22" then
    local start_line = vim.fn.line("v")
    local end_line = vim.fn.line(".")
    if start_line > end_line then
      start_line, end_line = end_line, start_line
    end
    if start_line ~= end_line then
      ref = ref .. ":" .. start_line .. "-" .. end_line
    else
      ref = ref .. ":" .. start_line
    end
    vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Esc>", true, false, true), "n", false)
  else
    ref = ref .. ":" .. vim.fn.line(".")
  end

  require("amp.message").send_to_prompt(ref)
  focus_agent_window()
end

return {
  {
    "sourcegraph/amp.nvim",
    branch = "main",
    lazy = false,
    opts = { auto_start = true, log_level = "info" },
    keys = {
      { "<leader>@", send_file_ref, mode = { "n", "v" }, desc = "Send file ref to Amp prompt" },
    },
  },
}
