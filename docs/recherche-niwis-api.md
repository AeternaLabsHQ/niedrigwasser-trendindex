# NIWIS-API — Recherche-Report (Stand 2026-08-24)

Ergebnis der Zugangs-Recherche für das NIWIS-Portal (niwis-online.de, BfG/LAWA). Alle Endpoints live getestet.

## Kernergebnis

**Offizielle, dokumentierte, öffentliche REST-API — kein Scraping nötig.**
Basis-URL: `https://niwis-online.de/api/daten` — JSON (UTF-8), keine Authentifizierung, kein API-Key.
Doku im Portal: „Informationen → Öffentliche API" (maschinell: `https://niwis-online.de/api/redaktion/215`, HTML im Feld `content`).

## Bulk-Ablauf (verifiziert)

1. `GET /api/daten/messstelle` → alle 695 Stationen (davon **361 mit Abfluss**: 336 Q+W, 25 nur Q)
2. Pro Station `GET /api/daten/stammdaten?messstelleNr=…` → Metadaten inkl. Einzugsgebiet
3. Pro Station `GET /api/daten/abfluss?messstelleNr=…&von=…&bis=…` → Tagesreihe (Limit **15.000 Werte/Request**)

## Endpoints mit Beispiel-Responses

### Stationsliste — `GET /api/daten/messstelle`

```json
{"messstelleNr":"DESM_DEBY18003004","name":"Wasserburg","landcode":"DEBY",
 "lizenz":"cc-by/4.0","messgroesse":["Abfluss","Wasserstand"]}
```

### Stammdaten — `GET /api/daten/stammdaten?messstelleNr=DESM_DEBY18003004`

```json
{"messstelleNr":"DESM_DEBY18003004","name":"Wasserburg","landcode":"DEBY",
 "lizenz":"cc-by/4.0","institution":"LfU BY","betreiber":"WWA Rosenheim",
 "urlMessstelle":"https://www.gkd.bayern.de/de/fluesse/abfluss/isar/wasserburg-18003004",
 "laenge":12.2343,"breite":48.0593,
 "gewaesser":"Inn","gkz":18,
 "lageGewaesser":"158.665",
 "ezgGroesse":11960,
 "hoehePnp":420.41,"hoehensystem":"DHHN2016",
 "nnq":93.8,"nnqDatum":"1969-12-28","nnw":null,
 "bemerkung":"Abflüsse werden durch ... beeinflusst"}
```

Topologie-Schlüsselfelder vorhanden: `ezgGroesse` (km²), `laenge`/`breite` (WGS84 lon/lat), `lageGewaesser` (Fluss-km, **String**), `gewaesser` + `gkz`.

### Tageswerte Abfluss — `GET /api/daten/abfluss?messstelleNr=…&von=1992-01-01&bis=1992-01-10`

```json
[{"messstelleNr":"DESM_DEBY18003004","datum":"1992-01-10","messwert":203.0,
  "einheit":"m³/s","flag":null}]
```

Sortierung **absteigend** (neuestes zuerst). Analog: `/wasserstand`, `/grundwasserstand`, `/quellschuettung`.

### Abgeleitete Größen

`GET /api/daten/abgeleiteteGroesse` (Katalog) plus Rechen-Endpoints `/berechneZeitreihenErgebnisNummer`, `/berechneKlassifikationsgrenzeDynamisch|Statisch`, `/berechneEinzelwertKategorie|Nummer` (Parameter: `abgeleiteteGroesse`, `messstelleNr`, optional `jahresdefinition` [HYDROLOGISCHESJAHR|WASSERHAUSHALTSJAHR|KALENDERJAHR], `startJahr`, `endJahr`, `von`, `bis`). Liefert u. a. NM7Q serverseitig — nützlich als Kreuzvalidierung der eigenen NM7Q-Berechnung.

### Interne UI-API (undokumentiert, offen)

- `GET /api/karte/messstelle/ABFLUSS?klassifikationsart=DYNAMISCH` — Kartenliste mit aktueller Niedrigwasserklasse/Trend
- `GET /api/config` — Bezugszeiträume (Klimareferenz 1991–2020, hydrologisches Jahr ab 1992)
- GeoServer `https://niwis-online.de/geoserver/geoserver/wms` (WMS + WFS 2.0) — nur Hintergrund-Layer (Flussgebiete, Flussnetz, Niederschlagsraster), keine Messstellen-Sachdaten
- `/api/shp` ist auth-geschützt (Keycloak id.bafg.de) — nicht nutzbar

## Zeitauflösung / Zeitraum (verifiziert)

- Echte **Tageswerte Q in m³/s**, `flag`-Feld für Prüf-/Fehlwerte.
- Testabruf Wasserburg/Inn: 1991-01-01 bis 2026-08-23 (tagesaktuell!), 13.019 Werte in einem Request (~1,3 MB).
- Reihenbeginn variiert je Station; `von` großzügig setzen, Server liefert, was da ist.
- 15.000-Werte-Cap: Reihen vor ~1985 brauchen zwei Requests (Zeitraum splitten).

## Lizenz

Pro Station im Feld `lizenz` (Zählung über 695 Stationen): `dl-zero-de/2.0` (218), `cc-by/4.0` (211), `dl-by-de/2.0` (210), `dl-de/by-2-0` (46), `cc by-sa 3.0` (10). Überwiegend DL-DE-Zero/DL-DE-BY/CC-BY — Weiterverwendung inkl. kommerziell erlaubt, **Namensnennung des jeweiligen Datenurhebers erforderlich** (außer DL-Zero); 10 Stationen CC-BY-SA 3.0 mit Share-Alike. Portalseiten: `/api/redaktion/210` (Datenquellen + Lizenzen je Land), `/api/redaktion/212` (Nutzungsbedingungen). Betreiber: BfG im Auftrag der LAWA. Kontakt: niwis@bafg.de.

## Fallback-Prüfung

- **GRDC**: kostenlos nach formloser Bestellung, aber anderes/kleineres deutsches Set, Nachführung hinkt Jahre hinterher, keine Fluss-km → kein Ersatz.
- **Pegelonline**: nur ~15-Minuten-Rohwerte der letzten 30 Tage, nur Bundeswasserstraßen → kein Ersatz.

## Risiken / Unbekannte

- Kein Versionierungs-Pfad (`/api/daten` ohne `/v1`), Portal erst seit Juli 2026 live — Endpoints können sich ändern. Kein OpenAPI/Swagger (404).
- Rate Limits nirgends dokumentiert → seriell mit Pausen abrufen.
- `lageGewaesser` ist String, evtl. null/uneinheitlich → defensiv parsen.
- `gkz` war im Test verdächtig kurz (18 statt voller LAWA-Gewässerkennzahl) → pro Station validieren, nicht blind für Topologie nutzen.
- Die Spezifikation sagt „356 Pegel", API liefert 361 mit Abfluss — Abweichung dokumentieren, nicht wegfiltern.
