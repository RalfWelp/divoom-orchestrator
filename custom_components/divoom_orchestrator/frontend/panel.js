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
        .hero { border-radius:18px; padding:14px 20px; background:linear-gradient(115deg,#145c70,#278b84); color:#fff; margin-bottom:22px; }
        .eyebrow { font-size:12px; letter-spacing:.12em; font-weight:700; text-transform:uppercase; opacity:.85; }
        h2 { font-size:23px; margin:9px 0; } p { line-height:1.5; }
        .hero h2 { margin:3px 0; font-size:20px; }
        .hero p { margin:3px 0; line-height:1.4; }
        .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr)); gap:20px; }
        .card { background:var(--panel-card); border-radius:16px; padding:22px; box-shadow:0 2px 12px #0001; }
        h3 { margin:0 0 8px; font-size:18px; } .muted { color:var(--panel-muted); font-size:14px; }
        .connection-card { display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 12px; padding:12px 22px; }
        .connection-card h3, .connection-card p { margin:0; }
        label { display:block; margin-top:17px; font-size:14px; font-weight:600; }
        input,select { width:100%; margin-top:7px; padding:11px; border:1px solid var(--panel-divider); border-radius:8px; background:var(--panel-card); color:var(--panel-text); font:inherit; }
        input[type=checkbox] { width:auto; margin-right:8px; }
        input[type=radio] { width:auto; margin:0 8px 0 0; }
        input[type=color] { height:44px; padding:4px; cursor:pointer; }
        input[type=color]::-webkit-color-swatch { border:1px solid var(--panel-divider); border-radius:4px; }
        input[type=color]::-moz-color-swatch { border:1px solid var(--panel-divider); border-radius:4px; }
        fieldset.text-speed { border:0; margin:17px 0 0; padding:0; min-width:0; }
        .text-speed legend { font-size:14px; font-weight:600; }
        .text-speed-options { display:flex; flex-wrap:wrap; gap:8px 18px; margin-top:10px; }
        .text-speed-options label { display:flex; align-items:center; margin:0; font-weight:normal; }
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
        .rotation-toggle { display:flex; flex:none; align-items:center; gap:6px; margin:0; font-size:13px; font-weight:normal; }
        .rotation-toggle input { width:auto; margin:0; accent-color:var(--primary-color,#16889a); }
        .rotation-edit { flex:none; width:40px; height:40px; padding:0; font-size:20px; }
        .community-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:12px; margin-top:18px; }
        .community-item { min-width:0; padding:10px; border:1px solid var(--panel-divider); border-radius:10px; background:var(--panel-secondary); }
        .community-item img { display:block; width:100%; aspect-ratio:1; object-fit:contain; image-rendering:pixelated; background:#111; border-radius:6px; }
        .community-item strong, .community-item small { display:block; overflow-wrap:anywhere; margin-top:6px; }
        .community-item small { color:var(--panel-muted); }
        .community-item button { width:100%; margin-top:10px; }
        .community-item .error { font-size:13px; }
        .rotation-block:has(.rotation-toggle input:not(:checked)) .rotation-description { opacity:.65; }
        dialog.rotation-dialog { width:min(680px, calc(100vw - 32px)); max-height:calc(100vh - 32px); overflow:auto; border:1px solid var(--panel-divider); border-radius:16px; padding:24px; background:var(--panel-card); color:var(--panel-text); box-shadow:0 12px 40px #0006; }
        dialog.rotation-dialog::backdrop { background:#0009; }
        @media (max-width:700px) { .event-layout { grid-template-columns:1fr; } .rotation-block { flex-wrap:wrap; } }
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
          <button type="button" class="secondary" data-page="community">Divoom Community</button>
          <button type="button" class="secondary" data-page="settings">Einstellungen</button>
        </nav>
        <div id="page-community" class="grid" hidden>
          <section class="card wide">
            <h3>Divoom Community</h3>
            <p class="muted">16×16-Pixelart suchen und einzeln als GIF in einen bestehenden Ordner speichern. Beachte die Rechte der Urheber und Divooms Nutzungsbedingungen.</p>
            <form id="community-search">
              <label>Suchbegriff<input name="query" maxlength="100" required autocomplete="off"></label>
              <label>Sortierung<select name="sort"><option value="1">Beliebt</option><option value="0">Neueste</option></select></label>
              <div class="actions"><button type="submit" class="primary">Suchen</button></div>
            </form>
            <label>Zielordner unter pixelart<input id="community-folder" value="." readonly></label>
            <label>Unterordner<select id="community-subfolder"><option value="">Kein Unterordner</option></select></label>
            <div class="actions"><button type="button" class="secondary" id="community-up">⬆ Überordner</button><button type="button" class="secondary" id="community-open">Ordner öffnen</button></div>
            <p id="community-message" class="message" role="status" aria-live="polite"></p>
            <div id="community-results" class="community-grid"></div>
            <div class="actions"><button type="button" class="secondary" id="community-prev" disabled>Zurück</button><span id="community-page"></span><button type="button" class="secondary" id="community-next" disabled>Weiter</button></div>
          </section>
        </div>
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
                  <label><input id="event-cooldown-enabled" type="checkbox">Abklingzeit</label>
                  <label>Abklingzeit (Sekunden)<input id="event-cooldown-seconds" type="number" min="0.01" step="any" disabled></label>
                  <p class="muted">Gilt ab Beginn für automatische Auslöser und HA-Aktionen; der Testknopf ist ausgenommen.</p>
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
                  <label>Terminart<select id="event-date-mode"><option value="annual">Zeitraum jährlich</option><option value="once">Zeitraum einmalig</option><option value="weekly">Wöchentlich</option><option value="dates_once">Einzelne Daten einmalig</option><option value="dates_annual">Einzelne Daten jährlich</option><option value="holiday">Feiertage aus HA-Kalender</option></select></label>
                  <div id="event-date-range">
                    <label>Beginn<input id="event-date-start" type="date"></label>
                    <label>Ende<input id="event-date-end" type="date"></label>
                    <p class="muted">Beide Tage zählen mit; jährliche Zeiträume dürfen über den Jahreswechsel reichen.</p>
                  </div>
                  <div id="event-date-weekly" hidden>
                    <p>Wochentage</p>
                    <div id="event-weekdays"></div>
                  </div>
                  <div id="event-date-list-group" hidden>
                    <p>Einzelne Daten</p><div id="event-date-list"></div>
                    <button type="button" class="secondary" id="event-date-add">+ Datum hinzufügen</button>
                  </div>
                  <p id="event-date-annual-hint" class="muted">Bei jährlicher Wiederholung wird nur Monat und Tag gespeichert; das gewählte Jahr wird ignoriert.</p>
                  <div id="event-date-holiday" hidden>
                    <label>Feiertagskalender<select id="event-calendar"><option value="">Bitte auswählen</option></select></label>
                    <div class="actions"><button type="button" class="secondary" id="event-holidays-load">Feiertage laden</button></div>
                    <p class="muted">Die Auswahl enthält Termine der nächsten zwei Jahre. Die Namen müssen mit dem Kalender übereinstimmen.</p>
                    <div id="event-holidays"></div>
                  </div>
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
              <button type="button" class="secondary" id="event-duplicate">Datums-Event duplizieren</button>
              <button type="button" class="secondary" id="event-delete">Event löschen</button>
            </div>
            <p id="event-message" class="message" role="status" aria-live="polite"></p>
            </div>
            </div>
          </section>
        </div>
        <div id="page-overview" class="grid">
          <section class="card connection-card">
            <h3>Verbindung:</h3>
            <p id="connection-status" role="status" title="Der Status stammt vom in den Einstellungen gewählten HA-Sensor, nicht direkt vom Pixoo.">Status wird geladen …</p>
          </section>
          <section class="card wide">
            <h3>Rotation</h3>
            <p class="muted">Blöcke bearbeiten oder per Drag &amp; Drop verschieben. Änderungen anschließend mit „Rotation speichern“ übernehmen. Die Startanimation bleibt immer vorn.</p>
            <ol class="rotation-preview" id="rotation-blocks" aria-label="Rotationsablauf">
              <li class="rotation-block"><span class="rotation-icon" aria-hidden="true">✨</span><span class="rotation-description"><strong>Startanimation</strong><span>Ausgewählte GIFs · am Anfang jedes Durchlaufs</span></span><span class="rotation-badge">🔒 Fest</span><button type="button" class="secondary rotation-edit" id="rotation-edit" aria-label="Startanimation bearbeiten" title="Startanimation bearbeiten"><ha-icon icon="mdi:cog" aria-hidden="true"></ha-icon></button></li>
              <li class="rotation-block" data-block="weather" draggable="true"><span class="rotation-icon" aria-hidden="true">🌤️</span><span class="rotation-description"><strong>Wetter</strong><span>Aktuelle Wetteranzeige · verschiebbar</span></span><label class="rotation-toggle"><input id="rotation-weather-enabled" type="checkbox" aria-label="Wetter aktivieren"><span>Inaktiv</span></label><button type="button" class="secondary rotation-edit" id="rotation-weather-edit" aria-label="Wetter bearbeiten" title="Wetter bearbeiten"><ha-icon icon="mdi:cog" aria-hidden="true"></ha-icon></button></li>
              <li class="rotation-block" data-block="date" draggable="true"><span class="rotation-icon" aria-hidden="true">📅</span><span class="rotation-description"><strong>Aktive Datums-Events</strong><span>Alle aktiven Events · alphabetisch · verschiebbar</span></span><label class="rotation-toggle"><input id="rotation-date-enabled" type="checkbox" aria-label="Datums-Events aktivieren" checked><span>Aktiv</span></label><button type="button" class="secondary rotation-edit" id="rotation-dates-edit" aria-label="Datums-Events bearbeiten" title="Datums-Events bearbeiten"><ha-icon icon="mdi:cog" aria-hidden="true"></ha-icon></button></li>
            </ol>
            <div class="actions"><button type="button" class="secondary" id="rotation-text-add">+ Textblock hinzufügen</button></div>
            <label>Fehlerbild-Anzeigedauer für alle Blöcke (Sekunden)<input id="rotation-error-seconds" type="number" min="0.01" max="3600" step="any" value="5"></label>
            <div class="actions"><button type="button" class="primary" id="rotation-save">Rotation speichern</button></div>
            <div class="actions"><button type="button" class="primary" id="rotation-start">▶ Rotation starten</button><button type="button" class="secondary" id="rotation-stop">■ Rotation stoppen</button></div>
            <p id="rotation-message" class="message" role="status" aria-live="polite"></p>
            <dialog id="rotation-editor" class="rotation-dialog" aria-labelledby="rotation-dialog-title" aria-describedby="rotation-dialog-help">
              <h3 id="rotation-dialog-title"></h3>
              <p id="rotation-dialog-help" class="muted">Änderungen bleiben als Entwurf erhalten. Nach dem Schließen mit „Rotation speichern“ dauerhaft speichern.</p>
              <div id="rotation-start-editor" hidden>
              <label>Ordner unter pixelart<input id="rotation-folder" value="rotation" autocomplete="off"></label>
              <div class="actions"><button type="button" class="secondary" id="rotation-load">GIFs laden</button></div>
              <p class="muted">GIFs auswählen, mit den Pfeilen sortieren und Sekunden oder geschätzte Durchläufe einstellen.</p>
              <div id="rotation-list"></div>
              </div>
              <div id="rotation-weather-settings" hidden>
                <label>Wetter-Entität<select id="rotation-weather-entity"><option value="">Bitte auswählen</option></select></label>
                <label>Wetter-Anzeigedauer (Sekunden)<input id="rotation-weather-seconds" type="number" min="0.01" max="3600" step="any" value="10"></label>
                <p class="muted">GIFs aus wetter/&lt;HA-Wetterzustand&gt;/tag oder /nacht; neue Dateien werden automatisch berücksichtigt.</p>
              </div>
              <div id="rotation-text-editor" hidden>
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
                <label>Schriftgröße<input id="text-size" type="number" min="1" max="64" step="1" value="10"></label>
                <fieldset class="text-speed"><legend>Geschwindigkeit</legend>
                  <div class="text-speed-options" id="text-speed">
                    <label><input type="radio" name="text-speed" value="1">Sehr schnell</label>
                    <label><input type="radio" name="text-speed" value="50">Schnell</label>
                    <label><input type="radio" name="text-speed" value="100">Mittel</label>
                    <label><input type="radio" name="text-speed" value="150">Langsam</label>
                    <label><input type="radio" name="text-speed" value="200">Sehr langsam</label>
                    <label id="text-speed-custom-label" hidden><input type="radio" name="text-speed" id="text-speed-custom"><span id="text-speed-custom-value"></span></label>
                  </div>
                </fieldset>
                <label>Anzeigemodus<select id="text-duration-mode"><option value="seconds">Sekunden</option><option value="loops">Durchläufe (grob geschätzt)</option></select></label>
                <label><span id="text-duration-label">Dauer (Sekunden)</span><input id="text-duration" type="number" min="0.01" max="3600" step="any" value="10"></label>
                <p class="muted">Durchläufe werden für den 16×16-Pixoo anhand der Textbreite geschätzt und sind nicht mit dem Display synchronisiert.</p>
                <div class="actions"><button type="button" class="secondary" id="text-remove">Textblock entfernen</button></div>
              </div>
              <p id="rotation-dialog-message" class="message" role="status" aria-live="polite"></p>
              <div class="actions"><button type="button" class="secondary" id="rotation-dialog-close">Fertig</button></div>
            </dialog>
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
    this._initCommunity();
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
    for (const name of ["overview", "events", "community", "settings"]) {
      this.shadowRoot.querySelector(`#page-${name}`).hidden = name !== page;
      const button = this.shadowRoot.querySelector(`[data-page="${name}"]`);
      if (name === page) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    }
  }

  _initCommunity() {
    const root = this.shadowRoot;
    const form = root.querySelector("#community-search");
    const folder = root.querySelector("#community-folder");
    const subfolder = root.querySelector("#community-subfolder");
    const message = root.querySelector("#community-message");
    const results = root.querySelector("#community-results");
    const prev = root.querySelector("#community-prev");
    const next = root.querySelector("#community-next");
    let revision = 0;
    let currentPage = 1;
    let currentQuery = "";
    let currentSort = 1;
    let folderReady = false;
    let folderRevision = 0;
    let activePreviews = 0;
    const previewWaiters = [];
    const acquirePreview = () => new Promise((resolve) => {
      if (activePreviews < 4) {
        activePreviews++;
        resolve();
      } else {
        previewWaiters.push(resolve);
      }
    });
    const releasePreview = () => {
      const next = previewWaiters.shift();
      if (next) next();
      else activePreviews--;
    };
    const report = (text, error = false) => {
      message.textContent = text;
      message.classList.toggle("error", error);
    };
    const loadFolder = async (value) => {
      const requestRevision = ++folderRevision;
      folderReady = false;
      try {
        const children = await this._hass.callWS({type: "divoom_orchestrator/event_folders", folder: value});
        if (requestRevision !== folderRevision) return;
        folder.value = value;
        subfolder.replaceChildren(new Option("Kein Unterordner", ""));
        children.forEach((child) => subfolder.add(new Option(child.split("/").pop(), child)));
        folderReady = true;
        report(`Zielordner: ${value}`);
      } catch (error) {
        if (requestRevision === folderRevision) report(`Ordner konnte nicht geladen werden: ${error.message || String(error)}`, true);
      }
    };
    root.querySelector("#community-open").addEventListener("click", () => {
      if (subfolder.value) loadFolder(subfolder.value);
    });
    root.querySelector("#community-up").addEventListener("click", () => {
      const parts = folder.value.split("/");
      parts.pop();
      loadFolder(parts.join("/") || ".");
    });
    const loadPage = async (page) => {
      const requestRevision = ++revision;
      prev.disabled = next.disabled = true;
      results.replaceChildren();
      report("Community-Ergebnisse werden geladen …");
      try {
        const search = await this._hass.callWS({
          type: "divoom_orchestrator/community_search", query: currentQuery, page, sort: currentSort,
        });
        if (requestRevision !== revision) return;
        const works = search.works;
        currentPage = page;
        root.querySelector("#community-page").textContent = `Seite ${page}`;
        prev.disabled = page <= 1;
        next.disabled = !search.has_more || page >= 100;
        report(works.length ? `${works.length} Ergebnisse. Vorschauen werden geladen …`
          : search.has_more ? "Keine sichtbaren Ergebnisse auf dieser Seite." : "Keine weiteren Ergebnisse.");
        const previews = [];
        for (const work of works) {
          const card = document.createElement("article");
          card.className = "community-item";
          const image = document.createElement("img");
          image.alt = `Vorschau: ${work.title}`;
          const title = document.createElement("strong");
          title.textContent = work.title || `Werk ${work.id}`;
          const author = document.createElement("small");
          author.textContent = work.author ? `von ${work.author}` : "Urheber unbekannt";
          const status = document.createElement("small");
          const save = document.createElement("button");
          save.type = "button";
          save.className = "primary";
          save.textContent = "Als GIF speichern";
          save.disabled = true;
          const importStatus = document.createElement("small");
          importStatus.setAttribute("role", "status");
          importStatus.setAttribute("aria-live", "polite");
          card.append(image, title, author, status, save, importStatus);
          results.append(card);
          if (!work.importable) {
            status.textContent = "Durch Rechtekennzeichnung nicht verfügbar.";
            continue;
          }
          status.textContent = "Vorschau wird geladen …";
          save.addEventListener("click", async () => {
            if (!folderReady) {
              importStatus.classList.add("error");
              importStatus.textContent = "Bitte zuerst einen Zielordner laden.";
              return;
            }
            save.disabled = true;
            save.textContent = "Wird gespeichert …";
            importStatus.classList.remove("error");
            importStatus.textContent = "GIF wird gespeichert …";
            try {
              const saved = await this._hass.callWS({
                type: "divoom_orchestrator/community_import", search_id: search.search_id, gallery_id: work.id, folder: folder.value,
              });
              importStatus.textContent = `Gespeichert: ${saved.file}`;
            } catch (error) {
              importStatus.classList.add("error");
              importStatus.textContent = `Import fehlgeschlagen: ${error.message || String(error)}`;
            } finally {
              save.disabled = false;
              save.textContent = "Als GIF speichern";
            }
          });
          previews.push({work, image, status, save});
        }
        await Promise.all(previews.map(async (item) => {
          await acquirePreview();
          try {
            if (requestRevision !== revision) return;
            const preview = await this._hass.callWS({
              type: "divoom_orchestrator/community_preview", search_id: search.search_id, gallery_id: item.work.id,
            });
            if (requestRevision !== revision) return;
            item.image.src = `data:image/gif;base64,${preview.data}`;
            item.status.textContent = "";
            item.save.disabled = false;
          } catch (error) {
            if (requestRevision !== revision) return;
            item.status.textContent = `Vorschau nicht verfügbar: ${error.message || String(error)}`;
            item.status.classList.add("error");
          } finally {
            releasePreview();
          }
        }));
        if (requestRevision === revision && works.length) report(`${works.length} Ergebnisse auf Seite ${page}.`);
      } catch (error) {
        if (requestRevision === revision) report(`Suche fehlgeschlagen: ${error.message || String(error)}`, true);
      }
    };
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      currentQuery = form.elements.query.value.trim();
      if (!currentQuery) return report("Bitte einen Suchbegriff eingeben.", true);
      currentSort = Number(form.elements.sort.value);
      loadPage(1);
    });
    prev.addEventListener("click", () => loadPage(currentPage - 1));
    next.addEventListener("click", () => loadPage(currentPage + 1));
    loadFolder(".");
  }

  _rotationMessage(text, error = false) {
    for (const id of ["rotation-message", "rotation-dialog-message"]) {
      const message = this.shadowRoot.querySelector(`#${id}`);
      message.textContent = text;
      message.classList.toggle("error", error);
    }
  }

  _rotationChanged() {
    this._rotationDirty = true;
    this._rotationRevision++;
    this._rotationMessage("Ungespeicherte Änderungen – bitte Rotation speichern.");
  }

  _rotationToggle(block) {
    const input = block.querySelector(".rotation-toggle input");
    const update = () => {
      input.nextElementSibling.textContent = input.checked ? "Aktiv" : "Inaktiv";
    };
    input.addEventListener("change", () => {
      update();
      this._rotationChanged();
    });
    update();
  }

  _rotationDialog(section, title) {
    const root = this.shadowRoot;
    for (const name of ["start-editor", "weather-settings", "text-editor"]) {
      root.querySelector(`#rotation-${name}`).hidden = name !== section;
    }
    root.querySelector("#rotation-dialog-title").textContent = title;
    const dialog = root.querySelector("#rotation-editor");
    if (!dialog.open) dialog.showModal();
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
    get("edit").addEventListener("click", () => this._rotationDialog("start-editor", "Startanimation bearbeiten"));
    get("dates-edit").addEventListener("click", () => this._showPage("events"));
    get("weather-edit").addEventListener("click", () => this._rotationDialog("weather-settings", "Wetter bearbeiten"));
    get("dialog-close").addEventListener("click", () => get("editor").close());
    get("editor").addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        get("editor").close();
      }
    });
    get("folder").addEventListener("input", () => this._rotationChanged());
    for (const id of ["weather-entity", "weather-seconds"]) {
      get(id).addEventListener("change", () => this._rotationChanged());
      get(id).addEventListener("input", () => this._rotationChanged());
    }
    const weather = get("weather-entity");
    Object.keys(this._hass.states).filter((id) => id.startsWith("weather.")).sort().forEach((id) => {
      weather.add(new Option(this._hass.states[id].attributes?.friendly_name || id, id));
    });
    const blocks = get("blocks");
    for (const block of blocks.querySelectorAll("[data-block]")) this._rotationToggle(block);
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
      const inactive = new Set(config.inactive_blocks || []);
      this._rotationTexts = Object.assign(Object.create(null), config.texts || {});
      get("weather-enabled").checked = order.includes("weather") && !inactive.has("weather");
      get("date-enabled").checked = order.includes("date") && !inactive.has("date");
      if (config.weather) {
        if (![...weather.options].some((option) => option.value === config.weather.entity)) {
          weather.add(new Option(`${config.weather.entity} (nicht verfügbar)`, config.weather.entity));
        }
        weather.value = config.weather.entity;
        get("weather-seconds").value = config.weather.seconds;
      }
      for (const name of order) {
        const block = name.startsWith("text:") ? this._textBlock(name, !inactive.has(name)) :
          blocks.querySelector(`[data-block="${name}"]`);
        if (block) blocks.append(block);
      }
      for (const name of ["weather", "date"]) {
        if (!order.includes(name)) blocks.append(blocks.querySelector(`[data-block="${name}"]`));
        const block = blocks.querySelector(`[data-block="${name}"]`);
        block.querySelector(".rotation-toggle span").textContent =
          block.querySelector(".rotation-toggle input").checked ? "Aktiv" : "Inaktiv";
      }
      this._rotationLoadFiles(config.steps);
    }).catch((error) => this._rotationMessage(`Rotation konnte nicht geladen werden: ${error.message || String(error)}`, true));
  }

  async _rotationLoadFiles(saved = null) {
    const folder = this.shadowRoot.querySelector("#rotation-folder").value.trim();
    if (!folder) return this._rotationMessage("Bitte einen Ordner eingeben.", true);
    const list = this.shadowRoot.querySelector("#rotation-list");
    if (saved === null) {
      const selected = Array.from(list.children)
        .filter((row) => row.querySelector('input[type="checkbox"]').checked)
        .map((row) => ({file: row.dataset.file, mode: row.querySelector("select").value,
          value: Number(row.querySelector('input[type="number"]').value)}));
      if (this._rotationFolder && this._rotationFolder !== folder && selected.length &&
          !window.confirm("GIF-Auswahl des bisherigen Startordners verwerfen?")) return;
      saved = this._rotationFolder === folder ? selected : [];
    }
    const revision = this._rotationRevision;
    try {
      const entries = await this._hass.callWS({type: "divoom_orchestrator/playlist_files", folder});
      if (this.shadowRoot.querySelector("#rotation-folder").value.trim() !== folder ||
          revision !== this._rotationRevision) {
        return this._rotationMessage("Einstellungen geändert; bitte erneut laden.", true);
      }
      this._rotationFolder = folder;
      this._rotationFiles = entries.map((entry) => entry.file);
      list.replaceChildren();
      const selected = new Set(saved.map((step) => step.file));
      for (const step of saved) this._rotationRow(step.file, step);
      for (const file of this._rotationFiles) if (!selected.has(file)) this._rotationRow(file, null);
      this._rotationMessage(`${entries.length} GIF(s) geladen.${this._rotationDirty ? " Ungespeicherte Änderungen – bitte Rotation speichern." : ""}`);
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
      background: [0, 0, 0], size: 10, time: 100, duration_mode: "seconds", duration: 10};
  }

  _textBlock(id, enabled = true) {
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
    const toggle = document.createElement("label");
    toggle.className = "rotation-toggle";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = enabled;
    input.setAttribute("aria-label", `Textblock ${name.textContent} aktivieren`);
    const state = document.createElement("span");
    toggle.append(input, state);
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "secondary rotation-edit";
    const editIcon = document.createElement("ha-icon");
    editIcon.setAttribute("icon", "mdi:cog");
    editIcon.setAttribute("aria-hidden", "true");
    edit.append(editIcon);
    edit.setAttribute("aria-label", `Textblock ${name.textContent} bearbeiten`);
    edit.title = `Textblock ${name.textContent} bearbeiten`;
    edit.addEventListener("click", () => this._textEdit(id));
    block.append(icon, description, toggle, edit);
    this._rotationToggle(block);
    this.shadowRoot.querySelector("#rotation-blocks").append(block);
    return block;
  }

  _initTextEditor() {
    const get = (name) => this.shadowRoot.querySelector(`#text-${name}`);
    const fields = {
      name: "name", source: "source", fixed: "text", entity: "entity", attribute: "attribute",
      selection: "selection", size: "size", "duration-mode": "duration_mode",
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
          if (block) {
            block.querySelector("strong").textContent = settings.name || "Text";
            block.querySelector(".rotation-toggle input").setAttribute("aria-label",
              `Textblock ${settings.name || "Text"} aktivieren`);
            const edit = block.querySelector(".rotation-edit");
            edit.setAttribute("aria-label", `Textblock ${settings.name || "Text"} bearbeiten`);
            edit.title = `Textblock ${settings.name || "Text"} bearbeiten`;
          }
          this.shadowRoot.querySelector("#rotation-dialog-title").textContent =
            `Textblock bearbeiten: ${settings.name || "Text"}`;
        }
        if (field === "source") this._textSource();
        if (field === "duration-mode") this._textDurationLabel();
      };
      input.addEventListener("input", update);
      input.addEventListener("change", update);
    }
    get("speed").addEventListener("change", (event) => {
      const settings = this._rotationTexts[this._editingText];
      if (!settings || event.target.name !== "text-speed" || !event.target.checked) return;
      settings.time = Number(event.target.value);
      this._rotationChanged();
    });
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
      this.shadowRoot.querySelector("#rotation-editor").close();
      this._rotationChanged();
    });
  }

  _textSource() {
    const source = this.shadowRoot.querySelector("#text-source").value;
    for (const name of ["fixed", "entity", "list"]) {
      this.shadowRoot.querySelector(`#text-${name}-group`).hidden = source !== name;
    }
  }

  _textDurationLabel() {
    const root = this.shadowRoot;
    root.querySelector("#text-duration-label").textContent =
      root.querySelector("#text-duration-mode").value === "seconds" ? "Dauer (Sekunden)" : "Anzahl Durchläufe";
  }

  _textEdit(id) {
    const settings = this._rotationTexts[id];
    if (!settings) return;
    this._editingText = id;
    this._rotationDialog("text-editor", `Textblock bearbeiten: ${settings.name || "Text"}`);
    const fields = {name: "name", source: "source", fixed: "text", entity: "entity",
      attribute: "attribute", selection: "selection", size: "size",
      "duration-mode": "duration_mode", duration: "duration"};
    for (const [field, key] of Object.entries(fields)) this.shadowRoot.querySelector(`#text-${field}`).value = settings[key];
    const speeds = this.shadowRoot.querySelectorAll('#text-speed input[type="radio"]');
    const preset = [...speeds].find((input) => input.id !== "text-speed-custom" && Number(input.value) === settings.time);
    const custom = this.shadowRoot.querySelector("#text-speed-custom");
    this.shadowRoot.querySelector("#text-speed-custom-label").hidden = Boolean(preset);
    if (!preset) {
      custom.value = settings.time;
      this.shadowRoot.querySelector("#text-speed-custom-value").textContent = `Bisheriger Wert (${settings.time} ms)`;
    }
    (preset || custom).checked = true;
    for (const name of ["foreground", "background"]) {
      this.shadowRoot.querySelector(`#text-${name}`).value = `#${settings[name].map((n) => n.toString(16).padStart(2, "0")).join("")}`;
    }
    this.shadowRoot.querySelector("#text-list-status").textContent = `${settings.lines.length} Zeilen im Textblock.`;
    this._textSource();
    this._textDurationLabel();
    this.shadowRoot.querySelector("#text-name").focus();
  }

  async _rotationSave() {
    const get = (name) => this.shadowRoot.querySelector(`#rotation-${name}`);
    if (!this._rotationFiles || get("folder").value.trim() !== this._rotationFolder) {
      this._rotationDialog("start-editor", "Startanimation bearbeiten");
      return this._rotationMessage("Bitte zuerst den Ordner laden.", true);
    }
    const steps = [];
    for (const row of get("list").children) {
      if (!row.querySelector('input[type="checkbox"]').checked) continue;
      const input = row.querySelector('input[type="number"]');
      if (!input.checkValidity()) {
        this._rotationDialog("start-editor", "Startanimation bearbeiten");
        input.reportValidity();
        return;
      }
      steps.push({file: row.dataset.file, mode: row.querySelector("select").value, value: Number(input.value)});
    }
    if (!steps.length) {
      this._rotationDialog("start-editor", "Startanimation bearbeiten");
      return this._rotationMessage("Bitte mindestens ein GIF auswählen.", true);
    }
    if (!get("error-seconds").reportValidity()) return;
    if ((get("weather-enabled").checked && !get("weather-entity").value) ||
        (get("weather-entity").value && !get("weather-seconds").checkValidity())) {
      this._rotationDialog("weather-settings", "Wetter bearbeiten");
      if (!get("weather-seconds").checkValidity()) get("weather-seconds").reportValidity();
      return this._rotationMessage("Bitte Wetter-Entität und Anzeigedauer wählen.", true);
    }
    const blockElements = [...get("blocks").querySelectorAll("[data-block]")];
    const blocks = blockElements.map((block) => block.dataset.block);
    const inactive_blocks = blockElements.filter((block) => !block.querySelector(".rotation-toggle input").checked)
      .map((block) => block.dataset.block);
    const config = {
      folder: this._rotationFolder, steps, date_events: get("date-enabled").checked,
      error_seconds: Number(get("error-seconds").value), blocks, inactive_blocks, texts: this._rotationTexts,
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
    for (const id of ["enabled", "priority", "cooldown-enabled", "cooldown-seconds", "date-mode", "date-start", "date-end", "calendar",
      "trigger-type", "trigger-entity", "trigger-to", "trigger-event"]) {
      get(id).addEventListener("change", dirty);
    }
    get("cooldown-seconds").addEventListener("input", dirty);
    get("cooldown-enabled").addEventListener("change", () => {
      const input = get("cooldown-seconds");
      input.disabled = !get("cooldown-enabled").checked;
      input.value = input.disabled ? "" : "10";
    });
    for (const id of ["date-start", "date-end"]) get(id).addEventListener("input", dirty);
    get("date-mode").addEventListener("change", () => this._eventDateMode());
    ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"].forEach((name, day) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = day;
      input.addEventListener("change", dirty);
      label.append(input, document.createTextNode(name));
      get("weekdays").append(label);
    });
    const calendar = get("calendar");
    Object.keys(this._hass.states).filter((id) => id.startsWith("calendar.")).sort().forEach((id) => {
      calendar.add(new Option(`${this._hass.states[id].attributes?.friendly_name || id} (${id})`, id));
    });
    calendar.addEventListener("change", () => {
      get("holidays").replaceChildren();
      this._holidayRequest = (this._holidayRequest || 0) + 1;
    });
    get("date-add").addEventListener("click", () => { this._eventDateRow(""); dirty(); });
    get("holidays-load").addEventListener("click", () => this._eventLoadHolidays());
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
    get("duplicate").addEventListener("click", () => this._eventDuplicate());
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
    this.shadowRoot.querySelector("#event-duplicate").hidden = this._eventKind !== "date";
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
    const mode = this.shadowRoot.querySelector("#event-date-mode").value;
    for (const [id, visible] of [
      ["range", mode === "annual" || mode === "once"],
      ["weekly", mode === "weekly"],
      ["list-group", mode === "dates_once" || mode === "dates_annual"],
      ["holiday", mode === "holiday"],
      ["annual-hint", mode === "annual" || mode === "dates_annual"],
    ]) this.shadowRoot.querySelector(`#event-date-${id}`).hidden = !visible;
  }

  _eventSetSchedule(event) {
    const schedule = event?.schedule || {};
    const pickerDate = (value) => value && value.length === 5 ? `2000-${value}` : value || "";
    this.shadowRoot.querySelector("#event-enabled").checked = event?.enabled !== false;
    this.shadowRoot.querySelector("#event-priority").value = event?.priority ?? 3;
    const cooldown = this.shadowRoot.querySelector("#event-cooldown-seconds");
    const cooldownEnabled = event?.cooldown_seconds != null;
    this.shadowRoot.querySelector("#event-cooldown-enabled").checked = cooldownEnabled;
    cooldown.disabled = !cooldownEnabled;
    cooldown.value = cooldownEnabled ? event.cooldown_seconds : "";
    this.shadowRoot.querySelector("#event-date-mode").value = schedule.mode || "annual";
    this.shadowRoot.querySelector("#event-date-start").value = pickerDate(schedule.start);
    this.shadowRoot.querySelector("#event-date-end").value = pickerDate(schedule.end);
    this.shadowRoot.querySelectorAll("#event-weekdays input").forEach((input) => {
      input.checked = (schedule.weekdays || []).includes(Number(input.value));
    });
    this.shadowRoot.querySelector("#event-date-list").replaceChildren();
    for (const day of schedule.dates || []) this._eventDateRow(pickerDate(day));
    const calendar = this.shadowRoot.querySelector("#event-calendar");
    if (schedule.calendar && !Array.from(calendar.options).some((option) => option.value === schedule.calendar)) {
      calendar.add(new Option(`${schedule.calendar} (nicht verfügbar)`, schedule.calendar));
    }
    calendar.value = schedule.calendar || "";
    this._holidayRequest = (this._holidayRequest || 0) + 1;
    this._eventHolidayRows(schedule.holidays || [], schedule.holidays || []);
    if (schedule.mode === "holiday" && schedule.calendar) this._eventLoadHolidays();
    this.shadowRoot.querySelector("#event-trigger-type").value = event?.trigger?.type || "manual";
    this.shadowRoot.querySelector("#event-trigger-entity").value = event?.trigger?.entity_id || "";
    this.shadowRoot.querySelector("#event-trigger-to").value = event?.trigger?.to || "";
    this.shadowRoot.querySelector("#event-trigger-event").value = event?.trigger?.event_type || "";
    this._eventTriggerMode();
    this._eventDateMode();
  }

  _eventDateRow(value) {
    const row = document.createElement("div");
    row.className = "event-row";
    const input = document.createElement("input");
    input.type = "date";
    input.value = value;
    input.setAttribute("aria-label", "Einzelnes Datum");
    const dirty = () => { this._eventDirty = true; this._eventRevision++; };
    input.addEventListener("input", dirty);
    input.addEventListener("change", dirty);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary";
    remove.textContent = "Entfernen";
    remove.addEventListener("click", () => { row.remove(); dirty(); });
    row.append(input, remove);
    this.shadowRoot.querySelector("#event-date-list").append(row);
  }

  _eventHolidayRows(names, selected) {
    const list = this.shadowRoot.querySelector("#event-holidays");
    list.replaceChildren();
    for (const name of names) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = name;
      input.checked = selected.includes(name);
      input.addEventListener("change", () => { this._eventDirty = true; this._eventRevision++; });
      label.append(input, document.createTextNode(name));
      list.append(label);
    }
  }

  async _eventLoadHolidays() {
    const calendar = this.shadowRoot.querySelector("#event-calendar").value;
    if (!calendar) return this._eventMessage("Bitte einen Feiertagskalender auswählen.", true);
    const request = this._holidayRequest = (this._holidayRequest || 0) + 1;
    this._eventMessage("Feiertage werden geladen …");
    try {
      const names = await this._hass.callWS({type: "divoom_orchestrator/holiday_names", calendar});
      if (request !== this._holidayRequest) return;
      const selected = Array.from(this.shadowRoot.querySelectorAll("#event-holidays input:checked"), (input) => input.value);
      this._eventHolidayRows(Array.from(new Set([...selected, ...names])), selected);
      this._eventMessage(`${names.length} Feiertag(e) geladen.`);
    } catch (error) {
      if (request === this._holidayRequest) this._eventMessage(`Feiertage konnten nicht geladen werden: ${error.message || String(error)}`, true);
    }
  }

  _eventDuplicate() {
    if (this._eventLoading || this._eventSaving || this._eventKind !== "date" || !this._eventSelected) {
      return this._eventMessage("Bitte zuerst ein gespeichertes Datums-Event auswählen.", true);
    }
    const original = this.shadowRoot.querySelector("#event-name").value.trim() || this._eventSelected;
    let number = 1;
    let name;
    do {
      const suffix = number === 1 ? " (Kopie)" : ` (Kopie ${number})`;
      name = original.slice(0, 80 - suffix.length) + suffix;
      number++;
    } while (this._events[name]);
    this._eventChoices("");
    this.shadowRoot.querySelector("#event-name").value = name;
    this._eventDirty = true;
    this._eventRevision++;
    this._eventMessage("Kopie als Entwurf erstellt; zum Anlegen speichern.");
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
      if (get("cooldown-enabled").checked) {
        const cooldown = get("cooldown-seconds");
        if (!cooldown.value || !cooldown.reportValidity()) return this._eventMessage("Bitte eine gültige Abklingzeit eingeben.", true);
        event.cooldown_seconds = Number(cooldown.value);
        if (!Number.isFinite(event.cooldown_seconds) || event.cooldown_seconds <= 0) return this._eventMessage("Bitte eine gültige Abklingzeit eingeben.", true);
      }
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
      const mode = get("date-mode").value;
      event.schedule = {mode};
      if (mode === "annual" || mode === "once") {
        const start = get("date-start").value, end = get("date-end").value;
        if (!start || !end) return this._eventMessage("Bitte Beginn und Ende auswählen.", true);
        event.schedule.start = mode === "annual" ? start.slice(5) : start;
        event.schedule.end = mode === "annual" ? end.slice(5) : end;
      } else if (mode === "weekly") {
        event.schedule.weekdays = Array.from(get("weekdays").querySelectorAll("input:checked"), (input) => Number(input.value));
        if (!event.schedule.weekdays.length) return this._eventMessage("Bitte Wochentage auswählen.", true);
      } else if (mode === "dates_once" || mode === "dates_annual") {
        const values = Array.from(get("date-list").querySelectorAll("input"), (input) => input.value);
        if (!values.length || values.some((value) => !value)) return this._eventMessage("Bitte mindestens ein vollständiges Datum auswählen.", true);
        event.schedule.dates = values.map((value) => mode === "dates_annual" ? value.slice(5) : value);
        if (new Set(event.schedule.dates).size !== values.length) return this._eventMessage("Bitte jedes Datum nur einmal auswählen.", true);
      } else if (mode === "holiday") {
        event.schedule.calendar = get("calendar").value;
        event.schedule.holidays = Array.from(get("holidays").querySelectorAll("input:checked"), (input) => input.value);
        if (!event.schedule.calendar || !event.schedule.holidays.length) return this._eventMessage("Bitte Kalender und Feiertage auswählen.", true);
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
