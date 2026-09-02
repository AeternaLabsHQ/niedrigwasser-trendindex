# Methoden — Niedrigwasser-Trendindex für das deutsche NIWIS-Messnetz

*Wird pro Phase fortgeschrieben.*

## Datengrundlage
- Quelle: NIWIS (BfG), 361 Messstellen mit Abfluss (NIWIS-API; die ursprüngliche
  Spezifikation nannte 356), Abfluss-Tageswerte (Q, m³/s), 1992–2025.
- Wasserstände (W) werden nicht verwendet (Pegelnullpunkt-Inkompatibilität, Sohlerosion).

## Sentinel-Behandlung im Ingest
NIWIS liefert Fehl-/Unplausibel-Werte nicht als `null`, sondern als negative Zahlen im
`messwert`-Feld — dominant der Sentinel **−777** (Flags `Fehlwert`/`BfGAdded`/
`BfGUnplausibel`), daneben vereinzelt weitere negative Werte ohne erkennbaren Flag.
Physikalisch ist `Q < 0` an keinem der Pegel möglich. `normalize_discharge`
(`src/niedrigwasser/stages/ingest.py`) setzt daher **jeden Wert mit `q < 0` auf `null`** und
überschreibt `quality_flag` mit `"sentinel"` (der ursprüngliche Flag-Wert wird dabei
verworfen — bei den `-777`-Zeilen drückt er ohnehin nur denselben Fehlwert-Status aus).
Downstream wirkt sich das direkt auf das Vollständigkeits-Screening aus
(`station_year_completeness` zählt bereits `q.is_not_null()` als Anwesenheitskriterium,
siehe unten) — Sentinel-Tage werden dadurch korrekt als Lücken statt als (falsche)
Tiefstwerte behandelt. Ohne diesen Fix wären −777 m³/s in NM7Q, Q95, `days_below`,
`deficit_volume` und SSI eingeflossen (siehe Validierungs-Fund aus einer
internen Gegenprüfung gegen eine unabhängige externe Analyse).

## Wasserjahr
- 1. November – 31. Oktober (deutsche Konvention); Wasserjahr 2025 = 01.11.2024–31.10.2025.

## Vollständigkeits-Screening
- Station-Jahre mit < 95 % Tagesabdeckung im Sommerhalbjahr (Mai–Okt, 184 Tage) werden verworfen.
- Stationen mit < 25 verwertbaren Jahren werden komplett verworfen.
- Lücken werden nicht interpoliert (Bias bei Extremwertstatistik).

## Homogenitäts-Screening (angelehnt an UKBN2)
Stationen werden geflaggt (`config/station_flags.csv`, versioniert, mit Begründung je Eintrag):
- `reservoir` — große Talsperre im Oberlauf, Steuerung überlagert das Klimasignal
- `transfer` — Überleitung zwischen Einzugsgebieten
- `mining` — bergbaubedingte Entnahme/Einleitung (z. B. Lausitzer Restseeflutung: Spree, Schwarze Elster)
- `erosion` — instabile W-Q-Beziehung (Sohlerosion, Sedimentation, Geschiebe,
  Pegel-Standortwechsel); reiner Hinweis, kein Ausschluss (betrifft W, nicht Q)

Naturnahes Subset = Stationen ohne `reservoir`/`transfer`/`mining`. Alle Analysen werden
doppelt gerechnet (alle Stationen vs. naturnahes Subset); starke Divergenz ist selbst ein Befund.

Herleitung der Kriterien, Quellenlage je Flag und vollständige Begründung jeder
Vorschlagszeile: `docs/homogenitaet-recherche.md`. Kernzahlen (Rev. 2, 205 Vorschlagszeilen
in `config/station_flags.csv`): **128 Stationen** mit mindestens einem Flag, davon
**125 Stationen** mit einem ausschließenden Flag (`reservoir`/`transfer`/`mining`;
12 zusätzliche Stationen tragen nur `erosion` und werden nicht ausgeschlossen); daraus
ergibt sich ein naturnahes Subset von **236 / 361 Stationen (65 %)** vor Vollständigkeits-
Screening.

## Nesting-Auflösung
- Gerichteter Stationsgraph über `downstream_id`.
- `A_incremental(i) = A(i) − Σ A(j)` über direkte Oberlieger j; muss ≥ 0 sein, sonst Abbruch.
- Gewichte der nationalen Aggregation: `w_i = A_incremental(i) / Σ A_incremental`.

## Topologie-Konstruktion
Der Stationsgraph (`downstream_id`) wird in zwei Schritten aus den NIWIS-Stammdaten
aufgebaut (`src/niedrigwasser/build_topology.py`, vollständiger Bericht:
`docs/topologie-report.md`):

1. **Auto-Kette pro Fluss** (`chain_within_river`): Stationen mit identischem,
   normalisiertem (getrimmt, kleingeschrieben) `river`-Namen werden aufsteigend nach
   `catchment_area` sortiert und linear verkettet. Das Einzugsgebiet wächst
   flussabwärts streng monoton — robuster als `river_km`, dessen Zählrichtung je
   Bundesland variiert (siehe `docs/recherche-niwis-api.md`). Die jeweils letzte
   (größte) Station pro Fluss bleibt zunächst Senke (`downstream_id = null`).
   **Guard:** eine Kante wird nur gesetzt, wenn `river` bei beiden Stationen gesetzt
   ist (kein `null`-Fluss) und die Luftlinie (Haversine über `lat`/`lon`) zwischen
   ihnen < 150 km beträgt — verhindert, dass zwei physisch unterschiedliche Gewässer
   gleichen Namens (z. B. mehrere "Schwarzbach"/"Kinzig"/"Nahe"/"Vils"/"Bode" in
   Deutschland) automatisch verkettet werden. Der Guard ist notwendig, aber nicht
   hinreichend — räumlich nahe Namenskollisionen (< 150 km) müssen zusätzlich per
   Override getrennt werden (siehe `docs/topologie-report.md`).
2. **Manuelle Overrides** (`config/topology_overrides.csv`, Spalten `station_id,
   downstream_id, note`; `apply_overrides`): verbindet echte Mündungen mit dem
   Empfängerfluss, sofern dieser ebenfalls einen NIWIS-Pegel im Datensatz hat, und
   trennt Namenskollisionen, die der 150-km-Guard nicht erfasst (leerer
   `downstream_id` = bewusste Senke/Trennung). Jede Zeile trägt eine Begründung.
   Auswahl des Downstream-Kandidaten: nächster Pegel am Empfängerfluss flussabwärts
   der Mündung — in der Praxis anhand bekannter Geographie (Mündungsort, Fluss-km,
   Koordinaten) bestimmt, nicht rein über EZG-Größenvergleich (der ist zwischen
   unterschiedlich großen Flusssystemen bedeutungslos). Unbekannte Stationen in
   Overrides lösen `ValueError` aus.
