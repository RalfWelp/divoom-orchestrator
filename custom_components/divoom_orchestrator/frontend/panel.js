class DivoomOrchestratorPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._busy = false;
    this._initialized = false;
  }

  set hass(hass) {
    this._hass = hass;
    this.toggleAttribute("data-dark", hass.themes?.darkMode === true);
    if (this.isConnected && !this._initialized) this._render();
    else if (this._initialized) this._updateConnection();
  }

  connectedCallback() {
    if (this._hass && !this._initialized) this._render();
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host { --panel-text:var(--primary-text-color,#202124); --panel-background:var(--primary-background-color,#f3f5f7); --panel-card:var(--card-background-color,#fff); --panel-secondary:var(--secondary-background-color,#e8eef0); --panel-muted:var(--secondary-text-color,#63717c); --panel-divider:var(--divider-color,#c7cdd2); display:block; min-height:100%; color:var(--panel-text); background:var(--panel-background); font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif); color-scheme:light; }
        :host([data-dark]) { --panel-text:var(--primary-text-color,#e8edf2); --panel-background:var(--primary-background-color,#111820); --panel-card:var(--card-background-color,#1d2731); --panel-secondary:var(--secondary-background-color,#283743); --panel-muted:var(--secondary-text-color,#b0bdc7); --panel-divider:var(--divider-color,#475764); color-scheme:dark; }
        * { box-sizing:border-box; }
        header { padding:18px 24px; background:var(--app-header-background-color,var(--panel-card)); color:var(--app-header-text-color,var(--panel-text)); box-shadow:0 2px 6px #0001; display:flex; gap:16px; align-items:center; }
        header button { font-size:22px; background:none; padding:2px 6px; color:inherit; }
        h1 { margin:0; font-size:21px; font-weight:500; }
        main { max-width:1100px; margin:auto; padding:28px 20px; }
        .hero { border-radius:18px; padding:26px; background:linear-gradient(115deg,#145c70,#278b84); color:#fff; margin-bottom:22px; }
        .eyebrow { font-size:12px; letter-spacing:.12em; font-weight:700; text-transform:uppercase; opacity:.85; }
        h2 { font-size:23px; margin:9px 0; } p { line-height:1.5; }
        .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr)); gap:20px; }
        .card { background:var(--panel-card); border-radius:16px; padding:22px; box-shadow:0 2px 12px #0001; }
        h3 { margin:0 0 8px; font-size:18px; } .muted { color:var(--panel-muted); font-size:14px; }
        label { display:block; margin-top:17px; font-size:14px; font-weight:600; }
        input,select { width:100%; margin-top:7px; padding:11px; border:1px solid var(--panel-divider); border-radius:8px; background:var(--panel-card); color:var(--panel-text); font:inherit; }
        input[type=checkbox] { width:auto; margin-right:8px; }
        button { border:0; border-radius:8px; padding:11px 16px; font:inherit; font-weight:600; cursor:pointer; }
        button:disabled { opacity:.5; cursor:wait; }
        .actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:20px; }
        .primary { color:white; background:var(--primary-color,#16889a); } .secondary { color:var(--panel-text); background:var(--panel-secondary); }
        .message { margin:16px 0 0; min-height:1.4em; font-size:14px; }
        .error { color:var(--error-color,#b00020); }
        .upcoming { border-left:4px solid var(--primary-color,#16889a); padding-left:14px; }
        .upcoming p { margin:6px 0; }
        .gif-row { display:flex; align-items:center; gap:12px; margin-top:10px; }
        .gif-row span { flex:1; overflow-wrap:anywhere; }
        .gif-row input { width:95px; margin:0; }
        .gif-preview { width:64px; height:64px; object-fit:contain; image-rendering:pixelated; background:#111; border-radius:6px; flex:none; }
        .gif-detail { display:flex; flex:1; flex-direction:column; gap:4px; min-width:0; }
        .gif-detail small { color:var(--panel-muted); font-weight:normal; }
        .wide { grid-column:1 / -1; }
        .event-row { display:flex; flex-wrap:wrap; align-items:center; gap:8px; padding:10px 0; border-bottom:1px solid var(--panel-divider); }
        .event-row input[type=checkbox] { width:auto; margin:0; }
        .event-row input[type=number] { width:95px; margin:0; }
        .event-row select { width:auto; margin:0; }
        .event-row button { padding:8px; }
        .navigation { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:22px; }
        .navigation button[aria-current="page"] { color:white; background:var(--primary-color,#16889a); }
        [hidden] { display:none !important; }
        .event-layout { display:grid; grid-template-columns:230px minmax(0,1fr); gap:20px; }
        .event-sidebar { background:var(--panel-secondary); border-radius:12px; padding:14px; align-self:start; }
        .event-sidebar h4 { margin:12px 0 6px; font-size:14px; }
        .event-sidebar button { width:100%; text-align:left; margin:2px 0; overflow-wrap:anywhere; }
        .event-sidebar button[aria-current="true"] { background:var(--primary-color,#16889a); color:white; }
        .event-sidebar .new-event { color:var(--primary-color,#16889a); background:transparent; }
        .rotation-preview { list-style:none; margin:18px 0 0; padding:0; display:grid; gap:10px; }
        .rotation-block { display:flex; align-items:center; gap:14px; padding:14px 16px; border:1px solid var(--panel-divider); border-radius:12px; background:var(--panel-secondary); }
        .rotation-icon { display:grid; place-items:center; width:42px; height:42px; flex:none; border-radius:10px; background:var(--panel-card); font-size:21px; }
        .rotation-description { flex:1; min-width:0; }
        .rotation-description strong, .rotation-description span { display:block; }
        .rotation-description span { color:var(--panel-muted); font-size:13px; margin-top:4px; }
        .rotation-badge { flex:none; color:var(--panel-muted); font-size:12px; }
        @media (max-width:700px) { .event-layout { grid-template-columns:1fr; } }
      </style>
      <header><button id="menu" aria-label="Menü öffnen">☰</button><h1>Divoom Orchestrator</h1></header>
      <main>
        <section class="hero"><div class="eyebrow">Deine Smart Doorbell</div>
          <h2>Animationen für deinen Pixoo</h2>
          <p>Rotation, Events und Einstellungen für dein Display.</p>
        </section>
        <nav class="navigation" aria-label="Orchestrator-Bereiche">
          <button type="button" class="secondary" data-page="overview" aria-current="page">Übersicht &amp; Rotation</button>
          <button type="button" class="secondary" data-page="events">Event-Editor</button>
          <button type="button" class="secondary" data-page="settings">Einstellungen</button>
        </nav>
        <div id="page-events" class="grid" hidden>
          <section class="card wide">
            <h3>Event-Editor</h3>
            <p class="muted">GIFs auswählen und sortieren. Triggered-Events benötigen die aktivierte Helligkeitsautomatik und unterbrechen die Rotation nach ihrer Priorität.</p>
            <div class="event-layout">
            <aside class="event-sidebar" aria-label="Events">
              <h4>⚡ Triggered-Events</h4>
              <div id="events-trigger"></div>
              <button type="button" class="new-event" data-new-event="trigger">+ Neues Triggered-Event</button>
              <h4>📅 Datums-Events</h4>
              <div id="events-date"></div>
              <button type="button" class="new-event" data-new-event="date">+ Neues Datums-Event</button>
            </aside>
            <div>
            <div class="grid">
              <div>
                <select id="event-choice" hidden aria-label="Gespeichertes Event"><option value="">Neues Event</option></select>
                <p id="event-kind" class="muted"></p>
                <label>Eventname<input id="event-name" maxlength="80" autocomplete="off" placeholder="z. B. Klingel"></label>
                <label><input id="event-enabled" type="checkbox" checked>Event aktiviert</label>
                <div id="event-priority-group">
                  <label>Priorität<input id="event-priority" type="number" min="1" max="100" step="1" value="3" required></label>
                  <p class="muted">1 ist die höchste Priorität. Ein wichtigeres Event kann ein laufendes unterbrechen.</p>
                  <label>Auslöser<select id="event-trigger-type"><option value="manual">Manuell / Aktion</option><option value="state">Zustandswechsel</option><option value="event">HA-Event</option></select></label>
                  <div id="event-trigger-state" hidden>
                    <label>Entität<input id="event-trigger-entity" placeholder="binary_sensor.bewegung" autocomplete="off"></label>
                    <label>Zielzustand<input id="event-trigger-to" placeholder="on" autocomplete="off"></label>
                    <p class="muted">Nur ein tatsächlicher Zustandswechsel löst aus, nicht der Zustand beim Start.</p>
                  </div>
                  <div id="event-trigger-bus" hidden>
                    <label>HA-Eventtyp<input id="event-trigger-event" placeholder="klingel" autocomplete="off"></label>
                  </div>
                </div>
                <div id="event-dates" hidden>
                  <label>Zeitraum<select id="event-date-mode"><option value="annual">Jährlich wiederkehrend</option><option value="once">Einmalig</option></select></label>
                  <label>Beginn<input id="event-date-start" type="text" placeholder="MM-TT" autocomplete="off"></label>
                  <label>Ende<input id="event-date-end" type="text" placeholder="MM-TT" autocomplete="off"></label>
                  <p class="muted">Beide Tage zählen mit; jährliche Zeiträume dürfen über den Jahreswechsel reichen.</p>
                </div>
                <label>Ausgewählter GIF-Ordner<input id="event-folder" value="." readonly></label>
                <label>Unterordner öffnen<select id="event-subfolder"><option value="">Kein Unterordner</option></select></label>
                <p class="muted">Die GIFs stammen aus dem ausgewählten Ordner. Wähle einen Unterordner und öffne ihn, um dorthin zu wechseln.</p>
                <div class="actions">
                  <button type="button" class="secondary" id="event-up">⬆ Überordner</button>
                  <button type="button" class="secondary" id="event-open">Ordner öffnen</button>
                  <button type="button" class="secondary" id="event-refresh">Ordner aktualisieren</button>
                </div>
              </div>
              <div>
                <p class="muted">Ausgewählte GIFs werden von oben nach unten abgespielt. Durchläufe sind eine Schätzung anhand der Framezeiten; der Pixoo kann abweichen. Neue GIFs sind zunächst nicht ausgewählt.</p>
                <div id="event-list"></div>
              </div>
            </div>
            <div class="actions">
              <button type="button" class="primary" id="event-save">Event speichern</button>
              <button type="button" class="secondary" id="event-test">Gespeichertes Event testen</button>
              <button type="button" class="secondary" id="event-delete">Event löschen</button>
            </div>
            <p id="event-message" class="message" role="status" aria-live="polite"></p>
            </div>
            </div>
          </section>
        </div>
        <div id="page-overview" class="grid">
          <section class="card">
            <h3>Verbindung</h3>
            <p id="connection-status" role="status">Status wird geladen …</p>
            <p class="muted">Der Status stammt vom in den Einstellungen gewählten HA-Sensor, nicht direkt vom Pixoo.</p>
          </section>
          <section class="card wide">
            <h3>Rotation</h3>
            <p class="muted">Blöcke per Drag &amp; Drop verschieben; anschließend in der Rotation speichern. Die Startanimation bleibt immer vorn.</p>
            <ol class="rotation-preview" id="rotation-blocks" aria-label="Rotationsablauf">
              <li class="rotation-block"><span class="rotation-icon" aria-hidden="true">✨</span><span class="rotation-description"><strong>Startanimation</strong><span>Ausgewählte GIFs · am Anfang jedes Durchlaufs</span></span><span class="rotation-badge">🔒 Fest</span><button type="button" class="secondary" id="rotation-edit">Bearbeiten</button></li>
              <li class="rotation-block" data-block="weather" draggable="true"><span class="rotation-icon" aria-hidden="true">🌤️</span><span class="rotation-description"><strong>Wetter</strong><span>Aktuelle Wetteranzeige · verschiebbar</span></span><button type="button" class="secondary" id="rotation-weather-edit">Bearbeiten</button></li>
              <li class="rotation-block" data-block="date" draggable="true"><span class="rotation-icon" aria-hidden="true">📅</span><span class="rotation-description"><strong>Aktive Datums-Events</strong><span>Alle aktiven Events · alphabetisch · verschiebbar</span></span><button type="button" class="secondary" id="rotation-dates-edit">Bearbeiten</button></li>
            </ol>
            <div class="actions"><button type="button" class="secondary" id="rotation-text-add">+ Textblock hinzufügen</button></div>
            <div class="actions"><button type="button" class="primary" id="rotation-start">▶ Rotation starten</button><button type="button" class="secondary" id="rotation-stop">■ Rotation stoppen</button></div>
            <p id="rotation-message" class="message" role="status" aria-live="polite"></p>
            <div id="rotation-editor" hidden>
              <h3>Rotation konfigurieren</h3>
              <label>Ordner unter pixelart<input id="rotation-folder" value="rotation" autocomplete="off"></label>
              <div class="actions"><button type="button" class="secondary" id="rotation-load">GIFs laden</button></div>
              <p class="muted">GIFs auswählen, mit den Pfeilen sortieren und Sekunden oder geschätzte Durchläufe einstellen.</p>
              <div id="rotation-list"></div>
              <label><input id="rotation-date-enabled" type="checkbox" checked>Aktive Datums-Events abspielen</label>
              <label><input id="rotation-weather-enabled" type="checkbox">Wetter abspielen</label>
              <div id="rotation-weather-settings">
                <label>Wetter-Entität<select id="rotation-weather-entity"><option value="">Bitte auswählen</option></select></label>
                <label>Wetter-Anzeigedauer (Sekunden)<input id="rotation-weather-seconds" type="number" min="0.01" max="3600" step="any" value="10"></label>
                <p class="muted">GIFs aus wetter/&lt;HA-Wetterzustand&gt;/tag oder /nacht; neue Dateien werden automatisch berücksichtigt.</p>
              </div>
              <div id="rotation-text-editor" hidden>
                <h3>Textblock bearbeiten</h3>
                <label>Name<input id="text-name" maxlength="80"></label>
                <label>Quelle<select id="text-source"><option value="fixed">Fester Text</option><option value="entity">HA-Entität oder Attribut</option><option value="list">TXT-Liste</option></select></label>
                <div id="text-fixed-group"><label>Text<input id="text-fixed" maxlength="4096"></label></div>
                <div id="text-entity-group" hidden>
                  <label>Entität<input id="text-entity" placeholder="sensor.beispiel"></label>
                  <label>Attribut (optional)<input id="text-attribute" placeholder="Zustand verwenden"></label>
                </div>
                <div id="text-list-group" hidden>
                  <label>UTF-8-TXT-Datei hochladen<input id="text-upload" type="file" accept=".txt,text/plain"></label>
                  <p id="text-list-status" class="muted"></p>
                  <label>Auswahl<select id="text-selection"><option value="daily_order">Täglich fortlaufend</option><option value="daily_random">Täglich zufällig</option><option value="call_order">Pro Aufruf fortlaufend</option><option value="call_random">Pro Aufruf zufällig</option></select></label>
                </div>
                <label>Textfarbe<input id="text-foreground" type="color" value="#ffffff"></label>
                <label>Hintergrundfarbe<input id="text-background" type="color" value="#000000"></label>
                <label>Schriftgröße<input id="text-size" type="number" min="1" max="64" step="1" value="8"></label>
                <label>Framezeit / Geschwindigkeit (ms)<input id="text-time" type="number" min="1" max="65535" step="1" value="100"></label>
                <label>Anzeigemodus<select id="text-duration-mode"><option value="seconds">Sekunden</option><option value="loops">Durchläufe (grob geschätzt)</option></select></label>
                <label>Dauer / Durchläufe<input id="text-duration" type="number" min="0.01" max="3600" step="any" value="10"></label>
                <p class="muted">Durchläufe sind nur grob geschätzt und nicht mit dem Display synchronisiert.</p>
                <div class="actions"><button type="button" class="secondary" id="text-remove">Textblock entfernen</button></div>
              </div>
              <label>Fehlerbild-Anzeigedauer (Sekunden)<input id="rotation-error-seconds" type="number" min="0.01" max="3600" step="any" value="5"></label>
              <div class="actions"><button type="button" class="primary" id="rotation-save">Rotation speichern</button></div>
            </div>
          </section>
          <section class="card">
            <details>
            <summary><strong>Ordner-Playlist · Übergang / Test</strong></summary>
            <p class="muted">GIFs aus einem Ordner wiederholt abspielen. Neue Dateien ohne gespeicherte Dauer werden übersprungen.</p>
            <form id="playlist">
              <label>Ordner unter pixelart<input name="folder" value="." required autocomplete="off"></label>
              <label>Reihenfolge<select name="order"><option value="alphabetical">Alphabetisch</option><option value="random">Zufällig</option></select></label>
              <div class="actions"><button type="button" class="secondary" id="load-gifs">GIFs laden / aktualisieren</button></div>
              <p class="muted">Für jede gewünschte Animation Sekunden eintragen (1–3600). Leer bedeutet: nicht abspielen.</p>
              <div id="gif-list"></div>
              <div class="actions"><button type="button" class="secondary" id="save-gifs" disabled>Anzeigezeiten speichern</button></div>
              <div class="actions"><button type="submit" class="primary">▶ Playlist starten</button><button type="button" class="secondary" id="stop">■ Stoppen</button></div>
              <p id="message" class="message" role="status" aria-live="polite"></p>
            </form>
            </details>
          </section>
        </div>
        <div id="page-settings" class="grid" hidden>
          <section class="card">
            <h3>Automatische Helligkeit</h3>
            <p class="muted">Die Automatik steuert das Display direkt. Bei Bewegung 100 %, mindestens 30 Sekunden. Tests gelten 30 Sekunden und setzen danach die Automatik fort.</p>
            <form id="brightness">
              <label><input type="checkbox" name="enabled">Automatik aktivieren</label>
              <label>Divoom-Gerätekennung für alle Wiedergaben<input name="device" required autocomplete="off"></label>
              <p class="muted">Einmal speichern; gilt für Helligkeit, Event-Tests und die Ordner-Playlist.</p>
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
              <div class="actions"><button type="submit" class="primary">Einstellungen speichern</button></div>
              <p id="brightness-message" class="message" role="status" aria-live="polite"></p>
            </form>
          </section>
        </div>
      </main>`;
    this._initialized = true;
    this.shadowRoot.querySelector("#menu").addEventListener("click", () => {
      this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
    });
    this.shadowRoot.querySelectorAll("[data-page]").forEach((button) => {
      button.addEventListener("click", () => this._showPage(button.dataset.page));
    });
    this._initRotation();
    this.shadowRoot.querySelector("#playlist").addEventListener("submit", (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const input = form.elements.folder;
      input.setCustomValidity(input.value.trim() ? "" : "Bitte einen Wert eingeben.");
      if (!form.reportValidity()) return;
      if (!this._device) {
        this._playlistMessage("Bitte zuerst die Gerätekennung in den Einstellungen speichern.", true);
        return;
      }
      const data = new FormData(form);
      if (this._gifFolder !== data.get("folder").trim() || this._gifDirty) {
        this._playlistMessage("Bitte GIFs laden und Änderungen an Anzeigezeiten speichern.", true);
        return;
      }
      this._call("start", {
        device: this._device,
        folder: data.get("folder").trim(),
        duration: 10,
        order: data.get("order"),
        individual_durations: true,
      });
    });
    this.shadowRoot.querySelector('#playlist [name="folder"]').addEventListener("input", (event) => {
      event.currentTarget.setCustomValidity("");
    });
    this.shadowRoot.querySelector("#stop").addEventListener("click", () => this._call("stop", {}));
    const playlist = this.shadowRoot.querySelector("#playlist");
    playlist.elements.folder.addEventListener("input", () => {
      this._gifRevision = (this._gifRevision || 0) + 1;
      this._updateGifButtons();
      if (this._gifFolder && playlist.elements.folder.value.trim() !== this._gifFolder) {
        this._playlistMessage(`Die angezeigten GIFs gehören noch zu "${this._gifFolder}".`);
      }
    });
    this.shadowRoot.querySelector("#load-gifs").addEventListener("click", () => this._loadGifs());
    this.shadowRoot.querySelector("#save-gifs").addEventListener("click", () => this._saveGifs());
    this._initEvents();
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

  _showPage(page) {
    for (const name of ["overview", "events", "settings"]) {
      this.shadowRoot.querySelector(`#page-${name}`).hidden = name !== page;
      const button = this.shadowRoot.querySelector(`[data-page="${name}"]`);
      if (name === page) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    }
  }

  _rotationMessage(text, error = false) {
    const message = this.shadowRoot.querySelector("#rotation-message");
    message.textContent = text;
    message.classList.toggle("error", error);
  }

  _rotationChanged() {
    this._rotationDirty = true;
    this._rotationRevision++;
  }

  _newTextId() {
    return Array.from(crypto.getRandomValues(new Uint8Array(16)),
      (byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  _initRotation() {
    const get = (name) => this.shadowRoot.querySelector(`#rotation-${name}`);
    this._rotationFiles = null;
    this._rotationDirty = false;
    this._rotationRevision = 0;
    this._rotationTexts = Object.create(null);
    get("edit").addEventListener("click", () => { get("editor").hidden = !get("editor").hidden; });
    get("dates-edit").addEventListener("click", () => this._showPage("events"));
    get("weather-edit").addEventListener("click", () => { get("editor").hidden = false; get("weather-entity").focus(); });
    get("folder").addEventListener("input", () => this._rotationChanged());
    get("date-enabled").addEventListener("change", () => this._rotationChanged());
    for (const id of ["weather-enabled", "weather-entity", "weather-seconds"]) {
      get(id).addEventListener("change", () => this._rotationChanged());
      get(id).addEventListener("input", () => this._rotationChanged());
    }
    const weather = get("weather-entity");
    Object.keys(this._hass.states).filter((id) => id.startsWith("weather.")).sort().forEach((id) => {
      weather.add(new Option(this._hass.states[id].attributes?.friendly_name || id, id));
    });
    const blocks = get("blocks");
    get("text-add").addEventListener("click", () => {
      const id = `text:${this._newTextId()}`;
      this._rotationTexts[id] = this._textDefaults();
      this._textBlock(id);
      this._rotationChanged();
      this._textEdit(id);
    });
    this._initTextEditor();
    let dragged = null;
    blocks.addEventListener("dragstart", (event) => {
      const block = event.target.closest("[data-block]");
      if (!block) return;
      dragged = block;
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", block.dataset.block);
    });
    blocks.addEventListener("dragover", (event) => {
      if (dragged && event.target.closest("[data-block]")) event.preventDefault();
    });
    blocks.addEventListener("drop", (event) => {
      const target = event.target.closest("[data-block]");
      if (!dragged || !target || target === dragged) return;
      event.preventDefault();
      const rect = target.getBoundingClientRect();
      blocks.insertBefore(dragged, event.clientY < rect.top + rect.height / 2 ? target : target.nextSibling);
      this._rotationChanged();
      dragged = null;
    });
    blocks.addEventListener("dragend", () => { dragged = null; });
    get("error-seconds").addEventListener("input", () => this._rotationChanged());
    get("load").addEventListener("click", () => this._rotationLoadFiles());
    get("save").addEventListener("click", () => this._rotationSave());
    for (const action of ["start", "stop"]) {
      get(action).addEventListener("click", async () => {
        if (action === "start" && this._rotationDirty) {
          this._rotationMessage("Bitte Änderungen an der Rotation zuerst speichern.", true);
          return;
        }
        try {
          await this._hass.callWS({type: `divoom_orchestrator/rotation_${action}`});
          this._rotationMessage(action === "start" ? "Rotation gestartet." : "Rotation gestoppt.");
        } catch (error) {
          this._rotationMessage(`Rotation: ${error.message || String(error)}`, true);
        }
      });
    }
    this._hass.callWS({type: "divoom_orchestrator/rotation"}).then((config) => {
      if (!config) return;
      if (this._rotationDirty) {
        this._rotationMessage("Gespeicherte Rotation wurde nicht geladen, da bereits Änderungen vorliegen.", true);
        return;
      }
      get("folder").value = config.folder;
      get("date-enabled").checked = config.date_events;
      get("error-seconds").value = config.error_seconds;
      const order = config.blocks || (config.date_events ? ["date"] : []);
      this._rotationTexts = Object.assign(Object.create(null), config.texts || {});
      get("weather-enabled").checked = order.includes("weather");
      get("date-enabled").checked = order.includes("date");
      if (config.weather) {
        if (![...weather.options].some((option) => option.value === config.weather.entity)) {
          weather.add(new Option(`${config.weather.entity} (nicht verfügbar)`, config.weather.entity));
        }
        weather.value = config.weather.entity;
        get("weather-seconds").value = config.weather.seconds;
      }
      for (const name of order) {
        const block = name.startsWith("text:") ? this._textBlock(name) :
          blocks.querySelector(`[data-block="${name}"]`);
        if (block) blocks.append(block);
      }
      this._rotationLoadFiles(config.steps);
    }).catch((error) => this._rotationMessage(`Rotation konnte nicht geladen werden: ${error.message || String(error)}`, true));
  }

  async _rotationLoadFiles(saved = []) {
    const folder = this.shadowRoot.querySelector("#rotation-folder").value.trim();
    if (!folder) return this._rotationMessage("Bitte einen Ordner eingeben.", true);
    if (this._rotationDirty && !window.confirm("Ungespeicherte Rotationseinstellungen verwerfen?")) return;
    const revision = this._rotationRevision;
    try {
      const entries = await this._hass.callWS({type: "divoom_orchestrator/playlist_files", folder});
      if (this.shadowRoot.querySelector("#rotation-folder").value.trim() !== folder ||
          revision !== this._rotationRevision) {
        return this._rotationMessage("Einstellungen geändert; bitte erneut laden.", true);
      }
      this._rotationFolder = folder;
      this._rotationFiles = entries.map((entry) => entry.file);
      const list = this.shadowRoot.querySelector("#rotation-list");
      list.replaceChildren();
      const selected = new Set(saved.map((step) => step.file));
      for (const step of saved) this._rotationRow(step.file, step);
      for (const file of this._rotationFiles) if (!selected.has(file)) this._rotationRow(file, null);
      if (saved.length) this._rotationDirty = false;
      this._rotationMessage(`${entries.length} GIF(s) geladen.`);
      this._eventPreviews(folder, Array.from(list.children), this._rotationFiles);
    } catch (error) {
      this._rotationFiles = null;
      this._rotationMessage(`Ordner konnte nicht geladen werden: ${error.message || String(error)}`, true);
    }
  }

  _rotationRow(file, step) {
    const list = this.shadowRoot.querySelector("#rotation-list");
    this._eventRow(file, step, !this._rotationFiles.includes(file), list,
      () => this._rotationChanged());
  }

  _textDefaults() {
    return {name: "Text", source: "fixed", text: "", entity: "", attribute: "",
      lines: [], list_version: "", selection: "daily_order", foreground: [255, 255, 255],
      background: [0, 0, 0], size: 8, time: 100, duration_mode: "seconds", duration: 10};
  }

  _textBlock(id) {
    const block = document.createElement("li");
    block.className = "rotation-block";
    block.dataset.block = id;
    block.draggable = true;
    const icon = document.createElement("span");
    icon.className = "rotation-icon";
    icon.textContent = "💬";
    const description = document.createElement("span");
    description.className = "rotation-description";
    const name = document.createElement("strong");
    name.textContent = this._rotationTexts[id]?.name || "Text";
    const subtitle = document.createElement("span");
    subtitle.textContent = "Textblock · verschiebbar";
    description.append(name, subtitle);
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "secondary";
    edit.textContent = "Bearbeiten";
    edit.addEventListener("click", () => this._textEdit(id));
    block.append(icon, description, edit);
    this.shadowRoot.querySelector("#rotation-blocks").append(block);
    return block;
  }

  _initTextEditor() {
    const get = (name) => this.shadowRoot.querySelector(`#text-${name}`);
    const fields = {
      name: "name", source: "source", fixed: "text", entity: "entity", attribute: "attribute",
      selection: "selection", size: "size", time: "time", "duration-mode": "duration_mode",
      duration: "duration",
    };
    for (const [field, key] of Object.entries(fields)) {
      const input = get(field);
      const update = () => {
        const settings = this._rotationTexts[this._editingText];
        if (!settings) return;
        settings[key] = input.type === "number" ? Number(input.value) : input.value;
        this._rotationChanged();
        if (field === "name") {
          const block = [...this.shadowRoot.querySelectorAll("#rotation-blocks [data-block]")]
            .find((item) => item.dataset.block === this._editingText);
          if (block) block.querySelector("strong").textContent = settings.name || "Text";
        }
        if (field === "source") this._textSource();
      };
      input.addEventListener("input", update);
      input.addEventListener("change", update);
    }
    for (const name of ["foreground", "background"]) {
      get(name).addEventListener("input", () => {
        const settings = this._rotationTexts[this._editingText];
        if (!settings) return;
        settings[name] = get(name).value.match(/[0-9a-f]{2}/gi).map((part) => parseInt(part, 16));
        this._rotationChanged();
      });
    }
    get("upload").addEventListener("change", async () => {
      const id = this._editingText;
      const file = get("upload").files[0];
      if (!file) return;
      try {
        if (file.size > 1024 * 1024) throw new Error("Datei ist größer als 1 MiB.");
        const text = new TextDecoder("utf-8", {fatal: true}).decode(await file.arrayBuffer());
        const lines = text.replace(/^\uFEFF/, "").split(/\r\n|\n|\r/).map((line) => line.trim()).filter(Boolean);
        if (!lines.length || lines.length > 10000 || lines.some((line) => line.length > 4096)) {
          throw new Error("Die Datei benötigt 1–10000 nichtleere Zeilen mit höchstens 4096 Zeichen.");
        }
        const settings = this._rotationTexts[id];
        if (!settings) return;
        settings.lines = lines;
        settings.list_version = this._newTextId();
        this._rotationChanged();
        if (id === this._editingText) get("list-status").textContent = `${lines.length} Zeilen geladen; Fortschritt wird beim Speichern zurückgesetzt.`;
      } catch (error) {
        this._rotationMessage(`TXT-Upload fehlgeschlagen: ${error.message || String(error)}`, true);
      } finally {
        get("upload").value = "";
      }
    });
    get("remove").addEventListener("click", () => {
      const id = this._editingText;
      if (!id || !window.confirm("Textblock entfernen?")) return;
      const block = [...this.shadowRoot.querySelectorAll("#rotation-blocks [data-block]")]
        .find((item) => item.dataset.block === id);
      if (block) block.remove();
      delete this._rotationTexts[id];
      this._editingText = null;
      this.shadowRoot.querySelector("#rotation-text-editor").hidden = true;
      this._rotationChanged();
    });
  }

  _textSource() {
    const source = this.shadowRoot.querySelector("#text-source").value;
    for (const name of ["fixed", "entity", "list"]) {
      this.shadowRoot.querySelector(`#text-${name}-group`).hidden = source !== name;
    }
  }

  _textEdit(id) {
    const settings = this._rotationTexts[id];
    if (!settings) return;
    this._editingText = id;
    this.shadowRoot.querySelector("#rotation-editor").hidden = false;
    this.shadowRoot.querySelector("#rotation-text-editor").hidden = false;
    const fields = {name: "name", source: "source", fixed: "text", entity: "entity",
      attribute: "attribute", selection: "selection", size: "size", time: "time",
      "duration-mode": "duration_mode", duration: "duration"};
    for (const [field, key] of Object.entries(fields)) this.shadowRoot.querySelector(`#text-${field}`).value = settings[key];
    for (const name of ["foreground", "background"]) {
      this.shadowRoot.querySelector(`#text-${name}`).value = `#${settings[name].map((n) => n.toString(16).padStart(2, "0")).join("")}`;
    }
    this.shadowRoot.querySelector("#text-list-status").textContent = `${settings.lines.length} Zeilen gespeichert.`;
    this._textSource();
    this.shadowRoot.querySelector("#text-name").focus();
  }

  async _rotationSave() {
    const get = (name) => this.shadowRoot.querySelector(`#rotation-${name}`);
    if (!this._rotationFiles || get("folder").value.trim() !== this._rotationFolder) {
      return this._rotationMessage("Bitte zuerst den Ordner laden.", true);
    }
    const steps = [];
    for (const row of get("list").children) {
      if (!row.querySelector('input[type="checkbox"]').checked) continue;
      const input = row.querySelector('input[type="number"]');
      if (!input.reportValidity()) return;
      steps.push({file: row.dataset.file, mode: row.querySelector("select").value, value: Number(input.value)});
    }
    if (!steps.length) return this._rotationMessage("Bitte mindestens ein GIF auswählen.", true);
    if (!get("error-seconds").reportValidity()) return;
    if (get("weather-enabled").checked &&
        (!get("weather-entity").value || !get("weather-seconds").reportValidity())) {
      return this._rotationMessage("Bitte Wetter-Entität und Anzeigedauer wählen.", true);
    }
    const blocks = [...get("blocks").querySelectorAll("[data-block]")]
      .map((block) => block.dataset.block)
      .filter((name) => name.startsWith("text:") ||
        get(name === "date" ? "date-enabled" : "weather-enabled").checked);
    const config = {
      folder: this._rotationFolder, steps, date_events: get("date-enabled").checked,
      error_seconds: Number(get("error-seconds").value), blocks, texts: this._rotationTexts,
    };
    if (get("weather-entity").value) config.weather = {
      entity: get("weather-entity").value, seconds: Number(get("weather-seconds").value),
    };
    const revision = this._rotationRevision;
    try {
      await this._hass.callWS({type: "divoom_orchestrator/rotation_save", config, files: this._rotationFiles});
      if (revision === this._rotationRevision) this._rotationDirty = false;
      this._rotationMessage(this._rotationDirty
        ? "Gespeichert; neuere Änderungen sind noch offen."
        : "Rotation gespeichert. Änderungen gelten ab dem nächsten Durchlauf.");
    } catch (error) {
      this._rotationMessage(`Speichern fehlgeschlagen: ${error.message || String(error)}`, true);
    }
  }

  _updateConnection() {
    const element = this.shadowRoot.querySelector("#connection-status");
    if (!element) return;
    if (this._connectionId === undefined) {
      element.textContent = "Status wird geladen …";
      return;
    }
    if (!this._connectionId) {
      element.textContent = "Kein Bluetooth-Statussensor konfiguriert.";
      return;
    }
    const state = this._hass.states[this._connectionId];
    element.textContent = state
      ? `${state.attributes?.friendly_name || this._connectionId}: ${state.state}`
      : `${this._connectionId}: nicht verfügbar`;
  }

  _playlistMessage(text, error = false) {
    const message = this.shadowRoot.querySelector("#message");
    message.textContent = text;
    message.classList.toggle("error", error);
  }

  _eventMessage(text, error = false) {
    const message = this.shadowRoot.querySelector("#event-message");
    message.textContent = text;
    message.classList.toggle("error", error);
  }

  _initEvents() {
    this._events = Object.create(null);
    this._eventDirty = false;
    this._eventFiles = [];
    this._eventRevision = 0;
    this._eventKind = "trigger";
    this._updateEventKind();
    const get = (id) => this.shadowRoot.querySelector(`#event-${id}`);
    const dirty = () => { this._eventDirty = true; this._eventRevision++; };
    get("name").addEventListener("input", dirty);
    for (const id of ["enabled", "priority", "date-mode", "date-start", "date-end",
      "trigger-type", "trigger-entity", "trigger-to", "trigger-event"]) {
      get(id).addEventListener("change", dirty);
    }
    for (const id of ["date-start", "date-end"]) get(id).addEventListener("input", dirty);
    get("date-mode").addEventListener("change", () => this._eventDateMode());
    get("trigger-type").addEventListener("change", () => this._eventTriggerMode());
    get("choice").addEventListener("change", async () => {
      const selected = get("choice").value;
      if (this._eventLoading || this._eventSaving) {
        get("choice").value = this._eventSelected || "";
        return;
      }
      if (this._eventDirty && !window.confirm("Ungespeicherte Event-Änderungen verwerfen?")) {
        get("choice").value = this._eventSelected || "";
        return;
      }
      this._eventSelected = selected;
      const event = this._events[selected];
      this._eventKind = event?.kind || "trigger";
      this._updateEventKind();
      this._eventChoices(selected);
      get("name").value = selected;
      this._eventSetSchedule(event);
      this._eventDirty = false;
      await this._eventLoadFolder(event?.folder || ".", event?.steps || []);
    });
    this.shadowRoot.querySelectorAll("[data-new-event]").forEach((button) => {
      button.addEventListener("click", async () => {
        if (this._eventLoading || this._eventSaving) return;
        if (this._eventDirty && !window.confirm("Ungespeicherte Event-Änderungen verwerfen?")) return;
        this._eventKind = button.dataset.newEvent;
        this._updateEventKind();
        this._eventChoices("");
        get("name").value = "";
        this._eventSetSchedule(null);
        this._eventDirty = false;
        await this._eventLoadDefaultFolder();
      });
    });
    get("open").addEventListener("click", () => {
      if (get("subfolder").value) this._eventChangeFolder(get("subfolder").value);
    });
    get("up").addEventListener("click", () => {
      const folder = get("folder").value;
      if (folder !== ".") this._eventChangeFolder(folder.includes("/") ? folder.slice(0, folder.lastIndexOf("/")) : ".");
    });
    get("refresh").addEventListener("click", () => this._eventChangeFolder(get("folder").value));
    get("save").addEventListener("click", () => this._eventSave());
    get("test").addEventListener("click", () => this._eventTest());
    get("delete").addEventListener("click", () => this._eventDelete());
    this._eventLoadInitial();
  }

  async _eventLoadInitial() {
    try {
      this._events = Object.assign(Object.create(null),
        await this._hass.callWS({type: "divoom_orchestrator/events"}));
      this._eventChoices("");
      await this._eventLoadFolder(".", []);
    } catch (error) {
      this._eventMessage(`Events konnten nicht geladen werden: ${error.message || String(error)}`, true);
    }
  }

  async _eventLoadDefaultFolder() {
    if (this._eventKind !== "date") {
      await this._eventLoadFolder(".", []);
      return;
    }
    this._eventLoading = true;
    this._eventFolderReady = false;
    try {
      const folders = await this._hass.callWS({type: "divoom_orchestrator/event_folders", folder: "."});
      await this._eventLoadFolder(folders.includes("date_events") ? "date_events" : ".", []);
    } catch (error) {
      this._eventFolderReady = false;
      this._eventMessage(`Ordner konnte nicht geladen werden: ${error.message || String(error)}`, true);
    } finally {
      this._eventLoading = false;
    }
  }

  _eventChoices(selected) {
    const choice = this.shadowRoot.querySelector("#event-choice");
    choice.replaceChildren(new Option("Neues Event", ""));
    Object.keys(this._events).sort((a, b) => a.localeCompare(b))
      .forEach((name) => choice.add(new Option(name, name)));
    choice.value = selected;
    this._eventSelected = selected;
    for (const kind of ["trigger", "date"]) {
      const list = this.shadowRoot.querySelector(`#events-${kind}`);
      list.replaceChildren();
      Object.keys(this._events).filter((name) => (this._events[name].kind || "trigger") === kind)
        .sort((a, b) => a.localeCompare(b))
        .forEach((name) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "secondary";
          button.textContent = name;
          if (selected === name) button.setAttribute("aria-current", "true");
          button.addEventListener("click", () => {
            choice.value = name;
            choice.dispatchEvent(new Event("change"));
          });
          list.append(button);
        });
    }
  }

  _updateEventKind() {
    this.shadowRoot.querySelector("#event-dates").hidden = this._eventKind !== "date";
    this.shadowRoot.querySelector("#event-priority-group").hidden = this._eventKind !== "trigger";
    this.shadowRoot.querySelector("#event-kind").textContent = this._eventKind === "date"
      ? "Datums-Event: aktive Events werden in die Rotation eingefügt."
      : "Triggered-Event: wähle einen Auslöser und eine Priorität.";
  }

  _eventTriggerMode() {
    const type = this.shadowRoot.querySelector("#event-trigger-type").value;
    this.shadowRoot.querySelector("#event-trigger-state").hidden = type !== "state";
    this.shadowRoot.querySelector("#event-trigger-bus").hidden = type !== "event";
  }

  _eventDateMode() {
    const annual = this.shadowRoot.querySelector("#event-date-mode").value === "annual";
    for (const id of ["start", "end"]) {
      this.shadowRoot.querySelector(`#event-date-${id}`).placeholder = annual ? "MM-TT" : "JJJJ-MM-TT";
    }
  }

  _eventSetSchedule(event) {
    this.shadowRoot.querySelector("#event-enabled").checked = event?.enabled !== false;
    this.shadowRoot.querySelector("#event-priority").value = event?.priority ?? 3;
    this.shadowRoot.querySelector("#event-date-mode").value = event?.schedule?.mode || "annual";
    this.shadowRoot.querySelector("#event-date-start").value = event?.schedule?.start || "";
    this.shadowRoot.querySelector("#event-date-end").value = event?.schedule?.end || "";
    this.shadowRoot.querySelector("#event-trigger-type").value = event?.trigger?.type || "manual";
    this.shadowRoot.querySelector("#event-trigger-entity").value = event?.trigger?.entity_id || "";
    this.shadowRoot.querySelector("#event-trigger-to").value = event?.trigger?.to || "";
    this.shadowRoot.querySelector("#event-trigger-event").value = event?.trigger?.event_type || "";
    this._eventTriggerMode();
    this._eventDateMode();
  }

  async _eventChangeFolder(folder) {
    if (this._eventLoading || this._eventSaving) return;
    const sameFolder = folder === this.shadowRoot.querySelector("#event-folder").value;
    if (!sameFolder && this._eventDirty &&
        !window.confirm("Ungespeicherte GIF-Auswahl verwerfen?")) return;
    const selected = sameFolder ? Array.from(this.shadowRoot.querySelector("#event-list").children)
      .filter((row) => row.querySelector('input[type="checkbox"]').checked)
      .map((row) => ({
        file: row.dataset.file, mode: row.querySelector("select").value,
        value: row.querySelector('input[type="number"]').value,
      })) : [];
    await this._eventLoadFolder(folder, selected);
    if (!sameFolder) {
      this._eventDirty = true;
      this._eventRevision++;
    }
  }

  async _eventLoadFolder(folder, selected) {
    const revision = ++this._eventRevision;
    this._eventLoading = true;
    this._eventFolderReady = false;
    this._eventMessage("Ordner wird geladen …");
    try {
      const [subfolders, files] = await Promise.all([
        this._hass.callWS({type: "divoom_orchestrator/event_folders", folder}),
        this._hass.callWS({type: "divoom_orchestrator/playlist_files", folder}),
      ]);
      if (revision !== this._eventRevision) {
        this._eventMessage("Eingaben geändert; bitte Ordner erneut laden.", true);
        return;
      }
      this.shadowRoot.querySelector("#event-folder").value = folder;
      const subfolder = this.shadowRoot.querySelector("#event-subfolder");
      subfolder.replaceChildren(new Option("Unterordner auswählen", ""));
      subfolders.forEach((value) => subfolder.add(new Option(value.split("/").pop(), value)));
      this._eventFiles = files.map((item) => item.file);
      this._eventFolderReady = true;
      const list = this.shadowRoot.querySelector("#event-list");
      list.replaceChildren();
      const selectedFiles = new Set(selected.map((step) => step.file));
      for (const step of selected) this._eventRow(step.file, step, !this._eventFiles.includes(step.file));
      for (const file of this._eventFiles) {
        if (!selectedFiles.has(file)) this._eventRow(file, null, false);
      }
      this._eventMessage(`${files.length} GIF(s) im Ordner gefunden.`);
      this._eventPreviews(folder, Array.from(list.children));
    } catch (error) {
      this._eventMessage(`Ordner konnte nicht geladen werden: ${error.message || String(error)}`, true);
    } finally {
      this._eventLoading = false;
    }
  }

  _eventRow(file, step, missing, list = this.shadowRoot.querySelector("#event-list"),
      dirty = () => { this._eventDirty = true; this._eventRevision++; }) {
    const row = document.createElement("div");
    row.className = "event-row";
    row.dataset.file = file;
    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = !!step;
    check.setAttribute("aria-label", `${file} auswählen`);
    const image = document.createElement("img");
    image.className = "gif-preview";
    image.alt = `Vorschau ${file}`;
    const detail = document.createElement("span");
    detail.className = "gif-detail";
    const name = document.createElement("span");
    name.textContent = file;
    const info = document.createElement("small");
    info.textContent = missing ? "Datei fehlt – bitte abwählen." : "Vorschau wird geladen …";
    detail.append(name, info);
    const mode = document.createElement("select");
    mode.setAttribute("aria-label", `Anzeigemodus für ${file}`);
    mode.add(new Option("Sekunden", "seconds"));
    mode.add(new Option("Durchläufe (ca.)", "loops"));
    mode.value = step?.mode || "seconds";
    const value = document.createElement("input");
    value.type = "number";
    value.min = "0.01";
    value.max = "3600";
    value.step = "any";
    value.required = true;
    value.value = step?.value ?? 10;
    value.setAttribute("aria-label", `Dauer oder Durchläufe für ${file}`);
    for (const input of [check, mode, value]) input.addEventListener("change", dirty);
    value.addEventListener("input", dirty);
    const up = document.createElement("button");
    up.type = "button";
    up.textContent = "↑";
    up.setAttribute("aria-label", `${file} nach oben`);
    const down = document.createElement("button");
    down.type = "button";
    down.textContent = "↓";
    down.setAttribute("aria-label", `${file} nach unten`);
    up.addEventListener("click", () => {
      if (row.previousElementSibling) { row.parentElement.insertBefore(row, row.previousElementSibling); dirty(); }
    });
    down.addEventListener("click", () => {
      if (row.nextElementSibling) { row.parentElement.insertBefore(row.nextElementSibling, row); dirty(); }
    });
    row.append(check, image, detail, mode, value, up, down);
    list.append(row);
  }

  async _eventPreviews(folder, rows, available = this._eventFiles) {
    for (const row of rows) {
      if (!row.isConnected) return;
      if (!available.includes(row.dataset.file)) continue;
      const info = row.querySelector("small");
      try {
        const preview = await this._hass.callWS({
          type: "divoom_orchestrator/gif_preview", folder, file: row.dataset.file,
        });
        if (!row.isConnected) return;
        row.querySelector("img").src = `data:image/gif;base64,${preview.data}`;
        info.textContent = preview.cycle_seconds === null
          ? "Keine verwertbare Durchlaufdauer; Sekunden verwenden."
          : `Ein Durchlauf: ca. ${preview.cycle_seconds} s`;
      } catch (error) {
        info.textContent = `Vorschau nicht verfügbar: ${error.message || String(error)}`;
      }
    }
  }

  async _eventSave() {
    if (this._eventLoading || this._eventSaving) return;
    if (!this._eventFolderReady) return this._eventMessage("Bitte zuerst einen Ordner erfolgreich laden.", true);
    const get = (id) => this.shadowRoot.querySelector(`#event-${id}`);
    const name = get("name").value.trim();
    if (!name) return this._eventMessage("Bitte Eventname eingeben.", true);
    if (name !== this._eventSelected && this._events[name] &&
        !window.confirm(`Event "${name}" überschreiben?`)) return;
    const steps = [];
    for (const row of get("list").children) {
      if (!row.querySelector('input[type="checkbox"]').checked) continue;
      const input = row.querySelector('input[type="number"]');
      if (!input.reportValidity()) return;
      steps.push({file: row.dataset.file, mode: row.querySelector("select").value, value: Number(input.value)});
    }
    if (!steps.length) return this._eventMessage("Bitte mindestens ein GIF auswählen.", true);
    const event = {kind: this._eventKind, enabled: get("enabled").checked, folder: get("folder").value, steps};
    if (this._eventKind === "trigger") {
      if (!get("priority").reportValidity()) return;
      event.priority = Number(get("priority").value);
      const type = get("trigger-type").value;
      event.trigger = {type};
      if (type === "state") {
        event.trigger.entity_id = get("trigger-entity").value.trim();
        event.trigger.to = get("trigger-to").value.trim();
        if (!event.trigger.entity_id || !event.trigger.to) return this._eventMessage("Bitte Entität und Zielzustand eingeben.", true);
      } else if (type === "event") {
        event.trigger.event_type = get("trigger-event").value.trim();
        if (!event.trigger.event_type) return this._eventMessage("Bitte einen HA-Eventtyp eingeben.", true);
      }
    }
    if (this._eventKind === "date") {
      event.schedule = {
        mode: get("date-mode").value,
        start: get("date-start").value.trim(),
        end: get("date-end").value.trim(),
      };
      if (!event.schedule.start || !event.schedule.end) {
        return this._eventMessage("Bitte Beginn und Ende des Datums-Events eingeben.", true);
      }
    }
    const revision = this._eventRevision;
    this._eventSaving = true;
    try {
      await this._hass.callWS({type: "divoom_orchestrator/event_save", name, event, files: this._eventFiles});
      this._events[name] = event;
      this._eventChoices(name);
      if (revision === this._eventRevision) this._eventDirty = false;
      this._eventMessage(this._eventDirty ? "Gespeichert; neuere Änderungen sind noch offen." : "Event gespeichert.");
    } catch (error) {
      this._eventMessage(`Speichern fehlgeschlagen: ${error.message || String(error)}`, true);
    } finally {
      this._eventSaving = false;
    }
  }

  async _eventTest() {
    if (this._eventLoading || this._eventSaving) return;
    if (!this._eventSelected || this._eventDirty) {
      return this._eventMessage("Bitte Event zuerst speichern.", true);
    }
    try {
      await this._hass.callWS({type: "divoom_orchestrator/event_test", name: this._eventSelected});
      this._eventMessage("Event-Test gestartet. Wiedergabefehler meldet Home Assistant separat.");
    } catch (error) {
      this._eventMessage(`Event-Test fehlgeschlagen: ${error.message || String(error)}`, true);
    }
  }

  async _eventDelete() {
    if (this._eventLoading || this._eventSaving) return;
    const name = this._eventSelected;
    if (!name || !window.confirm(`Event "${name}" löschen?`)) return;
    try {
      await this._hass.callWS({type: "divoom_orchestrator/event_delete", name});
      delete this._events[name];
      this._eventChoices("");
      this.shadowRoot.querySelector("#event-name").value = "";
      this._eventKind = "trigger";
      this._updateEventKind();
      this._eventSetSchedule(null);
      this._eventDirty = false;
      await this._eventLoadFolder(".", []);
      this._eventMessage("Event gelöscht.");
    } catch (error) {
      this._eventMessage(`Löschen fehlgeschlagen: ${error.message || String(error)}`, true);
    }
  }

  _updateGifButtons() {
    const form = this.shadowRoot.querySelector("#playlist");
    this.shadowRoot.querySelector("#load-gifs").disabled = !!this._gifBusy;
    this.shadowRoot.querySelector("#save-gifs").disabled = !!this._gifBusy ||
      !this._gifFolder || form.elements.folder.value.trim() !== this._gifFolder;
  }

  async _loadGifs() {
    if (this._gifBusy) return;
    const form = this.shadowRoot.querySelector("#playlist");
    const folder = form.elements.folder.value.trim();
    if (!folder) {
      this._playlistMessage("Bitte einen Ordner eingeben.", true);
      return;
    }
    if (this._gifDirty && !window.confirm("Ungespeicherte Anzeigezeiten verwerfen?")) return;
    const revision = this._gifRevision;
    this._gifBusy = true;
    this._updateGifButtons();
    this._playlistMessage("GIFs werden geladen …");
    try {
      const files = await this._hass.callWS({ type: "divoom_orchestrator/playlist_files", folder });
      if (form.elements.folder.value.trim() !== folder || this._gifRevision !== revision) {
        this._playlistMessage("Die Eingaben haben sich geändert; bitte erneut laden.", true);
        return;
      }
      const list = this.shadowRoot.querySelector("#gif-list");
      list.replaceChildren();
      for (const entry of files) {
        const label = document.createElement("label");
        label.className = "gif-row";
        const image = document.createElement("img");
        image.className = "gif-preview";
        image.alt = `Vorschau ${entry.file}`;
        const detail = document.createElement("span");
        detail.className = "gif-detail";
        const text = document.createElement("span");
        text.textContent = entry.file;
        const info = document.createElement("small");
        info.textContent = "Vorschau wird geladen …";
        detail.append(text, info);
        const input = document.createElement("input");
        input.type = "number";
        input.min = "1";
        input.max = "3600";
        input.step = "any";
        input.placeholder = "Sek.";
        input.value = entry.duration ?? "";
        input.dataset.file = entry.file;
        input.setAttribute("aria-label", `Sekunden für ${entry.file}`);
        input.addEventListener("input", () => {
          this._gifDirty = true;
          this._gifRevision = (this._gifRevision || 0) + 1;
        });
        label.append(image, detail, input);
        list.appendChild(label);
      }
      this._gifFolder = folder;
      this._gifDirty = false;
      this._playlistMessage(`${files.length} GIF(s) gefunden. Leere Felder werden übersprungen.`);
      this._loadPreviews(folder, files, list);
    } catch (error) {
      this._playlistMessage(`Ordner konnte nicht gelesen werden: ${error.message || String(error)}`, true);
    } finally {
      this._gifBusy = false;
      this._updateGifButtons();
    }
  }

  async _loadPreviews(folder, files, list) {
    const rows = Array.from(list.children);
    for (let index = 0; index < files.length; index++) {
      if (this._gifFolder !== folder || !rows[index].isConnected) return;
      const info = rows[index].querySelector("small");
      try {
        const preview = await this._hass.callWS({
          type: "divoom_orchestrator/gif_preview", folder, file: files[index].file,
        });
        if (this._gifFolder !== folder || !rows[index].isConnected) return;
        rows[index].querySelector("img").src = `data:image/gif;base64,${preview.data}`;
        info.textContent = preview.cycle_seconds === null
          ? "Keine verwertbare Durchlaufdauer."
          : `GIF-Durchlauf: ca. ${preview.cycle_seconds} s (Pixoo kann abweichen)`;
      } catch (error) {
        info.textContent = `Vorschau nicht verfügbar: ${error.message || String(error)}`;
      }
    }
  }

  async _saveGifs() {
    const form = this.shadowRoot.querySelector("#playlist");
    if (this._gifBusy || !this._gifFolder || form.elements.folder.value.trim() !== this._gifFolder) return;
    const durations = {};
    const files = [];
    for (const input of this.shadowRoot.querySelectorAll("#gif-list input")) {
      if (!input.reportValidity()) return;
      files.push(input.dataset.file);
      if (input.value !== "") durations[input.dataset.file] = Number(input.value);
    }
    const folder = this._gifFolder;
    const revision = this._gifRevision;
    this._gifBusy = true;
    this._updateGifButtons();
    try {
      await this._hass.callService("divoom_orchestrator", "playlist_durations", {
        folder, durations, files,
      });
      if (this._gifFolder === folder && this._gifRevision === revision) {
        this._gifDirty = false;
        this._playlistMessage("Anzeigezeiten gespeichert.");
      } else {
        this._playlistMessage("Gespeichert; neuere Änderungen sind noch nicht gespeichert.");
      }
    } catch (error) {
      this._playlistMessage(`Speichern fehlgeschlagen: ${error.message || String(error)}`, true);
    } finally {
      this._gifBusy = false;
      this._updateGifButtons();
    }
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
      this._device = config.device.trim();
      this._connectionId = config.connection;
      this._updateConnection();
      message.textContent = "";
      form.querySelectorAll("button").forEach((button) => { button.disabled = false; });
    } catch (error) {
      this.shadowRoot.querySelector("#connection-status").textContent =
        `Statussensor-Einstellung nicht verfügbar: ${error.message || String(error)}`;
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
      if (action === "brightness_configure") {
        this._device = data.device;
        this._connectionId = data.connection;
        this._updateConnection();
      }
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
    const buttons = this.shadowRoot.querySelectorAll('#playlist button[type="submit"], #stop');
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
