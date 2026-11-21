class DivoomOrchestratorPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._busy = false;
    this._initialized = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (this.isConnected && !this._initialized) this._render();
  }

  connectedCallback() {
    if (this._hass && !this._initialized) this._render();
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; min-height:100%; color:var(--primary-text-color,#202124); background:var(--primary-background-color,#f3f5f7); font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif); }
        * { box-sizing:border-box; }
        header { padding:18px 24px; background:var(--app-header-background-color,#fff); color:var(--app-header-text-color,#202124); box-shadow:0 2px 6px #0001; display:flex; gap:16px; align-items:center; }
        header button { font-size:22px; background:none; padding:2px 6px; color:inherit; }
        h1 { margin:0; font-size:21px; font-weight:500; }
        main { max-width:1100px; margin:auto; padding:28px 20px; }
        .hero { border-radius:18px; padding:26px; background:linear-gradient(115deg,#145c70,#278b84); color:#fff; margin-bottom:22px; }
        .eyebrow { font-size:12px; letter-spacing:.12em; font-weight:700; text-transform:uppercase; opacity:.85; }
        h2 { font-size:23px; margin:9px 0; } p { line-height:1.5; }
        .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr)); gap:20px; }
        .card { background:var(--card-background-color,#fff); border-radius:16px; padding:22px; box-shadow:0 2px 12px #0001; }
        h3 { margin:0 0 8px; font-size:18px; } .muted { color:var(--secondary-text-color,#63717c); font-size:14px; }
        label { display:block; margin-top:17px; font-size:14px; font-weight:600; }
        input,select { width:100%; margin-top:7px; padding:11px; border:1px solid var(--divider-color,#c7cdd2); border-radius:8px; background:var(--card-background-color,#fff); color:var(--primary-text-color,#202124); font:inherit; }
        input[type=checkbox] { width:auto; margin-right:8px; }
        button { border:0; border-radius:8px; padding:11px 16px; font:inherit; font-weight:600; cursor:pointer; }
        button:disabled { opacity:.5; cursor:wait; }
        .actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:20px; }
        .primary { color:white; background:var(--primary-color,#16889a); } .secondary { color:var(--primary-text-color,#202124); background:var(--secondary-background-color,#e8eef0); }
        .message { margin:16px 0 0; min-height:1.4em; font-size:14px; }
        .error { color:var(--error-color,#b00020); }
        .upcoming { border-left:4px solid var(--primary-color,#16889a); padding-left:14px; }
        .upcoming p { margin:6px 0; }
      </style>
      <header><button id="menu" aria-label="Menü öffnen">☰</button><h1>Divoom Orchestrator</h1></header>
      <main>
        <section class="hero"><div class="eyebrow">Deine Smart Doorbell</div>
          <h2>Animationen für deinen Pixoo</h2>
          <p>Playlists und automatische Helligkeit für dein Display.</p>
        </section>
        <div class="grid">
          <section class="card">
            <h3>Ordner-Playlist</h3>
            <p class="muted">GIFs aus einem Ordner wiederholt abspielen. Die Dateiliste wird nach jedem Durchlauf aktualisiert.</p>
            <form id="playlist">
              <label>Gerätekennung<input name="device" value="divoom_pixoo" required autocomplete="off"></label>
              <label>Ordner unter pixelart<input name="folder" value="." required autocomplete="off"></label>
              <label>Anzeigezeit je GIF (Sekunden)<input name="duration" type="number" value="10" min="1" max="3600" step="1" required></label>
              <label>Reihenfolge<select name="order"><option value="alphabetical">Alphabetisch</option><option value="random">Zufällig</option></select></label>
              <div class="actions"><button type="submit" class="primary">▶ Playlist starten</button><button type="button" class="secondary" id="stop">■ Stoppen</button></div>
              <p id="message" class="message" role="status" aria-live="polite"></p>
            </form>
          </section>
          <section class="card">
            <h3>Automatische Helligkeit</h3>
            <p class="muted">Die Automatik steuert das Display direkt. Bei Bewegung 100 %, mindestens 30 Sekunden. Tests gelten 30 Sekunden und setzen danach die Automatik fort.</p>
            <form id="brightness">
              <label><input type="checkbox" name="enabled">Automatik aktivieren</label>
              <label>Gerätekennung<input name="device" required autocomplete="off"></label>
              <label>Bewegungsmelder<select name="motion"><option value="">Keiner</option></select></label>
              <label>Bluetooth-Status für Wiederverbindung<select name="connection"><option value="">Keiner</option></select></label>
              <label>Startzeit morgens<input type="time" name="morning" required></label>
              <label>Tag (%)<input type="number" name="day" min="0" max="100" step="1" required></label>
              <button type="button" class="secondary brightness-test" data-level="day">Tag testen</button>
              <label>Dämmerung (%)<input type="number" name="twilight" min="0" max="100" step="1" required></label>
              <button type="button" class="secondary brightness-test" data-level="twilight">Dämmerung testen</button>
              <label>Nacht (%)<input type="number" name="night" min="0" max="100" step="1" required></label>
              <button type="button" class="secondary brightness-test" data-level="night">Nacht testen</button>
              <p class="muted">0 % schaltet das Display aus. Dämmerung ab Sonnenuntergang bis −6° Sonnenstand; morgens ab Startzeit bis Sonnenaufgang.</p>
              <div class="actions"><button type="submit" class="primary">Helligkeit speichern</button></div>
              <p id="brightness-message" class="message" role="status" aria-live="polite"></p>
            </form>
          </section>
          <section class="card">
            <h3>Als Nächstes</h3>
            <div class="upcoming"><p><strong>Rotation &amp; Events</strong></p><p class="muted">Abläufe, Prioritäten und Sensoren sind noch nicht konfigurierbar.</p></div>
            <div class="upcoming"><p><strong>Medienvorschau</strong></p><p class="muted">Auswahl und GIF-Vorschau folgen, sobald der Medienzugriff umgesetzt und geprüft ist.</p></div>
            <p class="muted">Diese Oberfläche zeigt noch keinen Live-Verbindungsstatus. Für den Bluetooth-Status weiterhin deine bestehende HA-Kachel verwenden.</p>
          </section>
        </div>
      </main>`;
    this._initialized = true;
    this.shadowRoot.querySelector("#menu").addEventListener("click", () => {
      this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
    });
    this.shadowRoot.querySelector("#playlist").addEventListener("submit", (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      for (const name of ["device", "folder"]) {
        const input = form.elements[name];
        input.setCustomValidity(input.value.trim() ? "" : "Bitte einen Wert eingeben.");
      }
      if (!form.reportValidity()) return;
      const data = new FormData(form);
      this._call("start", {
        device: data.get("device").trim(),
        folder: data.get("folder").trim(),
        duration: Number(data.get("duration")),
        order: data.get("order"),
      });
    });
    for (const name of ["device", "folder"]) {
      this.shadowRoot.querySelector(`[name="${name}"]`).addEventListener("input", (event) => {
        event.currentTarget.setCustomValidity("");
      });
    }
    this.shadowRoot.querySelector("#stop").addEventListener("click", () => this._call("stop", {}));
    const brightness = this.shadowRoot.querySelector("#brightness");
    brightness.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!brightness.reportValidity()) return;
      const config = {
        enabled: brightness.elements.enabled.checked,
        device: brightness.elements.device.value.trim(),
        motion: brightness.elements.motion.value,
        connection: brightness.elements.connection.value,
        morning: brightness.elements.morning.value,
        day: Number(brightness.elements.day.value),
        twilight: Number(brightness.elements.twilight.value),
        night: Number(brightness.elements.night.value),
      };
      this._brightnessCall("brightness_configure", config, "Einstellungen gespeichert.");
    });
    brightness.querySelectorAll(".brightness-test").forEach((button) => {
      button.addEventListener("click", () => {
        const input = brightness.elements[button.dataset.level];
        if (!input.reportValidity()) return;
        this._brightnessCall("brightness_test", { value: Number(input.value) }, "Test aktiv für 30 Sekunden.");
      });
    });
    this._loadBrightness();
  }

  async _loadBrightness() {
    const form = this.shadowRoot.querySelector("#brightness");
    const message = this.shadowRoot.querySelector("#brightness-message");
    form.querySelectorAll("button").forEach((button) => { button.disabled = true; });
    message.textContent = "Einstellungen werden geladen …";
    try {
      const config = await this._hass.callWS({ type: "divoom_orchestrator/brightness" });
      for (const [name, filter] of [
        ["motion", (id) => id.startsWith("binary_sensor.")],
        ["connection", (id) => id.startsWith("sensor.") || id.startsWith("binary_sensor.")],
      ]) {
        const select = form.elements[name];
        Object.values(this._hass.states).filter((state) => filter(state.entity_id))
          .sort((a, b) => (a.attributes.friendly_name || a.entity_id).localeCompare(b.attributes.friendly_name || b.entity_id))
          .forEach((state) => {
            const option = document.createElement("option");
            option.value = state.entity_id;
            option.textContent = `${state.attributes.friendly_name || state.entity_id} (${state.entity_id})`;
            select.appendChild(option);
          });
        if (config[name] && !Array.from(select.options).some((option) => option.value === config[name])) {
          const option = document.createElement("option");
          option.value = config[name];
          option.textContent = `${config[name]} (nicht verfügbar)`;
          select.appendChild(option);
        }
      }
      for (const name of ["device", "motion", "connection", "morning", "day", "twilight", "night"]) {
        form.elements[name].value = config[name];
      }
      form.elements.enabled.checked = config.enabled;
      message.textContent = "";
      form.querySelectorAll("button").forEach((button) => { button.disabled = false; });
    } catch (error) {
      message.textContent = `Einstellungen konnten nicht geladen werden: ${error.message || String(error)}`;
      message.classList.add("error");
    }
  }

  async _brightnessCall(action, data, success) {
    const form = this.shadowRoot.querySelector("#brightness");
    const message = this.shadowRoot.querySelector("#brightness-message");
    const buttons = form.querySelectorAll("button");
    buttons.forEach((button) => { button.disabled = true; });
    message.classList.remove("error");
    message.textContent = "Bitte warten …";
    try {
      await this._hass.callService("divoom_orchestrator", action, data);
      message.textContent = success;
    } catch (error) {
      message.textContent = `Aktion fehlgeschlagen: ${error.message || String(error)}`;
      message.classList.add("error");
    } finally {
      buttons.forEach((button) => { button.disabled = false; });
    }
  }

  async _call(action, data) {
    if (this._busy) return;
    this._busy = true;
    const buttons = this.shadowRoot.querySelectorAll(".actions button");
    const message = this.shadowRoot.querySelector("#message");
    buttons.forEach((button) => { button.disabled = true; });
    message.textContent = action === "start" ? "Playlist wird gestartet …" : "Playlist wird gestoppt …";
    message.classList.remove("error");
    try {
      await this._hass.callService("divoom_orchestrator", action, data);
      message.textContent = action === "start"
        ? "Start angefordert. Fehler bei der Wiedergabe meldet Home Assistant separat."
        : "Playlist gestoppt.";
    } catch (error) {
      message.textContent = `Aktion fehlgeschlagen: ${error.message || String(error)}`;
      message.classList.add("error");
    } finally {
      this._busy = false;
      buttons.forEach((button) => { button.disabled = false; });
    }
  }
}

customElements.define("divoom-orchestrator-panel", DivoomOrchestratorPanel);