3. **Validierung** (`build_topology`): `validate_topology` (Zyklen, Duplikate,
   unbekannte Referenzen) und `incremental_areas` (`A_incremental ≥ 0`, sonst
   `TopologyError` mit der Liste der Verletzer). Overrides werden iterativ ergänzt/
   korrigiert, bis der Aufbau fehlerfrei durchläuft — **niemals** wird negative Fläche
   geclampt. `niedrigwasser ingest` (`src/niedrigwasser/stages/ingest.py`) wendet `build_topology`
   nach der Normalisierung an und **bricht bei `TopologyError` (bzw. jeder anderen
   `ValueError` aus `apply_overrides`) hart ab**, statt mit unbefülltem
   `downstream_id` weiterzulaufen — eine stillschweigend leere Topologie würde jede
   Station zur Senke machen und die nationale Gewichtung in Phase 3 grob verzerren
   (z. B. den Rhein vielfach übergewichten). Bei gesetztem `--limit` (Smoke-Test auf
   einer Teilmenge der Stationen) wird die Topologie-Stufe übersprungen und nur
   geloggt, statt an den auf den vollen Datensatz abgestimmten Overrides zu scheitern.

Nicht jede Station wird angeschlossen: Hauptstromgewässer ohne deutschen Empfänger im
Datensatz (Rhein, Elbe, Oder, Weser, Donau) sowie Zubringer, deren Empfängerfluss
keinen eigenen NIWIS-Pegel hat (z. B. alle Isar-/Lech-/Regnitz-Zubringer), bleiben
bewusst Senken. Das führt dazu, dass `Σ a_incremental` über allen Stationen die Fläche
Deutschlands übersteigen kann. `docs/topologie-report.md` schlüsselt die Senken in drei
Kategorien auf: (i) echte Basin-Auslässe mit Auslandsanteilen (dominanter Effekt),
(ii) legitim eigenständige Systeme (additiv, nicht doppelt gezählt), und
(iii) verschachtelte, mangels Empfänger-Pegel unverbundene Teilflächen, die
hydrologisch bereits in (i) enthalten sind. **Für die nationale Gewichtung in Phase 3
gilt:** Kategorie-(iii)-Senken dürfen nicht zusätzlich zu ihrem umfassenden
Basin-Auslass gezählt werden, sonst wird dieselbe Fläche doppelt gewichtet — die genaue
Behandlung (ignorieren/anteilig zurechnen/flaggen) ist eine Entscheidung für Phase 3
und wird im Topologie-Report nur dokumentiert, nicht vorweggenommen.

## Screening-Ergebnis (Lauf 2026-08-25, nach Sentinel-Fix)

`uv run niedrigwasser screen` auf dem vollen Datensatz (`data/niedrigwasser.duckdb`, vorab verifiziert:
361 Stationen, 4.699.859 Abfluss-Tageswerte).

