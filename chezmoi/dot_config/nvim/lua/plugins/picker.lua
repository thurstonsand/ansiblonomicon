return {
  {
    "folke/snacks.nvim",
    opts = {
      picker = {
        sources = {
          explorer = { hidden = true },
          files = { hidden = true },
          grep = { hidden = true },
        },
      },
      terminal = {
        win = { position = "float", width = 0.8, height = 0.8, backdrop = false, wo = { winblend = 15 } },
      },
      image = {
        enabled = true,
        doc = {
          inline = true,
          float = true,
        },
      },
    },
  },
}
