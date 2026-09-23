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
const resource = (type, text) => ({
  location: `data:${type},${encodeURIComponent(text)}`,
  cache: true,
});
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
    this.listMode = false;
    this.cards = [];
    this.mobile = false;
    this.keyboardNavigation = false;
    this.addEventListener(
      "pointerdown",
      () => {
        this.keyboardNavigation = false;
      },
      { capture: true },
    );
    this.addEventListener(
      "keydown",
      () => {
        this.keyboardNavigation = true;
      },
      { capture: true },
    );
    this.resizeObserver = new ResizeObserver(([entry]) => {
      const mobile = entry.contentRect.width <= 900;
      if (mobile !== this.mobile) {
        this.mobile = mobile;
        if (this.helpers) this.renderDetails();
      }
    });
  }

  connectedCallback() {
    this.resizeObserver.observe(this);
    if (this.helpers) this.renderDetails();
  }

  disconnectedCallback() {
    this.resizeObserver.disconnect();
    const sheet = this.shadowRoot.querySelector("ha-bottom-sheet");
    if (sheet) sheet.open = false;
  }

  setConfig(config) {
    if (!Array.isArray(config.floors) || config.floors.length !== 3)
      throw new Error("House Atlas requires three floors.");
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
      }
    }
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
    if (!this.helpers) {
      if (!this.loading) {
        this.loading = window
          .loadCardHelpers()
          .then((helpers) => {
            this.helpers = helpers;
            this.renderMap();
            this.renderDetails();
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
    for (const card of this.cards) card.hass = hass;
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
          display: block; container-type: inline-size;
          position: relative; z-index: 0; isolation: isolate;
          background: var(--atlas-bg); color: var(--atlas-fg);
          font-family: var(--paper-font-body1_-_font-family, Arial, sans-serif);
          min-height: calc(100dvh - 56px);
        }
        * { box-sizing: border-box; }
        button { font: inherit; color: inherit; cursor: pointer; touch-action: manipulation; min-height: 48px; }
        button:focus-visible { outline: 3px solid var(--atlas-accent); outline-offset: 3px; }
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
        .layout { display: grid; grid-template-columns: minmax(0,1fr) 360px; gap: 32px; align-items: start; }
        .detail-host:empty { display: none; }
        .map-panel { min-width: 0; }
        .map-wrap { width: min(100%,calc((100dvh - 360px) * var(--floor-ratio))); min-width: min(100%,320px); margin: auto; }
        .detail-host { position: sticky; top: 76px; }
        aside.details { border: 1px solid var(--atlas-border); background: var(--atlas-bg); border-radius: 10px; max-height: calc(100dvh - 275px); overflow: auto; overscroll-behavior: contain; }
        ha-bottom-sheet { --ha-bottom-sheet-max-height: 75dvh; --ha-bottom-sheet-max-width: 720px; --ha-bottom-sheet-surface-background: var(--atlas-bg); --ha-bottom-sheet-scrim-color: #28282866; --ha-bottom-sheet-border-radius: 18px; }
        .detail-heading { position: sticky; top: 0; background: var(--atlas-bg); z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 22px 20px 16px; border-bottom: 1px solid var(--atlas-border); }
        .detail-heading h2 { font: 400 27px/1.15 Georgia,serif; margin: 0; }
        .close { flex: 0 0 48px; width: 48px; background: none; border: 0; font-size: 28px; font-weight: 300; }
        .detail-body { padding: 16px; display: grid; gap: 12px; }
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
        @container(max-width:900px) {
          .atlas { padding: 16px 12px 24px; }
          .top { padding-bottom: 12px; }
          .eyebrow { font-size: 9px; }
          .tools { gap: 0; }
          .mode { padding: 0 10px; }
          .layout { display: block; }
          .map-wrap { width: 100%; min-width: 0; max-width: 520px; }
          .floors { margin-bottom: 12px; }
          .detail-heading { padding: 24px 18px 12px; }
          .detail-heading h2 { font-size: 26px; }
          .detail-body { padding: 14px 16px 20px; }
        }
        @media(max-height:500px) {
          .atlas { padding-top: 8px; }
          .top { padding-bottom: 6px; }
          .eyebrow { display: none; }
          .floors { margin-top: 4px; }
        }
      </style>
      <main class="atlas">
        <header class="top"><div><div class="eyebrow">Loch Highland</div><h1>House</h1></div><div class="tools"><button class="mode" aria-pressed="false">Room list</button></div></header>
        <nav class="floors" aria-label="Floors">${this.config.floors.map((floor) => `<button data-floor="${escapeXml(floor.id)}" aria-current="${floor.id === this.floorId}">${escapeXml(floor.name)}</button>`).join("")}</nav>
        <div class="layout"><section class="map-panel" aria-label="Floor map"><div class="map-wrap"></div><div class="room-list" hidden></div></section><div class="detail-host"></div></div>
        <p class="error" role="alert"></p>
      </main>`;
    this.shadowRoot.querySelectorAll("[data-floor]").forEach((button) =>
      button.addEventListener("click", () => {
        this.floorId = button.dataset.floor;
        this.roomId = null;
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
    this.shadowRoot.querySelector(".mode").addEventListener("click", () => {
      this.listMode = !this.listMode;
      this.updateMode();
    });
    this.shadowRoot
      .querySelector(".atlas")
      .addEventListener("ll-custom", (event) => {
        if (event.detail.atlas_room) {
          event.stopPropagation();
          this.selectRoom(event.detail.atlas_room);
        }
      });
    this.shadowRoot
      .querySelector(".atlas")
      .addEventListener("keydown", (event) => {
        if (event.key === "Escape" && this.roomId) {
          event.stopPropagation();
          this.selectRoom(null);
        }
        if (event.key === "Enter" || event.key === " ") {
          const target = event
            .composedPath()
            .find((node) => node.dataset?.room);
          if (target) {
            event.preventDefault();
            this.selectRoom(target.dataset.room);
          }
        }
      });
    if (this.helpers) {
      this.renderMap();
      this.renderDetails();
    }
  }

  updateMode() {
    const button = this.shadowRoot.querySelector(".mode");
    button.textContent = this.listMode ? "Floor map" : "Room list";
    button.setAttribute("aria-pressed", String(this.listMode));
    this.shadowRoot.querySelector(".map-wrap").hidden = this.listMode;
    this.shadowRoot.querySelector(".room-list").hidden = !this.listMode;
    this.updateList();
  }

  selectRoom(id) {
    if (id && !this.floor.rooms.some((room) => room.id === id)) return;
    this.roomId = id;
    this.renderMap();
    this.renderDetails();
    if (id && this.keyboardNavigation)
      this.shadowRoot.querySelector(".close")?.focus({ preventScroll: true });
    else if (!id && this.keyboardNavigation)
      this.shadowRoot
        .querySelector(`[data-floor="${this.floorId}"]`)
        ?.focus({ preventScroll: true });
    else if (!id) this.shadowRoot.activeElement?.blur();
  }

  renderMap() {
    if (!this.helpers || !this._hass) return;
    const floor = this.floor;
    const styles = `
      svg{font-family:Arial,sans-serif;color:var(--atlas-fg);background:var(--atlas-bg)}
      .room{cursor:pointer;outline:none}
      .wall{stroke:var(--atlas-wall);stroke-width:1.6;stroke-linejoin:round;fill:var(--atlas-bg)}
      .room.connected .wall{fill:var(--atlas-surface)}
      .room.outdoor .wall{fill:url(#deck);stroke-dasharray:5 3}
      .room:focus-visible .wall,.room.selected .wall{fill:var(--atlas-selected);stroke:var(--atlas-accent);stroke-width:2.5}
      .room.outdoor:focus-visible .wall,.room.outdoor.selected .wall{fill:url(#deck)}
      @media(hover:hover){.room:hover .wall{fill:var(--atlas-selected);stroke:var(--atlas-accent);stroke-width:2.5}.room.outdoor:hover .wall{fill:url(#deck)}}
      .opening{stroke:var(--atlas-bg);stroke-width:5;fill:none;pointer-events:none}
      .label{fill:var(--atlas-fg);font-size:13px;text-anchor:middle;pointer-events:none}
      .status{fill:var(--atlas-muted);font-size:10px;text-anchor:middle;pointer-events:none}
      .indicator{fill:var(--atlas-light);pointer-events:none}
      .off{fill:var(--atlas-bg);stroke:var(--atlas-muted);stroke-width:1}
      .active{fill:var(--atlas-light);stroke:none}
      .unavailable{fill:var(--atlas-error);stroke:var(--atlas-bg);stroke-width:1;stroke-dasharray:2 2}
      .context{fill:url(#hatch);stroke:var(--atlas-border);stroke-width:1}
      .context-label{fill:var(--atlas-muted);font-size:11px;text-anchor:middle}
      .stairs{stroke:var(--atlas-wall);stroke-width:1;fill:none;pointer-events:none}
      .pickup{display:none;pointer-events:none;text-anchor:middle}
      .pickup.visible{display:inline}
      .pickup-bin{display:none}
      .pickup.garbage .garbage-bin,.pickup.recycling .recycling-bin{display:inline}
      .garbage-bin{color:var(--house-atlas-secure,#79740e)}
      .recycling-bin{color:#458588}
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
        const connected = !!(room.lights || room.entity || room.note);
        const [x, y] = room.label;
        const lines = room.lines || [room.name];
        return `<g id="room-${room.id}" data-room="${room.id}" class="room ${connected ? "connected" : ""} ${room.outdoor ? "outdoor" : ""} ${this.roomId === room.id ? "selected" : ""}" tabindex="0" role="button" aria-label="${escapeXml(room.name)}" aria-pressed="${this.roomId === room.id}"><path class="wall" d="${escapeXml(room.path)}"/><text class="label">${lines.map((line, i) => `<tspan x="${x}" y="${y + i * 17}">${escapeXml(line)}</tspan>`).join("")}</text>${connected ? `<text id="status-${room.id}" class="status" x="${x}" y="${y + lines.length * 17 + 5}">${escapeXml(room.lights ? `${room.lights.length} lights` : room.mapNote || "")}</text>` : ""}${room.lights ? `<circle id="dot-${room.id}" class="indicator" cx="${x}" cy="${y - 20}" r="3.5"/>` : ""}</g>`;
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
    const rules = floor.rooms.map((room) => ({
      element: `room-${room.id}`,
      tap_action: { action: "fire-dom-event", atlas_room: room.id },
      hold_action: { action: "none" },
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
      if (room.lights) {
        const ids = JSON.stringify(room.lights);
        rules.push({
          entities: room.lights,
          element: `dot-${room.id}`,
          state_action: {
            action: "call-service",
            service: "floorplan.class_set",
            service_data: {
              class: `> const values = ${ids}.map(id => entities[id] && entities[id].state); return values.some(s => s === 'on') ? 'indicator active' : values.some(s => s === 'unavailable' || s === 'unknown' || !s) ? 'indicator unavailable' : 'indicator off';`,
            },
          },
        });
        rules.push({
          entities: room.lights,
          element: `status-${room.id}`,
          state_action: {
            action: "call-service",
            service: "floorplan.text_set",
            service_data: {
              text: `> const values = ${ids}.map(id => entities[id] && entities[id].state || 'unavailable'); const missing = values.filter(s => s === 'unavailable').length; const unknown = values.filter(s => s === 'unknown').length; return '${room.lights.length} lights' + (missing ? ' · ' + missing + ' offline' : '') + (unknown ? ' · ' + unknown + ' unknown' : '');`,
            },
          },
        });
      } else if (room.entity) {
        rules.push({
          entity: room.entity,
          element: `status-${room.id}`,
          state_action: {
            action: "call-service",
            service: "floorplan.text_set",
            service_data: {
              text: `> return entity.state.replaceAll('_', ' ');`,
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
    mapWrap.replaceChildren(card);
    this.updateMode();
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

  renderDetails() {
    const host = this.shadowRoot.querySelector(".detail-host");
    const room = this.room;
    this.cards = [];
    host.replaceChildren();
    if (!room) return;
    const details = document.createElement(
      this.mobile ? "ha-bottom-sheet" : "aside",
    );
    details.className = "details";
    details.setAttribute("aria-label", "Room controls");
    host.append(details);
    details.innerHTML = `<header class="detail-heading"><div><h2>${escapeXml(room.name)}</h2><p class="status"></p></div><button class="close" aria-label="Close room controls">×</button></header><div class="detail-body"></div>`;
    if (this.mobile) {
      details.querySelector("header").slot = "header";
      details.flexContent = true;
      details.open = true;
      details.addEventListener("closed", (event) => {
        if (event.target === details && details.isConnected)
          this.selectRoom(null);
      });
    }
    this.shadowRoot.querySelector(".close").addEventListener("click", () => {
      if (this.mobile) details.open = false;
      else this.selectRoom(null);
    });
    this.updateSummary();
    const body = details.querySelector(".detail-body");
    const add = (config) => {
      const card = this.helpers.createCardElement(config);
      card.hass = this._hass;
      this.cards.push(card);
      body.append(card);
    };
    if (room.group)
      add({
        type: "tile",
        entity: room.group,
        name: "Room lighting",
        color: "amber",
        tap_action: { action: "more-info" },
        icon_tap_action: { action: "toggle" },
        features: [{ type: "light-brightness" }],
      });
    if (room.lights) {
      const controls =
        room.controls ||
        room.lights.map((entity) => ({
          entity,
          name:
            this._hass.states[entity]?.attributes.friendly_name?.replace(
              `${room.name} `,
              "",
            ) || entity,
        }));
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
    } else if (room.entity?.startsWith("lock.")) {
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
      add({
        type: "tile",
        entity: room.entity,
        name: "Garage Door",
        tap_action: { action: "more-info" },
        icon_tap_action: { action: "more-info" },
        features: [{ type: "cover-open-close" }],
      });
    } else if (room.entity?.startsWith("media_player.")) {
      add({
        type: "tile",
        entity: room.entity,
        name: "HomePod",
        tap_action: { action: "more-info" },
        icon_tap_action: { action: "more-info" },
        features: [
          { type: "media-player-playback" },
          { type: "media-player-volume-slider" },
        ],
      });
    } else {
      const text = document.createElement("p");
      text.className = "muted";
      text.textContent = room.note || "No connected devices in this room yet.";
      body.append(text);
    }
    if (room.hueScenes) {
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

  updateScenes() {
    const container = this.shadowRoot.querySelector(".hue-scenes");
    if (!container || !this.room) return;
    const scenes = Object.values(this._hass.entities || {})
      .filter((entity) => {
        const device = this._hass.devices?.[entity.device_id];
        return (
          entity.platform === "hue" &&
          entity.entity_id.startsWith("scene.") &&
          (entity.area_id || device?.area_id) === this.room.id &&
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
    const signature = JSON.stringify(scenes);
    if (container.dataset.scenes === signature) return;
    container.dataset.scenes = signature;
    container.innerHTML =
      '<p class="section-label">Hue scenes</p><div class="scenes"></div>';
    for (const scene of scenes) {
      const button = document.createElement("button");
      button.className = "scene";
      button.textContent = scene.name;
      button.disabled = scene.unavailable;
      button.addEventListener("click", () =>
        this.perform("scene", "turn_on", scene.entity),
      );
      container.querySelector(".scenes").append(button);
    }
    if (!scenes.length)
      container.innerHTML += '<p class="muted">No Hue scenes in this room.</p>';
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

  async perform(domain, service, entity) {
    const error = this.shadowRoot.querySelector(".details .error");
    if (error) error.textContent = "";
    try {
      await this._hass.callService(domain, service, { entity_id: entity });
    } catch (error) {
      this.showError(error);
    }
  }

  showError(error) {
    const target =
      this.shadowRoot.querySelector(".details .error") ||
      this.shadowRoot.querySelector(".atlas > .error");
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
