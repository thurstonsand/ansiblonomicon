return {
  {
    "swaits/zellij-nav.nvim",
    lazy = true,
    event = "VeryLazy",
    keys = {
      { "<c-h>", "<cmd>ZellijNavigateLeftTab<cr>", desc = "Navigate left (zellij)" },
      { "<c-j>", "<cmd>ZellijNavigateDown<cr>", desc = "Navigate down (zellij)" },
      { "<c-k>", "<cmd>ZellijNavigateUp<cr>", desc = "Navigate up (zellij)" },
      { "<c-l>", "<cmd>ZellijNavigateRightTab<cr>", desc = "Navigate right (zellij)" },
    },
    opts = {},
  },
}
