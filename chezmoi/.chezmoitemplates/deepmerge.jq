# Deep-merge two JSON objects with null-deletion.
# Usage: jq -s -f deepmerge.jq base.json overlay.json
#
# - Objects are recursively merged (overlay keys win)
# - Overlay values of `null` delete the key from output
# - Arrays and scalars in overlay replace base entirely

def deepmerge:
  if length == 0 then null
  elif length == 1 then .[0]
  else
    .[0] as $a | .[1] as $b |
    if ($a | type) == "object" and ($b | type) == "object" then
      # Preserve base key order, append overlay-only keys at end
      (($a | keys_unsorted) + (($b | keys_unsorted) - ($a | keys_unsorted))) | map(
        . as $k |
        if ($b | has($k)) then
          if $b[$k] == null then empty
          elif ($a | has($k)) and (($a[$k] | type) == "object") and (($b[$k] | type) == "object") then
            { ($k): ([$a[$k], $b[$k]] | deepmerge) }
          else
            { ($k): $b[$k] }
          end
        else
          { ($k): $a[$k] }
        end
      ) | add // {}
    else
      $b
    end
  end;

deepmerge
