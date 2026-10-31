-- When the mic picked as default is missing, falls back by priority.session instead of to whichever
-- mic was picked before it, so the fallback follows the order in mic-priority.conf.
SimpleEventHook {
  name = "default-nodes/rank-sources-by-priority",
  after = { "default-nodes/find-selected-default-node",
            "default-nodes/find-stored-default-node" },
  before = { "default-nodes/find-best-default-node" },
  interests = {
    EventInterest {
      Constraint { "event.type", "=", "select-default-node" },
      Constraint { "default-node.type", "=", "audio.source" },
    },
  },
  execute = function (event)
    -- find-selected-default-node scores the picked default at 30000 and up; earlier picks score below 20001.
    if (event:get_data ("selected-node-priority") or 0) < 30000 then
      event:set_data ("selected-node-priority", 0)
      event:set_data ("selected-node", nil)
    end
  end
}:register ()
