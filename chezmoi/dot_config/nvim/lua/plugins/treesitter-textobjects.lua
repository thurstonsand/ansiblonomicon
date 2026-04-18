local function select(query)
  return function()
    require("nvim-treesitter-textobjects.select").select_textobject(query, "textobjects")
  end
end

return {
  {
    "nvim-treesitter/nvim-treesitter-textobjects",
    opts = {
      select = {
        lookahead = true,
        selection_modes = {
          ["@function.outer"] = "V",
          ["@class.outer"] = "V",
        },
      },
    },
    -- stylua: ignore
    keys = {
      { "af", select("@function.outer"),    mode = { "x", "o" }, desc = "around function" },
      { "if", select("@function.inner"),    mode = { "x", "o" }, desc = "inside function" },
      { "ac", select("@class.outer"),       mode = { "x", "o" }, desc = "around class" },
      { "ic", select("@class.inner"),       mode = { "x", "o" }, desc = "inside class" },
      { "aa", select("@parameter.outer"),   mode = { "x", "o" }, desc = "around parameter" },
      { "ia", select("@parameter.inner"),   mode = { "x", "o" }, desc = "inside parameter" },
      { "ai", select("@conditional.outer"), mode = { "x", "o" }, desc = "around conditional" },
      { "ii", select("@conditional.inner"), mode = { "x", "o" }, desc = "inside conditional" },
      { "al", select("@loop.outer"),        mode = { "x", "o" }, desc = "around loop" },
      { "il", select("@loop.inner"),        mode = { "x", "o" }, desc = "inside loop" },
    },
  },
}
