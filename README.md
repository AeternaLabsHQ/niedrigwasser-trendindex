# Niedrigwasser-Trendindex für das deutsche NIWIS-Messnetz

„National“ meint hier das Messnetz, nicht die Staatsfläche: aus den Landesmessnetzen von
Niedersachsen, Bremen und Hamburg ist keine Station enthalten (der Nordwesten ist nur
über Bundespegel an Weser, Aller und Ems vertreten), und die Auswertung umfasst
mindestens rund 214.000 km² Einzugsgebiet außerhalb Deutschlands (Alpenrhein, Mosel,
Moldau, obere Oder u. a.) — rechnet man die alpinen Anteile von Inn und Salzach hinzu,
die außerhalb der fünf Basin-Auslässe liegen, sind es mindestens rund 229.000 km² und
damit etwa 45 % der maximalen Gewichtungsmasse (Herleitung:
`docs/recherche-auslandsanteil.md`).

Unabhängige, reproduzierbare Analyse der Niedrigwasser-Entwicklung in Deutschland
1992–2025 auf Basis öffentlicher Abfluss-Tageswerte (NIWIS/BfG).

Diese Analyse ist kein amtliches Produkt, keine Attribution auf Klimawandel/
Landnutzung und keine Vorhersage — sie zeigt einen statistisch geprüften Trend in
beobachteten Niedrigwasserkennzahlen. Details, Grenzen und offene Fragen: `docs/`.

## ▶ Ergebnisse ansehen

**<https://aeternalabs.io/de/niedrigwasser/>** — die interaktive Projektseite mit
Karte, Heatmap und Stationsdetails. Englische Fassung:
<https://aeternalabs.io/en/niedrigwasser/>.

Dieselbe Darstellung liegt als self-contained HTML im Repo (`site/index.html`,
`site/index.en.html`) und lässt sich ohne Build-Schritt und ohne Webserver direkt
im Browser öffnen — siehe „Seite lokal öffnen“.

## Kernergebnis

Der Median der Niedrigwassertage je Stationsjahr ist von 5–6 Tagen (1992–2013) auf
45 Tage (2014–2025) gestiegen; 224 von 359 Stationen (62,4 %) zeigen einen statistisch
signifikanten (TFPW-Mann-Kendall, p < 0,05) steigenden Trend bei Tagen unter Q95 — auch
nach Multiplizitätskorrektur (Benjamini-Hochberg-FDR über die 359 parallelen Tests)
bleiben es 211 von 359 (58,8 %) —, robust über vier Aggregationsvarianten und drei
Sensitivitätsläufe (Referenzperiode, Pooling-Fenster). 2018 ist mit index_days 93,5 (flächengewichtetes Mittel über
≈208 Stationen) das trockenste Jahr der gesamten Reihe, gefolgt von 2019 und 2022 —
sieben der zehn trockensten Jahre seit 1991 liegen im Zeitraum 2015–2025 (siehe
`docs/ergebnisse-phase4.md`).

## Installation & Reproduktion

