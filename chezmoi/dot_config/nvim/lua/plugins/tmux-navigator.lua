local ghostty_nav = require("lib.ghostty-nav")

ghostty_nav.setup()

return {
  { "christoomey/vim-tmux-navigator", enabled = false },
  {
    dir = ".",
    name = "ghostty-navigator",
    keys = {
      { "<C-h>", function() ghostty_nav.navigate("h", "left") end, desc = "Navigate Left" },
      { "<C-j>", function() ghostty_nav.navigate("j", "down") end, desc = "Navigate Down" },
      { "<C-k>", function() ghostty_nav.navigate("k", "up") end, desc = "Navigate Up" },
      { "<C-l>", function() ghostty_nav.navigate("l", "right") end, desc = "Navigate Right" },
    },
  },
}