**Ursprünglicher Lauf (vor dem Sentinel-Fix, siehe Abschnitt „Sentinel-Behandlung im
Ingest" oben):**
- Station-Jahre gesamt: 12.996; verwertbar (≥ 95 % Sommerhalbjahr-Abdeckung): 12.635
  (361 verworfen).
- Stationen nach 25-Jahre-Filter überlebt: 361 / 361 (0 verworfen) — jede Station brachte
  einheitlich genau 35 verwertbare Wasserjahre mit (min = max = 35).

**Nach dem Sentinel-Fix (q < 0 ⇒ null) — aktueller Stand:**
- **Station-Jahre gesamt:** 12.996 (unverändert — Anzahl Station×Wasserjahr-Kombinationen
  ändert sich durch den Fix nicht, nur deren Vollständigkeit)
- **Station-Jahre verwertbar** (≥ 95 % Sommerhalbjahr-Abdeckung): **12.497** — 499 Station-Jahre
  verworfen (vorher 361; +138 zusätzlich verworfen, weil vormals als „vorhanden" gezählte
  Sentinel-Tage jetzt korrekt als Lücken zählen)
- **Stationen nach 25-Jahre-Filter überlebt:** **360 / 361** (1 verworfen: `DESM_DEXX24300304`,
  fällt durch den Sentinel-Fix von 22 auf effektiv unter 25 verwertbare Jahre)
- **Geflaggt** (`config/station_flags.csv`, Homogenitäts-Flags übernommen, Rev. 2, siehe
  `docs/homogenitaet-recherche.md`): **124** der 360 überlebenden Stationen tragen
  mindestens einen ausschließenden Flag (`reservoir`/`transfer`/`mining`) — 125 Stationen
  insgesamt sind in der Flags-Datei ausschließend erfasst, eine davon
  (`DESM_DEXX24300304`) fällt bereits durch den 25-Jahre-Filter heraus
- **Naturnahes Subset:** **236 / 360** — konsistent mit der vorab (vor Vollständigkeits-
  Screening) berechneten Kennzahl 236 / 361 (65 %) aus `docs/homogenitaet-recherche.md`

Ergebnis-Reports liegen als Parquet unter `data/interim/screen/`
(`completeness.parquet`, `usable_station_years.parquet`, `usable_stations.parquet`);
Stage-Log: `logs/screen.log`.

## Schwellenwert und Kennzahlen (Phase 2)
- Q95 aus fixer Referenzperiode Wasserjahre 1992–2011 (Dauerlinien-5.-Perzentil, linear
  interpoliert); Sensitivität: 1991–2020 (WMO). MNQ = Mittel der Jahres-NQ der Referenzperiode.
- Ereignis-Pooling: Inter-Event-Kriterium ≤ 5 Tage (Sensitivität 3/7). `max_spell` misst die
  Spannweite des gepoolten Ereignisses inkl. überbrückter Tage; `days_below` bleibt ungepoolt.
- NM7Q: Minimum des 7-Tage-Mittels, nur vollständige Fenster (Lücken brechen das Fenster,
  keine Interpolation).
- SSI: Jahreswert = Sommerhalbjahres-Mittel (Mai–Okt) des Abflusses („Jahreswerte" in der Spezifikation
  so konkretisiert); Gamma-/Log-Normal-Fit (floc=0) an die Referenzjahre, Auswahl per
  KS-Statistik, Fallback auf Weibull-Plotting-Position + Probit bei p < 0,05 beider Fits oder
  < 10 Referenzjahren. Kennzahlen werden nur für verwertbare Station-Jahre ausgewiesen.

## Nationale Aggregation (Phase 3)

`uv run niedrigwasser aggregate` (`src/niedrigwasser/stages/aggregate.py`, Kernfunktion
`national_index` in `src/niedrigwasser/aggregate.py`) verdichtet die Station-Jahr-Kennzahlen
aus Phase 2 (`data/interim/metrics/station_year_metrics.parquet`) zu einer
Jahres-Zeitreihe über das gesamte Messnetz (zur Reichweite des Begriffs „national“
siehe den gleichnamigen Abschnitt am Ende dieses Kapitels).

### Formel

Für jedes Wasserjahr wird pro Kennzahl ein flächengewichtetes Mittel über die in
diesem Jahr verwertbaren Stationen gebildet, mit `a_incremental` (inkrementelle
Einzugsgebietsfläche aus der Nesting-Auflösung, siehe oben) als Gewicht:

```
index_days    = Σ(days_below_i    · a_incremental_i) / Σ(a_incremental_i)   [nur i mit days_below_i  ≠ null]
index_deficit = Σ(deficit_mm_i    · a_incremental_i) / Σ(a_incremental_i)   [nur i mit deficit_mm_i  ≠ null]
index_ssi     = Σ(ssi_i           · a_incremental_i) / Σ(a_incremental_i)   [nur i mit ssi_i         ≠ null]
```

Der Nenner läuft je Kennzahl nur über die Stationen, die für diese Kennzahl in diesem
Jahr einen nicht-null Wert liefern (`_weighted` in `src/niedrigwasser/aggregate.py`) — die drei
nationalen Indizes eines Jahres können daher auf leicht unterschiedlichen
Stationsmengen beruhen, falls einzelne Stationen nur für einzelne Kennzahlen fehlende
Werte haben. Zusätzlich werden `n_stations` (Zahl beitragender Stationen) und
`coverage_area_km2` (Σ `a_incremental` der beitragenden Stationen) je Jahr mit
ausgewiesen.

### mm-Normierung von `index_deficit`

`deficit_volume_m3` (Defizitvolumen, Summe der Unterschreitungen unter Q95 über das
Jahr, aus Phase 2) wird vor der Gewichtung auf die Einzugsgebietsfläche der jeweiligen
Station normiert:

```
deficit_mm = deficit_volume_m3 / (catchment_area_km2 · 1e6) · 1000
```

(`catchment_area` in km² → m² via `· 1e6`, m → mm via `· 1000`). Das macht
`index_deficit` größen- und flächenunabhängig vergleichbar zwischen kleinen Bächen und
großen Flüssen und über die Zeit, in der sich die Stationsmenge (und damit die
gewichtete Gesamtfläche) leicht ändert.

### Senken-Entscheidung: outlet / standalone / nested

Der Topologie-Report (`docs/topologie-report.md`) klassifiziert alle Stationen ohne
`downstream_id` (Senken des Stationsgraphen) in drei Kategorien
(`config/sink_categories.csv`, Spalten `station_id,category,note`,
`category ∈ {outlet, standalone, nested}`), Ergebnis: **5 outlet / 34 standalone /
152 nested** (von 191 Senken insgesamt):

- **outlet** — echter Basin-Auslass mit signifikantem Auslandsanteil (Rhein, Elbe,
  Oder, Weser, Donau u. Ä.) — die Fläche ist real, nicht doppelt gezählt, aber die
  Station deckt oft nur den deutschen Teil des Einzugsgebiets ab.
- **standalone** — legitim eigenständiges System (z. B. direkt in einen See oder ins
  Meer entwässernder Zubringer ohne größeren Empfänger im Datensatz) — additiv, nicht
  doppelt gezählt.
- **nested** — verschachtelte Teilfläche, deren Fläche bereits im übergeordneten
  Basin-Auslass enthalten ist, aber mangels gepegeltem Empfängerfluss im Stationsgraph
  nicht direkt verbunden werden konnte (`docs/topologie-report.md`, Kategorie (iii)).
  Würde eine `nested`-Station zusätzlich zu ihrem Basin-Auslass mit vollem Gewicht in
  den nationalen Index eingehen, würde dieselbe Fläche doppelt gezählt.

**Entscheidung:** Die maßgebliche Variante `primary` schließt `nested`-Stationen aus
(`select_index_stations(..., include_nested=False)`), um Doppelzählung von Fläche zu
vermeiden. `nested` bleibt dabei nur ein Ausschlusskriterium für die *nationale
Gewichtung* — die Stationen selbst sind weiterhin vollwertiger Teil der
Stations-Trendanalyse (Abschnitt „Trendstatistik" unten, `out/station_trends.csv`),
dort spielt Flächen-Doppelzählung keine Rolle.

#### Bekannte Restunschärfe: `standalone`-Senken oberhalb eines anderen Pegels

Der `nested`-Ausschluss greift nur dort, wo die Verschachtelung erkannt wurde. Drei
Stationen des primary-Sets sind als `standalone` geführt — sie haben kein
`downstream_id`, weil ihr Gewässer Deutschland ohne weiteren Pegel verlässt —,
entwässern aber tatsächlich in die Rur oberhalb des Pegels Stah
(`DESM_DENW2829100000100`, 2.135 km², selbst eine `standalone`-Senke):

| Station | Gewässer | `station_id` | Einzugsgebiet |
|---|---|---|---|
| Gemünd | Urft | `DESM_DENW2822900000200` | 345 km² |
| Randerath | Wurm | `DESM_DENW2828900000200` | 311 km² |
| Eschweiler | Inde | `DESM_DENW2824590000400` | 232 km² |

Ist die Fläche dieser drei bereits im amtlichen Einzugsgebietswert von Stah enthalten
— wovon bei 1.335 km² für den oberhalb liegenden Pegel Jülich Stadion und 2.135 km²
für Stah auszugehen ist —, dann zählen zusammen **888 km²** im flächengewichteten
Index doppelt. Bezogen auf die maximale jährliche Abdeckung des primary-Sets
(511.744 km², siehe `docs/ergebnisse-phase4.md`) sind das **0,17 %** der
Gewichtungsmasse.

Derselbe Vorbehalt gilt für die Wriezener Alte Oder (`DESM_DEBB6940000`, 1.084 km²,
rund 0,21 %); dort ist die Kategorie `standalone` belegt, die Flächenfrage aber offen
(Herleitung und Quellen: `docs/topologie-report.md`, Abschnitt „Nachträgliche
Web-Verifikation der drei offenen Grenzfälle").

**Status: bekannt, nicht korrigiert.** Zusammen rund 0,4 % der Gewichtungsmasse — die
Größenordnung liegt unter der Auflösung jeder hier berichteten Kennzahl. Eine
Korrektur über `config/topology_overrides.csv` wäre billig, zöge aber einen
vollständigen Neulauf der Pipeline und eine Neuprüfung aller publizierten Zahlen nach
sich; beides steht der Aussage nicht gegenüber. Wer die Sensitivität beziffern will,
rechnet die Variante `allsinks` gegen `primary` (Abschnitt „Varianten") — sie misst
denselben Effekt für die 152 erkannten `nested`-Senken und damit für eine mehr als
50-fach größere Fläche (53.110 km²).

### Varianten

`niedrigwasser aggregate` rechnet vier Varianten in einem Lauf (`VARIANTS` in
`src/niedrigwasser/stages/aggregate.py`), Ergebnis-Parquet je Variante unter
`data/interim/aggregate/national_index_<variante>.parquet`:

| Variante | `include_nested` | `natural_only` | Bedeutung |
|---|---|---|---|
| `primary` | Nein | Nein | maßgebliche Variante: alle screening-überlebenden Stationen, keine Flächen-Doppelzählung |
| `natural` | Nein | Ja | wie `primary`, zusätzlich auf naturnahes Subset beschränkt (`is_near_natural`, siehe Homogenitäts-Screening) |
| `allsinks` | Ja | Nein | wie `primary`, aber `nested`-Senken werden mitgezählt (Doppelzählungs-Sensitivität) |
| `allsinks_natural` | Ja | Ja | Kombination aus `allsinks` und `natural` |

Nur `primary` wird zusätzlich in DuckDB (`national_index`-Tabelle) und
`out/national_index.csv` geschrieben; die drei übrigen Varianten dienen ausschließlich
der Sensitivitätsbewertung in Phase 4 (siehe `docs/ergebnisse-phase4.md`, Abschnitt 2)
und liegen nur als Parquet vor.

### Reichweite des Begriffs „national“

Der Index heißt „national“, weil er das gesamte ausgewertete Messnetz zusammenfasst —
nicht, weil er die Staatsfläche Deutschlands abbildet. Zwei Einschränkungen gehören
sichtbar dazu und werden deshalb auch auf der Site benannt:

1. **Das NIWIS-Messnetz ist unvollständig.** Unter den 359 ausgewerteten Stationen
   stammt keine einzige aus den Landesmessnetzen von **Niedersachsen, Bremen oder
   Hamburg** — die Länderpräfixe `DENI`, `DEHB`, `DEHH` fehlen in den Stations-IDs
   vollständig. Vertreten ist der Nordwesten nur über Bundespegel (`DEXX`) an den
   Hauptströmen: Intschede, Dörverden, Liebenau (Weser), Rethem (Aller), Lingen-Darme
   (Ems). Die Nebenflüsse dieses Raums — Leine unterhalb Thüringens, Hunte, Oste,
   Ilmenau, Wümme — kommen im Netz nicht vor.
2. **Die gewichtete Fläche ist größer als Deutschland.** Die jahresabhängige Coverage
   der `primary`-Variante liegt zwischen **453.778 und 511.744 km²** und übersteigt die
   Gebietsfläche Deutschlands (rund 357.600 km², Destatis) deutlich. Ursache ist kein
   Topologiefehler, sondern die Struktur der Basin-Ketten: Rhein/Rees, Elbe/Wittenberge,
   Oder/Hohensaaten-Finow und Donau/Hofkirchen bringen die **vollständigen** Oberläufe
   ihrer Ströme in die Gewichtungsmasse ein, und diese reichen weit ins Ausland.

Für die fünf Basin-Auslässe ist der Inlandsanteil einzeln recherchiert und belegt
(`config/basin_domestic_area.csv`, Herleitung und Primärquellen in
`docs/recherche-auslandsanteil.md`). Daraus ergibt sich ein Auslandsanteil von
**mindestens 213.801 km²** — rund 42 % der maximalen Gewichtungsmasse. Der Wert ist eine
**untere** Schranke: bei Oder und Donau ist `domestic_km2` bewusst als obere Schranke
gesetzt, und die alpinen `standalone`-Senken Inn/Wasserburg und Salzach/Burghausen
(zusammen rund 15.600 km² Ausland) liegen außerhalb der fünf Ketten und sind in der Zahl
nicht enthalten. Rechnet man diese alpinen Anteile von Inn und Salzach hinzu, liegt der
Auslandsanteil bei **mindestens rund 229.000 km²** (~45 %); der wahre Wert dürfte eher
bei 230.000–232.000 km² liegen.

Die Render-Stage rechnet den Auslandsanteil bei jedem Lauf aus der CSV neu
(`_foreign_area` in `src/niedrigwasser/stages/render.py`) und exportiert ihn als
`meta.coverage_foreign_km2` plus `meta.coverage_foreign_is_lower_bound` nach
`site/data.json`; fehlt die CSV, fällt der Wert auf die quellenfreie Schranke
`max(0, coverage − 357.600 km²)` zurück. Umgekehrt gilt: der Index erfasst höchstens
rund 282.000 km² deutsche Fläche, also höchstens etwa 79 % Deutschlands. Das ist das
Spiegelbild der Ausland-Untergrenze — weil `domestic_km2` bei Oder und Donau als *obere*
Schranke angesetzt ist, ist die deutsche Fläche eine obere Schranke. Auch als Obergrenze
bleibt es die belastbare Aussage zur Abdeckung.

## Trendstatistik (Phase 4)

`uv run niedrigwasser trend` (`src/niedrigwasser/stages/trend.py`, Kernfunktionen in
`src/niedrigwasser/trend.py`) rechnet drei unabhängige Analysen auf den Phase-2/3-Ergebnissen:
nationale und stationsweise Trends (TFPW-MK/Sen), Dekadenvergleich, nicht-stationäre
GEV-Extremwertanalyse.

### TFPW-Mann-Kendall + Sen-Slope

`mk_trend()` nutzt den *Trend-Free Pre-Whitening*-modifizierten Mann-Kendall-Test
(`pymannkendall.trend_free_pre_whitening_modification_test`) statt des einfachen
MK-Tests, um Autokorrelation in den Jahreszeitreihen nicht fälschlich als Trend zu
werten, plus die klassische Theil-Sen-Steigung (`pymannkendall.sens_slope`) als
Effektstärke. Sonderfälle: bei `n < 10` Werten wird `"insufficient"` statt eines
Testergebnisses zurückgegeben (zu wenig Datenpunkte für einen sinnvollen MK-Test); bei
einer konstanten Reihe (`np.ptp < 1e-12`) wird `"no trend"`/`p=1.0`/`slope=0.0`
zurückgegeben, statt die bei Varianz 0 undefinierte (0/0) TFPW-Autokorrelation
crashen oder eine `NaN` durchreichen zu lassen.

**Fenster:** alle Trendtests (national wie stationsweise) laufen auf **Wasserjahre
1992–2025 (n=34)**. Die `national_index_*`-Parquets enthalten zusätzlich das
Wasserjahr 1991; dieses wird vor dem MK-Test herausgefiltert (`WINDOW`-Filter,
Kommentar `F1` in `src/niedrigwasser/stages/trend.py`).

**Grund ist die Datenlage, nicht das Ergebnis.** NIWIS liefert ab dem 1.1.1991, das
Wasserjahr 1991 beginnt aber am 1.11.1990: ihm fehlen November und Dezember 1990
vollständig, es hat **304 statt 365 Tage**. Eine Jahreskennzahl aus zehn Zwölfteln
eines Jahres ist mit vollständigen Jahren nicht vergleichbar, gleich in welche
Richtung sie zeigt; der Ausschluss wäre also auch dann zwingend, wenn er am Ergebnis
nichts änderte.

Dass er etwas ändert, gehört trotzdem hierher: ohne den Filter zieht der 1991-Wert
den TFPW-MK-Trend, insbesondere bei `index_ssi`, sichtbar Richtung „no trend". Das
ist die *Wirkung* des Schnitts, nicht seine Begründung. Wasserjahr 1991 bleibt in den
Parquet-/CSV-Dateien unverändert enthalten und damit nachprüfbar.

**National** (`_national_trends`): je Variante (`primary`/`natural`/`allsinks`/
`allsinks_natural`) und Metrik (`index_days`/`index_deficit`/`index_ssi`) ein
MK-Test über die 34 Jahreswerte → `data/interim/trend/national_trends.parquet`
(12 Zeilen = 4 Varianten × 3 Metriken).

**Stationsweise** (`_station_trends`): je Station mit **mindestens 25 Jahren** im
Fenster 1992–2025 ein MK-Test auf `days_below` und auf `nm7q` (getrennt, jeweils nur
über die nicht-null-Jahre der Station) → `out/station_trends.csv`. Zusätzlich wird je
Station das Jahr des NM7Q-Allzeitminimums (`min_year`) ausgewiesen; bei mehreren
Jahren mit identischem Minimalwert gewinnt das früheste Jahr (Tie-Break, zweites
Sortkriterium `water_year` aufsteigend). Der 25-Jahre-Schwellenwert filtert Stationen
mit zu kurzer Historie im Fenster aus einer nach dem allgemeinen
Vollständigkeits-Screening (Phase 1, Schwelle 95 % Sommerhalbjahr-Abdeckung je
Stationsjahr) bereits bereinigten Grundgesamtheit heraus.

**Multiplizität (Benjamini-Hochberg-FDR):** stationsweise werden **359 MK-Tests je
Kennzahl** parallel gerechnet. Bei α = 0,05 wären allein durch Zufall **höchstens** ≈ 18
Falsch-Positive je Kennzahl zu erwarten (359 × 0,05 = 17,95) — diese Obergrenze gilt
allerdings nur unter der globalen Nullhypothese, also wenn *kein einziger* der 359
Trends echt wäre. Die tatsächliche Erwartung ist m₀ × α, wobei m₀ die Zahl der wirklich
trendfreien Stationen ist; bei einer Trefferquote von über 60 % liegt m₀ plausibel eher
bei 135–150 und die erwartete Zahl zufälliger Treffer damit eher bei ≈ 7. In beiden
Fällen gilt: ein Befund „X von 359 Stationen signifikant" ist ohne Korrektur
systematisch zu optimistisch.
`bh_adjust()` (`src/niedrigwasser/trend.py`, `scipy.stats.false_discovery_control`,
`method="bh"`) adjustiert die p-Werte deshalb nach Benjamini-Hochberg und schreibt sie
als **Zusatzspalten** `days_below_p_fdr` / `nm7q_p_fdr` nach `out/station_trends.csv`.
Wichtig:

- **Zwei getrennte Testfamilien.** `days_below` und `nm7q` werden **je separat** über
  ihre 359 Tests korrigiert, nicht gemeinsam über 718 — es sind zwei inhaltlich
  eigenständige Fragestellungen, und eine gemeinsame Familie würde die Korrektur
  künstlich verschärfen.
- **Die Roh-p-Werte bleiben unangetastet.** `days_below_p` / `nm7q_p` und die
  bestehende Signifikanzlogik (Karte, Detail-Panel, alle bisher berichteten Quoten)
  ändern sich nicht; die FDR-Spalten kommen additiv dazu. Stationen ohne Test
  (`"insufficient"`, p-Wert `None`) bekommen auch keinen FDR-Wert.
- **Ergebnis auf den Realdaten** (Lauf 2026-08-25, Schwelle 0,05, Richtung wie bisher):

  | Kennzahl | roh signifikant | nach BH-FDR |
  |---|---:|---:|
  | `days_below` steigend | 224 / 359 (62,4 %) | **211 / 359 (58,8 %)** |
  | `nm7q` fallend | 222 / 359 (61,8 %) | **197 / 359 (54,9 %)** |

  Die Korrektur ist hier mild, weil die Trefferquote (>60 %) weit über dem
  Zufallsniveau liegt: BH ist umso nachsichtiger, je mehr echte Effekte in der Familie
  stecken. Es fallen 13 (`days_below`) bzw. 25 (`nm7q`) Stationen aus der Signifikanz;
  keine Station wird durch die Adjustierung neu signifikant (BH-adjustierte p-Werte
  sind stets ≥ den Roh-p-Werten). Die Kernaussage — deutliche Mehrheit der Stationen
  mit signifikantem Trend — bleibt damit auch nach Multiplizitätskorrektur bestehen.

Die Zählungen werden bei jedem Lauf ins Stage-Log geschrieben
(`Multiplizitaet (…, alpha=0.05): roh N/359 signifikant, nach
Benjamini-Hochberg-FDR M/359`).

Für die Sensitivitätsanalyse (Abschnitt „Sensitivitätsanalysen" unten) wird
zusätzlich `max_spell` (gepoolte Ereignis-Spannweite, Pooling-abhängig — anders als
`days_below`/`nm7q`) je Station mit demselben 25-Jahre-Kriterium getestet; Ergebnis
fließt aggregiert (Anteil signifikant steigend, Median-Sen-Slope) in
`out/sensitivity.csv` ein, nicht als Einzelstations-Tabelle.

### Dekadenvergleich

`decade_stats()` berechnet Mittel, Median, P90 und Anteil Nullwerte je Kennzahl
(`days_below`, `deficit_mm`, `nm7q`) über **alle** Station-Jahre (nicht
flächengewichtet — reine Verteilungsstatistik, jedes Stationsjahr zählt gleich) in
drei fest definierten Dekaden:

```
DECADES = [(1992, 2001), (2002, 2013), (2014, 2025)]   # Grenzen inklusiv
```

Die erste Dekade (1992–2001) umfasst 10 Jahre, die beiden folgenden (2002–2013 und
2014–2025) je 12 Jahre (10+12+12=34) — bewusst ungleich lang, damit die Fensterlänge
1992–2025 (34 Jahre) ohne Restjahr in genau drei Dekaden aufgeht.
Ergebnis: `data/interim/trend/decade_stats.parquet` (9 Zeilen = 3 Kennzahlen ×
3 Dekaden).

### GEV-Spezifikation

`fit_gev_nonstationary()` fittet zwei generalisierte Extremwertverteilungen (GEV) per
Maximum-Likelihood (`scipy.optimize.minimize`, Nelder-Mead) an die nationale
`index_deficit`-Zeitreihe (Variante `primary`, 34 Werte, Fenster 1992–2025):

- **stationär**: `GEV(μ, σ, ξ)`, 3 Parameter.
- **nicht-stationär**: `GEV(μ(t), σ, ξ)` mit `μ(t) = μ0 + μ1·t`, `t = 0..33`
  (Jahresindex ab 1992), `σ`/`ξ` konstant über die Zeit — 4 Parameter. `μ1` ist der
  Trendkoeffizient im Lageparameter.

Beide werden mit gemeinsamen, aus den Daten hergeleiteten Startwerten initialisiert
(Momentenschätzer: `σ₀ = std·√6/π`, `μ₀ = mean − Euler-Mascheroni-Konstante·σ₀`,
`ξ₀ = 0,1`). Der **Likelihood-Ratio-Test** prüft, ob die nicht-stationäre Variante
signifikant besser passt als die stationäre: `LR = 2·(ll_ns − ll_s)` (auf 0 geklemmt,
falls die nicht-stationäre Optimierung numerisch schlechter abschneidet als die
stationäre), `p = 1 − χ²(df=1).cdf(LR)` (ein Freiheitsgrad, da `μ1` der einzige
zusätzliche Parameter ist).

**ξ-Bound-Problematik:** Bei nur 34 Jahreswerten ist der GEV-Formparameter `ξ`
numerisch fragil — ein unrestringierter Fit kann in physikalisch unplausible Bereiche
laufen. `fit_gev_nonstationary` wird deshalb **zweimal** aufgerufen: einmal mit
`xi_bound=0.5` (Default; `|ξ|` wird über eine Penalty in der Zielfunktion auf `[-0,5,
0,5]` beschränkt — ein für Abflussextreme literaturüblicher, konservativer Bereich)
und einmal mit `xi_bound=None` (unrestringiert). Ergebnis für `index_deficit`/
`primary`: `ξ_bounded = 0,500` (exakt am Rand der Schranke — ein Hinweis, dass die
Schranke selbst die Schätzung trägt, nicht die Daten) gegenüber `ξ_free = 1,049`
(deutlich außerhalb des plausiblen Bereichs). **Der LR-Test-p-Wert ist zwischen beiden
Parametrisierungen praktisch identisch** (0,234 bounded / 0,236 free) — die
Trend-Frage ist robust gegenüber der ξ-Behandlung. **Die
Wiederkehrintervall-Punktschätzung (`return_period_shift`, RP von `index_deficit`
unter `μ(t)` am Fit-Anfang vs. -Ende) ist es dagegen nicht**: 34,8/31,9 Jahre
(bounded) gegenüber 12,5/12,2 Jahren (free) für Wasserjahr 2018 — ein Faktor ~2,7
zwischen den Parametrisierungen. Konsequenz für die Ergebnisinterpretation: der
LR-Test-Befund (nicht signifikant, p≈0,23) ist belastbar, die
RP-Punktschätzung ist es bei n=34 nicht — siehe `docs/ergebnisse-phase4.md`,
Abschnitt 5, für die vollständige Einordnung. Als verteilungsfreie Referenz dient
zusätzlich `empirical_weibull_rp()` (Weibull-Plotting-Position, `RP = (n+1)/r` mit `r`
= Rang des Zielwerts in absteigender Sortierung) — unabhängig vom GEV-Fit und robust,
aber nur für Werte innerhalb der beobachteten Spanne aussagekräftig.

Ergebnis je Zielwert (`GEV_TARGET_YEAR = 2018`, `index_deficit`-Wert dieses Jahres):
`data/interim/trend/gev_deficit.parquet` (1 Zeile, Spalten für beide
Parametrisierungen: `xi`/`mu1`/`p_value`/`rp_start`/`rp_end` bounded,
`xi_free`/`mu1_free`/`p_value_free`/`rp_start_free`/`rp_end_free` free, plus
`rp_empirical`).

## Sensitivitätsanalysen

`uv run python scripts/sensitivity.py` orchestriert zwei Familien von
Sensitivitätsläufen. Die erste, teure Familie (metrics wird neu gerechnet) prüft
Referenzperiode und Ereignis-Pooling; die zweite, billige Familie (nur das Screening
läuft neu) prüft die Homogenitäts-Flags und ist per `--flags-only` einzeln aufrufbar
(Abschnitt „Flags-Sensitivität" unten).

Die drei metrics-basierten Läufe laufen end-to-end
(`niedrigwasser metrics --out-suffix X` → `niedrigwasser aggregate --metrics-suffix X --out-suffix X` →
`niedrigwasser trend --agg-suffix X`, jeweils via eigenem `interim/<stage>-X/`-Ordner, ohne
DB/CSV-Export) und vergleichen ihre nationalen Trends (Variante `primary`, Fenster
1992–2025) mit dem Hauptlauf:

- **refwmo**: Referenzperiode WMO-Standard 1991–2020 statt 1992–2011 (`--ref-start 1991
  --ref-end 2020`).
- **pool3** / **pool7**: Inter-Event-Kriterium 3 bzw. 7 Tage statt 5
  (`--inter-event 3` / `7`).

Ergebnistabelle (`out/sensitivity.csv`):

| Lauf   | index_days              | index_deficit            | index_ssi                 |
|--------|--------------------------|---------------------------|----------------------------|
| main   | increasing, p=0,0013, Sen=+0,853  | increasing, p=0,0025, Sen=+0,0452 | decreasing, p=0,0365, Sen=−0,0310 |
| refwmo | increasing, p=0,0046, Sen=+0,492  | increasing, p=0,0042, Sen=+0,0260 | decreasing, p=0,0393, Sen=−0,0288 |
| pool3  | increasing, p=0,0013, Sen=+0,853  | increasing, p=0,0025, Sen=+0,0452 | decreasing, p=0,0365, Sen=−0,0310 |
| pool7  | increasing, p=0,0013, Sen=+0,853  | increasing, p=0,0025, Sen=+0,0452 | decreasing, p=0,0365, Sen=−0,0310 |

**Vorzeichen-Stabilität: gegeben.** Alle drei Metriken bleiben über alle Läufe hinweg
signifikant (p < 0,05) und behalten ihre Trendrichtung (`index_days`/`index_deficit`
increasing, `index_ssi` decreasing) — kein Vorzeichenwechsel, das Kernkriterium der Spezifikation ist
erfüllt.

**Einordnung:**
- **pool3/pool7 sind erwartungsgemäß identisch zum Hauptlauf**: Das Inter-Event-Kriterium
  beeinflusst laut Definition (Abschnitt „Schwellenwert und Kennzahlen") nur `max_spell`
  (Spannweite des gepoolten Ereignisses); `days_below`, `deficit_volume_m3`, `nm7q` und
  `ssi` — und damit alle drei hier verglichenen nationalen Indizes — werden ungepoolt
  berechnet und bleiben vom Pooling-Parameter unberührt. Die Pooling-Sensitivität ist
  damit für die nationalen Trends strukturell bestätigt, nicht bloß numerisch zufällig
  gleich. **Das bedeutet aber auch: Die drei nationalen Indizes können die
  Pooling-Sensitivität per Konstruktion gar nicht prüfen** — dafür braucht es eine Metrik,
  auf die das Inter-Event-Kriterium tatsächlich wirkt (siehe nächster Abschnitt).

### Stations-`max_spell`-Sensitivität (Pooling wirkt hier tatsächlich)

`max_spell` ist die einzige Kennzahl, die vom Inter-Event-Kriterium beeinflusst wird.
Für jede Station mit ≥ 25 Jahren im Fenster 1992–2025 (identisches Kriterium wie die
Stations-Trends in `out/station_trends.csv`) wird TFPW-MK + Sen-Slope auf der
`max_spell`-Zeitreihe gerechnet; verglichen werden der Anteil Stationen mit signifikant
(p < 0,05) steigendem `max_spell` und die Median-Sen-Slope, je Lauf main/pool3/pool7:

| Lauf  | Anteil signifikant steigend | Median-Sen-Slope |
|-------|------------------------------|-------------------|
| main  | 61,3 %                       | 0,556             |
| pool3 | 63,2 %                       | 0,500             |
| pool7 | 61,8 %                       | 0,615             |

**Robust.** Die Anteile liegen für alle drei Inter-Event-Kriterien (3/5/7 Tage) in
derselben Größenordnung (61–63 %), ebenso die Median-Sen-Slopes (0,5–0,62) — keine
Verschiebung, die auf eine Pooling-Abhängigkeit der Kernaussage hindeuten würde. Zeilen
in `out/sensitivity.csv`: `metric` = `station_max_spell_share_increasing` /
`station_max_spell_median_sen` (Wert jeweils in `sens_slope`, `trend`/`p_value` leer —
es sind aggregierte Kennzahlen über alle Stationen, kein einzelner MK-Test).
- **refwmo zeigt eine niedrigere Sen-Slope bei gleichbleibender Signifikanz und
  Richtung.** Das ist plausibel und kein Alarmsignal: Die WMO-Referenzperiode 1991–2020
  schließt die niedrigwasserreichen 2010er/2020er-Jahre in die Schwellenwertbildung (Q95,
  MNQ) mit ein, wodurch die Schwellen selbst niedriger ausfallen als bei der festen
  Referenz 1992–2011. Niedrigere absolute Schwellen sind hier also erwartet und sagen
  nichts über die Trendrichtung aus — relevant für die Robustheit der Kernaussage ist
  ausschließlich, dass Vorzeichen und Signifikanz der Trends stabil bleiben, nicht das
  absolute Niveau der Kennzahlen.

### Flags-Sensitivität (`flagslax` / `flagsstrict`)

**Motivation.** Die Homogenitäts-Flags in `config/station_flags.csv` (205 Einträge: 88
`reservoir`, 57 `transfer`, 48 `mining`, 12 `erosion`) entscheiden allein darüber,
welche Station als naturnah gilt — und damit über die gesamte `natural`-Variante. Sie
waren bis dahin der größte ungetestete Hebel der Analyse: für Referenzperiode und
Pooling gab es Sensitivitätsläufe, für die Flags keinen. Die beiden folgenden Läufe
klammern die Flags-Entscheidung von beiden Seiten ein.

**Konstruktion.** Beide Läufe rechnen `metrics` **nicht** neu — Flags beeinflussen
ausschließlich `is_near_natural` im Screening, nicht die Stations-Kennzahlen. Die Kette
je Lauf ist deshalb `niedrigwasser screen --flags F --out-suffix X [--exclude-flags …]` →
`niedrigwasser aggregate --screen-suffix X --out-suffix X` → `niedrigwasser trend --agg-suffix X`
(`aggregate` liest die Kennzahlen aus dem Hauptlauf `interim/metrics/`).

- **`flagslax`** (laxer, größeres Subset): Die Flags-CSV wird deterministisch aus
  `config/station_flags.csv` erzeugt, indem alle Zeilen mit `note`-Präfix `unsicher:`
  entfernt werden (205 → 175 Zeilen, 30 entfernt; Ablage
  `data/interim/sensitivity/station_flags_lax.csv`, reine Funktion `lax_flags()` in
  `scripts/sensitivity.py`). Unsichere Flags gelten damit als nicht gesetzt.
  Ausschlusslogik unverändert (`reservoir`/`transfer`/`mining`).
- **`flagsstrict`** (strikter, kleineres Subset): Original-CSV, aber
  `--exclude-flags reservoir,transfer,mining,erosion` — auch das sonst nur hinweisende
  `erosion`-Flag schließt hier aus.

**Warum nur die Variante `natural` verglichen wird.** Die `primary`-Variante wird in der
`aggregate`-Stage mit `natural_only=False` gebildet und ist damit **per Konstruktion**
flags-unabhängig; nur `natural` (und `allsinks_natural`) hängen an `is_near_natural`.
Der Vergleich in `out/sensitivity_flags.csv` läuft deshalb ausschließlich auf `natural`
(Spalte `variant`). Der Orchestrator verifiziert die Konstruktionsaussage am echten
Output: `check_primary_identity()` prüft, dass `national_index_primary.parquet` beider
Flags-Läufe identisch zum Hauptlauf ist (im Lauf vom 2026-08-25 bestätigt, je 35 Zeilen
identisch). Zusätzlich prüft der Lauf die Plausibilität der Subset-Größen
(`flagslax` > `main` > `flagsstrict`) und die Vorzeichen-Stabilität analog
`check_sign_stability` — Exit 1 bei Verletzung.

Ergebnisse und Einordnung: `docs/ergebnisse-phase4.md`, Abschnitt 6.

## Phase 5: Darstellung

`uv run niedrigwasser render` (`src/niedrigwasser/stages/render.py`, Kernfunktion `daily_below_share`
in `src/niedrigwasser/daily_share.py`) erzeugt aus den Phase-1/3-Ergebnissen eine tagesgenaue
Heatmap-Datenbasis, zwei explorative PNG-Grafiken (`out/figures/`) und den Datenexport
für die interaktive Ergebnisseite (`site/data.json`, optional eingebettet in
`site/index.html`).

### Heatmap-Kennzahl `share`

Für jeden Kalendertag `t` eines Wasserjahres wird der flächengewichtete Anteil des
Stationsnetzes berechnet, der an diesem Tag unter dem stationseigenen Q95 liegt:

```
share(t) = Σ w_i · 1(q_i(t) < q95_i) / Σ w_i
```

Summiert wird über das **primary-Stationsset** (dieselbe Auswahl wie in der
`aggregate`-Stage: screening-überlebende, nicht-verschachtelte Stationen,
`select_index_stations(..., include_nested=False, natural_only=False)`, siehe
„Nationale Aggregation" oben) mit `w_i = a_incremental` (inkrementelle
Einzugsgebietsfläche). In den Nenner geht an Tag `t` **nur** ein, wer an diesem Tag
tatsächlich einen nicht-null Abflusswert liefert — Zähler und Nenner werden pro Tag neu
über die tatsächlich meldenden Stationen gebildet (`daily_below_share`, Join auf
`q.is_not_null()` vor der Gewichtung). Diese tägliche Renormierung ist bewusst und nicht
optional: ohne sie würde ein Ausfall/eine Lücke bei einer einzelnen Station den
Nenner künstlich konstant halten und den Anteilswert verzerren (Scheinausschlag nach
unten, weil eine fehlende „unter Schwelle"-Meldung wie eine „über Schwelle"-Meldung
gezählt würde). Zusätzlich wird `share` nur für (Station, Wasserjahr)-Kombinationen aus
`usable_years` (Phase-1-Screening) berücksichtigt — dieselbe Filterlogik wie in der
`metrics`-Stage.

Die Zahl der an einem Tag beitragenden Stationen (`n_stations`) schwankt tagesgenau
zwischen **185 und 208** (verifiziert gegen `data/interim/render/daily_share.parquet`,
12.714 Zeilen über 35 Wasserjahre × ≤365 Tage) — die Site zeigt `n_stations` deshalb pro
Zelle im Tooltip, statt eine irreführende konstante Netzgröße zu suggerieren
(siehe unten).

### Schalttags-Faltung (doy 366 → 365)

Das Wasserjahr beginnt am 1. November; in einem Schaltjahr fällt der 29. Februar in das
laufende Wasserjahr und erzeugt Tag 366. Damit die Heatmap-Matrix für alle 35
Wasserjahre rechteckig (365 Spalten) bleibt, wird Tag 366 auf Tag 365 gefaltet:

```
doy' = min(doy, 365)
share(doy'=365)      = max(share(365), share(366))
n_stations(doy'=365) = max(n_stations(365), n_stations(366))
```

(`daily_below_share`: `pl.min_horizontal(doy, 365)` gefolgt von einem zweiten
`group_by(water_year, doy).agg(max, max)`.) Die Wahl fällt bewusst auf **Maximum**, nicht
Mittelwert oder Summe: `share` ist ein Anteil zwischen 0 und 1, ein Mittel zweier
Anteilstage würde den Wert eines einzelnen Tages künstlich glätten und den in
Schaltjahren real erreichten Extremwert unterschätzen. Da beide gefalteten Tage
(30./31. Oktober) meteorologisch benachbart sind, ist die Verzerrung durch die Faltung
selbst gering; das Frontend beschriftet die gefaltete Spalte in Schalt-Wasserjahren
entsprechend als „30.–31. Okt." statt eines einzelnen Datums.

### Site-Datenexport und `--embed`-Build

`niedrigwasser render` schreibt `site/data.json` (Meta, Heatmap-Matrix inkl. `n_stations`,
nationale Zeitreihen `primary`/`natural`, MK-Trendergebnisse, Dekaden-Histogramm/-Stats,
Stationsliste) — alle Zahlen unverändert aus den Phase-1–4-Parquets/CSVs übernommen,
keine im Frontend neu berechneten Statistiken. `--embed` (Default aus, `cli.py`) bettet
diese JSON-Datei anschließend über `src/niedrigwasser/site_embed.py` in `site/template.html`
(Marker `/*__DATA__*/` in einem `<script type="application/json">`-Block) ein und
schreibt `site/index.html` — self-contained, ohne `fetch`, funktioniert per
`file://`-Doppelklick. `site/template.html` ist die gepflegte Quelle;
`site/index.html` ist generiert und wird mitversioniert. Steuerbar über
`--site-data`/`--site-template`/`--site-html` (Pfad-Overrides, z. B. für Tests).

**Reproduzierbarkeit des Builds.** Das einzige nicht-datenabhängige Feld des Exports
ist `meta.generated`. Es kommt deshalb nicht aus der Wallclock, sondern aus dem
Maximum der Modifikationszeiten der von `render` *gelesenen* Artefakte (DuckDB,
Screening-/Metrics-/Aggregat-/Trend-Parquets, `out/station_trends.csv`, die beiden
Config-CSVs sowie `site/template.html` und `site/geo.json` als Quellen des
`--embed`-Builds) — die eigenen Ausgaben der Stufe sind bewusst ausgenommen, sonst
würde sich der Wert bei jedem Lauf selbst verstellen. Ist `SOURCE_DATE_EPOCH` gesetzt
(Standard von reproducible-builds.org), gewinnt dieser Wert; das ist der Weg für
CI- und Repro-Builds. Ergebnis: zwei aufeinanderfolgende `niedrigwasser render --embed` auf
demselben Rechner und unangetastetem Working Tree erzeugen bit-identische
`site/data.json` und `site/index.html`; ein Diff dort belegt dann eine echte
Datenänderung.

Die Grenze dieser Zusage ist git selbst: Modifikationszeiten werden nicht
versioniert. Nach `clone`, Branch-Wechsel oder `stash pop` sind die mtimes der
Eingaben neu, und der nächste Render schreibt einen reinen `meta.generated`-Diff,
obwohl sich keine Zahl geändert hat — dieser Diff ist zu verwerfen oder durch ein
explizit gesetztes `SOURCE_DATE_EPOCH` zu vermeiden. Ein maschinenübergreifend
bit-gleicher Build ist also nur mit `SOURCE_DATE_EPOCH` zu haben; der mtime-Fallback
löst den Alltagsfall (wiederholte Läufe auf demselben Arbeitsstand), nicht den
Cross-Machine-Fall. (Implementierung: `generated_timestamp` in
`src/niedrigwasser/stages/render.py`.)

### Bewusste Anti-Pattern-Entscheidungen

Vorgabe der Spezifikation: Zwei Darstellungsformen wurden bewusst **nicht**
umgesetzt, obwohl sie in Niedrigwasser-/Hydrologie-Berichten verbreitet sind:

- **Keine Trendgerade auf der Anomalie-Linie.** Bei Abfluss-Kennzahlen übersteigt die
  interannuelle Varianz (siehe die Jahr-für-Jahr-Sprünge in `out/national_index.csv`,
  z. B. 2018→2019→2020: 93,5 → 89,4 → 50,8 Tage) das eigentliche Trendsignal so weit,
  dass eine eingezeichnete Regressionsgerade auf einer verrauschten Zeitreihe optisch
  suggeriert, der Trend sei mit bloßem Auge sichtbar — ist er nicht, er ist nur mit dem
  TFPW-MK-Test statistisch nachweisbar. Die Site zeigt die nationale Zeitreihe deshalb
  als reine Säulen ohne eingezeichnete Gerade; das MK-Ergebnis (Richtung, p-Wert,
  Sen-Slope) steht daneben als separate Textkarte, explizit als Testergebnis
  gekennzeichnet statt optisch in die Rohdaten hineinmontiert.
- **Kein CUSUM/keine Doppelsummenkurve.** Kumulative Summenkurven sind für die
  *Regimeshift-Detektion in der Analyse* ein legitimes Werkzeug, als *Außendarstellung*
  aber irreführend: Kumulation erzeugt aus praktisch jedem Rauschen einen optisch
  überzeugenden Knick, den Betrachter ohne statistisches Vorwissen als „hier hat sich
  klar etwas verändert" lesen, ohne dass ein Signifikanztest dahintersteht. Diese
  Analyse verwendet für die Schaltjahr-/Regimefrage stattdessen den dokumentierten
  TFPW-MK-Test (Autokorrelation-robust) und den Dekadenvergleich (Abschnitt
  „Dekadenvergleich" oben) — beide mit explizit ausgewiesener statistischer Aussage
  (p-Wert bzw. Verteilungskennzahlen je Dekade), nicht mit einer optisch suggestiven,
  aber statistisch unbewerteten Kurvenform.

Beide Entscheidungen sind Vorgabe der Spezifikation (nicht nachträglich improvisiert)
und wurden von Beginn an als Ausschlusskriterium geführt.

