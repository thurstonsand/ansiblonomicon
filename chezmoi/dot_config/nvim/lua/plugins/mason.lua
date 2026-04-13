return {
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
            },
            executionEnvironment = {
              enabled = false,
            },
          },
          cmd_env = {
            PATH = vim.fn.getcwd() .. "/.venv/bin:" .. vim.env.PATH,
          },
        },
        biome = { mason = false },
        vtsls = { mason = false },
        yamlls = { mason = false },
      },
    },
  },
}
