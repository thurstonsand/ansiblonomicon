const escapeXml = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&apos;",
      })[c],
  );
const POLAROID_LIFE = 15 * 60 * 1000;
const MODE_NAMES = {
  off: "Off",
  heat: "Heat",
  cool: "Cool",
  heat_cool: "Heat/cool",
  auto: "Auto",
  dry: "Dry",
  fan_only: "Fan",
};
const HOLDS = {
  lights: (room) =>
    !!room.lights &&
    (room.hold.scenes || []).every(
      (scene) =>
        /^([01]\d|2[0-3]):[0-5]\d$/.test(scene.from) &&
        /^(scene|script)\./.test(scene.entity || ""),
    ),
  lock: (room) => !!room.entity?.startsWith("lock."),
  toggle: (room) => !!room.entity?.startsWith("cover."),
};
const resource = (type, text) => ({
  location: `data:${type},${encodeURIComponent(text)}`,
  cache: true,
});
// Hue Icons by arallsopp, CC BY-NC-SA 4.0, revision 4604f9ad40f251f829da9ac27a82dac74666742c.
// https://github.com/arallsopp/hass-hue-icons — unchanged paths; no icon-pack installation required.
const FIXTURE_PATHS = {
  "house:floor-lamp-full-shade":
    "M7 2H17V22H7Z M8 6V7H16V6Z M8 11V12H16V11Z M8 16V17H16V16Z",
  "house:homepod":
    "M5 6C5 1 19 1 19 6V18C19 23 5 23 5 18ZM7 6C7 8.5 17 8.5 17 6C17 3.5 7 3.5 7 6Z",
  "house:nest-hub":
    "M3 3H21Q23 3 23 5V16Q23 18 21 18H3Q1 18 1 16V5Q1 3 3 3ZM3 5V15H21V5ZM8 19H16L18 22H6Z",
  "hue:floor-spot":
    "M16.31,10.71c-0.89,0.32-2.1-0.77-2.68-2.43c-0.59-1.66-0.34-3.26,0.56-3.57c0.89-0.32,2.09,0.77,2.68,2.43 C17.46,8.8,17.21,10.4,16.31,10.71 M18.28,6.64c-0.88-2.43-2.67-4.02-4-3.56L5.37,7.22c-1.02,0.39-1.16,2.4-0.32,4.48 c0.84,2.08,2.57,3.56,3.59,3.17l1.12-0.41v2.81c-2.2,0.08-3.96,0.53-4.39,1.11c-0.07,0.09-0.11,0.19-0.11,0.28v0.94 c0,0.78,2.35,1.41,5.25,1.41s5.25-0.63,5.25-1.41v-0.94c0-0.71-1.96-1.29-4.5-1.39v-3.31l6.18-2.07 C18.78,11.42,19.15,9.07,18.28,6.64",
  "hue:iris":
    "M19.2,13.75c-1.15-0.38-2.85-1.48-5.14-3.78c-1.84-1.84-3.29-3.88-3.76-5.12c-0.1-0.27,0.14-0.54,0.43-0.49 c0.29,0.05,0.69,0.18,1.2,0.42c1.39,0.64,2.66,1.48,4.25,3.07c1.59,1.59,2.43,2.86,3.07,4.25c0.25,0.52,0.37,0.93,0.42,1.22 C19.72,13.59,19.46,13.83,19.2,13.75 M16.53,16.88c-0.05,0.16-0.2,0.26-0.36,0.26c-0.04,0-0.08,0-0.11-0.02 c-1.03-0.34-2.32-1.17-3.77-2.44c-1.72,0.95-4.54,2.06-4.47,2.54c0.14,0.92-0.41,1.43-1.45,0.39c-1.04-1.04-0.53-1.59,0.39-1.45 c0.48,0.07,1.61-2.78,2.55-4.5C8.18,10.32,7.29,8.96,6.93,8C6.85,7.8,6.95,7.59,7.14,7.52c0.19-0.07,0.41,0.02,0.48,0.22 C8.1,9,9.57,11,11.3,12.73c2.53,2.53,4.11,3.4,4.99,3.68C16.48,16.47,16.59,16.68,16.53,16.88 M20.43,11.8 c-1.44-3.09-5.12-6.8-8.18-8.24C11,2.97,10.08,2.87,9.51,3.16C9.44,3.2,9.38,3.25,9.3,3.29c-0.75,0.5-1.48,1.08-2.16,1.75 c-4.23,4.22-5.9,9.4-1.73,13.57c4.12,4.11,9.36,2.5,13.59-1.72c0.67-0.67,1.24-1.39,1.73-2.12c0.03-0.05,0.06-0.09,0.09-0.14 C21.14,14.06,21.04,13.09,20.43,11.8",
  "hue:signe-gradient-floor":
    "M12.2,13V1.4c0-0.3-0.2-0.5-0.5-0.5H9.8H9.2c-0.3,0-0.5,0.2-0.5,0.5v12.5c-0.3,0.3-0.6,0.6-0.6,1v0.3v6.3 c0,0.1,0,0.1,0,0.2c0.2,1.1,2.2,1.7,4.1,1.7s3.9-0.6,4.1-1.7c0-0.1,0-0.1,0-0.2v-6.3v-0.3C16.5,13.5,14.3,12.9,12.2,13z M11.2,14 c0,0.1-0.2,0.3-0.5,0.3s-0.5-0.2-0.5-0.3V1.9h1V14z",
  "hue:signe-gradient-table":
    "M11.6,15.5V1.4c0-0.3-0.2-0.5-0.5-0.5H8.4H7.5C7.2,0.9,7,1.1,7,1.4v15.3C6.5,17,6.2,17.4,6.2,18v2.6 c0,1.7,2.9,2.5,5.8,2.5s5.8-0.9,5.8-2.5V18C17.8,16.2,14.6,15.4,11.6,15.5z M10.6,16.8c0,0.1-0.1,0.5-0.8,0.5 c-0.7,0-0.8-0.4-0.8-0.5V1.9h1.7V16.8z",
  "hue:table-shade":
    "M14.16,5.77c-1.18,0.3-3.12,0.3-4.3,0C8.7,5.47,8.73,4.99,9.91,4.71c1.16-0.29,3.03-0.29,4.19,0 C15.28,4.99,15.32,5.47,14.16,5.77 M18.71,11.2l-2.03-6.93L16.66,4.2c-0.19-0.43-1.11-0.85-2.75-1.07c-1.25-0.17-2.52-0.17-3.77,0 C8.51,3.35,7.59,3.76,7.41,4.2L7.37,4.31L5.29,11.2c-0.03,0.1-0.05,0.2-0.04,0.3c0.17,1.14,2.23,2.06,6,2.17v3.6 c-1.83,0.1-3.3,0.54-3.66,1.11c-0.06,0.09-0.09,0.19-0.09,0.28v0.94 c0,0.78,2.02,1.41,4.5,1.41c2.48,0,4.5-0.63,4.5-1.41v-0.94 c0-0.7-1.62-1.27-3.75-1.39v-3.6c3.77-0.11,5.82-1.03,5.99-2.17C18.76,11.4,18.74,11.3,18.71,11.2",
};
// Top-down silhouettes drawn to scale at 1 unit = 40mm, nose toward -y, rendered rotated to face the bays.
const CAR_SHAPES = {
  beetle: `<path class="car-wheel" d="M-27 -39.7H-19V-23.7H-27ZM19 -39.7H27V-23.7H19ZM-27 23.7H-19V39.7H-27ZM19 23.7H27V39.7H19Z"/><path class="car-body" d="M-22 -15L-27 -13.5V-9.5L-22 -8.5ZM22 -15L27 -13.5V-9.5L22 -8.5Z"/><path class="car-body" d="M0 -53.5C11 -53.5 19.5 -50.5 22.5 -44C24.2 -39 24.6 -33 24.6 -27C24.6 -18 23.8 -8 23.8 2C23.8 12 24.8 20 24.8 29C24.8 38 24 46 20 50.5C16 53.2 9 53.5 0 53.5C-9 53.5 -16 53.2 -20 50.5C-24 46 -24.8 38 -24.8 29C-24.8 20 -23.8 12 -23.8 2C-23.8 -8 -24.6 -18 -24.6 -27C-24.6 -33 -24.2 -39 -22.5 -44C-19.5 -50.5 -11 -53.5 0 -53.5Z"/><path class="car-glass" d="M-15 -23.5C-5 -24.5 5 -24.5 15 -23.5C17.5 -20 19 -15.5 19.5 -11H-19.5C-19 -15.5 -17.5 -20 -15 -23.5Z"/><path class="car-glass" d="M-19.2 7H19.2C18.8 12 17.5 17 15 20.5C6 21.5 -6 21.5 -15 20.5C-17.5 17 -18.8 12 -19.2 7Z"/>`,
  model3: `<path class="car-wheel" d="M-25.5 -45.5H-18.5V-29.5H-25.5ZM18.5 -45.5H25.5V-29.5H18.5ZM-25.5 26.4H-18.5V42.4H-25.5ZM18.5 26.4H25.5V42.4H18.5Z"/><path class="car-body" d="M-21 -13L-25.5 -11.5V-7.5L-21 -6.5ZM21 -13L25.5 -11.5V-7.5L21 -6.5Z"/><path class="car-body" d="M0 -58.7C8 -58.7 14 -57.6 17.5 -55C21 -52 23.1 -46 23.1 -34C23.3 -10 23.1 12 22.6 32C22.3 44 21.8 52.5 20 55.8C17 58.2 8 58.7 0 58.7C-8 58.7 -17 58.2 -20 55.8C-21.8 52.5 -22.3 44 -22.6 32C-23.1 12 -23.3 -10 -23.1 -34C-23.1 -46 -21 -52 -17.5 -55C-14 -57.6 -8 -58.7 0 -58.7Z"/><path class="car-glass" d="M-11.5 -31C-4 -32.2 4 -32.2 11.5 -31C15 -27 17.4 -20 17.8 -12C18 -8 18 -4 18 -1H-18C-18 -4 -18 -8 -17.8 -12C-17.4 -20 -15 -27 -11.5 -31Z"/><path class="car-glass" d="M-18 2H18C17.8 12 16.5 22 14 28C12.5 31 7 32 0 32C-7 32 -12.5 31 -14 28C-16.5 22 -17.8 12 -18 2Z"/>`,
};

