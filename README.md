# Divoom Orchestrator

Eine separate Home-Assistant-Integration für GIF-Playlists mit
[hass-divoom](https://github.com/d03n3rfr1tz3/hass-divoom). Sie ist ein
Prototyp: Home-Assistant-Installation, Bluetooth-Übertragung und Betrieb mit
Nextcloud wurden noch nicht auf einem echten System getestet.

## Voraussetzungen

- Die bestehende Divoom-Integration ist installiert, eingerichtet und kann ein
  einzelnes GIF über `divoom.image` anzeigen.
- Der GIF-Ordner ist für Home Assistant unter `/config/pixelart` lesbar und
  entspricht **dem in Divoom konfigurierten Medienordner**. Das ist bei einer
  Divoom-Einrichtung per Oberfläche der Standard; abweichend konfigurierte
  Divoom-Medienordner werden aktuell nicht unterstützt.
- Eine NAS-/Nextcloud-Freigabe muss der Admin einmalig so einrichten, dass HA
  und Nextcloud dieselben Dateien sehen. Ein Mount kann vorhandene Dateien
  verdecken; vorher prüfen und bei Bedarf übernehmen. Für die Wiedergabe reicht
  Lesezugriff für den HA-Container.

## Installation über HACS

Nach Veröffentlichung der gewünschten Version auf GitHub:

HACS unterstützt nur öffentliche GitHub-Repositories. Solange dieses Repository
privat ist, funktioniert die Installation über HACS nicht.

1. In HACS unter den benutzerdefinierten Repositories
   `https://github.com/RalfWelp/divoom-orchestrator` als **Integration** hinzufügen.
2. **Divoom Orchestrator** herunterladen und Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen**
   **Divoom Orchestrator** hinzufügen.

Der Ordner muss für die Installation noch nicht vorhanden sein; er wird beim
Start einer Playlist geprüft. Diese Anleitung ist noch nicht praktisch mit HACS
und Home Assistant validiert.

## Oberfläche

Nach der Einrichtung erscheint für Administratoren **Divoom Orchestrator** in
der Seitenleiste. Die erste Version bietet dort das Starten und Stoppen einer
Ordner-Playlist. Gerätekennung und Ordner werden noch von Hand eingegeben und
nicht dauerhaft gespeichert. Die Anzeige bestätigt lediglich die Startanfrage;
spätere Wiedergabefehler erscheinen als HA-Benachrichtigung.

Eine separat aktivierbare Helligkeitsautomatik ist ebenfalls im Panel
konfigurierbar. Der grafische Ablauf-Editor, die Animationen für Rotation und
Events, Medienauswahl und GIF-Vorschau sind noch nicht implementiert.
Die Oberfläche zeigt ausdrücklich keinen
Live-Verbindungsstatus; dafür kann die bestehende MQTT-Statusentität genutzt
werden. Ein Live-Test in Home Assistant steht noch aus.

### Helligkeit

Die Automatik ist zunächst ausgeschaltet. Im Panel Divoom-Gerätekennung,
Bewegungsmelder und optional den Bluetooth-Statussensor auswählen, Werte und
morgendliche Startzeit einstellen und aktiv speichern. Andere Automationen,
die die Helligkeit desselben Displays steuern, vorher deaktivieren.

Vor der morgendlichen Startzeit gilt der Nachtwert. Danach gilt bis zum
Sonnenaufgang der Dämmerungswert, bis Sonnenuntergang der Tageswert und
anschließend bis zum Ende der bürgerlichen Dämmerung (Sonnenstand −6°) wieder
der Dämmerungswert. Sonst gilt der Nachtwert. Die Sonnenposition kommt aus HA.
Ein Wert von 0 % schaltet das Display aus.

Bewegung schaltet auf 100 %, solange der Sensor aktiv ist, mindestens aber
30 Sekunden ab Auslösung. Danach wird der aktuelle Zeitwert wiederhergestellt.
Das Display wird dafür gegebenenfalls eingeschaltet. Klingelereignisse sind
noch nicht angebunden. Ein Testknopf verwendet den aktuell eingegebenen Wert
für 30 Sekunden, auch wenn dieser Wert noch nicht gespeichert wurde; danach
setzt sich die Automatik fort. Die Automatik muss dafür eingeschaltet und
gespeichert sein.

Helligkeitswechsel erfolgen in bis zu vier Schritten mit kurzen Pausen.
Geräteübertragungen können die tatsächliche Dauer verlängern. Bei einem
Fehler wird eine dauerhafte HA-Benachrichtigung erstellt und später erneut
versucht. Bei Wiederverbindung des ausgewählten Statussensors wird der Wert
erneut angewendet. Einstellungen bleiben über HA-Neustarts erhalten; ein
temporärer Test nicht.

## Aktionen

Über **Entwicklerwerkzeuge → Aktionen** kann `Divoom Orchestrator: Playlist starten`
ausprobiert und später in Automationen genutzt werden. Beispiel:

```yaml
action: divoom_orchestrator.start
data:
  device: divoom_pixoo
  folder: wetter/regen
  duration: 10
  order: alphabetical
```

`device` ist derselbe Wert wie bei `divoom.image`. `folder` ist relativ zu
`/config/pixelart`, z. B. `wetter/regen`, oder `.` für das Stammverzeichnis.
Nur GIF-Dateien direkt im angegebenen Ordner werden berücksichtigt, nicht dessen
Unterordner. `duration` ist die Anzeigezeit in Sekunden **nach Abschluss des
Sendens**, nicht die Übertragungsgeschwindigkeit oder Dauer einer GIF-Schleife.
Erlaubt sind 1 bis 3600 Sekunden. `order` ist `alphabetical` oder `random`; für
Zufallsreihenfolge wird jeder neue Durchlauf erneut gemischt.

Nach jedem Durchlauf wird die Datei-Liste neu gelesen: hinzugefügte und
entfernte GIFs werden dann berücksichtigt. Wird eine Datei während eines
Durchlaufs entfernt, bevor sie gesendet wurde, kann die Playlist mit einem
Fehler anhalten. Leere oder fehlende Ordner werden beim Start gemeldet; werden
sie später leer oder unzugänglich, stoppt die Wiedergabe mit Protokolleintrag
und dauerhafter HA-Benachrichtigung.

Zum Beenden die Aktion `divoom_orchestrator.stop` ausführen. Ein laufender
Bildtransfer wird abgewartet, danach wird kein neues GIF gesendet; das letzte
Bild bleibt auf dem Pixoo. Es kann nur eine Playlist gleichzeitig laufen:
Eine andere zunächst stoppen und anschließend starten. Ein HA-Neustart startet
die Playlist **nicht** automatisch erneut; das lässt sich bei Bedarf mit einer
Automation einrichten.

Andere Divoom-Aktionen können das aktuelle Bild überschreiben, stoppen die
Playlist aber nicht. Event-Prioritäten und das automatische Fortsetzen einer
Rotation sind noch nicht implementiert.

## Tests

Die eigenständigen Tests brauchen nur Python 3.11 oder neuer:

```powershell
python -m unittest discover -s test -v
```

Sie simulieren die Wiedergabe und ersetzen keinen Praxistest mit Home Assistant,
dem NAS und dem Pixoo.