Voraussetzung ist [uv](https://docs.astral.sh/uv/); die Python-Version (3.12) legt
`.python-version` fest — uv holt sie bei Bedarf selbst.

```bash
git clone <repo-url> niedrigwasser-trendindex
cd niedrigwasser-trendindex
uv sync            # Umgebung + Abhängigkeiten aus uv.lock
uv run pytest      # Testsuite (die `live`-Tests mit echten NIWIS-Calls sind
                   #   per default deselektiert: `uv run pytest -m live`)
```

`data/` ist **nicht Teil des Repos** (rund 640 MB, gitignored). Der Erstlauf
`uv run niedrigwasser ingest` lädt daher etwa 516 MB Rohdaten von der NIWIS-API nach
`data/raw/niwis/` — das dauert und braucht Netz. Danach liegen die Rohdaten
vollständig lokal: alle weiteren Stufen und komplette Rebuilds laufen offline,
solange kein `--refresh` gesetzt wird. Für einen schnellen Funktionstest ohne
Vollabzug reicht `uv run niedrigwasser ingest --limit 20`.

Die versionierten Ergebnisse (`out/`, `site/`) sind im Repo enthalten — wer nur
die Zahlen und die Seite ansehen will, braucht den Ingest gar nicht.

## Pipeline

Sechs Stufen, jede idempotent, mit Parquet-Zwischenständen unter `data/interim/`:

```bash
uv run niedrigwasser ingest    # NIWIS-Rohdaten laden, normalisieren, Topologie aufbauen
                        #   --limit N   nur N Stationen (Smoke-Test)
                        #   --refresh   Rohdaten neu herunterladen

uv run niedrigwasser screen     # Vollständigkeits- + Homogenitäts-Screening
                        #   --flags config/station_flags.csv

uv run niedrigwasser metrics    # Kennzahlen je Station/Wasserjahr (Q95, NM7Q, SSI, ...)
                        #   --ref-start 1992 --ref-end 2011   Referenzperiode
                        #   --inter-event 5                    Ereignis-Pooling (Tage)

uv run niedrigwasser aggregate  # Nationaler Index, 4 Varianten (primary/natural/allsinks/...)
                        #   --sinks config/sink_categories.csv

uv run niedrigwasser trend      # TFPW-Mann-Kendall/Sen, Dekadenvergleich, nicht-stationäre GEV
                        #   --out-dir out

uv run niedrigwasser render     # PNG-Grafiken + Site-Datenexport
                        #   --embed   bettet site/data.json in site/template.html ein
                        #             und schreibt die self-contained Seiten
                        #             site/index.html (aus site/text.de.json) und
                        #             site/index.en.html (aus site/text.en.json)
```

Jede Stufe unterstützt `--db`, `--interim-dir`, `--log-dir` zum Umleiten von
DuckDB/Zwischenständen/Logs; volles `--help` je Stufe zeigt alle Flags
(`uv run niedrigwasser <stufe> --help`). Sensitivitätsläufe (Referenzperiode, Pooling) laufen
end-to-end über `uv run python scripts/sensitivity.py`.

## Daten aktualisieren

Frischer Datenstand von der NIWIS-API bis zur fertigen Seite — die komplette Kette:

```bash
uv run niedrigwasser ingest --refresh   # Rohdaten neu von NIWIS holen (Netz, ~516 MB)
uv run niedrigwasser screen
uv run niedrigwasser metrics
uv run niedrigwasser aggregate
uv run niedrigwasser trend
uv run niedrigwasser render --embed     # site/data.json + site/index.html + site/index.en.html

uv run python scripts/sensitivity.py   # optional: Sensitivitätsläufe nachziehen
```

`--refresh` ist dabei entscheidend: **ohne** dieses Flag überspringt `ingest` jede
Rohdatei, die unter `data/raw/niwis/` bereits liegt — auch das offene Zeitfenster
ab 1990 (stabiler Dateiname `<nr>_1990-01-01_current.json`), es holt also keine
neuen Tage nach. Der Lauf ist dann rein lokal: er normalisiert den vorhandenen
Cache erneut und schreibt `stations`/`discharge_daily` in DuckDB neu (`DELETE` +
`INSERT`, also idempotent). Ein inkrementelles „nur die neuen Tage"-Laden gibt es
nicht — `--refresh` lädt alle Fenster aller Stationen komplett neu.

Der Rebuild ist reproduzierbar: `meta.generated` in `site/data.json` kommt nicht
mehr von der Wallclock, sondern aus der jüngsten Modifikationszeit der gelesenen
Eingabe-Artefakte (DuckDB, Vorstufen-Parquets/CSVs, `site/template.html`,
`site/geo.json`, `site/text.de.json`, `site/text.en.json`);
`SOURCE_DATE_EPOCH=<unix-ts>` setzt den Wert bei Bedarf explizit
(Standard von reproducible-builds.org). Zweimal `uv run niedrigwasser render --embed` auf
unverändertem Arbeitsverzeichnis liefert deshalb bit-identische Dateien, und Diffs
in `out/` und `site/` zeigen dann echte Datenänderungen statt des Laufzeitpunkts.

Die Einschränkung dazu: git speichert keine Modifikationszeiten. Nach einem
`git clone`, einem Branch-Wechsel oder einem `git stash pop` haben die Eingaben
neue mtimes — der nächste Render erzeugt dort weiterhin einen reinen
`meta.generated`-Diff. Der ist dann bedeutungslos: entweder verwerfen
(`git checkout -- site/data.json site/index.html site/index.en.html`) oder den Lauf mit einem festen
`SOURCE_DATE_EPOCH` fahren. Auf derselben Maschine mit unangetastetem Working Tree
tritt das nicht auf.

## Seite lokal öffnen

Die Seite gibt es zweisprachig: `site/index.html` (deutsch) und
`site/index.en.html` (englisch). Beide sind self-contained — Daten
(`site/data.json`) und Basemap (`site/geo.json`) sind eingebettet, es gibt keine
externen Skripte, Fonts oder Netzwerkaufrufe. Die Dateien lassen sich deshalb
direkt per Doppelklick bzw. als `file://`-URL im Browser öffnen — kein Webserver
nötig. Online steht dieselbe Seite unter
<https://aeternalabs.io/de/niedrigwasser/> bzw.
<https://aeternalabs.io/en/niedrigwasser/>.

Neu erzeugen lassen sie sich mit `uv run niedrigwasser render --embed` (oder, ohne die
render-Stage neu zu rechnen, mit `uv run python scripts/build_site.py`). Beide
Wege schreiben beide Sprachfassungen.

Gebaut wird jede Seite aus drei Teilen: `site/template.html` liefert Struktur,
Stil und Logik, `site/text.<sprache>.json` die gesamte Prosa, `site/data.json`
die Zahlen. Das Template ist sprachneutral und trägt **keinen** Text mehr,
sondern nur Schlüssel (`data-i18n`, `data-i18n-attr`, `t("…")`) — wer eine
Formulierung ändern will, ändert den Katalog, nicht das Template. Öffnet man
`site/template.html` direkt, erscheint deshalb nur ein Bau-Hinweis. Fehlt ein
Schlüssel in einem der beiden Kataloge, weichen die Daten-Platzhalter oder die
benannten `{platzhalter}` zwischen den Sprachen voneinander ab, oder ist der
`__locale__`-Block unvollständig, bricht der Build hart ab
(`src/niedrigwasser/i18n.py`).

## Verzeichnisstruktur

```
src/niedrigwasser/       Pipeline-Code (Stages in src/niedrigwasser/stages/, Kernlogik daneben)
config/          Versionierte Konfiguration: Stations-Flags, Sink-Kategorien,
                 Topologie-Overrides
data/            DuckDB + Rohdaten + Zwischenstände (gitignored)
out/             Ergebnis-CSVs + Analyse-PNGs (out/figures/), versioniert
site/            Interaktive Ergebnisseite, zweisprachig
                 (template.html = Struktur/Stil/Logik ohne Prosa,
                 text.de.json + text.en.json = Textkataloge,
                 data.json = Datenexport, geo.json = Basemap,
                 index.html + index.en.html = generiert)
docs/            Methodik, Ergebnisse, Topologie- und Homogenitäts-Recherche
tests/           pytest-Suite
```

## Datenquellen

Abfluss-Tageswerte über die NIWIS-API der Bundesanstalt für Gewässerkunde (BfG), die
Messstellen selbst werden von den zuständigen Bundes- und Landesbehörden betrieben.
**Die Lizenz ist je Station unterschiedlich** und wird im `license`-Feld der
`stations`-Tabelle mitgeführt (`data/niedrigwasser.duckdb`) — bei Weiterverwendung einzelner
Stationsdaten gilt die dort hinterlegte Lizenz inklusive etwaiger
Namensnennungspflicht, nicht eine pauschale Lizenz für den gesamten Datensatz. Die
vollständige Aufschlüsselung (Lizenz × Betreiber, Namensnennungs- und
Share-Alike-Pflichten) steht in `docs/attribution.md`, generiert aus der Datenbank
über `uv run python scripts/build_attribution.py`. Diese Auswertung selbst nennt
NIWIS/BfG/die jeweiligen Landesbehörden als Quelle auf jeder Grafik und in der Seite
(`SOURCE_LINE` in `src/niedrigwasser/stages/render.py`).

Die Kartengrundlage (`site/geo.json`) stammt von
[Natural Earth](https://www.naturalearthdata.com/) (gemeinfrei) und wird über
`scripts/fetch_geodata.py` erzeugt.

## Lizenz

`LICENSE` ist reiner MIT-Text und deckt **ausschließlich den Code** dieses Projekts ab.
Für die zugrunde liegenden Messdaten und für die abgeleiteten Datenprodukte gelten
davon unabhängige, eigene Lizenzen:

- **Code** (`src/`, `scripts/`, `tests/`, Markup unter `site/`): MIT — siehe
  `LICENSE`.
- **Messdaten**: je Station unterschiedlich, siehe `docs/attribution.md`. 221 der 361
  Stationen sind namensnennungspflichtig, 5 (LUNG MV) stehen unter CC BY-SA 3.0.
- **Abgeleitete Datenprodukte** (`out/`, `site/data.json`, die PNGs unter
  `out/figures/`): CC BY 4.0 — **mit Share-Alike-Vorbehalt** für die abgeleiteten
  Reihen der fünf CC-BY-SA-Stationen aus Mecklenburg-Vorpommern. Wer diese
  weiterverwendet, muss sie CC-BY-SA-kompatibel weitergeben und LUNG MV nennen.

## Zitieren

Zitierangaben (Titel, Autor, Jahr, Version) liegen maschinenlesbar in `CITATION.cff`.
Kurzform:

> Aeterna Labs (2026): *Niedrigwasser-Trendindex für das deutsche NIWIS-Messnetz*,
> Version 0.2.0.

## Weiterführende Dokumentation

- `docs/methods.md` — vollständige Methodik je Phase (Ingest bis Darstellung)
- `docs/ergebnisse-phase4.md` — Ergebnisdokumentation mit Quellenverweisen je Zahl
- `docs/topologie-report.md` — Stationsgraph, Senken-Klassifikation
- `docs/homogenitaet-recherche.md` — Herleitung der Homogenitäts-Flags
- `docs/recherche-auslandsanteil.md` — Herleitung des Auslandsanteils der Einzugsgebiete
- `docs/recherche-niwis-api.md` — Struktur und Eigenheiten der NIWIS-API
- `docs/attribution.md` — Lizenzen und Namensnennung je Station (generiert)
