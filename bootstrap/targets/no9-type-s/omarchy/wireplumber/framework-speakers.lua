-- The headphone jack and speakers share one ALSA sink. Only the speaker route gets the correction.
local cutils = require("common-utils")

SimpleEventHook({
	name = "linking/framework-speakers",
	before = "linking/rescan-trigger",
	interests = {
		EventInterest({
			Constraint({ "event.type", "=", "device-params-changed" }),
			Constraint({ "event.subject.param-id", "=", "Route" }),
			Constraint({ "device.name", "=", "alsa_card.pci-0000_00_1f.3" }),
		}),
		EventInterest({
			Constraint({ "event.type", "=", "node-added" }),
			Constraint({ "node.name", "=", "effect_input.Framework13Pro_Dynamic_Balanced" }),
		}),
		EventInterest({
			Constraint({ "event.type", "=", "metadata-added" }),
			Constraint({ "metadata.name", "=", "filters" }),
		}),
	},
	execute = function(event)
		local source = event:get_source()
		local nodes = source:call("get-object-manager", "node")
		local devices = source:call("get-object-manager", "device")
		local metadata = source:call("get-object-manager", "metadata")
		local filter = nodes:lookup({
			Constraint({ "node.name", "=", "effect_input.Framework13Pro_Dynamic_Balanced" }),
		})
		local device = devices:lookup({
			Constraint({ "device.name", "=", "alsa_card.pci-0000_00_1f.3" }),
		})
		local filters = metadata:lookup({ Constraint({ "metadata.name", "=", "filters" }) })
		if not filter or not device or not filters then
			return
		end

		local speakers = false
		for param in device:iterate_params("Route") do
			local route = cutils.parseParam(param, "Route")
			if route and route.name == "analog-output-speaker" then
				speakers = true
			end
		end
		filters:set(filter["bound-id"], "filter.smart.disabled", "Spa:Bool", tostring(not speakers))
	end,
}):register()