class HouseAtlas extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.floorId = "main";
    this.roomId = null;
    this.deviceId = null;
    this.listMode = false;
    this.controlRoom = false;
    this.pendingTargets = new Map();
    this.cards = [];
    this.lampCards = [];
    this.polaroids = new Map();
    this.mobile = false;
    this.keyboardNavigation = false;
    this.resizeObserver = new ResizeObserver(([entry]) => {
      const mobile = entry.contentRect.width <= 1000;
      if (mobile !== this.mobile) {
        this.mobile = mobile;
        if (this.helpers) this.renderSceneDocks();
      }
      this.positionDevices();
      this.positionFloorDevices();
    });
  }

  connectedCallback() {
    this.inputEvents = new AbortController();
    this.ownerDocument.addEventListener(
      "pointerdown",
      () => {
        this.keyboardNavigation = false;
        this.removeAttribute("keyboard-navigation");
      },
      { capture: true, signal: this.inputEvents.signal },
    );
    this.ownerDocument.addEventListener(
      "keydown",
      (event) => {
        if (
          !event.altKey &&
          !event.metaKey &&
          [
            "Tab",
            "Enter",
            " ",
            "ArrowUp",
            "ArrowDown",
            "ArrowLeft",
            "ArrowRight",
            "ContextMenu",
            "F10",
          ].includes(event.key)
        ) {
          this.keyboardNavigation = true;
          this.setAttribute("keyboard-navigation", "");
        }
      },
      { capture: true, signal: this.inputEvents.signal },
    );
    this.mobile = this.getBoundingClientRect().width <= 1000;
    this.resizeObserver.observe(this);
    if (this.helpers) this.renderDetails();
  }

  disconnectedCallback() {
    this.inputEvents.abort();
    this.resizeObserver.disconnect();
    this.shadowRoot
      .querySelectorAll("dialog[open]")
      .forEach((dialog) => dialog.close());
  }

  setConfig(config) {
    if (!config.floors?.length) throw new Error("House Atlas requires floors.");
    for (const floor of config.floors) {
      for (const room of floor.rooms) {
        if (
          !/^[a-z_]+$/.test(room.id) ||
          !room.name ||
          !room.path ||
          !room.label
        )
          throw new Error("Invalid room definition.");
        for (const vehicle of room.vehicles || [])
          if (!CAR_SHAPES[vehicle.id])
            throw new Error(`No car shape for vehicle "${vehicle.id}".`);
        if (room.hold && !HOLDS[room.hold.action]?.(room))
          throw new Error(`Invalid hold for room "${room.id}".`);
      }
    }
    if (!config.override?.startsWith("input_boolean."))
      throw new Error("House Atlas requires an input_boolean override.");
    for (const [entity, point] of Object.entries(config.placements || {})) {
      const floor = config.floors.find((floor) => floor.id === point.floor);
      if (
        !/^(light|lock|cover|camera|climate|media_player|switch)\.[a-z0-9_]+$/.test(
          entity,
        ) ||
        !floor?.rooms.some((room) => room.id === point.room) ||
        !Number.isFinite(point.x) ||
        !Number.isFinite(point.y) ||
        point.x < 0 ||
        point.x > floor.width ||
        point.y < 0 ||
        point.y > floor.height
      )
        throw new Error(`Invalid placement for "${entity}".`);
      if (
        point.door !== undefined &&
        !(
          (point.door === "front" && entity.startsWith("lock.")) ||
          (point.door === "garage" && entity.startsWith("cover."))
        )
      )
        throw new Error(`Invalid door for "${entity}".`);
      if (
        entity.startsWith("light.") &&
        (!point.icon ||
          (!/^mdi:[a-z0-9-]+$/.test(point.icon) && !FIXTURE_PATHS[point.icon]))
      )
        throw new Error(`Choose a fixture icon for "${entity}".`);
      if (
        point.glowPercent !== undefined &&
        (!Number.isFinite(point.glowPercent) ||
          point.glowPercent < 0 ||
          point.glowPercent > 100)
      )
        throw new Error(
          `glowPercent must be between 0 and 100 for "${entity}".`,
        );
      if (
        point.fallbackColor !== undefined &&
        (!Array.isArray(point.fallbackColor) ||
          point.fallbackColor.length !== 3 ||
          point.fallbackColor.some(
            (value) => !Number.isInteger(value) || value < 0 || value > 255,
          ))
      )
        throw new Error(
          `fallbackColor must be three RGB bytes for "${entity}".`,
        );
    }
    if (
      !config.thermostats?.length ||
      config.thermostats.some(
        (zone) => !zone.entity?.startsWith("climate.") || !zone.name,
      )
    )
      throw new Error("House Atlas requires named climate thermostats.");
    const [low, high] = config.thermostatScale || [];
    if (!Number.isInteger(low) || !Number.isInteger(high) || low >= high)
      throw new Error("House Atlas requires a thermostatScale of [low, high].");
    if (
      (config.lamps || []).some(
        (lamp) =>
          !lamp.entity?.startsWith("light.") ||
          !lamp.name ||
          (lamp.sceneArea !== undefined && typeof lamp.sceneArea !== "string"),
      )
    )
      throw new Error("House Atlas lamps must be named lights.");
    this.config = config;
    this.render();
  }

  getCardSize() {
    return 12;
  }

  set hass(hass) {
    const previous = this._hass;
    this._hass = hass;
    if (!this.config) return;
    this.updateGlobal();
    this.updateControlRoom();
    this.updatePolaroids();
    if (!this.helpers) {
      if (!this.loading) {
        this.loading = window
          .loadCardHelpers()
          .then((helpers) => {
            this.helpers = helpers;
            helpers.importMoreInfoControl("light");
            this.renderMap();
            this.renderDetails();
            this.renderLamps();
          })
          .catch((error) => this.showError(error));
      }
      return;
    }
    // Floorplan binds rules only for entities present when the map is created.
    if (
      this.mapEntities(this.floor).some(
        (id) => !previous?.states[id] && hass.states[id],
      )
    ) {
      this.renderMap();
    }
    if (this.map) this.map.hass = hass;
    for (const card of [...this.cards, ...this.lampCards]) card.hass = hass;
    this.updateRoomDevices();
    this.updateSummary();
    this.updateList();
    this.updateLockButtons();
    this.updateScenes();
  }

  get floor() {
    return this.config.floors.find((floor) => floor.id === this.floorId);
  }
  get room() {
    return this.floor.rooms.find((room) => room.id === this.roomId);
  }

  get roomPlacements() {
    return Object.entries(this.config.placements || {}).filter(
      ([, point]) => point.floor === this.floorId && point.room === this.roomId,
    );
  }

  get roomFocus() {
    return (
      !this.listMode && !this.controlRoom && this.roomPlacements.length > 0
    );
  }

  hasDevices(room) {
    return !!(
      room.lights?.length ||
      room.entity ||
      room.appliances?.length ||
      Object.values(this.config.placements || {}).some(
        (p) => p.room === room.id,
      )
    );
  }

  get visiblePlacements() {
    return Object.entries(this.config.placements || {}).filter(
      ([, point]) =>
        point.floor === this.floorId &&
        (!this.roomFocus || point.room === this.roomId),
    );
  }

  get rooms() {
    return this.config.floors.flatMap((floor) => floor.rooms);
  }

  get lamps() {
    return this.config.lamps || [];
  }

  houseLights() {
    return [
      ...new Set([
        ...this.rooms.flatMap((room) => room.lights || []),
        ...this.lamps.map((lamp) => lamp.entity),
      ]),
    ];
  }

  lightControl(entity) {
    const room = this.rooms.find((room) => room.lights?.includes(entity));
    return (
      room?.controls?.find(
        (control) =>
          control.entity === entity ||
          this._hass.states[control.entity]?.attributes.entity_id?.includes(
            entity,
          ),
      )?.entity ||
      room?.group ||
      entity
    );
  }

  roomLightTargets(room) {
    return room.group
      ? [room.group]
      : [...new Set(room.lights.map((entity) => this.lightControl(entity)))];
  }

  toggleRoomLights(room) {
    const on = room.lights.some((id) => this._hass.states[id]?.state === "on");
    const scene = this.currentScene(room.hold?.scenes || []);
    if (!on && scene) return this.activateScene(scene.entity);
    const targets = this.roomLightTargets(room).filter((id) =>
      ["on", "off"].includes(this._hass.states[id]?.state),
    );
    if (targets.length)
      return this.perform("light", on ? "turn_off" : "turn_on", targets);
  }

  perimeter() {
    return this.rooms
      .filter((room) => /^(lock|cover)\./.test(room.entity || ""))
      .map((room) => {
        const state = this._hass.states[room.entity]?.state;
        const lock = room.entity.startsWith("lock.");
        return {
          entity: room.entity,
          lock,
          name: room.mapNote.replace(/ Door$/, " door"),
          open: lock ? state !== "locked" : state !== "closed",
        };
      });
  }

  pausedSince() {
    return new Date(
      this._hass.states[this.config.override].last_changed,
    ).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }

  updateGlobal() {
    const root = this.shadowRoot;
    const on = (id) => this._hass.states[id]?.state === "on";
    const lit = this.houseLights().filter(on).length;
    const lights = root.querySelector(".g-lights");
    lights.hidden = !!this.room || !lit;
    lights.querySelector("b").textContent =
      `${lit} ${lit === 1 ? "light" : "lights"} on`;
    lights.querySelector("small").textContent = [
      ...this.rooms.filter((room) => (room.lights || []).some(on)),
      ...this.lamps.filter((lamp) => on(lamp.entity)),
    ]
      .map((place) => place.name)
      .join(" · ");
    const perimeter = this.perimeter();
    const open = perimeter.filter((door) => door.open);
    const secure = root.querySelector(".g-secure");
    secure.hidden = !open.length;
    secure.querySelector("b").textContent =
      open.length === 1
        ? `${open[0].name} ${open[0].lock ? "unlocked" : "open"}`
        : `${open.length} open`;
    secure.querySelector("small").textContent = open
      .map((door) => door.name)
      .join(" · ");
    root.querySelector(".strip").hidden = lights.hidden && secure.hidden;
    const paused = this._hass.states[this.config.override]?.state === "on";
    const stamp = root.querySelector(".stamp");
    if (stamp.hidden === paused) stamp.removeAttribute("style");
    stamp.hidden = !paused;
    if (paused)
      stamp.querySelector(".since").textContent =
        `since ${this.pausedSince()} · drag off to resume`;
  }

  zoneView(zone) {
    const entity = this._hass.states[zone.entity];
    const attributes = entity?.attributes || {};
    const unit = this._hass.config.unit_system.temperature;
    const pending = this.pendingTargets.get(zone.entity);
    return {
      entity,
      attributes,
      unit,
      available: !!entity && !["unavailable", "unknown"].includes(entity.state),
      current: attributes.current_temperature ?? null,
      target: pending ? pending.value : (attributes.temperature ?? null),
      pending: !!pending,
      min: attributes.min_temp,
      max: attributes.max_temp,
      step: attributes.target_temp_step || (unit === "°C" ? 0.5 : 1),
    };
  }

  setTarget(zone, value, delay) {
    const view = this.zoneView(zone);
    const [low, high] = this.config.thermostatScale;
    const target = Math.min(
      Math.min(view.max, high),
      Math.max(
        Math.max(view.min, low),
        Math.round(value / view.step) * view.step,
      ),
    );
    const pending = this.pendingTargets.get(zone.entity) || {};
    clearTimeout(pending.commit);
    clearTimeout(pending.expiry);
    pending.value = Number(target.toFixed(1));
    pending.state = "draft";
    if (delay !== null)
      pending.commit = setTimeout(() => this.commitTarget(zone.entity), delay);
    this.pendingTargets.set(zone.entity, pending);
    this.updateControlRoom();
  }

  async commitTarget(entity) {
    const pending = this.pendingTargets.get(entity);
    const { value } = pending;
    pending.state = "sent";
    // Nest reports the new setpoint seconds after the call returns; release the preview if it never does.
    pending.expiry = setTimeout(() => this.clearPending(entity), 30000);
    try {
      await this._hass.callService("climate", "set_temperature", {
        entity_id: entity,
        temperature: value,
      });
    } catch (error) {
      if (this.pendingTargets.get(entity)?.value === value)
        this.clearPending(entity);
      this.showError(error);
    }
  }

  clearPending(entity) {
    clearTimeout(this.pendingTargets.get(entity)?.commit);
    clearTimeout(this.pendingTargets.get(entity)?.expiry);
    this.pendingTargets.delete(entity);
    this.updateControlRoom();
  }

  wireThermostat(article, zone) {
    for (const button of article.querySelectorAll(".step"))
      button.addEventListener("click", () => {
        const view = this.zoneView(zone);
        this.setTarget(
          zone,
          view.target + Number(button.dataset.step) * view.step,
          700,
        );
      });
    article.querySelector(".hvac-mode").addEventListener("change", (event) =>
      this.perform("climate", "set_hvac_mode", zone.entity, {
        hvac_mode: event.target.value,
      }),
    );
    const mark = article.querySelector(".target-mark");
    const track = article.querySelector(".track");
    const valueAt = (event) => {
      const rect = track.getBoundingClientRect();
      const [low, high] = this.config.thermostatScale;
      const share = (event.clientX - rect.left) / rect.width;
      return low + Math.min(1, Math.max(0, share)) * (high - low);
    };
    let moved = false;
    mark.addEventListener("keydown", (event) => {
      const direction = {
        ArrowLeft: -1,
        ArrowDown: -1,
        ArrowRight: 1,
        ArrowUp: 1,
      }[event.key];
      if (!direction) return;
      event.preventDefault();
      const view = this.zoneView(zone);
      this.setTarget(zone, view.target + direction * view.step, 700);
    });
    mark.addEventListener("pointerdown", (event) => {
      mark.setPointerCapture(event.pointerId);
      article.classList.add("dragging");
      moved = false;
    });
    mark.addEventListener("pointermove", (event) => {
      if (!article.classList.contains("dragging")) return;
      moved = true;
      this.setTarget(zone, valueAt(event), null);
    });
    mark.addEventListener("pointerup", (event) => {
      if (!article.classList.contains("dragging")) return;
      article.classList.remove("dragging");
      if (moved) this.setTarget(zone, valueAt(event), 0);
    });
    mark.addEventListener("pointercancel", () => {
      article.classList.remove("dragging");
      if (this.pendingTargets.get(zone.entity)?.state === "draft")
        this.clearPending(zone.entity);
    });
  }

  updateControlRoom() {
    if (!this.controlRoom || !this._hass) return;
    const root = this.shadowRoot;
    for (const article of root.querySelectorAll(".zone")) {
      const zone = this.config.thermostats[article.dataset.zone];
      const pending = this.pendingTargets.get(zone.entity);
      if (
        pending?.state === "sent" &&
        this._hass.states[zone.entity]?.attributes.temperature === pending.value
      ) {
        clearTimeout(pending.expiry);
        this.pendingTargets.delete(zone.entity);
      }
      this.updateThermostat(article, this.zoneView(zone));
    }
    const paused = this._hass.states[this.config.override]?.state === "on";
    const policy = root.querySelector(".policy");
    policy.classList.toggle("paused", paused);
    policy.querySelector(".policy-doors").textContent = this.perimeter()
      .map((door) => door.name)
      .join(" · ");
    policy.querySelector(".policy-toggle").textContent = paused
      ? "Resume"
      : "Pause";
  }

  updateThermostat(article, view) {
    const format = (value) =>
      `${Number.isInteger(value) ? value : value.toFixed(1)}${view.unit}`;
    article.classList.toggle("unavailable", !view.available);
    article.querySelector(".action").textContent = view.available
      ? (view.attributes.hvac_action || "").replaceAll("_", " ")
      : "Unavailable";
    const modes = view.attributes.hvac_modes || [];
    const select = article.querySelector(".hvac-mode");
    if (select.dataset.modes !== modes.join()) {
      select.dataset.modes = modes.join();
      select.innerHTML = modes
        .map(
          (mode) =>
            `<option value="${escapeXml(mode)}">${escapeXml(MODE_NAMES[mode] || mode.replaceAll("_", " "))}</option>`,
        )
        .join("");
    }
    select.hidden = !view.available || !modes.length;
    select.value = view.entity.state;
    const offline = article.querySelector(".offline");
    offline.hidden = view.available;
    if (!view.available) {
      const since = new Date(view.entity.last_changed);
      offline.textContent = `No reading since ${
        since.toDateString() === new Date().toDateString()
          ? since.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
          : since.toLocaleDateString([], { month: "short", day: "numeric" })
      }`;
    }
    const values = [view.current, view.target].filter((v) => v !== null);
    const rule = article.querySelector(".rule");
    rule.hidden = !view.available || !values.length;
    if (rule.hidden) return;
    const [low, high] = this.config.thermostatScale;
    const at = (value) =>
      `${Math.min(100, Math.max(0, ((value - low) / (high - low)) * 100))}%`;
    const measured = article.querySelector(".measured-mark");
    measured.hidden = view.current === null;
    if (view.current !== null) {
      measured.style.left = at(view.current);
      measured.setAttribute("aria-label", `Measured ${format(view.current)}`);
    }
    const [lower, raise] = article.querySelectorAll(".step");
    lower.disabled =
      view.target === null || view.target <= Math.max(view.min, low);
    raise.disabled =
      view.target === null || view.target >= Math.min(view.max, high);
    const target = article.querySelector(".target-mark");
    target.hidden = view.target === null;
    target.classList.toggle("pending", view.pending);
    if (view.target !== null) {
      target.style.left = at(view.target);
      target.setAttribute("aria-valuemin", view.min);
      target.setAttribute("aria-valuemax", view.max);
      target.setAttribute("aria-valuenow", view.target);
      target.setAttribute(
        "aria-valuetext",
        `${format(view.target)}${view.pending ? ", setting" : ""}`,
      );
    }
  }

  setControlRoom(open) {
    this.controlRoom = open;
    if (open) this.listMode = false;
    if (open && this.roomId) {
      this.roomId = null;
      this.renderMap();
      this.renderDetails();
    }
    this.updateMode();
  }

  secureHouse() {
    for (const door of this.perimeter().filter((door) => door.open))
      this.perform(
        door.lock ? "lock" : "cover",
        door.lock ? "lock" : "close_cover",
        door.entity,
      );
  }

  wireThrow(element, tilt, { onThrow, onTap }) {
    const THROW = 130;
    let start = null;
    const distance = (event) => {
      const dx = event.clientX - start.x;
      const dy = event.clientY - start.y;
      return [dx, dy, Math.hypot(dx, dy)];
    };
    element.addEventListener("pointerdown", (event) => {
      start = { x: event.clientX, y: event.clientY };
      element.setPointerCapture(event.pointerId);
      element.classList.add("grab");
    });
    element.addEventListener("pointermove", (event) => {
      if (!start) return;
      const [dx, dy, d] = distance(event);
      element.style.transform = `translate(${dx}px,${dy}px) rotate(${tilt + dx / 10}deg) scale(${1 + Math.min(d, THROW) / 900})`;
      element.style.opacity = Math.max(0.25, 0.94 - d / 320);
      element.classList.toggle("armed", d > THROW);
    });
    const release = (event) => {
      if (!start) return;
      const [dx, dy, d] = distance(event);
      start = null;
      element.classList.remove("grab", "armed");
      if (event.type === "pointerup" && d > THROW) {
        element.style.transform = `translate(${dx * 5}px,${dy * 5}px) rotate(${tilt + dx / 2}deg)`;
        element.style.opacity = 0;
        setTimeout(onThrow, 300);
        return;
      }
      element.style.removeProperty("transform");
      element.style.removeProperty("opacity");
      if (d < 6) onTap();
    };
    element.addEventListener("pointerup", release);
    element.addEventListener("pointercancel", release);
  }

  dismissedPolaroids() {
    return JSON.parse(localStorage.getItem("house-atlas-dismissed") || "{}");
  }

  updatePolaroids() {
    const room = this.rooms.find((room) => room.doorbell);
    if (!room) return;
    const dismissed = this.dismissedPolaroids();
    for (const kind of ["ring", "motion"]) {
      const event = this._hass.states[room.doorbell[kind]];
      const id = event?.attributes.nest_event_id;
      const at = Date.parse(event?.state);
      if (
        !id ||
        !(Date.now() - at < POLAROID_LIFE) ||
        this.polaroids.has(id) ||
        dismissed[id]
      )
        continue;
      const polaroid = {
        id,
        kind,
        at,
        label:
          kind === "ring"
            ? "Ring"
            : { camera_person: "Person", camera_sound: "Sound" }[
                event.attributes.event_type
              ] || "Motion",
        time: new Date(at).toLocaleTimeString([], {
          hour: "numeric",
          minute: "2-digit",
        }),
      };
      this.polaroids.set(id, polaroid);
      this.loadSnapshot(
        polaroid,
        `${room.doorbell.snapshots}/${kind}-${Math.floor(at / 1000) % 1000}.jpg`,
      );
    }
    this.renderPolaroids();
  }

  async loadSnapshot(polaroid, mediaId) {
    const { url } = await this._hass.callWS({
      type: "media_source/resolve_media",
      media_content_id: mediaId,
    });
    // Slots repeat every 1000 seconds, so a file older than the event is an earlier event's frame still awaiting this one.
    const since = Math.floor(polaroid.at / 1000) * 1000;
    for (let attempt = 0; attempt < 10; attempt++) {
      if (!this.polaroids.has(polaroid.id)) return;
      const response = await fetch(this._hass.hassUrl(url), {
        cache: "no-store",
      });
      if (
        response.ok &&
        Date.parse(response.headers.get("last-modified")) >= since
      ) {
        polaroid.photo = URL.createObjectURL(await response.blob());
        this.renderPolaroids();
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }

  dropPolaroid(id) {
    const polaroid = this.polaroids.get(id);
    if (polaroid.photo) URL.revokeObjectURL(polaroid.photo);
    this.polaroids.delete(id);
    for (const dialog of this.shadowRoot.querySelectorAll(".lightbox"))
      if (dialog.dataset.id === id) dialog.close();
  }

  dismissPolaroid(id) {
    const dismissed = Object.fromEntries(
      Object.entries(this.dismissedPolaroids()).filter(
        ([, at]) => Date.now() - at < POLAROID_LIFE,
      ),
    );
    dismissed[id] = this.polaroids.get(id).at;
    localStorage.setItem("house-atlas-dismissed", JSON.stringify(dismissed));
    this.dropPolaroid(id);
    this.renderPolaroids();
  }

  openPolaroid(id) {
    const polaroid = this.polaroids.get(id);
    const room = this.rooms.find((room) => room.doorbell);
    const dialog = document.createElement("dialog");
    dialog.className = "lightbox";
    dialog.dataset.id = id;
    dialog.setAttribute("aria-label", `${polaroid.label} at ${polaroid.time}`);
    dialog.innerHTML = `<figure>${polaroid.photo ? `<img src="${polaroid.photo}" alt="">` : '<span class="photo"><ha-icon icon="mdi:doorbell-video"></ha-icon></span>'}<figcaption class="caption"><span>${polaroid.label} ·</span> <span>${polaroid.time}</span></figcaption></figure><div class="lightbox-actions"><button class="live"><ha-icon icon="mdi:cctv"></ha-icon>Live</button><button class="dismiss"><ha-icon icon="mdi:close"></ha-icon>Dismiss</button></div>`;
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    dialog.querySelector(".live").addEventListener("click", () => {
      dialog.close();
      this.selectRoom(room.id);
      this.shadowRoot
        .querySelector(".detail-host")
        .scrollIntoView({ block: "nearest" });
    });
    dialog.querySelector(".dismiss").addEventListener("click", () => {
      dialog.close();
      this.dismissPolaroid(id);
    });
    dialog.addEventListener("close", () => dialog.remove());
    this.shadowRoot.append(dialog);
    dialog.showModal();
  }

  renderPolaroids() {
    clearTimeout(this.polaroidExpiry);
    for (const polaroid of this.polaroids.values())
      if (Date.now() - polaroid.at >= POLAROID_LIFE)
        this.dropPolaroid(polaroid.id);
    const next = Math.min(...[...this.polaroids.values()].map((p) => p.at));
    if (this.polaroids.size)
      this.polaroidExpiry = setTimeout(
        () => this.renderPolaroids(),
        next + POLAROID_LIFE - Date.now(),
      );
    const layer = this.shadowRoot.querySelector(".map-wrap .pins");
    const room = this.floor.rooms.find((room) => room.doorbell);
    if (!layer) return;
    const shown = room
      ? [...this.polaroids.values()].sort((a, b) => b.at - a.at).slice(0, 3)
      : [];
    const existing = new Map(
      [...layer.children].map((pin) => [pin.dataset.id, pin]),
    );
    for (const [id, pin] of existing)
      if (!shown.some((polaroid) => polaroid.id === id)) pin.remove();
    shown.forEach((polaroid, index) => {
      let pin = existing.get(polaroid.id);
      if (!pin) {
        const tilt = (polaroid.at % 13) - 6;
        pin = document.createElement("div");
        pin.className = "pin";
        pin.dataset.id = polaroid.id;
        pin.innerHTML = `<div class="polaroid" role="button" tabindex="0" data-polaroid="${polaroid.id}" style="--tilt:${tilt}deg" aria-label="${polaroid.label} at ${polaroid.time}. Opens the snapshot; drag off to dismiss."><span class="photo"><ha-icon icon="mdi:doorbell-video"></ha-icon></span>${polaroid.kind === "ring" ? '<b class="ring-stamp">Ring</b>' : ""}<span class="caption"><span>${polaroid.label} ·</span> <span>${polaroid.time}</span></span></div>`;
        pin
          .querySelector(".photo")
          .style.setProperty(
            "animation-delay",
            `${(polaroid.at - Date.now()) / 1000}s`,
          );
        this.wireThrow(pin.firstChild, tilt, {
          onThrow: () => this.dismissPolaroid(polaroid.id),
          onTap: () => this.openPolaroid(polaroid.id),
        });
        layer.append(pin);
      }
      const [x, y] = room.doorbell.pin;
      pin.style.left = `calc(${(x / this.floor.width) * 100}% - ${index * 18}px)`;
      pin.style.top = `calc(${(y / this.floor.height) * 100}% - ${index * 10}px)`;
      pin.style.zIndex = shown.length - index;
      if (polaroid.photo)
        pin.querySelector(".photo").style.backgroundImage =
          `url(${polaroid.photo})`;
    });
  }

  mapEntities(floor) {
    return floor.rooms.flatMap((room) => [
      ...(room.pickup ? [room.pickup.entity] : []),
      ...(room.vehicles || []).map((vehicle) => vehicle.entity),
    ]);
  }

  summary(room) {
    const ids = room.lights || (room.entity ? [room.entity] : []);
    if (!ids.length) return room.note || "No connected devices";
    const states = ids.map(
      (id) => this._hass?.states[id]?.state || "unavailable",
    );
    if (!room.lights) return states[0].replaceAll("_", " ");
    const on = states.filter((state) => state === "on").length;
    const unavailable = states.filter(
      (state) => state === "unavailable",
    ).length;
    const unknown = states.filter((state) => state === "unknown").length;
    return [
      `${on} on`,
      unavailable && `${unavailable} unavailable`,
      unknown && `${unknown} unknown`,
    ]
      .filter(Boolean)
      .join(" · ");
  }

  render() {
    const [low, high] = this.config.thermostatScale;
    const ticks = Array.from({ length: high - low + 1 }, (_, i) => {
      const left = `${(i / (high - low)) * 100}%`;
      return `<span class="tick" style="left:${left}"></span><span class="tick-label" style="left:${left}">${low + i}</span>`;
    }).join("");
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --atlas-bg: var(--house-atlas-bg, var(--primary-background-color));
          --atlas-surface: var(--house-atlas-surface, var(--card-background-color));
          --atlas-selected: var(--house-atlas-selected, var(--secondary-background-color));
          --atlas-fg: var(--house-atlas-fg, var(--primary-text-color));
          --atlas-muted: var(--house-atlas-muted, var(--secondary-text-color));
          --atlas-border: var(--house-atlas-border, var(--divider-color));
          --atlas-wall: var(--house-atlas-wall, var(--secondary-text-color));
          --atlas-accent: var(--house-atlas-accent, var(--primary-color));
          --atlas-on-accent: var(--house-atlas-on-accent, var(--text-primary-color));
          --atlas-light: var(--house-atlas-light, var(--state-light-active-color));
          --atlas-error: var(--house-atlas-error, var(--error-color));
          --atlas-warning: var(--house-atlas-warning, var(--warning-color));
          --atlas-secure: var(--house-atlas-secure, var(--success-color));
          display: block; container-type: inline-size;
          position: relative; z-index: 0; isolation: isolate;
          background: var(--atlas-bg); color: var(--atlas-fg);
          font-family: var(--paper-font-body1_-_font-family, Arial, sans-serif);
          min-height: calc(100dvh - 56px);
        }
        * { box-sizing: border-box; }
        [hidden] { display: none !important; }
        button { font: inherit; color: inherit; cursor: pointer; touch-action: manipulation; min-height: 48px; -webkit-user-select: none; user-select: none; -webkit-touch-callout: none; }
        button:focus-visible { outline: 3px solid var(--atlas-accent); outline-offset: 3px; }
        :host(:not([keyboard-navigation])) button:focus-visible { outline: none; }
        button:disabled { opacity: .45; cursor: default; }
        button:active { transform: translateY(1px); }
        .atlas { max-width: 1440px; margin: auto; padding: 22px 26px 30px; }
        .top { display: flex; align-items: end; justify-content: space-between; gap: 20px; border-bottom: 1px solid var(--atlas-border); padding-bottom: 18px; }
        .eyebrow { font-size: 10px; letter-spacing: .22em; text-transform: uppercase; color: var(--atlas-muted); margin-bottom: 6px; }
        h1 { font: 400 clamp(28px,4vw,42px)/1.1 Georgia,serif; margin: 0; }
        .tools { display: flex; align-items: center; gap: 8px; }
        .mode { background: transparent; border: 1px solid var(--atlas-border); border-radius: 6px; padding: 0 14px; font-size: 12px; white-space: nowrap; }
        .floors { display: flex; gap: 4px; margin: 12px 0 18px; border-bottom: 1px solid var(--atlas-border); }
        .floors button { flex: 1; background: none; border: 0; border-bottom: 3px solid transparent; padding: 12px 8px; }
        .floors button[aria-current=true] { border-color: var(--atlas-accent); color: var(--atlas-accent); font-weight: 600; }
        .layout { display: block; }
        .detail-host:empty { display: none; }
        .map-panel { min-width: 0; }
        .map-wrap { width: 100%; margin: auto; }
        .map-wrap.focused { max-width: 800px; }
        .floor-stage { position: relative; width: min(100%,680px); aspect-ratio: var(--floor-ratio); margin: auto; }
        .floor-stage > floorplan-card { display: block; width: 100%; height: 100%; }
        .light-map { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
        .light-field { isolation: isolate; opacity: .55; }
        .glow { mix-blend-mode: screen; }
        .scene-dock { width: 100%; margin: 16px auto 0; }
        .scene-dock .scenes { gap: 4px; }
        .scene-dock .scene { background: transparent; padding: 0 10px; font-size: 12px; }
        .atlas-dialog { padding: 16px; color: var(--atlas-fg); background: var(--atlas-bg); border: 1px solid var(--atlas-border); border-radius: 12px; width: 340px; max-width: calc(100vw - 24px); max-height: calc(100dvh - 24px); overflow: auto; box-shadow: 0 12px 48px #0005; }
        .atlas-dialog:focus { outline: none; }
        .atlas-dialog::backdrop { background: #0003; }
        .atlas-dialog header { display: flex; align-items: center; gap: 8px; }
        .atlas-dialog h2 { margin: 0; flex: 1; font: 400 23px Georgia,serif; }
        .dialog-body { display: grid; gap: 10px; }
        .dialog-body label { font-size: 13px; }
        .dialog-body output { float: right; color: var(--atlas-muted); }
        .dialog-body input { display: block; width: 100%; min-height: 48px; accent-color: var(--atlas-accent); }
        .dialog-body ha-hs-color-picker { display: block; width: min(100%,240px, max(140px,calc(100dvh - 420px))); margin: auto; aspect-ratio: 1; touch-action: none; }
        .dialog-body ha-hs-color-picker:not(:defined) { display: none; }
        .dialog-body ha-hs-color-picker:defined + .wheel-loading { display: none; }
        .white-control input { accent-color: #dfb67e; background: linear-gradient(90deg,#ffa757,#fff4df,#b9d8ff); border-radius: 24px; }
        .white-control > span { display: flex; justify-content: space-between; font-size: 12px; color: var(--atlas-muted); }
        .focus-heading { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
        .focus-heading h2 { font: 400 28px/1.2 Georgia,serif; margin: 0; }
        .room-stage { position: relative; height: clamp(300px,52dvh,520px); overflow: hidden; border: 1px solid var(--atlas-border); border-radius: 10px; background: var(--atlas-bg); }
        .map-wrap, .atlas-dialog { -webkit-user-select: none; user-select: none; -webkit-touch-callout: none; }
        .focus-map, .fixture-layer { position: absolute; inset: 0; width: 100%; height: 100%; }
        .focus-map .room-outline { fill: var(--atlas-surface); stroke: var(--atlas-accent); stroke-width: 1.5; }
        .focus-map .neighbor { fill: none; stroke: var(--atlas-border); opacity: .35; }
        .focus-map .opening { fill: none; stroke: var(--atlas-bg); stroke-width: 4; }
        .partitions { fill: none; stroke: var(--atlas-wall); stroke-width: 1.6; pointer-events: none; }
        .fixture-layer { pointer-events: none; }
        .room-power { position: absolute; width: 44px; height: 44px; min-height: 44px; padding: 8px; translate: -50% -50%; pointer-events: auto; border: 0; background: transparent; color: var(--atlas-muted); }
        .room-power svg { width: 28px; height: 20px; }
        .room-power[aria-pressed="true"] { color: var(--atlas-accent); }
        .room-power .switch-thumb { cx: 8px; }
        .room-power[aria-pressed="true"] .switch-thumb { cx: 20px; }
        .room-power:disabled { opacity: .4; }
        .fixture { position: absolute; width: 56px; height: 56px; min-height: 56px; padding: 10px; translate: -50% -50%; border-radius: 50%; background: transparent; border: 0; pointer-events: auto; display: grid; place-items: center; color: var(--fixture-color,var(--atlas-muted)); -webkit-touch-callout: none; -webkit-user-select: none; user-select: none; }
        .fixture > svg, .fixture > ha-icon { width: 26px; height: 26px; filter: drop-shadow(0 1px 1px var(--atlas-bg)); }
        .fixture > * { pointer-events: none; }
        .fixture.door { border-radius: 4px; padding: 0; }
        .fixture.door > svg { position: absolute; left: 50%; top: 50%; translate: -50% -50%; overflow: visible; }
        .fixture.garage > svg { overflow: hidden; }
        .door-structure { color: var(--atlas-fg); fill: var(--atlas-bg); stroke: currentColor; stroke-width: 1.5; }
        .door-swing { fill: none; stroke-dasharray: 3 3; opacity: .5; }
        .door-state { position: absolute; width: 22px; height: 22px; background: var(--atlas-bg); border-radius: 4px; display: grid; place-items: center; pointer-events: auto; }
        .door-state svg { width: 16px; height: 16px; }
        .door.garage .door-state { left: calc(50% - 11px); top: calc(50% - 11px); }
        .door.front .door-state { left: calc(50% - 11px); top: 100%; }
        .atlas-dialog.local-zoom { padding: 0; margin: 0; border-radius: 50%; overflow: hidden; }
        .local-zoom::backdrop { background: transparent; }
        .local-zoom .dialog-body, .zoom-stage { width: 100%; height: 100%; }
        .zoom-stage { position: relative; overflow: hidden; background: var(--atlas-bg); }
        .zoom-background { position: absolute; inset: 0; pointer-events: none; }
        .zoom-stage .fixture span { position: absolute; top: 48px; left: 50%; translate: -50% 0; width: 96px; color: var(--atlas-fg); font-size: 11px; line-height: 14px; }
        .fixture.selected { outline: 2px solid var(--atlas-accent); }
        .fixture.unavailable { border: 1px dashed var(--atlas-error); }
        .details { max-width: 800px; margin: 16px auto 0; }
        .detail-heading { position: sticky; top: 0; background: var(--atlas-bg); z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 22px 20px 16px; border-bottom: 1px solid var(--atlas-border); }
        .detail-heading h2 { font: 400 27px/1.15 Georgia,serif; margin: 0; }
        .close { flex: 0 0 48px; width: 48px; background: none; border: 0; font-size: 28px; font-weight: 300; }
        .detail-body { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; }
        .detail-body > hui-picture-entity-card, .detail-body > .lock-actions { grid-column: 1/-1; }
        .status { font-size: 12px; margin: 8px 0 0; color: var(--atlas-muted); }
        .scenes { display: flex; flex-wrap: wrap; gap: 8px; }
        .scene { background: var(--atlas-selected); border: 1px solid var(--atlas-border); border-radius: 6px; padding: 0 14px; font-size: 13px; }
        .section-label { margin: 10px 0 0; font-size: 10px; text-transform: uppercase; letter-spacing: .16em; color: var(--atlas-muted); }
        .error { background: var(--atlas-bg); color: var(--atlas-fg); padding: 12px; border: 1px solid var(--atlas-error); border-radius: 6px; font-size: 13px; }
        .error:empty { display: none; }
        .room-list { display: grid; gap: 8px; }
        .room-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; width: 100%; text-align: left; padding: 15px 16px; border: 1px solid var(--atlas-border); background: var(--atlas-surface); border-radius: 6px; }
        .room-row[aria-pressed=true] { border-color: var(--atlas-accent); background: var(--atlas-selected); }
        .room-row small { display: block; font-size: 12px; margin-top: 6px; color: var(--atlas-muted); }
        .lock-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .lock-action { border: 1px solid var(--atlas-accent); background: var(--atlas-accent); color: var(--atlas-on-accent); border-radius: 6px; }
        .lock-action.secondary { background: transparent; color: var(--atlas-accent); }
        .muted { color: var(--atlas-muted); font-size: 13px; line-height: 1.6; }
        .map-wrap[hidden], .room-list[hidden] { display: none; }
        .strip { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0,1fr); gap: 10px; margin: 18px 0 0; }
        .g-cell { min-width: 0; display: flex; align-items: center; gap: 14px; border: 1px solid var(--atlas-border); background: var(--atlas-surface); border-radius: 8px; padding: 10px 10px 10px 16px; }
        .g-cell[hidden] { display: none; }
        .g-cell ha-icon { color: var(--atlas-muted); flex: 0 0 auto; }
        .g-cell.warn { border-color: var(--atlas-warning); background: color-mix(in srgb, var(--atlas-warning) 16%, var(--atlas-bg)); }
        .g-lights ha-icon { color: var(--atlas-light); }
        .g-cell.warn ha-icon { color: var(--atlas-warning); }
        .g-text { flex: 1; min-width: 0; }
        .g-text b { display: block; font-weight: 600; font-size: 14px; }
        .g-text small { display: block; font-size: 12px; color: var(--atlas-muted); margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .g-cell button { background: var(--atlas-bg); border: 1px solid var(--atlas-border); border-radius: 6px; padding: 0 14px; font-size: 12px; white-space: nowrap; }
        .desk-title { font: 400 24px/1.15 Georgia,serif; margin: 22px 0 16px; padding-bottom: 12px; border-bottom: 1px solid var(--atlas-border); }
        .desk { display: grid; grid-template-columns: repeat(var(--zones),minmax(0,1fr)) minmax(240px,.7fr); gap: 16px; align-items: stretch; }
        .instrument { min-width: 0; border: 1px solid var(--atlas-border); background: var(--atlas-surface); border-radius: 8px; padding: 16px 18px 18px; }
        .instrument-head { display: flex; align-items: center; gap: 12px; min-height: 36px; }
        .instrument-head h2 { font: 400 22px/1.2 Georgia,serif; margin: 0 auto 0 0; }
        .action { font-size: 12px; color: var(--atlas-muted); text-transform: capitalize; }
        .hvac-mode { appearance: none; height: 32px; padding: 0 28px 0 10px; border: 1px solid var(--atlas-border); border-radius: 6px; background: linear-gradient(45deg, transparent 50%, currentColor 50%) right 15px center/5px 5px no-repeat, linear-gradient(135deg, currentColor 50%, transparent 50%) right 10px center/5px 5px no-repeat, var(--atlas-bg); color: inherit; font: inherit; font-size: 12px; cursor: pointer; }
        .hvac-mode:focus-visible { outline: 3px solid var(--atlas-accent); outline-offset: 2px; }
        .zone.unavailable .action { color: var(--atlas-error); }
        .rule { display: flex; align-items: flex-start; gap: 14px; padding: 18px 0 34px; }
        .track { position: relative; flex: 1; height: 40px; }
        .track::before { content: ""; position: absolute; left: 0; right: 0; top: 20px; border-top: 1px solid var(--atlas-wall); }
        .tick { position: absolute; top: 10px; width: 1px; height: 10px; translate: -50% 0; background: var(--atlas-wall); }
        .tick-label { position: absolute; top: 25px; line-height: 1; translate: -50% 0; font-size: 11px; color: var(--atlas-muted); pointer-events: none; }
        .measured-mark { position: absolute; top: 0; width: 6px; height: 22px; translate: -50% 0; background: var(--atlas-fg); border-radius: 3px; pointer-events: none; }
        .target-mark { position: absolute; top: 0; width: 44px; height: 72px; translate: -50% 0; cursor: grab; touch-action: none; outline: none; }
        .target-mark::before { content: ""; position: absolute; left: 50%; top: 20px; height: 22px; width: 2px; translate: -50% 0; background: var(--atlas-accent); }
        .grip { position: absolute; left: 50%; top: 40px; width: 6px; height: 22px; translate: -50% 0; border-radius: 3px; background: var(--atlas-accent); transition: width .12s, box-shadow .12s; }
        .target-mark:hover .grip { width: 8px; }
        .dragging .grip { width: 10px; box-shadow: 0 3px 8px rgb(0 0 0 / .3); }
        .target-mark:focus-visible .grip { outline: 2px solid var(--atlas-accent); outline-offset: 3px; }
        .target-mark.pending { opacity: .55; }
        .dragging .target-mark { cursor: grabbing; }
        .step { position: relative; flex: 0 0 30px; height: 30px; min-height: 0; margin-top: 5px; display: grid; place-items: center; padding: 0 0 2px; border: 1px solid var(--atlas-border); border-radius: 50%; background: var(--atlas-bg); font-size: 18px; line-height: 1; }
        .step::after { content: ""; position: absolute; inset: -7px; }
        .step:hover:not(:disabled) { border-color: var(--atlas-light); background: color-mix(in srgb, var(--atlas-light) 35%, var(--atlas-bg)); }
        .step:disabled { visibility: hidden; }
        .offline { margin: 10px 0 0; font-size: 13px; color: var(--atlas-muted); }
        .policy { display: flex; flex-direction: column; gap: 12px; }
        .policy-doors { margin: 0; font-size: 13px; line-height: 1.5; color: var(--atlas-muted); }
        .policy-toggle { margin-top: auto; border: 1px solid var(--atlas-border); background: var(--atlas-bg); border-radius: 6px; }
        .policy.paused .policy-toggle { border-color: var(--atlas-accent); background: var(--atlas-accent); color: var(--atlas-on-accent); }
        .lamps { grid-column: 1 / -1; }
        .lamp { display: grid; grid-template-rows: auto auto; align-content: start; }
        .lamp-scenes .section-label { margin-top: 12px; }
        .lamp-scenes .section-label + .scenes { margin-top: 8px; }
        .lamp-tiles { display: grid; grid-template-columns: repeat(auto-fill,minmax(280px,1fr)); gap: 12px; margin-top: 12px; }
        .map-panel { position: relative; }
        .stamp { position: absolute; left: 4%; top: 46%; z-index: 2; transform: rotate(-11deg); padding: 10px 18px; border: 4px double var(--atlas-accent); border-radius: 4px; background: color-mix(in srgb, var(--atlas-bg) 90%, transparent); color: var(--atlas-accent); opacity: .94; font: 700 clamp(15px,3.2cqw,24px)/1.1 Georgia,serif; letter-spacing: .12em; text-transform: uppercase; text-align: center; box-shadow: 0 1px 0 #28282818; touch-action: none; user-select: none; cursor: grab; transition: transform .4s cubic-bezier(.2,.9,.3,1.25), opacity .4s; animation: thunk .35s cubic-bezier(.3,1.6,.5,1); }
        .stamp[hidden] { display: none; }
        .stamp small { display: block; margin-top: 4px; font: 400 11px/1.3 Arial,sans-serif; letter-spacing: .06em; text-transform: none; }
        .stamp.grab { transition: none; cursor: grabbing; box-shadow: 0 10px 24px #28282840; }
        .stamp.armed { border-style: dashed; }
        .stamp.nudge { animation: nudge .45s; }
        .stamp .let-go, .stamp.armed .since { display: none; }
        .stamp.armed .let-go { display: inline; }
        .map-wrap { position: relative; }
        .pins { position: absolute; inset: 0; pointer-events: none; }
        .pin { position: absolute; translate: -50% -100%; width: clamp(72px,21%,116px); pointer-events: auto; animation: pin .5s cubic-bezier(.3,1.5,.5,1) both; }
        .polaroid { position: relative; display: block; padding: 7% 7% 0; background: #fbf8ef; color: #3c3836; border-radius: 2px; box-shadow: 0 2px 6px #28282840, 0 0 0 1px #28282814; transform: rotate(var(--tilt)); touch-action: none; user-select: none; cursor: grab; transition: transform .4s cubic-bezier(.2,.9,.3,1.25), opacity .4s; }
        .polaroid::before { content: ""; position: absolute; z-index: 1; top: -5px; left: 50%; translate: -50% 0; width: 11px; height: 11px; border-radius: 50%; background: var(--atlas-error); box-shadow: 0 1px 2px #28282880; }
        .polaroid:focus-visible { outline: 3px solid var(--atlas-accent); outline-offset: 3px; }
        .polaroid.grab { transition: none; cursor: grabbing; box-shadow: 0 12px 26px #28282855; }
        .polaroid.armed { outline: 2px dashed var(--atlas-error); outline-offset: 4px; }
        .photo { display: grid; place-items: center; aspect-ratio: 3/4; background: #32302f center/cover no-repeat; color: #7c6f64; animation: age 900s linear both; }
        .photo[style*=background-image] ha-icon { display: none; }
        .caption { display: block; padding: 7px 0 9px; font: italic 12px/1.2 Georgia,serif; text-align: center; text-wrap: balance; }
        .caption span { white-space: nowrap; }
        .lightbox { border: 0; padding: 0; background: none; max-width: none; max-height: none; overflow: visible; }
        .lightbox::backdrop { background: #1d2021e0; }
        .lightbox figure { margin: 0; padding: 14px 14px 0; background: #fbf8ef; color: #3c3836; border-radius: 2px; box-shadow: 0 16px 40px #00000080; transform: rotate(-1deg); }
        .lightbox img, .lightbox .photo { display: grid; width: min(86vw, 68vh); aspect-ratio: 1; object-fit: cover; }
        .lightbox .caption { padding: 12px 0 16px; font-size: 20px; }
        .lightbox-actions { display: flex; justify-content: center; gap: 12px; margin-top: 20px; }
        .lightbox-actions button { display: flex; align-items: center; gap: 8px; padding: 0 20px; background: #fbf8ef; color: #3c3836; border: 0; border-radius: 6px; font-size: 15px; }
        .lightbox-actions .dismiss { background: none; color: #fbf8ef; border: 1px solid #fbf8ef80; }
        .ring-stamp { position: absolute; top: 22%; left: 50%; translate: -50% 0; transform: rotate(-14deg); padding: 2px 7px; border: 3px double #cc241d; background: #fbf8efd9; color: #cc241d; font: 700 15px/1.1 Georgia,serif; letter-spacing: .14em; text-transform: uppercase; }
        @keyframes pin { from { transform: translateY(-36px) rotate(10deg) scale(1.2); opacity: 0; } }
        @keyframes age { to { filter: sepia(.75) contrast(.8) brightness(1.1); opacity: .5; } }
        @keyframes thunk { from { transform: rotate(-11deg) scale(1.8); opacity: 0; } }
        @keyframes nudge { 25% { transform: rotate(-6deg) translateX(10px); } 60% { transform: rotate(-14deg) translateX(-4px); } }
        @container(max-width:1000px) {
          .atlas { display: flex; flex-direction: column; padding: 16px 12px 24px; }
          .strip { order: 1; grid-auto-flow: row; grid-auto-columns: auto; gap: 8px; margin-top: 16px; }
          .atlas > .error { order: 2; }
          .g-cell { padding: 6px 6px 6px 12px; gap: 10px; }
          .top { padding-bottom: 12px; }
          .eyebrow { font-size: 9px; }
          .tools { gap: 6px; }
          .mode { padding: 0 10px; }
          .layout { display: block; }
          .map-wrap { width: 100%; min-width: 0; max-width: 520px; }
          .floor-stage { width: 100%; min-width: 0; }
          .atlas-dialog:not(.local-zoom) { position: fixed; inset: auto 0 12px !important; margin: 0 auto !important; width: min(520px,calc(100% - 24px)); }
          .floors { margin-bottom: 12px; }
          .detail-heading { padding: 24px 18px 12px; }
          .detail-heading h2 { font-size: 26px; }
          .detail-body { grid-template-columns: minmax(0,1fr); }
          .focus-heading { gap: 12px; }
          .focus-heading h2 { font-size: 24px; }
          .room-stage { height: 360px; }
          .desk-title { margin: 16px 0 12px; }
          .desk { grid-template-columns: minmax(0,1fr); gap: 12px; }
          .instrument { padding: 14px 16px 16px; }
        }
        @media(max-height:500px) {
          .atlas { padding-top: 8px; }
          .top { padding-bottom: 6px; }
          .eyebrow { display: none; }
          .floors { margin-top: 4px; }
        }
      </style>
      <main class="atlas">
        <header class="top"><div><div class="eyebrow">Loch Highland</div><h1>House</h1></div><div class="tools"><button class="mode control-toggle" aria-pressed="false">Control Room</button><button class="mode list-toggle" aria-pressed="false">Room list</button></div></header>
        <section class="strip" aria-label="Suggested actions" hidden>
          <div class="g-cell g-lights" hidden><ha-icon icon="mdi:lightbulb-group-outline"></ha-icon><div class="g-text"><b></b><small></small></div><button>Turn all off</button></div>
          <div class="g-cell g-secure warn" hidden><ha-icon icon="mdi:shield-alert-outline"></ha-icon><div class="g-text"><b></b><small></small></div><button>Secure</button></div>
        </section>
        <section class="control-room" aria-label="Control Room" hidden>
          <h2 class="desk-title">Control Room</h2>
          <div class="desk" style="--zones:${this.config.thermostats.length}">
            ${this.config.thermostats
              .map(
                (zone, index) =>
                  `<article class="instrument zone" data-zone="${index}"><header class="instrument-head"><h2>${escapeXml(zone.name)}</h2><span class="action"></span><select class="hvac-mode" aria-label="${escapeXml(zone.name)} mode"></select></header><p class="offline" hidden></p><div class="rule"><button class="step" data-step="-1" aria-label="Lower ${escapeXml(zone.name)} target">‹</button><div class="track"><div class="ticks">${ticks}</div><div class="target-mark" role="slider" tabindex="0" aria-label="${escapeXml(zone.name)} target temperature"><span class="grip"></span></div><div class="measured-mark" role="img"></div></div><button class="step" data-step="1" aria-label="Raise ${escapeXml(zone.name)} target">›</button></div></article>`,
              )
              .join("")}
            <article class="instrument policy"><header class="instrument-head"><h2>Auto-lock &amp; close</h2></header><p class="policy-doors"></p><button class="policy-toggle"></button></article>
            ${this.lamps.length ? '<article class="instrument lamps"><header class="instrument-head"><h2>Lamps</h2></header><div class="lamp-tiles"></div></article>' : ""}
          </div>
        </section>
        <nav class="floors" aria-label="Floors">${this.config.floors.map((floor) => `<button data-floor="${escapeXml(floor.id)}" aria-current="${floor.id === this.floorId}">${escapeXml(floor.name)}</button>`).join("")}</nav>
        <div class="layout"><section class="map-panel" aria-label="Floor map"><div class="map-wrap"></div><div class="room-list" hidden></div><div class="stamp" hidden>Auto-lock paused<small><span class="since"></span><span class="let-go">let go to resume</span></small></div></section><div class="detail-host"></div></div>
        <p class="error" role="alert"></p>
      </main>`;
    this.shadowRoot.querySelectorAll("[data-floor]").forEach((button) =>
      button.addEventListener("click", () => {
        this.floorId = button.dataset.floor;
        this.roomId = null;
        this.deviceId = null;
        this.shadowRoot
          .querySelectorAll("[data-floor]")
          .forEach((tab) =>
            tab.setAttribute(
              "aria-current",
              String(tab.dataset.floor === this.floorId),
            ),
          );
        this.renderMap();
        this.renderDetails();
      }),
    );
    this.shadowRoot
      .querySelector(".list-toggle")
      .addEventListener("click", () => {
        const listMode = this.controlRoom || !this.listMode;
        this.setControlRoom(false);
        this.listMode = listMode;
        this.selectRoom(null);
        this.updateMode();
      });
    this.shadowRoot
      .querySelector(".control-toggle")
      .addEventListener("click", () => this.setControlRoom(!this.controlRoom));
    this.shadowRoot
      .querySelector(".g-lights button")
      .addEventListener("click", () =>
        this.perform("light", "turn_off", [
          ...this.rooms
            .filter((room) => room.lights?.length)
            .flatMap((room) => this.roomLightTargets(room)),
          ...this.lamps.map((lamp) => lamp.entity),
        ]),
      );
    this.shadowRoot
      .querySelector(".g-secure button")
      .addEventListener("click", () => this.secureHouse());
    this.shadowRoot
      .querySelectorAll(".zone")
      .forEach((article) =>
        this.wireThermostat(
          article,
          this.config.thermostats[article.dataset.zone],
        ),
      );
    this.shadowRoot
      .querySelector(".policy-toggle")
      .addEventListener("click", () =>
        this.perform(
          "input_boolean",
          this._hass.states[this.config.override]?.state === "on"
            ? "turn_off"
            : "turn_on",
          this.config.override,
        ),
      );
    const stamp = this.shadowRoot.querySelector(".stamp");
    this.wireThrow(stamp, -11, {
      onThrow: () =>
        this.perform("input_boolean", "turn_off", this.config.override),
      onTap: () => {
        stamp.classList.remove("nudge");
        void stamp.offsetWidth;
        stamp.classList.add("nudge");
      },
    });
    if (this._hass) this.updateGlobal();
    this.shadowRoot
      .querySelector(".atlas")
      .addEventListener("ll-custom", (event) => {
        if (event.detail.atlas_room) {
          event.stopPropagation();
          // Floorplan still fires the tap when a long press is released; it holds at 400 ms.
          const held = performance.now() - this.pressedAt >= 400;
          const room = this.floor.rooms.find(
            (room) => room.id === event.detail.atlas_room,
          );
          if (!(held && room?.hold)) this.selectRoom(event.detail.atlas_room);
        } else if (event.detail.atlas_hold) {
          event.stopPropagation();
          this.hold(event.detail.atlas_hold);
        }
      });
    const mapWrap = this.shadowRoot.querySelector(".map-wrap");
    mapWrap.addEventListener("contextmenu", (event) => event.preventDefault());
    mapWrap.addEventListener(
      "pointerdown",
      () => (this.pressedAt = performance.now()),
      true,
    );
    this.shadowRoot
      .querySelector(".atlas")
      .addEventListener("keydown", (event) => {
        if (event.key === "Escape" && this.roomId) {
          event.stopPropagation();
          this.selectRoom(null);
        } else if (event.key === "Escape" && this.controlRoom) {
          event.stopPropagation();
          this.setControlRoom(false);
        }
        if (event.key === "Enter" || event.key === " ") {
          const target = event
            .composedPath()
            .find((node) => node.dataset?.room || node.dataset?.polaroid);
          if (target?.dataset.polaroid) {
            event.preventDefault();
            this.openPolaroid(target.dataset.polaroid);
          } else if (target) {
            event.preventDefault();
            this.selectRoom(target.dataset.room);
          }
        }
      });
    if (this.helpers) {
      this.renderMap();
      this.renderDetails();
      this.renderLamps();
    }
  }

  updateMode() {
    const root = this.shadowRoot;
    const list = root.querySelector(".list-toggle");
    const listing = this.listMode && !this.controlRoom;
    list.textContent = listing ? "Floor map" : "Room list";
    list.setAttribute("aria-pressed", String(listing));
    const control = root.querySelector(".control-toggle");
    control.textContent = this.controlRoom ? "Floor map" : "Control Room";
    control.setAttribute("aria-pressed", String(this.controlRoom));
    root.querySelector(".control-room").hidden = !this.controlRoom;
    root.querySelector(".floors").hidden = this.controlRoom;
    root.querySelector(".layout").hidden = this.controlRoom;
    root.querySelector(".map-wrap").hidden = this.listMode;
    root.querySelector(".room-list").hidden = !this.listMode;
    this.updateList();
    this.updateControlRoom();
  }

  selectRoom(id) {
    if (
      id &&
      !this.floor.rooms.some((room) => room.id === id && this.hasDevices(room))
    )
      return;
    this.roomId = id;
    this.deviceId = null;
    if (id && this.roomPlacements.length) this.listMode = false;
    this.renderMap();
    this.renderDetails();
    if (id && this.keyboardNavigation)
      this.shadowRoot
        .querySelector(".back-floor, .detail-body button")
        ?.focus({ preventScroll: true });
    else if (!id && this.keyboardNavigation)
      this.shadowRoot
        .querySelector(`[data-floor="${this.floorId}"]`)
        ?.focus({ preventScroll: true });
    else if (!id) this.shadowRoot.activeElement?.blur();
  }

  renderMap() {
    if (!this.helpers || !this._hass) return;
    this.updateGlobal();
    this.shadowRoot
      .querySelector(".layout")
      .classList.toggle("focused", this.roomFocus);
    this.shadowRoot
      .querySelector(".map-wrap")
      .classList.toggle("focused", this.roomFocus);
    if (this.roomFocus) {
      this.updateMode();
      this.renderRoomMap();
      return;
    }
    const floor = this.floor;
    const styles = `
      svg{font-family:Arial,sans-serif;color:var(--atlas-fg);background:var(--atlas-bg);-webkit-user-select:none;user-select:none;-webkit-touch-callout:none}
      /* Floorplan forces ":host svg *{pointer-events:all!important}"; overlays inside rooms must pass presses through. */
      svg g.vehicle *,svg g.pickup *,svg g.stairs *,svg .partitions{pointer-events:none!important}
      .room.held .wall{animation:held .6s ease-out}
      @keyframes held{40%{fill:var(--atlas-light);stroke:var(--atlas-accent);stroke-width:4}}
      .room{outline:none}
      .room.connected{cursor:pointer}
      .wall{stroke:var(--atlas-wall);stroke-width:1.6;stroke-linejoin:round;fill:var(--atlas-bg)}
      .partitions{fill:none;stroke:var(--atlas-wall);stroke-width:1.6}
      .room.connected .wall{fill:var(--atlas-surface)}
      .room.outdoor .wall{fill:url(#deck);stroke-dasharray:5 3}
      .room:focus-visible .wall,.room.selected .wall{fill:var(--atlas-selected);stroke:var(--atlas-accent);stroke-width:2.5}
      .room.outdoor:focus-visible .wall,.room.outdoor.selected .wall{fill:url(#deck)}
      @media(hover:hover){.room.connected:hover .wall{fill:var(--atlas-selected);stroke:var(--atlas-accent);stroke-width:2.5}.room.outdoor.connected:hover .wall{fill:url(#deck)}}
      .opening{stroke:var(--atlas-bg);stroke-width:5;fill:none;pointer-events:none}
      .label{fill:var(--atlas-fg);font-size:13px;text-anchor:middle;pointer-events:none}
      .status{fill:var(--atlas-muted);font-size:10px;text-anchor:middle;pointer-events:none}
      .context{fill:url(#hatch);stroke:var(--atlas-border);stroke-width:1}
      .context-label{fill:var(--atlas-muted);font-size:11px;text-anchor:middle}
      .stairs{stroke:var(--atlas-wall);stroke-width:1;fill:none;pointer-events:none}
      .pickup{display:none;pointer-events:none;text-anchor:middle}
      .pickup.visible{display:inline}
      .pickup-bin{display:none}
      .pickup.garbage .garbage-bin,.pickup.recycling .recycling-bin{display:inline}
      .garbage-bin{color:var(--house-atlas-garbage,#79740e)}
      .recycling-bin{color:var(--house-atlas-recycling,#458588)}
      .pickup.garbage.recycling .recycling-bin{transform:translateX(32px)}
      .pickup-body{fill:currentColor}
      .pickup-lid{fill:currentColor;stroke:var(--atlas-bg);stroke-width:.5}
      .pickup-window{fill:var(--atlas-bg);opacity:.85}
      .vehicle{display:none;pointer-events:none}
      .vehicle.visible{display:inline}
      .car-body{fill:currentColor;stroke:var(--atlas-wall);stroke-width:.8;stroke-linejoin:round}
      .car-wheel{fill:var(--atlas-wall)}
      .car-glass{fill:var(--atlas-wall);opacity:.45}
      .car-beetle{color:#fcfcfe}
      .car-model3{color:#f7f6f3}
    `;
    const rooms = floor.rooms
      .map((room) => {
        const connected = this.hasDevices(room);
        const [x, y] = room.label;
        const lines = room.lines || [room.name];
        return `<g id="room-${room.id}" data-room="${room.id}" class="room ${connected ? "connected" : ""} ${room.outdoor ? "outdoor" : ""}" ${connected ? 'tabindex="0" role="button"' : 'role="group"'} aria-label="${escapeXml(room.name)}"><path class="wall" d="${escapeXml(room.path)}"/>${room.partitions ? `<path class="partitions" d="${escapeXml(room.partitions)}"/>` : ""}<text class="label">${lines.map((line, i) => `<tspan x="${x}" y="${y + i * 17}">${escapeXml(line)}</tspan>`).join("")}</text>${connected && !room.lights ? `<text id="status-${room.id}" class="status" x="${x}" y="${y + lines.length * 17 + 5}">${escapeXml(room.mapNote || "")}</text>` : ""}</g>`;
      })
      .join("");
    const openings = (floor.openings || [])
      .map(
        ({ path }) =>
          `<path class="opening" aria-hidden="true" d="${escapeXml(path)}"/>`,
      )
      .join("");
    const pickups = floor.rooms
      .filter((room) => room.pickup)
      .map((room) => {
        const [x, y] = room.pickup.position;
        const bins = ["garbage", "recycling"]
          .map(
            (type) =>
              `<g class="pickup-bin ${type}-bin"><path class="pickup-body" d="M-10 6H10L8 31H-8Z"/><path class="pickup-lid" d="M-12 3H12V7H-12ZM-8 0H8L10 3H-10Z"/><path class="pickup-window" d="M0 13L5 16V22L0 25L-5 22V16Z"/></g>`,
          )
          .join("");
        return `<g id="pickup-${room.id}" class="pickup" transform="translate(${x} ${y})" role="img" aria-labelledby="pickup-title-${room.id}"><title id="pickup-title-${room.id}"></title>${bins}</g>`;
      })
      .join("");
    const vehicles = floor.rooms
      .flatMap((room) =>
        (room.vehicles || []).map((vehicle) => {
          const [x, y] = vehicle.position;
          const title = `vehicle-title-${room.id}-${vehicle.id}`;
          return `<g id="vehicle-${room.id}-${vehicle.id}" class="vehicle car-${vehicle.id}" transform="translate(${x} ${y}) rotate(90)" role="img" aria-labelledby="${title}"><title id="${title}"></title>${CAR_SHAPES[vehicle.id]}</g>`;
        }),
      )
      .join("");
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${floor.width} ${floor.height}" role="group" aria-label="${escapeXml(floor.name)} floor rooms"><defs><pattern id="hatch" patternUnits="userSpaceOnUse" width="6" height="6"><path d="M0 6L6 0" stroke="var(--atlas-border)" stroke-width=".6"/></pattern><pattern id="deck" patternUnits="userSpaceOnUse" width="12" height="12"><rect width="12" height="12" fill="var(--atlas-surface)"/><path d="M0 11H12" stroke="var(--atlas-border)" stroke-width=".7"/></pattern></defs>${floor.context || ""}${rooms}${floor.stairs || ""}${openings}${pickups}${vehicles}</svg>`;
    const rules = floor.rooms
      .filter((room) => this.hasDevices(room))
      .map((room) => ({
        element: `room-${room.id}`,
        tap_action: { action: "fire-dom-event", atlas_room: room.id },
        hold_action: room.hold
          ? { action: "fire-dom-event", atlas_hold: room.id }
          : { action: "none" },
        double_tap_action: false,
      }));
    for (const room of floor.rooms) {
      if (room.pickup) {
        rules.push({
          entity: room.pickup.entity,
          element: `pickup-${room.id}`,
          state_action: {
            action: "call-service",
            service: "floorplan.class_set",
            service_data: {
              class: `> const types = entity.attributes.pickup_types || []; if (!['tomorrow', 'today'].includes(entity.state) || !types.some(type => ['Garbage', 'Recycling'].includes(type))) return 'pickup'; return 'pickup visible' + (types.includes('Garbage') ? ' garbage' : '') + (types.includes('Recycling') ? ' recycling' : '');`,
            },
          },
        });
        rules.push({
          entity: room.pickup.entity,
          element: `pickup-title-${room.id}`,
          state_action: {
            action: "call-service",
            service: "floorplan.text_set",
            service_data: {
              text: `> return (entity.attributes.pickup_types || []).join(' and ') + ' pickup ' + entity.state;`,
            },
          },
        });
      }
      for (const vehicle of room.vehicles || []) {
        rules.push({
          entity: vehicle.entity,
          element: `vehicle-${room.id}-${vehicle.id}`,
          state_action: {
            action: "call-service",
            service: "floorplan.class_set",
            service_data: {
              class: `> return 'vehicle car-${vehicle.id}' + (entity.state === 'on' ? ' visible' : '');`,
            },
          },
        });
        rules.push({
          entity: vehicle.entity,
          element: `vehicle-title-${room.id}-${vehicle.id}`,
          state_action: {
            action: "call-service",
            service: "floorplan.text_set",
            service_data: {
              text: `> return '${vehicle.name} ' + (entity.state === 'on' ? 'parked' : 'away');`,
            },
          },
        });
      }
      if (room.entity && !room.lights) {
        rules.push({
          entity: room.entity,
          element: `status-${room.id}`,
          state_action: {
            action: "call-service",
            service: "floorplan.text_set",
            service_data: {
              text: `> return ({ opening: '▲ opening', closing: '▼ closing' })[entity.state] || entity.state.replaceAll('_', ' ');`,
            },
          },
        });
      }
    }
    const card = this.helpers.createCardElement({
      type: "custom:floorplan-card",
      config: {
        image: resource("image/svg+xml", svg),
        stylesheet: resource("text/css", styles),
        rules,
        console_log_level: "error",
      },
    });
    card.style.setProperty("--ha-card-border-width", "0");
    card.style.setProperty("--ha-card-background", "transparent");
    card.hass = this._hass;
    this.map = card;
    const mapWrap = this.shadowRoot.querySelector(".map-wrap");
    mapWrap.style.setProperty("--floor-ratio", floor.width / floor.height);
    const pins = document.createElement("div");
    pins.className = "pins";
    const stage = document.createElement("div");
    stage.className = "floor-stage";
    stage.innerHTML = `<svg class="light-map" viewBox="0 0 ${floor.width} ${floor.height}" aria-hidden="true">${this.lightFields()}</svg><div class="fixture-layer"></div>`;
    stage.prepend(card);
    stage.append(pins);
    mapWrap.replaceChildren(stage);
    this.positionFloorDevices();
    this.renderSceneDocks();
    this.renderPolaroids();
    this.updateMode();
  }

  deviceName(entity) {
    const room = this.rooms.find(
      (r) => r.id === this.config.placements[entity]?.room,
    );
    const name = this._hass.states[entity]?.attributes.friendly_name;
    return name
      ? name.replace(`${room?.name} `, "")
      : entity.split(".")[1].replace(`${room?.id}_`, "").replaceAll("_", " ");
  }

  lightFields(prefix = "") {
    return this.floor.rooms
      .filter((room) => !this.roomFocus || room.id === this.roomId)
      .map(
        (room) =>
          `<defs><clipPath id="${prefix}clip-${room.id}"><path d="${escapeXml(room.path)}"/></clipPath></defs><g class="light-field" clip-path="url(#${prefix}clip-${room.id})">${this.visiblePlacements
            .map(([entity, point], i) =>
              entity.startsWith("light.") && point.room === room.id
                ? `<radialGradient id="${prefix}glow-${i}"><stop offset="0"/><stop offset=".35" stop-opacity=".6"/><stop offset="1" stop-opacity="0"/></radialGradient><circle class="glow" data-glow="${entity}" cx="${point.x}" cy="${point.y}" r="65" fill="url(#${prefix}glow-${i})"/>`
                : "",
            )
            .join("")}</g>`,
      )
      .join("");
  }

  fixtureIcon(entity) {
    const icon =
      this.config.placements[entity].icon ||
      {
        lock: "mdi:lock-outline",
        cover: "mdi:garage",
        camera: "mdi:cctv",
        climate: "mdi:thermostat",
        media_player: "mdi:speaker",
        switch: "mdi:power-socket-us",
      }[entity.split(".")[0]];
    return FIXTURE_PATHS[icon]
      ? `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" fill-rule="evenodd" d="${FIXTURE_PATHS[icon]}"/></svg>`
      : `<ha-icon icon="${escapeXml(icon)}" aria-hidden="true"></ha-icon>`;
  }

  fixtureButton(entity, choose) {
    const button = document.createElement("button");
    button.className = "fixture";
    button.dataset.device = entity;
    button.innerHTML = this.fixtureIcon(entity);
    const door = this.config.placements[entity].door;
    if (door && !choose) {
      button.classList.add("door", door);
      button.innerHTML =
        door === "front"
          ? '<svg viewBox="0 0 60 36" aria-hidden="true"><g class="door-structure"><path d="M0 28H60" stroke-width="5"/><path d="M4 28H29V32H4Z"/><path d="M56 28L39 7L36 10L53 31Z"/><path class="door-swing" d="M30 28A26 26 0 0 1 39 7"/></g></svg>'
          : '<svg aria-hidden="true"><g class="door-structure garage-panel"></g></svg>';
      button.innerHTML += '<span class="door-state" aria-hidden="true"></span>';
    }
    const activate = (event, adjust) => {
      event.stopPropagation();
      if (choose) choose(entity, adjust);
      else this.resolveFixture(event, entity, button, adjust);
    };
    let timer,
      origin,
      scrolling,
      suppressClick = false;
    const cancel = () => {
      clearTimeout(timer);
      origin = null;
      scrolling?.abort();
    };
    button.onpointerdown = (event) => {
      if (event.button !== 0) return;
      suppressClick = false;
      origin = [event.clientX, event.clientY];
      scrolling = new AbortController();
      window.addEventListener(
        "scroll",
        () => {
          suppressClick = true;
          cancel();
        },
        { capture: true, passive: true, signal: scrolling.signal },
      );
      timer = setTimeout(() => {
        suppressClick = true;
        cancel();
        if (button.isConnected) activate(event, true);
      }, 450);
    };
    button.onpointermove = (event) => {
      if (
        origin &&
        Math.hypot(event.clientX - origin[0], event.clientY - origin[1]) > 8
      ) {
        suppressClick = true;
        cancel();
      }
    };
    button.onpointerup = cancel;
    button.onpointerleave = cancel;
    button.onpointercancel = () => {
      suppressClick = true;
      cancel();
    };
    button.oncontextmenu = (event) => {
      event.preventDefault();
      cancel();
      suppressClick = true;
      activate(event, true);
    };
    button.onkeydown = (event) => {
      if (
        event.key === "ContextMenu" ||
        (event.shiftKey && event.key === "F10")
      ) {
        event.preventDefault();
        activate(event, true);
      }
    };
    button.onclick = (event) => {
      if (suppressClick && event.detail !== 0) {
        suppressClick = false;
        return;
      }
      activate(event, false);
    };
    return button;
  }

  activateFixture(entity, anchor, adjust) {
    const domain = entity.split(".")[0];
    const state = this._hass.states[entity]?.state;
    if (
      adjust ||
      !["light", "lock", "cover"].includes(domain) ||
      (domain === "lock" && this.config.placements[entity].door !== "front")
    ) {
      this.openDevice(entity, anchor);
    } else if (![undefined, "unknown", "unavailable"].includes(state)) {
      if (domain === "lock") {
        if (["locked", "unlocked"].includes(state))
          this.perform(domain, state === "locked" ? "unlock" : "lock", entity);
      } else
        this.perform(
          domain,
          "toggle",
          domain === "light" ? this.lightControl(entity) : entity,
        );
    }
  }

  resolveFixture(event, entity, anchor, adjust) {
    // Keyboard and assistive activation already identify one specific device.
    if (
      event instanceof KeyboardEvent ||
      (event.type === "click" && event.detail === 0)
    ) {
      this.activateFixture(entity, anchor, adjust);
      return;
    }
    const stage = anchor.closest(".room-stage, .floor-stage");
    const svg = stage.querySelector(".focus-map, .light-map");
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(
      svg.getScreenCTM().inverse(),
    );
    const room = this.floor.rooms.find((room) =>
      svg.querySelector(`#clip-${room.id} path`)?.isPointInFill(point),
    );
    const candidates = [...stage.querySelectorAll("[data-device]")].filter(
      (button) => {
        return [button, button.querySelector(".door-state")]
          .filter(Boolean)
          .some((target) => {
            const rect = target.getBoundingClientRect();
            return (
              event.clientX >= rect.left &&
              event.clientX <= rect.right &&
              event.clientY >= rect.top &&
              event.clientY <= rect.bottom
            );
          });
      },
    );
    const sameLightGroup =
      !adjust &&
      candidates.length > 1 &&
      candidates.every((button) =>
        button.dataset.device.startsWith("light."),
      ) &&
      new Set(
        candidates.map((button) => this.lightControl(button.dataset.device)),
      ).size === 1;
    if (candidates.length === 1 || sameLightGroup)
      this.activateFixture(candidates[0].dataset.device, candidates[0], adjust);
    else if (candidates.length > 1)
      this.openLocalZoom(candidates, anchor, adjust);
    else if (!adjust && room && this.hasDevices(room)) this.selectRoom(room.id);
  }

  openLocalZoom(candidates, anchor, adjust) {
    const entries = candidates.map((button) => [
      button.dataset.device,
      this.config.placements[button.dataset.device],
    ]);
    const rooms = this.rooms.filter((room) =>
      entries.some(([, point]) => point.room === room.id),
    );
    const multipleRooms = rooms.length > 1;
    const dialog = this.openDialog(
      multipleRooms ? "Choose a device" : rooms[0].name,
      anchor,
    );
    dialog.classList.add("local-zoom");
    dialog.querySelector("header").remove();
    const diameter = Math.min(300, innerWidth - 24, innerHeight - 24);
    dialog.style.width = `${diameter}px`;
    dialog.style.height = `${diameter}px`;
    const body = dialog.querySelector(".dialog-body");
    body.innerHTML = `<div class="zoom-stage"><div class="zoom-background" inert></div><svg class="light-map" aria-hidden="true">${this.lightFields("zoom-")}</svg><div class="fixture-layer"></div></div>`;
    const stage = body.querySelector(".zoom-stage");
    const size = stage.clientWidth;
    const xs = entries.map(([, p]) => p.x),
      ys = entries.map(([, p]) => p.y);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2,
      cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    let separation = Infinity;
    for (let i = 0; i < entries.length; i++)
      for (let j = i + 1; j < entries.length; j++)
        separation = Math.min(
          separation,
          Math.max(Math.abs(xs[i] - xs[j]), Math.abs(ys[i] - ys[j])),
        );
    const radius = Math.max(
      ...entries.map(([, p]) => Math.hypot(p.x - cx, p.y - cy)),
    );
    const scale = Math.min(16, 80 / separation, (size / 2 - 64) / radius);
    const viewBox = `${cx - size / scale / 2} ${cy - size / scale / 2} ${size / scale} ${size / scale}`;
    const mapStage = anchor.closest(".room-stage, .floor-stage");
    const source = this.roomFocus
      ? mapStage.querySelector(".focus-map")
      : this.map.shadowRoot
          .querySelector("floorplan-element")
          .shadowRoot.querySelector("svg");
    const background = source.cloneNode(true);
    // Copy the rendered SVG styles so the lens matches Floorplan's stateful map,
    // including deck patterns, stairs and parked cars, without duplicating its renderer.
    const originals = [source, ...source.querySelectorAll("*")];
    const copies = [background, ...background.querySelectorAll("*")];
    originals.forEach((original, i) => {
      const style = getComputedStyle(original);
      for (const property of [
        "fill",
        "stroke",
        "stroke-width",
        "stroke-dasharray",
        "opacity",
        "display",
        "color",
        "font-family",
        "font-size",
        "text-anchor",
        "transform",
      ])
        copies[i].style.setProperty(property, style.getPropertyValue(property));
      copies[i].removeAttribute("tabindex");
    });
    background
      .querySelectorAll(".light-field")
      .forEach((field) => field.remove());
    background.setAttribute("viewBox", viewBox);
    background.setAttribute("aria-hidden", "true");
    background.style.width = "100%";
    background.style.height = "100%";
    stage
      .querySelector(".zoom-background")
      .attachShadow({ mode: "open" })
      .append(background);
    stage.querySelector(".light-map").setAttribute("viewBox", viewBox);
    const center = new DOMPoint(cx, cy).matrixTransform(
      mapStage.querySelector(".focus-map, .light-map").getScreenCTM(),
    );
    dialog.style.left = `${Math.max(12, Math.min(innerWidth - diameter - 12, center.x - diameter / 2))}px`;
    dialog.style.top = `${Math.max(12, Math.min(innerHeight - diameter - 12, center.y - diameter / 2))}px`;
    const separated = separation * scale >= 64;
    const layer = stage.querySelector(".fixture-layer");
    for (const [index, [entity, point]] of entries.entries()) {
      const original = candidates.find(
        (button) => button.dataset.device === entity,
      );
      const button = this.fixtureButton(entity, (selected, held) => {
        dialog.close();
        this.activateFixture(selected, original, adjust || held);
      });
      if (separated) {
        button.style.left = `${size / 2 + (point.x - cx) * scale}px`;
        button.style.top = `${size / 2 + (point.y - cy) * scale}px`;
      } else {
        const angle = (index * 2 * Math.PI) / entries.length;
        button.style.left = `${size / 2 + Math.cos(angle) * (size / 2 - 64)}px`;
        button.style.top = `${size / 2 + Math.sin(angle) * (size / 2 - 64)}px`;
        button.innerHTML += `<span>${escapeXml(this.deviceName(entity))}</span>`;
      }
      const roomName = multipleRooms
        ? rooms.find((room) => room.id === point.room).name
        : "";
      button.dataset.roomName = roomName;
      layer.append(button);
    }
    this.updateRoomDevices();
    if (this.keyboardNavigation)
      layer.querySelector("button").focus({ preventScroll: true });
  }

  positionFloorDevices() {
    const stage = this.shadowRoot.querySelector(".floor-stage");
    if (!stage || !this.isConnected) return;
    const rect = stage.getBoundingClientRect();
    if (!rect.width) return;
    const layer = stage.querySelector(".fixture-layer");
    const signature = `${rect.width}:${rect.height}`;
    if (layer.dataset.size === signature) return;
    layer.dataset.size = signature;
    layer.replaceChildren(
      ...this.visiblePlacements.map(([entity]) => this.fixtureButton(entity)),
      ...this.roomPowerButtons(),
    );
    this.positionDevices();
    this.updateRoomDevices();
  }

  roomPowerButtons() {
    return this.floor.rooms
      .filter(
        (room) =>
          room.lights?.length && (!this.roomFocus || room.id === this.roomId),
      )
      .map((room) => {
        const button = document.createElement("button");
        button.className = "room-power";
        button.dataset.powerRoom = room.id;
        button.innerHTML =
          '<svg viewBox="0 0 28 20" aria-hidden="true"><rect x="1" y="3" width="26" height="14" rx="7" fill="none" stroke="currentColor" stroke-width="1.5"/><circle class="switch-thumb" cy="10" r="4" fill="currentColor"/></svg>';
        button.onclick = (event) => {
          event.stopPropagation();
          this.toggleRoomLights(room);
        };
        return button;
      });
  }

  garageWidth(entity) {
    const state = this._hass.states[entity];
    const position =
      state?.state === "closed"
        ? 0
        : (state?.attributes.current_position ??
          (state?.state === "open" ? 100 : 0));
    return 6 + Math.max(0, Math.min(100, position)) * 0.94;
  }

  renderRoomMap() {
    this.map = null;
    const room = this.room;
    const devices = this.roomPlacements;
    const wrap = this.shadowRoot.querySelector(".map-wrap");
    const outlines = this.floor.rooms
      .map(
        (r) =>
          `<path class="${r.id === room.id ? "room-outline" : "neighbor"}" d="${escapeXml(r.path)}"/>${r.partitions ? `<path class="partitions" d="${escapeXml(r.partitions)}"/>` : ""}`,
      )
      .join("");
    const openings = (this.floor.openings || [])
      .map(({ path }) => `<path class="opening" d="${escapeXml(path)}"/>`)
      .join("");
    wrap.innerHTML = `<header class="focus-heading"><button class="mode back-floor">← ${escapeXml(this.floor.name)}</button><h2>${escapeXml(room.name)}</h2></header><div class="room-stage"><svg class="focus-map" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escapeXml(room.name)} device locations">${outlines}${this.lightFields()}${openings}</svg><div class="fixture-layer"></div></div>`;
    wrap.querySelector(".back-floor").onclick = () => this.selectRoom(null);
    const svg = wrap.querySelector(".focus-map");
    const box = svg.querySelector(".room-outline").getBBox();
    const left = Math.min(box.x, ...devices.map(([, p]) => p.x)) - 24;
    const top = Math.min(box.y, ...devices.map(([, p]) => p.y)) - 24;
    const right =
      Math.max(box.x + box.width, ...devices.map(([, p]) => p.x)) + 24;
    const bottom =
      Math.max(box.y + box.height, ...devices.map(([, p]) => p.y)) + 24;
    svg.setAttribute(
      "viewBox",
      `${left} ${top} ${right - left} ${bottom - top}`,
    );
    wrap
      .querySelector(".fixture-layer")
      .replaceChildren(
        ...devices.map(([entity]) => this.fixtureButton(entity)),
        ...this.roomPowerButtons(),
      );
    this.updateRoomDevices();
    this.positionDevices();
    this.renderSceneDocks();
  }

  positionDevices() {
    const stage = this.shadowRoot.querySelector(".room-stage, .floor-stage");
    if (!stage || !this.isConnected) return;
    const svg = stage.querySelector(".focus-map, .light-map");
    const rect = stage.getBoundingClientRect();
    const matrix = svg.getScreenCTM();
    if (!matrix || !rect.width) return;
    this.visiblePlacements.forEach(([entity, point]) => {
      const button = stage.querySelector(`[data-device="${entity}"]`);
      if (!button) return;
      const anchor = new DOMPoint(point.x, point.y).matrixTransform(matrix);
      button.style.left = `${anchor.x - rect.left}px`;
      button.style.top = `${anchor.y - rect.top}px`;
      if (point.door) {
        const width =
          (point.door === "front" ? 34 : this.garageWidth(entity)) * matrix.a;
        const height = (point.door === "front" ? 20.4 : 132) * matrix.d;
        if (point.door === "garage")
          button.style.left = `${anchor.x - rect.left + width / 2}px`;
        button.style.width = `${Math.max(56, width)}px`;
        button.style.height = `${Math.max(56, height)}px`;
        button.querySelector("svg").style.width = `${width}px`;
        button.querySelector("svg").style.height = `${height}px`;
      }
    });
    for (const button of stage.querySelectorAll("[data-power-room]")) {
      const room = this.floor.rooms.find(
        (room) => room.id === button.dataset.powerRoom,
      );
      const [x, y] = room.power || [room.label[0], room.label[1] - 26];
      const anchor = new DOMPoint(x, y).matrixTransform(matrix);
      button.style.left = `${anchor.x - rect.left}px`;
      button.style.top = `${anchor.y - rect.top}px`;
    }
  }

  updateRoomDevices() {
    const stage = this.shadowRoot.querySelector(".room-stage, .floor-stage");
    if (!stage) return;
    this.visiblePlacements.forEach(([entity, point]) => {
      const domain = entity.split(".")[0];
      const state = this._hass.states[entity];
      const available =
        state && !["unavailable", "unknown"].includes(state.state);
      const active =
        available &&
        ["on", "playing", "open", "unlocked"].includes(state.state);
      const color = !available
        ? "var(--atlas-error)"
        : domain === "light" && active
          ? state.attributes.rgb_color
            ? `rgb(${state.attributes.rgb_color.join(",")})`
            : point.fallbackColor
              ? `rgb(${point.fallbackColor.join(",")})`
              : "#d5d2ca"
          : ["lock", "cover"].includes(domain)
            ? state.state === (domain === "lock" ? "locked" : "closed")
              ? "var(--atlas-secure)"
              : "var(--atlas-warning)"
            : active
              ? "var(--atlas-accent)"
              : "var(--atlas-muted)";
      let status = available ? state.state.replaceAll("_", " ") : "Unavailable";
      if (
        domain === "light" &&
        active &&
        state.attributes.brightness !== undefined
      )
        status = `${Math.round((state.attributes.brightness / 255) * 100)}%`;
      const name = this.deviceName(entity);
      for (const button of this.shadowRoot.querySelectorAll(
        `[data-device="${entity}"]`,
      )) {
        if (domain === "light")
          button.setAttribute("aria-pressed", String(!!active));
        button.classList.toggle("unavailable", !available);
        button.classList.toggle("selected", entity === this.deviceId);
        const label = button.dataset.roomName
          ? `${name} · ${button.dataset.roomName}`
          : name;
        button.setAttribute("aria-label", `${label} · ${status}`);
        button.title = `${label} · ${status}${domain === "light" ? " · Hold for controls" : ""}`;
        button.style.setProperty("--fixture-color", color);
        const panel = button.querySelector(".garage-panel");
        if (panel) {
          const width = this.garageWidth(entity);
          panel.parentElement.setAttribute("viewBox", `0 0 ${width} 132`);
          panel.setAttribute("transform", `translate(${width - 100} 0)`);
          panel.innerHTML =
            '<rect x="1" y="3" width="98" height="126" rx="1"/><path d="M25 3V129M50 3V129M75 3V129" opacity=".45"/>';
        }
        const indicator = button.querySelector(".door-state");
        if (indicator) {
          const path = !available
            ? "M12 4V14M12 18V20"
            : domain === "lock"
              ? `${state.state === "locked" ? "M7 11V8A5 5 0 0 1 17 8V11" : "M7 11V8A5 5 0 0 1 17 8"}M5 11H19V21H5ZM12 15V18`
              : state.state === "closed"
                ? "M4 5H20V21H4ZM4 10H20M4 15H20"
                : state.state === "open"
                  ? "M4 21V3H20V21M8 9L12 5L16 9"
                  : state.state === "opening"
                    ? "M5 15L12 8L19 15M5 9L12 2L19 9"
                    : state.state === "closing"
                      ? "M5 9L12 16L19 9M5 15L12 22L19 15"
                      : "M12 4V14M12 18V20";
          indicator.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${path}"/></svg>`;
        }
      }
      for (const glow of this.shadowRoot.querySelectorAll(
        `[data-glow="${entity}"]`,
      )) {
        glow.style.opacity = active
          ? ((state.attributes.brightness ?? 255) / 255) *
            ((point.glowPercent ?? 100) / 100)
          : 0;
        glow.previousElementSibling
          .querySelectorAll("stop")
          .forEach((stop) => stop.setAttribute("stop-color", color));
      }
    });
    for (const button of stage.querySelectorAll("[data-power-room]")) {
      const room = this.floor.rooms.find(
        (room) => room.id === button.dataset.powerRoom,
      );
      const on = room.lights.some(
        (id) => this._hass.states[id]?.state === "on",
      );
      button.disabled = !room.lights.some((id) =>
        ["on", "off"].includes(this._hass.states[id]?.state),
      );
      button.setAttribute("aria-pressed", String(on));
      button.setAttribute(
        "aria-label",
        `${room.name}: turn ${on ? "off" : "on"} all lights`,
      );
      button.title = button.getAttribute("aria-label");
    }
    this.positionDevices();
    const doorDialog = this.shadowRoot.querySelector("[data-door][open]");
    if (doorDialog) {
      for (const card of doorDialog.cards) card.hass = this._hass;
      const state = this._hass.states[doorDialog.dataset.door]?.state;
      for (const button of doorDialog.querySelectorAll("[data-lock-action]"))
        button.disabled =
          !["locked", "unlocked"].includes(state) ||
          state === `${button.dataset.lockAction}ed`;
    }
    this.updateDeviceDialog();
  }

  openDialog(title, anchor) {
    this.shadowRoot.querySelector(".atlas-dialog[open]")?.close();
    const dialog = document.createElement("dialog");
    dialog.className = "atlas-dialog";
    dialog.tabIndex = -1;
    dialog.setAttribute("aria-label", title);
    dialog.innerHTML = `<header><h2>${escapeXml(title)}</h2><button class="close" aria-label="Close controls">×</button></header><div class="dialog-body"></div><p class="error" role="alert"></p>`;
    this.shadowRoot.append(dialog);
    dialog.querySelector(".close").onclick = () => dialog.close();
    let outside = false;
    dialog.onpointerdown = (e) => {
      outside = e.target === dialog;
    };
    dialog.onclick = (e) => {
      if (outside && e.target === dialog) dialog.close();
    };
    dialog.onkeydown = (e) => e.stopPropagation();
    dialog.onclose = () => {
      dialog.remove();
      if (this.deviceId === dialog.dataset.light) this.deviceId = null;
      this.updateRoomDevices();
      if (anchor?.isConnected && !this.shadowRoot.querySelector("dialog[open]"))
        anchor.focus({ preventScroll: true });
    };
    dialog.showModal();
    if (!this.keyboardNavigation) dialog.focus({ preventScroll: true });
    if (!this.mobile && anchor) {
      const rect = anchor.getBoundingClientRect();
      dialog.style.margin = "0";
      dialog.style.left = `${Math.max(12, Math.min(innerWidth - 352, rect.right + 12))}px`;
      dialog.style.top = `${Math.max(12, Math.min(innerHeight - dialog.offsetHeight - 12, rect.top))}px`;
    }
    return dialog;
  }

  moreInfo(entity) {
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId: entity },
        bubbles: true,
        composed: true,
      }),
    );
  }

  openDevice(entity, anchor) {
    const room = this.rooms.find(
      (room) => room.entity === entity && room.doorbell,
    );
    if (room) {
      const dialog = this.openDialog(this.deviceName(entity), anchor);
      dialog.dataset.door = entity;
      dialog.cards = [];
      const body = dialog.querySelector(".dialog-body");
      for (const config of [
        {
          type: "picture-entity",
          entity: room.doorbell.camera,
          camera_view: "live",
          show_name: false,
          show_state: false,
        },
        {
          type: "tile",
          entity,
          tap_action: { action: "more-info" },
          icon_tap_action: { action: "more-info" },
        },
      ]) {
        const card = this.helpers.createCardElement(config);
        card.hass = this._hass;
        dialog.cards.push(card);
        body.append(card);
      }
      const actions = document.createElement("div");
      actions.className = "lock-actions";
      for (const action of ["lock", "unlock"]) {
        const button = document.createElement("button");
        button.className = "lock-action secondary";
        button.dataset.lockAction = action;
        button.textContent = action === "lock" ? "Lock" : "Unlock";
        button.onclick = () => this.perform("lock", action, entity);
        actions.append(button);
      }
      body.append(actions);
      this.updateRoomDevices();
      if (!this.mobile && anchor)
        dialog.style.top = `${Math.max(12, Math.min(innerHeight - dialog.offsetHeight - 12, anchor.getBoundingClientRect().top))}px`;
      return;
    }
    if (!entity.startsWith("light.")) {
      this.moreInfo(entity);
      return;
    }
    if (
      this.deviceId === entity &&
      this.shadowRoot.querySelector(".atlas-dialog")
    )
      return;
    const dialog = this.openDialog(this.deviceName(entity), anchor);
    this.deviceId = entity;
    dialog.dataset.light = entity;
    const body = dialog.querySelector(".dialog-body");
    const attrs = this._hass.states[entity]?.attributes || {};
    const modes = attrs.supported_color_modes || [];
    body.innerHTML = `<button class="scene light-power"></button>`;
    if (modes.some((mode) => !["onoff", "unknown"].includes(mode)))
      body.innerHTML +=
        '<label>Brightness <output></output><input aria-label="Brightness" type="range" min="0" max="100" data-light-value="brightness"></label>';
    if (
      modes.some((mode) => ["hs", "xy", "rgb", "rgbw", "rgbww"].includes(mode))
    )
      body.innerHTML +=
        '<ha-hs-color-picker aria-label="Light color"></ha-hs-color-picker><p class="muted wheel-loading">Loading color wheel… More controls also opens Home Assistant’s picker.</p>';
    if (
      modes.includes("color_temp") &&
      attrs.min_color_temp_kelvin &&
      attrs.max_color_temp_kelvin
    )
      body.innerHTML += `<label class="white-control">White light<input aria-label="White temperature" type="range" min="${attrs.min_color_temp_kelvin}" max="${attrs.max_color_temp_kelvin}" step="1" data-light-value="color_temp_kelvin"><span><span>Warm</span><span>Cool</span></span></label>`;
    body.innerHTML += '<button class="mode more-info">More controls</button>';
    const wheel = body.querySelector("ha-hs-color-picker");
    if (wheel) {
      wheel.addEventListener("cursor-moved", (event) => {
        wheel.dataset.dragging = String(event.detail.value !== undefined);
      });
      wheel.addEventListener("value-changed", (event) => {
        const [hue, saturation] = event.detail.value;
        this.perform("light", "turn_on", entity, {
          hs_color: [hue, saturation * 100],
        });
      });
    }
    body.querySelector(".light-power").onclick = () =>
      this.perform("light", "toggle", entity);
    body.querySelector(".more-info").onclick = () => {
      dialog.close();
      this.moreInfo(entity);
    };
    for (const input of body.querySelectorAll("input")) {
      input.oninput = () => {
        if (input.dataset.lightValue === "brightness")
          body.querySelector("output").textContent = `${input.value}%`;
      };
      input.onchange = () => {
        const key = input.dataset.lightValue;
        const value =
          key === "brightness"
            ? Math.round((Number(input.value) * 255) / 100)
            : Number(input.value);
        this.perform("light", "turn_on", entity, { [key]: value });
      };
    }
    this.updateRoomDevices();
    if (!this.mobile && anchor)
      dialog.style.top = `${Math.max(12, Math.min(innerHeight - dialog.offsetHeight - 12, anchor.getBoundingClientRect().top))}px`;
  }

  updateDeviceDialog() {
    const dialog = this.shadowRoot.querySelector("[data-light]");
    if (!dialog) return;
    const state = this._hass.states[dialog.dataset.light];
    const available =
      state && !["unknown", "unavailable"].includes(state.state);
    const power = dialog.querySelector(".light-power");
    power.disabled = !available;
    power.textContent = available
      ? state.state === "on"
        ? "Turn off"
        : "Turn on"
      : "Unavailable";
    const wheel = dialog.querySelector("ha-hs-color-picker");
    if (wheel) {
      wheel.disabled = !available;
      if (available && wheel.dataset.dragging !== "true") {
        const [hue, saturation] = state.attributes.hs_color || [0, 0];
        wheel.value = [hue, saturation / 100];
      }
    }
    for (const input of dialog.querySelectorAll("input")) {
      input.disabled = !available;
      if (!available || this.shadowRoot.activeElement === input) continue;
      const key = input.dataset.lightValue;
      if (key === "brightness") {
        input.value =
          state.state === "off"
            ? 0
            : Math.round(((state.attributes.brightness ?? 255) * 100) / 255);
        dialog.querySelector("output").textContent = `${input.value}%`;
      } else if (state.attributes[key] != null)
        input.value = state.attributes[key];
    }
  }

  updateList() {
    const list = this.shadowRoot.querySelector(".room-list");
    if (!list || !this.listMode) return;
    if (list.dataset.floor !== this.floorId) {
      list.replaceChildren(
        ...this.floor.rooms.map((room) => {
          const button = document.createElement("button");
          button.className = "room-row";
          button.dataset.id = room.id;
          button.disabled = !this.hasDevices(room);
          button.innerHTML = `<span>${escapeXml(room.name)}<small></small></span>`;
          button.addEventListener("click", () => this.selectRoom(room.id));
          return button;
        }),
      );
      list.dataset.floor = this.floorId;
    }
    for (const button of list.children) {
      const room = this.floor.rooms.find(
        (room) => room.id === button.dataset.id,
      );
      button.setAttribute("aria-pressed", String(this.roomId === room.id));
      button.querySelector("small").textContent = this.summary(room);
    }
  }

  updateSummary() {
    const target = this.shadowRoot.querySelector(".status");
    if (target && this.room) target.textContent = this.summary(this.room);
  }

  renderLamps() {
    this.lampCards = [];
    const tiles = this.lamps.map(({ entity, name, sceneArea }) => {
      const card = this.helpers.createCardElement({
        type: "tile",
        entity,
        name,
        color: "amber",
        tap_action: { action: "more-info" },
        icon_tap_action: { action: "toggle" },
        features: [{ type: "light-brightness" }],
      });
      card.hass = this._hass;
      this.lampCards.push(card);
      const lamp = document.createElement("div");
      lamp.append(card);
      lamp.className = "lamp";
      if (sceneArea) {
        const scenes = document.createElement("section");
        scenes.className = "lamp-scenes";
        scenes.dataset.area = sceneArea;
        lamp.append(scenes);
      }
      return lamp;
    });
    this.shadowRoot.querySelector(".lamp-tiles")?.replaceChildren(...tiles);
    this.updateScenes();
  }

  renderDetails() {
    const host = this.shadowRoot.querySelector(".detail-host");
    const room = this.room;
    this.cards = [];
    host.replaceChildren();
    if (!room) return;
    const details = document.createElement("section");
    details.className = "details";
    details.setAttribute("aria-label", "Room controls");
    host.append(details);
    details.innerHTML = '<div class="detail-body"></div>';
    details.onkeydown = (e) => e.stopPropagation();
    const body = details.querySelector(".detail-body");
    const add = (config, target = body) => {
      const card = this.helpers.createCardElement(config);
      card.hass = this._hass;
      this.cards.push(card);
      target.append(card);
    };
    if (room.doorbell)
      add({
        type: "picture-entity",
        entity: room.doorbell.camera,
        camera_view: "live",
        show_name: false,
        show_state: false,
      });
    if (room.lights) {
      const controls = [
        ...(room.group ? [{ entity: room.group, name: "Room lighting" }] : []),
        ...(room.controls ||
          room.lights.map((entity) => ({
            entity,
            name: this.deviceName(entity),
          }))),
      ];
      controls.forEach(({ entity, name }) =>
        add({
          type: "tile",
          entity,
          name,
          color: "amber",
          tap_action: { action: "more-info" },
          icon_tap_action: { action: "toggle" },
          features: [{ type: "light-brightness" }],
        }),
      );
    }
    if (room.entity?.startsWith("lock.")) {
      add({
        type: "tile",
        entity: room.entity,
        tap_action: { action: "more-info" },
        icon_tap_action: { action: "more-info" },
      });
      const actions = document.createElement("div");
      actions.className = "lock-actions";
      for (const action of ["lock", "unlock"]) {
        const button = document.createElement("button");
        button.className = `lock-action ${action === "lock" ? "secondary" : ""}`;
        button.dataset.lockAction = action;
        button.textContent = action === "lock" ? "Lock" : "Unlock";
        button.addEventListener("click", () =>
          this.perform("lock", action, room.entity),
        );
        actions.append(button);
      }
      body.append(actions);
      this.updateLockButtons();
    } else if (room.entity?.startsWith("cover.")) {
      // The frontend's "toggle" action closes a moving door; cover.toggle stops it.
      const toggle = {
        action: "perform-action",
        perform_action: "cover.toggle",
        target: { entity_id: room.entity },
      };
      add({
        type: "tile",
        entity: room.entity,
        name: "Garage Door",
        tap_action: toggle,
        icon_tap_action: toggle,
      });
    } else if (
      !room.lights &&
      !room.entity &&
      !room.appliances &&
      !this.roomFocus
    ) {
      const text = document.createElement("p");
      text.className = "muted";
      text.textContent = room.note || "No connected devices in this room yet.";
      body.append(text);
    }
    if (room.entity?.startsWith("media_player."))
      add({
        type: "tile",
        entity: room.entity,
        name: room.mapNote,
        tap_action: { action: "more-info" },
        icon_tap_action: { action: "more-info" },
        features: [
          { type: "media-player-playback" },
          { type: "media-player-volume-slider" },
        ],
      });
    for (const { entity, name } of room.appliances || [])
      add({
        type: "tile",
        entity,
        name,
        tap_action: { action: "more-info" },
        icon_tap_action: { action: "toggle" },
      });
    if (!this.roomFocus && (room.scenes || room.hueScenes)) {
      const scenes = document.createElement("section");
      scenes.className = "hue-scenes";
      body.append(scenes);
      this.updateScenes();
    }
    const error = document.createElement("p");
    error.className = "error";
    error.setAttribute("role", "alert");
    body.append(error);
  }

  renderSceneDocks() {
    const wrap = this.shadowRoot.querySelector(".map-wrap");
    if (!wrap || !this._hass) return;
    wrap.querySelectorAll(".scene-dock").forEach((dock) => dock.remove());
    if (!this.roomFocus || !(this.room.scenes || this.room.hueScenes)) return;
    const dock = document.createElement("section");
    dock.className = "scene-dock";
    dock.setAttribute("aria-label", `${this.room.name} scenes`);
    dock.dataset.sceneRoom = this.roomId;
    wrap.append(dock);
    this.updateScenes();
  }

  roomScenes(room) {
    return room.scenes
      ? room.scenes.map(({ entity, name }) => ({
          entity,
          name,
          unavailable: [undefined, "unknown", "unavailable"].includes(
            this._hass.states[entity]?.state,
          ),
        }))
      : room.hueScenes
        ? this.hueScenes(room.id)
        : [];
  }

  updateScenes() {
    for (const container of this.shadowRoot.querySelectorAll(
      "[data-scene-room]",
    )) {
      const room = this.rooms.find((r) => r.id === container.dataset.sceneRoom);
      this.fillScenes(container, "", this.roomScenes(room), "");
    }
    for (const container of this.shadowRoot.querySelectorAll(".lamp-scenes"))
      this.fillScenes(
        container,
        "Hue scenes",
        this.hueScenes(container.dataset.area),
        "No Hue scenes for this lamp.",
      );
    const container = this.shadowRoot.querySelector(".hue-scenes");
    if (!container || !this.room) return;
    this.fillScenes(
      container,
      this.room.scenes ? "Scenes" : "Hue scenes",
      this.roomScenes(this.room),
      "No Hue scenes in this room.",
    );
  }

  fillScenes(container, label, scenes, empty) {
    const signature = JSON.stringify(scenes);
    if (container.dataset.scenes === signature) return;
    container.dataset.scenes = signature;
    container.innerHTML = `${label ? `<p class="section-label">${label}</p>` : ""}<div class="scenes"></div>`;
    const compact = container.hasAttribute("data-scene-room");
    for (const scene of compact ? scenes.slice(0, 3) : scenes) {
      const button = document.createElement("button");
      button.className = "scene";
      button.textContent = scene.name;
      button.disabled = scene.unavailable;
      button.addEventListener("click", async () => {
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        await this.activateScene(scene.entity);
        button.removeAttribute("aria-busy");
        button.disabled = scene.unavailable;
      });
      container.querySelector(".scenes").append(button);
    }
    if (compact && scenes.length > 3) {
      const more = document.createElement("button");
      more.className = "scene";
      more.textContent = "⋯";
      more.setAttribute("aria-label", "More scenes");
      more.onclick = () => {
        const room = this.rooms.find(
          (r) => r.id === container.dataset.sceneRoom,
        );
        const dialog = this.openDialog(`${room.name} scenes`, more);
        this.fillScenes(
          dialog.querySelector(".dialog-body"),
          "",
          this.roomScenes(room),
          "",
        );
      };
      container.querySelector(".scenes").append(more);
    }
    if (!scenes.length && empty)
      container.innerHTML += `<p class="muted">${empty}</p>`;
  }

  activateScene(entity) {
    const hue = this._hass.entities?.[entity]?.platform === "hue";
    return this.perform(
      hue ? "hue" : entity.split(".")[0],
      hue ? "activate_scene" : "turn_on",
      entity,
      hue ? { dynamic: true } : {},
    );
  }

  hueScenes(area) {
    return Object.values(this._hass.entities || {})
      .filter((entity) => {
        const device = this._hass.devices?.[entity.device_id];
        return (
          entity.platform === "hue" &&
          entity.entity_id.startsWith("scene.") &&
          (entity.area_id || device?.area_id) === area &&
          !entity.hidden &&
          this._hass.states[entity.entity_id]
        );
      })
      .map((entity) => ({
        entity: entity.entity_id,
        name:
          entity.name || this._hass.states[entity.entity_id].attributes.name,
        unavailable:
          this._hass.states[entity.entity_id].state === "unavailable",
      }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  updateLockButtons() {
    if (!this.room?.entity?.startsWith("lock.")) return;
    const state = this._hass.states[this.room.entity]?.state;
    const unavailable =
      !state ||
      ["unknown", "unavailable", "locking", "unlocking"].includes(state);
    this.shadowRoot.querySelectorAll("[data-lock-action]").forEach((button) => {
      button.disabled =
        unavailable ||
        state ===
          (button.dataset.lockAction === "lock" ? "locked" : "unlocked");
    });
  }

  hold(id) {
    const room = this.floor.rooms.find((room) => room.id === id);
    window.dispatchEvent(new CustomEvent("haptic", { detail: "medium" }));
    const element = this.mapRoom(id);
    element?.classList.remove("held");
    void element?.getBBox();
    element?.classList.add("held");
    if (room.hold.action === "toggle")
      return this.perform("cover", "toggle", room.entity);
    if (room.hold.action === "lock")
      return this.perform("lock", "lock", room.entity);
    return this.toggleRoomLights(room);
  }

  // Each entry starts at `from`, house time, and runs until the next; the latest one carries past midnight.
  currentScene(scenes) {
    if (!scenes.length) return null;
    const now = new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
      timeZone: this._hass.config.time_zone,
    }).format(new Date());
    const sorted = [...scenes].sort((a, b) => a.from.localeCompare(b.from));
    return sorted.filter((scene) => scene.from <= now).pop() || sorted.at(-1);
  }

  mapRoom(id) {
    const walk = (node) => {
      if (node.dataset?.room === id) return node;
      for (const child of [
        ...(node.shadowRoot?.children || []),
        ...node.children,
      ]) {
        const found = walk(child);
        if (found) return found;
      }
    };
    return this.map && walk(this.map);
  }

  async perform(domain, service, entity, data = {}) {
    const error =
      this.shadowRoot.querySelector(
        ".atlas-dialog[open] .error, .details .error",
      ) || this.shadowRoot.querySelector(".atlas > .error");
    if (error) error.textContent = "";
    try {
      await this._hass.callService(domain, service, {
        entity_id: entity,
        ...data,
      });
    } catch (error) {
      this.showError(error);
    }
  }

  showError(error) {
    const target =
      this.shadowRoot.querySelector(
        ".atlas-dialog[open] .error, .details .error",
      ) || this.shadowRoot.querySelector(".atlas > .error");
    if (target) target.textContent = error.message || String(error);
  }
}

customElements.define("house-atlas-card", HouseAtlas);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "house-atlas-card",
  name: "House Atlas",
  description: "Loch Highland: floor maps and room controls.",
});
