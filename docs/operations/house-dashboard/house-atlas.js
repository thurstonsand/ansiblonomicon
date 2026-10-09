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
    this.controlRoom = false;
    this.pendingTargets = new Map();
    this.cards = [];
    this.polaroids = new Map();
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
      }
    }
    if (!config.override?.startsWith("input_boolean."))
      throw new Error("House Atlas requires an input_boolean override.");
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

  get rooms() {
    return this.config.floors.flatMap((floor) => floor.rooms);
  }

  houseLights() {
    return [...new Set(this.rooms.flatMap((room) => room.lights || []))];
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
    lights.hidden = !lit;
    lights.querySelector("b").textContent =
      `${lit} ${lit === 1 ? "light" : "lights"} on`;
    lights.querySelector("small").textContent = this.rooms
      .filter((room) => (room.lights || []).some(on))
      .map((room) => room.name)
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
          display: block; container-type: inline-size;
          position: relative; z-index: 0; isolation: isolate;
          background: var(--atlas-bg); color: var(--atlas-fg);
          font-family: var(--paper-font-body1_-_font-family, Arial, sans-serif);
          min-height: calc(100dvh - 56px);
        }
        * { box-sizing: border-box; }
        [hidden] { display: none !important; }
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
        .strip { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0,1fr); gap: 10px; margin: 18px 0 0; }
        .g-cell { min-width: 0; display: flex; align-items: center; gap: 14px; border: 1px solid var(--atlas-border); background: var(--atlas-surface); border-radius: 8px; padding: 10px 10px 10px 16px; }
        .g-cell[hidden] { display: none; }
        .g-cell ha-icon { color: var(--atlas-muted); flex: 0 0 auto; }
        .g-cell.warn { border-color: var(--atlas-light); background: color-mix(in srgb, var(--atlas-light) 16%, var(--atlas-bg)); }
        .g-lights ha-icon, .g-cell.warn ha-icon { color: var(--atlas-light); }
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
        @container(max-width:900px) {
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
          .floors { margin-bottom: 12px; }
          .detail-heading { padding: 24px 18px 12px; }
          .detail-heading h2 { font-size: 26px; }
          .detail-body { padding: 14px 16px 20px; }
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
        this.updateMode();
      });
    this.shadowRoot
      .querySelector(".control-toggle")
      .addEventListener("click", () => this.setControlRoom(!this.controlRoom));
    this.shadowRoot
      .querySelector(".g-lights button")
      .addEventListener("click", () =>
        this.perform("light", "turn_off", this.houseLights()),
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
          this.selectRoom(event.detail.atlas_room);
        }
      });
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
        const connected = !!(
          room.lights ||
          room.entity ||
          room.appliances ||
          room.note
        );
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
    const pins = document.createElement("div");
    pins.className = "pins";
    mapWrap.replaceChildren(card, pins);
    this.renderPolaroids();
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
    if (room.doorbell)
      add({
        type: "picture-entity",
        entity: room.doorbell.camera,
        camera_view: "live",
        show_name: false,
        show_state: false,
      });
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
      add({
        type: "tile",
        entity: room.entity,
        name: "Garage Door",
        tap_action: { action: "more-info" },
        icon_tap_action: { action: "more-info" },
        features: [{ type: "cover-open-close" }],
      });
    } else if (!room.lights && !room.entity && !room.appliances) {
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
    if (room.scenes || room.hueScenes) {
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
    const scenes = this.room.scenes
      ? this.room.scenes.map(({ entity, name }) => ({
          entity,
          name,
          unavailable: [undefined, "unavailable"].includes(
            this._hass.states[entity]?.state,
          ),
        }))
      : this.hueScenes();
    const signature = JSON.stringify(scenes);
    if (container.dataset.scenes === signature) return;
    container.dataset.scenes = signature;
    container.innerHTML = `<p class="section-label">${
      this.room.scenes ? "Scenes" : "Hue scenes"
    }</p><div class="scenes"></div>`;
    for (const scene of scenes) {
      const button = document.createElement("button");
      button.className = "scene";
      button.textContent = scene.name;
      button.disabled = scene.unavailable;
      button.addEventListener("click", () =>
        this.perform(scene.entity.split(".")[0], "turn_on", scene.entity),
      );
      container.querySelector(".scenes").append(button);
    }
    if (!scenes.length)
      container.innerHTML += '<p class="muted">No Hue scenes in this room.</p>';
  }

  hueScenes() {
    return Object.values(this._hass.entities || {})
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

  async perform(domain, service, entity, data = {}) {
    const error = this.shadowRoot.querySelector(".details .error");
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
