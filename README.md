# Divoom Orchestrator

Eine separate Home-Assistant-Integration für GIF-Playlists mit
[hass-divoom](https://github.com/d03n3rfr1tz3/hass-divoom). Sie ist ein
Prototyp: Frühere Versionen wurden mit Home Assistant und Pixoo getestet;
der Event-Editor ist noch nicht auf einem echten System erprobt.

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

HACS unterstützt nur öffentliche GitHub-Repositories.

1. In HACS unter den benutzerdefinierten Repositories
   `https://github.com/RalfWelp/divoom-orchestrator` als **Integration** hinzufügen.
2. **Divoom Orchestrator** herunterladen und Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen**
   **Divoom Orchestrator** hinzufügen.

Der Ordner muss für die Installation noch nicht vorhanden sein; er wird beim
Start einer Playlist geprüft.

## Oberfläche

Nach der Einrichtung erscheint für Administratoren **Divoom Orchestrator** in
der Seitenleiste. Das Panel hat drei Bereiche: **Übersicht & Rotation**
(inklusive Bluetooth-Status des ausgewählten HA-Sensors und Ordner-Playlist),
**Event-Editor** und **Einstellungen**. Die Ordner-Playlist ist als
Übergangslösung einklappbar; ihr Ordner wird von Hand eingegeben und nicht
dauerhaft gespeichert. Mit **GIFs laden / aktualisieren** werden die
Dateien des Ordners aufgelistet; für jede gewünschte Animation lässt sich eine
eigene Anzeigezeit in Sekunden einstellen und speichern. Leere Felder und neue,
noch nicht konfigurierte Dateien werden übersprungen. Die Zeiten sind pro
relativem Dateipfad gespeichert und bleiben nach einem HA-Neustart erhalten;
umbenannte oder verschobene Dateien müssen neu eingestellt werden.
Sind keine konfigurierten Dateien vorhanden, lässt sich die Playlist nicht
starten. Falls sich die Liste während des Bearbeitens ändert, muss sie vor dem
Speichern neu geladen werden. Die Anzeige bestätigt lediglich die Startanfrage;
spätere Wiedergabefehler erscheinen als HA-Benachrichtigung.

GIFs bis 2 MiB werden über die für Administratoren zugängliche HA-WebSocket-
Verbindung als animierte Vorschau geladen; der Medienordner wird nicht
öffentlich freigegeben. Bei GIFs mit verwertbaren Framezeiten wird die
rechnerische Dauer eines Durchlaufs angezeigt. Sie ist nur eine Näherung:
Der Pixoo meldet das Ende eines Durchlaufs nicht und Divoom kann Frames
reduzieren. Fehlende oder null Millisekunden lange Framezeiten werden nicht
geschätzt. Im Event-Editor und für die Startabfolge lässt sich alternativ eine
geschätzte Anzahl an Durchläufen einstellen.

Eine separat aktivierbare Helligkeitsautomatik ist ebenfalls im Panel
konfigurierbar.
Der angezeigte Verbindungsstatus stammt aus der konfigurierten MQTT-Entität,
nicht direkt vom Pixoo. Ein Live-Test des Event-Editors in Home Assistant steht noch aus.
Das Panel übernimmt das helle oder dunkle Home-Assistant-Theme; es ändert
keine globalen Theme-Einstellungen.

### Event-Editor

Im Event-Editor einen Namen eingeben, mit dem Ordnerbrowser einen Unterordner
wählen und die gewünschten GIFs markieren. Die Divoom-Gerätekennung wird
einmal in den Einstellungen gespeichert und für Helligkeit, Event-Tests
und die Ordner-Playlist verwendet. Bereits gespeicherte Event-Gerätekennungen
werden nicht für die Wiedergabe verwendet. Service-Aufrufe mit expliziter
Gerätekennung bleiben unverändert.
Die Seitenleiste gruppiert gespeicherte Einträge in Triggered-Events und
Datums-Events. Für Datums-Events können jährliche oder einmalige Zeiträume
und ein Aktivierungszustand gespeichert werden. Beide Grenztage zählen mit;
jährliche Zeiträume dürfen über den Jahreswechsel reichen. Aktivierte Events
werden im Datumsblock anhand des lokalen HA-Datums ausgewertet.
Triggered-Events unterstützen einen Zustandswechsel einer HA-Entität, einen
HA-Eventtyp oder die manuelle Aktion `divoom_orchestrator.trigger`.
Ein bereits beim Start aktiver Zustand löst nicht aus. Deaktivierte Events
werden automatisch und über die Aktion nicht ausgelöst.
Bei neuen Datums-Events öffnet der Browser den Ordner `date_events`, falls
dieser existiert. Anderenfalls beginnt er im Stammordner. Der ausgewählte
GIF-Ordner zeigt die aktuell geladenen GIFs; mit „Unterordner öffnen“ kann
man in einen seiner direkten Unterordner wechseln.
Die Reihenfolge lässt sich über die Pfeile ändern. Pro GIF gelten Sekunden
oder eine ganzzahlige Zahl geschätzter GIF-Durchläufe; dieselbe Datei kann in
verschiedenen Events andere Einstellungen haben. Neue Dateien bleiben zunächst
unmarkiert. Bei fehlenden Framezeiten oder Einzelbildern sind nur Sekunden
möglich. Ein gespeichertes Event lässt sich testen oder löschen.

Ein Test spielt die Schritte einmal ab. Während einer Playlist wartet er auf
einen laufenden Transfer und setzt anschließend mit dem nächsten GIF fort.
Playlist und Event müssen dasselbe Gerät verwenden. Nach dem letzten GIF bleibt dieses
Bild angezeigt, wenn keine Playlist läuft. Die berechnete Durchlaufdauer
beginnt nach dem Senden und ist keine Bestätigung des Geräts; Frames können
beim Pixoo anders lang sein oder reduziert werden. Die GIF-Metadaten werden
beim Test erneut geprüft.

Für automatische Auslöser, die Aktion und manuelle Tests gilt die numerische
Priorität: Ein wichtigeres Event unterbricht ein laufendes Event; gleiche
oder niedrigere Prioritäten werden ignoriert beziehungsweise bei manueller
Auslösung abgelehnt. Ein laufender Transfer wird
abgewartet, das unterbrochene Event nicht fortgesetzt. Ein Trigger-Test benötigt
die aktivierte Helligkeitsautomatik und stellt während des Events sowie für
mindestens 30 Sekunden ab Beginn 100 % Helligkeit ein. Die Klingelhardware
ist noch nicht angebunden.

### Rotation

Über **Bearbeiten** an der Startanimation einen Ordner laden, GIFs auswählen,
sortieren und die jeweilige Dauer einstellen. Wetter und Textblöcke werden in
eigenen Dialogen bearbeitet. **Fertig** schließt den Dialog und behält die
Änderungen als Entwurf; erst **Rotation speichern** in der Übersicht speichert
alle Änderungen dauerhaft. Die Startabfolge steht am Anfang
jedes Durchlaufs; optional folgen ein Wetterblock, mehrere Textblöcke und alle
aktiven Datums-Events alphabetisch. Ihre Reihenfolge lässt sich per Drag & Drop ändern und im
Rotationseditor speichern. Änderungen werden beim nächsten Durchlauf übernommen. Bei
gespeicherter Startabfolge und Gerätekennung startet die Rotation automatisch;
ein manueller Stopp bleibt bis zum Neustart oder einem manuellen Start gültig.
Die bisherige Ordner-Playlist und die Rotation verwenden denselben Controller
und können nicht gleichzeitig laufen.

Für das Wetter eine HA-Wetterentität wählen und GIFs unter
`wetter/<Wetterzustand>/tag` beziehungsweise `wetter/<Wetterzustand>/nacht`
ablegen. Der Zustand von `sun.sun` bestimmt Tag oder Nacht. Pro Durchlauf wird
zufällig ein GIF gewählt; bei mehreren Dateien wird die direkte Wiederholung
vermieden. Neue Dateien werden automatisch berücksichtigt.

Ein Textblock kann festen Text, den Zustand einer HA-Entität, ein einfaches
Attribut oder eine hochgeladene UTF-8-TXT-Liste (eine Zeile pro Spruch,
maximal 1 MiB) verwenden. Für Listen gibt es tägliche und aufrufbezogene
Auswahl, jeweils fortlaufend oder zufällig. Die tägliche Auswahl und der
Fortschritt bleiben nach Neustarts erhalten; ein erneuter Upload setzt sie
zurück. Leere beziehungsweise `unknown`/`unavailable` Werte und komplexe
Attribute gelten als Fehler. Der Tageswechsel folgt der HA-Zeitzone.
Textfarbe, Hintergrundfarbe, Größe, Framezeit und Anzeigedauer sind
einstellbar. Neue Textblöcke verwenden standardmäßig Schriftgröße 10;
vorhandene Größen bleiben unverändert. Für die Textgeschwindigkeit stehen fünf
Stufen zur Auswahl; abweichende bisherige Framezeiten bleiben erhalten, bis
eine Stufe gewählt wird. Für Textdurchläufe schätzt der Orchestrator die Dauer
anhand der Standardschrift und Frame-Schrittweite von `hass-divoom` für den
16×16-Pixoo und ergänzt einen Puffer von 0,5 Sekunden. Die Messung wurde mit
`hass-divoom` 1.5.2 am Pixoo geprüft. Andere Geräte, spätere Änderungen an
`hass-divoom` und Übertragungsverzögerungen können das Ergebnis beeinflussen;
eine Rückmeldung über das tatsächliche Durchlaufende gibt es nicht. Das Senden
erfolgt über `divoom.text`. Acht angehängte Leerzeichen sorgen beim Pixoo
dafür, dass das Ende längerer Texte sichtbar bleibt; sie werden bei der
Durchlauf-Schätzung berücksichtigt und nicht in der Textquelle gespeichert.

Fehler bei der Auswahl der Start-, Wetter-, Text-, Datums- oder Triggerbilder werden als dauerhafte
Benachrichtigung gemeldet und durch `fehler/start.gif` beziehungsweise
`fehler/wetter.gif`, `fehler/text.gif`, `fehler/datum.gif` oder `fehler/trigger.gif` ersetzt,
sofern vorhanden. Die gemeinsame Anzeigedauer ist
einstellbar. Bei Übertragungsfehlern wird alle 30 Sekunden erneut versucht;
ein Stopp oder Event kann das Warten unterbrechen.

Die Rotationsfunktion und insbesondere die Textdarstellung wurden noch nicht
auf einem echten Home-Assistant-/Pixoo-System geprüft.

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
Playlist aber nicht. Event-Prioritäten gelten nur für Events, die über den
Orchestrator ausgelöst werden.

Die Aktion `divoom_orchestrator.start` verwendet aus Gründen der
Abwärtskompatibilität weiterhin die gemeinsame `duration`. Mit
`individual_durations: true` gelten stattdessen die im Panel gespeicherten
Einzelzeiten; unkonfigurierte GIFs werden ausgelassen. Die Anzeigezeit beginnt
jeweils nach Abschluss der Übertragung, nicht mit deren Beginn.

## Tests

Die eigenständigen Tests brauchen Python 3.11 oder neuer, Pillow und
Voluptuous (in Home Assistant vorhanden):

```powershell
python -m unittest discover -s test -v
```

Sie simulieren die Wiedergabe und ersetzen keinen Praxistest mit Home Assistant,
dem NAS und dem Pixoo.
