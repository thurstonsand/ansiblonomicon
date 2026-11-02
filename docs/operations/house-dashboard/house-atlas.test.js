// Browser contract checks. Pass a disconnected preview card and its hass fixture.
export async function checkMapControls(card, hass) {
  const calls = [];
  const fixture = {
    ...hass,
    states: structuredClone(hass.states),
    callService: async (...args) => calls.push(args),
  };
  const root = card.shadowRoot;
  const assert = (condition, message) => {
    if (!condition) throw new Error(message);
  };
  const findButton = (name, scope) => {
    const found = [...scope.querySelectorAll('button, [role="button"]')].find(
      (b) => b.getAttribute("aria-label") === name || b.textContent === name,
    );
    if (found) return found;
    for (const element of scope.querySelectorAll("*")) {
      if (!element.shadowRoot) continue;
      const nested = findButton(name, element.shadowRoot);
      if (nested) return nested;
    }
  };
  const button = (name) => {
    const found = findButton(name, root);
    assert(found, `Missing control: ${name}`);
    return found;
  };
  const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const close = async () => {
    button("Close controls").click();
    await pause(0);
  };
  const event = (target, type, options = {}) =>
    target.dispatchEvent(
      new PointerEvent(type, {
        bubbles: true,
        composed: true,
        button: 0,
        clientX:
          target.getBoundingClientRect().x +
          target.getBoundingClientRect().width / 2,
        clientY:
          target.getBoundingClientRect().y +
          target.getBoundingClientRect().height / 2,
        ...options,
      }),
    );
  card.hass = fixture;
  try {
    button("Main").click();
    await pause(50);
    button("Living Room").dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Enter",
        bubbles: true,
        composed: true,
        cancelable: true,
      }),
    );
    assert(
      root.querySelector(".room-stage"),
      "Room selection opens focus directly",
    );
    const controlsText = [...root.querySelector(".detail-body").children]
      .map((element) => element.shadowRoot?.textContent || element.textContent)
      .join(" ");
    assert(
      controlsText.includes("Ambient light") &&
        controlsText.includes("Floor lamps") &&
        !root.querySelector("details"),
      "Existing groups are directly available without a dropdown",
    );
    assert(
      root.querySelector(".g-lights").hidden,
      "House-wide off is absent in a room",
    );
    button("Living Room: turn off all lights").click();
    assert(
      JSON.stringify(calls.pop()) ===
        JSON.stringify([
          "light",
          "turn_off",
          {
            entity_id: [
              "light.living_room_ambient_light",
              "light.living_room_floor_lamps",
            ],
          },
        ]),
      "Room off includes both living-room groups but no other room",
    );
    const livingLights = [
      "light.living_room_floor_light_left",
      "light.living_room_floor_light_right",
      "light.living_room_wall_wash_right",
      "light.living_room_front_right_floor_lamp",
      "light.living_room_rear_center_floor_lamp",
    ];
    for (const id of livingLights) fixture.states[id].state = "off";
    card.hass = { ...fixture };
    button("Living Room: turn on all lights").click();
    const roomOn = calls.pop();
    assert(
      roomOn[0] === "script" &&
        roomOn[1] === "turn_on" &&
        [
          "script.living_room_tokyo",
          "script.living_room_evening_lights",
          "script.living_room_late_night",
        ].includes(roomOn[2].entity_id),
      "An unlit room activates its usual scene instead of raw bulb power",
    );
    fixture.states[livingLights[0]].state = "on";
    card.hass = { ...fixture };
    button("Living Room: turn off all lights").click();
    assert(calls.pop()[1] === "turn_off", "A mixed room turns everything off");
    for (const id of livingLights) fixture.states[id].state = "unavailable";
    card.hass = { ...fixture };
    assert(
      button("Living Room: turn on all lights").disabled,
      "Unavailable room power is disabled",
    );
    for (const id of livingLights)
      fixture.states[id].state = hass.states[id].state;
    card.hass = { ...fixture };
    const light = [...root.querySelectorAll("button")].find((b) =>
      b.getAttribute("aria-label")?.startsWith("Floor Light Left ·"),
    );
    assert(light, "Living Room fixture is accessible by name");
    light.click();
    assert(
      JSON.stringify(calls.pop()) ===
        JSON.stringify([
          "light",
          "toggle",
          { entity_id: "light.living_room_ambient_light" },
        ]),
      "Tap toggles the existing group instead of only the selected bulb",
    );
    assert(calls.length === 0, "Tap sends one command");

    event(light, "pointerdown");
    await pause(500);
    event(light, "pointerup");
    light.dispatchEvent(new MouseEvent("click", { bubbles: true, detail: 1 }));
    assert(
      root.querySelector('dialog[open] input[aria-label="Brightness"]'),
      "Hold opens supported brightness controls",
    );
    assert(calls.length === 0, "Hold and trailing click never toggle");
    const brightness = root.querySelector('input[aria-label="Brightness"]');
    brightness.value = "37";
    brightness.dispatchEvent(new Event("input"));
    assert(calls.length === 0, "Dragging brightness does not send a command");
    brightness.dispatchEvent(new Event("change"));
    assert(
      JSON.stringify(calls.pop()) ===
        JSON.stringify([
          "light",
          "turn_on",
          { entity_id: "light.living_room_floor_light_left", brightness: 94 },
        ]),
      "Brightness commits an uncalibrated 37% command",
    );
    const color = root.querySelector("ha-hs-color-picker");
    color.dispatchEvent(
      new CustomEvent("cursor-moved", { detail: { value: [217, 0.63] } }),
    );
    assert(
      calls.length === 0,
      "Moving around the color wheel sends no command",
    );
    color.dispatchEvent(
      new CustomEvent("value-changed", { detail: { value: [217, 0.63] } }),
    );
    assert(
      JSON.stringify(calls.pop()) ===
        JSON.stringify([
          "light",
          "turn_on",
          {
            entity_id: "light.living_room_floor_light_left",
            hs_color: [217, 63],
          },
        ]),
      "Color wheel converts fractional saturation to HA percent",
    );
    await close();

    light.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Alt",
        altKey: true,
        bubbles: true,
        composed: true,
      }),
    );
    light.blur();
    light.focus();
    assert(
      getComputedStyle(light).outlineStyle === "none",
      "Restoring pointer focus after app switching does not draw a ring",
    );

    event(light, "pointerdown");
    event(light, "pointermove", { clientX: 120 });
    await pause(500);
    event(light, "pointerup");
    light.dispatchEvent(new MouseEvent("click", { detail: 1 }));
    assert(
      !root.querySelector("dialog[open]") && !calls.length,
      "Scrolling cancels hold and toggle",
    );
    event(light, "pointerdown");
    event(light, "pointercancel");
    await pause(500);
    assert(
      !root.querySelector("dialog[open]") && !calls.length,
      "Pointer cancellation cancels hold",
    );

    event(light, "contextmenu", { cancelable: true });
    assert(
      root.querySelector("dialog[open]") && !calls.length,
      "Right-click opens controls without a toggle",
    );
    await close();
    light.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "F10",
        shiftKey: true,
        bubbles: true,
        composed: true,
        cancelable: true,
      }),
    );
    assert(
      root.querySelector("dialog[open]") && !calls.length,
      "Keyboard context shortcut opens controls",
    );
    await close();
    assert(
      root.activeElement === light,
      "Closing controls restores fixture focus",
    );
    assert(
      getComputedStyle(light).outlineStyle !== "none",
      "Keyboard focus remains visible",
    );

    button("Evening lights").click();
    await pause(0);
    assert(
      JSON.stringify(calls.pop()) ===
        JSON.stringify([
          "script",
          "turn_on",
          { entity_id: "script.living_room_evening_lights" },
        ]),
      "Room dock runs the existing combined script",
    );
    fixture.states["light.living_room_floor_light_left"].state = "unavailable";
    card.hass = { ...fixture };
    light.click();
    assert(!calls.length, "Unavailable light cannot toggle");
    assert(
      light.getAttribute("aria-label").includes("Unavailable"),
      "Unavailable is not presented as off",
    );
    button("← Main").click();
    await pause(50);
    assert(
      !root.querySelector(".g-lights").hidden,
      "House-wide off returns on the full map",
    );
    fixture.states["light.living_room_floor_light_left"].state = "on";
    card.hass = { ...fixture };
    const boundary = new DOMPoint(200, 217).matrixTransform(
      root.querySelector(".light-map").getScreenCTM(),
    );
    event(
      root.querySelector('[data-device="climate.foyer_main_floor_thermostat"]'),
      "click",
      { detail: 1, clientX: boundary.x, clientY: boundary.y },
    );
    assert(
      !calls.length && root.querySelector("dialog[open]"),
      "Overlapping targets across a wall require a choice before acting",
    );
    const boundaryChoices = [...root.querySelectorAll("dialog[open] .fixture")];
    assert(
      boundaryChoices.length === 2 &&
        boundaryChoices.some((b) =>
          b.getAttribute("aria-label").includes("Foyer"),
        ) &&
        boundaryChoices.some((b) =>
          b.getAttribute("aria-label").includes("Living Room"),
        ),
      "Cross-room choices retain accessible room identities",
    );
    assert(
      !root.querySelector("dialog header") &&
        !root.querySelector("dialog .muted"),
      "Lens has no header or instruction chrome",
    );
    const lens = root.querySelector("dialog");
    const lensRect = lens.getBoundingClientRect();
    assert(
      Math.abs(lensRect.width - lensRect.height) < 1 &&
        getComputedStyle(lens).borderRadius === "50%",
      "Chooser is a circular lens",
    );
    boundaryChoices
      .find((b) =>
        b.getAttribute("aria-label").startsWith("Floor Light Left ·"),
      )
      .click();
    await pause(0);
    assert(
      JSON.stringify(calls.pop()) ===
        JSON.stringify([
          "light",
          "toggle",
          { entity_id: "light.living_room_ambient_light" },
        ]) && !root.querySelector("dialog[open]"),
      "Choosing across the wall operates only the selected light group",
    );
    const homepod = [...root.querySelectorAll(".fixture")].find((b) =>
      b.getAttribute("aria-label").startsWith("HomePod ·"),
    );
    event(homepod, "click", { detail: 1 });
    assert(
      root.querySelector(".local-zoom[open]"),
      "Ambiguous hit opens the local close-up",
    );
    assert(!calls.length, "Opening the chooser never operates a device");
    const choices = [...root.querySelectorAll("dialog[open] .fixture")];
    assert(
      choices.length === 2,
      "Only the overlapping bedroom pair is offered",
    );
    const lamp = choices.find((b) =>
      b.getAttribute("aria-label").startsWith("Thurston Fluff Lamp ·"),
    );
    const a = choices[0].getBoundingClientRect(),
      b = choices[1].getBoundingClientRect();
    assert(
      a.right <= b.left ||
        b.right <= a.left ||
        a.bottom <= b.top ||
        b.bottom <= a.top,
      "Zoom separates full touch targets without moving the original anchors",
    );
    lamp.click();
    await pause(0);
    assert(
      JSON.stringify(calls.pop()) ===
        JSON.stringify([
          "light",
          "toggle",
          { entity_id: "light.main_bedroom_ambient_light" },
        ]),
      "Choosing the lamp toggles its existing bedroom group",
    );
    assert(
      !calls.length && !root.querySelector("dialog[open]"),
      "Selection dismisses the chooser",
    );
    card.hass = {
      ...fixture,
      callService: async () => {
        throw new Error("Test device rejected command");
      },
    };
    event(homepod, "click", { detail: 1 });
    root
      .querySelector(
        'dialog[open] [data-device="light.main_bedroom_thurston_fluff_lamp"]',
      )
      .click();
    await pause(50);
    assert(
      [...root.querySelectorAll('[role="alert"]')].some(
        (el) =>
          el.checkVisibility() &&
          el.textContent === "Test device rejected command",
      ),
      "A rejected chooser command remains visible after the chooser closes",
    );
    card.hass = { ...fixture };
    event(homepod, "pointerdown");
    await pause(500);
    assert(
      root.activeElement === root.querySelector("dialog[open]"),
      "Pointer hold focuses the dialog, not the Close button",
    );
    event(homepod, "pointerup");
    event(homepod, "click", { detail: 1 });
    root
      .querySelector(
        'dialog[open] [data-device="light.main_bedroom_thurston_fluff_lamp"]',
      )
      .click();
    await pause(0);
    assert(
      root.querySelector('dialog[open] input[aria-label="Brightness"]') &&
        !calls.length,
      "Ambiguous hold resolves identity then opens controls without toggling",
    );
    await close();
    const door = root.querySelector(
      '.fixture[data-device="lock.foyer_front_door"]',
    );
    fixture.states["lock.foyer_front_door"].state = "locked";
    card.hass = { ...fixture };
    event(door, "click", { detail: 1 });
    assert(
      JSON.stringify(calls.pop()) ===
        JSON.stringify([
          "lock",
          "unlock",
          { entity_id: "lock.foyer_front_door" },
        ]),
      "A locked front door tap unlocks once",
    );
    fixture.states["lock.foyer_front_door"].state = "unlocked";
    card.hass = { ...fixture };
    event(door, "click", { detail: 1 });
    assert(
      JSON.stringify(calls.pop()) ===
        JSON.stringify([
          "lock",
          "lock",
          { entity_id: "lock.foyer_front_door" },
        ]),
      "An unlocked front door tap locks once",
    );
    event(door, "contextmenu", { cancelable: true });
    assert(
      root.querySelector("dialog[open] .dialog-body").firstElementChild.config
        ?.camera_view === "live",
      "Door controls open with the live camera card first",
    );
    assert(!calls.length, "Door context never operates the lock");
    await close();
    const garage = root.querySelector(
      '.fixture[data-device="cover.garage_door"]',
    );
    fixture.states["cover.garage_door"].state = "closed";
    fixture.states["cover.garage_door"].attributes.current_position = 0;
    card.hass = { ...fixture };
    const closedPanel = garage.querySelector("svg").getBoundingClientRect();
    fixture.states["cover.garage_door"].state = "open";
    fixture.states["cover.garage_door"].attributes.current_position = 100;
    card.hass = { ...fixture };
    const openPanel = garage.querySelector("svg").getBoundingClientRect();
    const openSlab = garage
      .querySelector(".garage-panel rect")
      .getBoundingClientRect();
    const garageGlyph = garage
      .querySelector(".door-state")
      .getBoundingClientRect();
    assert(
      openPanel.width > closedPanel.width * 5 &&
        Math.abs(openPanel.left - closedPanel.left) < 1,
      "Open garage panel extends inward from the fixed doorway",
    );
    assert(
      garageGlyph.left >= openPanel.left &&
        garageGlyph.right <= openPanel.right &&
        garageGlyph.top >= openPanel.top &&
        garageGlyph.bottom <= openPanel.bottom,
      "Garage status sits on the open panel",
    );
    fixture.states["cover.garage_door"].attributes.current_position = 37;
    fixture.states["cover.garage_door"].state = "opening";
    card.hass = { ...fixture };
    const movingWidth = garage
      .querySelector("svg")
      .getBoundingClientRect().width;
    assert(
      movingWidth > closedPanel.width && movingWidth < openPanel.width,
      "Partial garage extension uses the reported position",
    );
    const movingSlab = garage
      .querySelector(".garage-panel rect")
      .getBoundingClientRect();
    assert(
      Math.abs(movingSlab.width - openSlab.width) < 1 &&
        movingSlab.left < openSlab.left,
      "Rigid garage panels translate horizontally instead of stretching",
    );
    event(
      root.querySelector('.fixture[data-device="cover.garage_door"]'),
      "click",
      { detail: 1 },
    );
    assert(
      JSON.stringify(calls.pop()) ===
        JSON.stringify(["cover", "toggle", { entity_id: "cover.garage_door" }]),
      "The wide garage control uses cover.toggle, including while moving",
    );
    for (const [floor, entity, target] of [
      [
        "Main",
        "light.living_room_front_right_floor_lamp",
        "light.living_room_floor_lamps",
      ],
      ["Main", "light.breakfast_nook_yellow_lamp", "light.breakfast_nook"],
      ["Main", "light.main_bath_tub_light", "light.main_bath_tub_light"],
      [
        "Second",
        "light.thurston_office_desk_lamp_right",
        "light.thurston_office_desk_lights",
      ],
      [
        "Second",
        "light.thurston_office_wall_wash_left",
        "light.thurston_office_ambient_light",
      ],
      ["Second", "light.thurston_office_iris", "light.thurston_office_iris"],
      [
        "Basement",
        "light.basement_under_main_bedroom_front_bulb",
        "light.basement_under_main_bedroom",
      ],
      [
        "Basement",
        "light.basement_under_living_room_right_bulb",
        "light.basement_under_living_room",
      ],
      [
        "Basement",
        "light.basement_entryway_front_bulb",
        "light.basement_entryway",
      ],
      [
        "Basement",
        "light.basement_under_kitchen_rear_bulb",
        "light.basement_under_kitchen",
      ],
    ]) {
      button(floor).click();
      await pause(50);
      root.querySelector(`[data-device="${entity}"]`).click();
      assert(
        JSON.stringify(calls.pop()) ===
          JSON.stringify(["light", "toggle", { entity_id: target }]),
        `${entity} operates its original control`,
      );
      assert(!calls.length, "Group tap sends only one command");
    }
    findButton("Basement", card.map.shadowRoot).dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Enter",
        bubbles: true,
        composed: true,
      }),
    );
    assert(
      root.querySelectorAll('.room-stage [data-device^="light."]').length === 8,
      "Basement focuses as one room with all eight bulbs",
    );
    const basementLights = [
      "light.basement_under_main_bedroom_front_bulb",
      "light.basement_under_main_bedroom_rear_bulb",
      "light.basement_under_living_room_left_bulb",
      "light.basement_under_living_room_right_bulb",
      "light.basement_entryway_front_bulb",
      "light.basement_entryway_rear_bulb",
      "light.basement_under_kitchen_front_bulb",
      "light.basement_under_kitchen_rear_bulb",
    ];
    for (const id of basementLights) fixture.states[id].state = "off";
    fixture.states["light.basement_entryway_rear_bulb"].state = "on";
    card.hass = { ...fixture };
    button("Basement: turn off all lights").click();
    assert(
      JSON.stringify(calls.pop()) ===
        JSON.stringify([
          "light",
          "turn_off",
          { entity_id: ["light.basement"] },
        ]),
      "Basement room power covers all four groups, never upstairs or the lock",
    );
    fixture.states["light.basement_entryway_rear_bulb"].state = "off";
    card.hass = { ...fixture };
    button("Basement: turn on all lights").click();
    assert(
      JSON.stringify(calls.pop()) ===
        JSON.stringify(["light", "turn_on", { entity_id: ["light.basement"] }]),
      "A room without a preferred scene powers its native group",
    );
    button("Main").click();
    for (const id of [
      "light.main_bedroom_fluff_floor_lamp",
      "light.main_bedroom_yanie_fluff_lamp",
      "light.main_bedroom_thurston_fluff_lamp",
      "light.main_bedroom_cloud_painting",
    ])
      fixture.states[id].state = "off";
    card.hass = { ...fixture };
    button("Main Bedroom: turn on all lights").click();
    assert(
      JSON.stringify(calls.pop()) ===
        JSON.stringify([
          "hue",
          "activate_scene",
          {
            entity_id: "scene.main_bedroom_main_bedroom_pensive",
            dynamic: true,
          },
        ]),
      "Room power recalls native Hue scenes with dynamic playback",
    );
    return "PASS: original lighting groups, individual hold controls, room power on/off/mixed/unavailable, pointer vs keyboard focus, unified basement with four groups, overhead garage closed/partial/open, chrome-free circular lens, tap/hold/cancel, brightness/wheel, scenes, cross-room ambiguity, lock/unlock, camera-first context";
  } finally {
    root.querySelector("dialog[open]")?.close();
    card.hass = hass;
  }
}
