local venv_bin = vim.fn.getcwd() .. "/.venv/bin"

return {
  {
    "mason-org/mason.nvim",
    opts = { ensure_installed = {} },
  },
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        ansiblels = {
          mason = false,
          settings = {
            ansible = {
              path = "ansible",
              python = { activationScript = "" },
              validation = {
                lint = { path = venv_bin .. "/ansible-lint" },
              },
            },
            executionEnvironment = {
              enabled = false,
            },
          },
          cmd_env = {
            PATH = venv_bin .. ":" .. vim.env.PATH,
          },
        },
        biome = { mason = false },
        vtsls = { mason = false },
        yamlls = { mason = false },
      },
    },
  },
}
