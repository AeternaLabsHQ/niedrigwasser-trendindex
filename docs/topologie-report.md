# Topologie-Report — Stationsgraph NIWIS-Abflusspegel

*Stand: 2026-08-25 (Phase 1, Ingest + Topologie). Die Befunde einer internen
Prüfung sind eingearbeitet — siehe Änderungshistorie am Ende.*

## Ausgangslage

Voll-Ingest von NIWIS lieferte **361 Abfluss-Stationen** (695 Messstellen insgesamt, davon
361 mit `messgroesse` Abfluss) und **4.699.859 Tageswerte** über den Zeitraum
**1991-01-01 bis 2026-08-23**. Die Abweichung von der Spezifikations-Zahl "356 Pegel" ist bekannt
(API liefert 361) und wird nicht gefiltert.

Ziel: `downstream_id` für alle Stationen so setzen, dass ein gültiger Stationsgraph
entsteht (keine Zyklen, keine Verweise auf unbekannte Stationen) und
`A_incremental(i) = A(i) − Σ A(j)` über direkte Oberlieger j für jede Station ≥ 0 ist.

## Methode

1. **Auto-Kette pro Fluss** (`chain_within_river`): Stationen mit identischem,
   normalisiertem `river`-Namen werden aufsteigend nach `catchment_area` (EZG) sortiert
   und linear verkettet (kleinstes EZG → nächstgrößeres). Begründung: EZG wächst
   flussabwärts streng monoton, unabhängig von uneinheitlicher `river_km`-Zählrichtung
   je Bundesland. **Guard (Fix-Runde 1, F3/F7):** eine Kante wird nur gesetzt, wenn
     (a) `river` bei beiden Stationen nicht `null` ist, und
     (b) die Luftlinie (Haversine über `lat`/`lon`) zwischen den beiden Stationen
         < 150 km beträgt.
   Ohne diesen Guard verkettet ein gleicher Flussname automatisch auch zwei physisch
   unterschiedliche Gewässer (z. B. mehrere "Schwarzbach", "Kinzig", "Nahe", "Bode",
   "Vils" in Deutschland) — das erzeugte in Fix-Runde 1 fünf nachweislich falsche
   Auto-Kanten (siehe unten).
2. **Manuelle Overrides** (`config/topology_overrides.csv`, `apply_overrides`): für jede
   echte Mündung, deren Empfängerfluss ebenfalls einen Pegel im Datensatz hat, wird der
   Mündungspegel manuell an die/den passende(n) Station(en) des Empfängerflusses
   angeschlossen — ebenso zur gezielten Trennung falscher Auto-Kanten (Namenskollisionen,
   die der 150-km-Guard nicht erfasst, weil die beiden Stationen zufällig < 150 km
   auseinanderliegen). Auswahlkriterium: nächster Pegel am Empfängerfluss flussabwärts
   der Mündung, anhand bekannter Geographie (Mündungsort, Fluss-km, Koordinaten)
   bestimmt und iterativ gegen `build_topology`/`incremental_areas` validiert.
3. **Validierung** (`build_topology`): `validate_topology` (Zyklen, unbekannte IDs,
   Duplikate) + `incremental_areas` (A_incremental ≥ 0, sonst `TopologyError` mit
   Liste der Verletzer). Iteriert bis fehlerfrei. Seit Fix-Runde 1 bricht
   `niedrigwasser ingest` bei einem `TopologyError` hart ab (kein stilles Weiterlaufen mit
   leerem `downstream_id`) — siehe `docs/methods.md`.

## Fünf falsche Auto-Kanten durch Flussnamens-Kollisionen (F3)

Vor Fix-Runde 1 verkettete `chain_within_river` fälschlich folgende Stationspaare
(gleicher Flussname, unterschiedliches physisches Gewässer):

| Auto-Kante (falsch) | Distanz | Korrektur |
|---|---|---|
| Nahe/Schleusingen (TH) → Nahe/Oberstein (RP) | 258,6 km | > 150-km-Guard bricht automatisch; Schleusingen bleibt Senke (kein sinnvoller Empfänger identifiziert) |
| Kinzig/Steinau (HE) → Kinzig/Schwaibach (BW) | 238,5 km | > 150-km-Guard bricht automatisch; Steinau bleibt Senke (kein Main-Pegel unterhalb Hanau im Datensatz) |
| Schwarzbach/Eschelbronn (BW) → Schwarzbach/Einöd (SL) | 110,5 km | < 150 km, Guard greift nicht → per Override manuell getrennt: Eschelbronn → Neckar/Rockenau, Einöd → Blies/Reinheim |
| Vils/Dietldorf (Naab-System) → Vils/Grafenmühle (Donau-direkt, Vilshofen) | 109,6 km | < 150 km, Guard greift nicht → per Override manuell getrennt; kein Naab-Pegel unterhalb Kallmünz im Datensatz, Dietldorf bleibt Senke |
| Bode/Bleicherode (TH, Wipper-System) → Bode/Hadmersleben (ST, Harz/Saale-System) | 79,5 km | < 150 km, Guard greift nicht → per Override manuell getrennt: Bleicherode → Wipper/Hachelbich |

Zwei der fünf Fälle (Nahe, Kinzig) liegen zufällig über der 150-km-Schwelle und werden
automatisch durch den Guard verhindert. Die anderen drei (Schwarzbach, Vils, Bode)
liegen darunter und mussten explizit per Override getrennt werden — der Distanz-Guard
allein ist also eine notwendige, aber keine hinreichende Absicherung gegen
Namenskollisionen bei räumlich nahen, aber unterschiedlichen Gewässern.

**Bekannte Nebenwirkung des Guards:** Beuron und Donauwörth (beide echte Donau-Pegel im
dünn beguagten Donau-Oberlauf) liegen 153,5 km auseinander und wurden vom Guard
fälschlich getrennt — mit Override wieder verbunden (`config/topology_overrides.csv`).

## Iterationsergebnis (nach Fix-Runde 1)

- **65 Overrides** in `config/topology_overrides.csv`, jede mit Mündungs-Begründung.
- **191 Senken** (kein `downstream_id`), **170 Stationen** mit gesetztem `downstream_id`.
- `build_topology` läuft ohne `TopologyError` durch; `A_incremental ≥ 0` überall erfüllt.

### Korrekturen gegenüber der ursprünglichen Fassung (F2, F6)

Acht der in der ersten Fassung verworfenen Overrides waren nicht grundsätzlich falsch,
sondern hatten einen falsch gewählten Zielpegel (zu weit oberhalb der echten Mündung).
Mit korrigiertem Ziel funktionieren sie (empirisch gegen `incremental_areas` geprüft):

| Zubringer | Falsches Ziel (verworfen) | Korrektes Ziel |
|---|---|---|
| Saale/Calbe | Elbe/Magdeburg Strombrücke | Elbe/**Barby** |
| Weiße Elster/Kleindalzig | Saale/Bernburg UP | Saale/**Halle Trotha UP** |
| Fränkische Saale/Wolfsmünster | Main/Würzburg | Main/**Raunheim** |
| Spree/Sophienwerder | Untere Havel/Havelberg | Untere Havel/**Ketzin** |
| Zwickauer Mulde/Wechselburg 1 | (fehlte komplett) | Vereinigte Mulde/**Golzern 1** |
| Lenne/Altena | (Senke, kein Ruhr-Pegel unterhalb Hagen) | Rhein/**Duisburg-Ruhrort** (direkt, ohne Ruhr-Zwischenpegel) |
| Großer Graben/Oschersleben | (Senke, unklarer Empfänger) | Ohre/**Wolmirstedt** |
| Thyra/Stolberg | (Senke, Kombination mit Zorge negativ) | Helme/**Sundhausen** (separat von Zorge) |

Zusätzlich korrigiert (F6): **Regen** mündet bei **Regensburg**, nicht Deggendorf — Ziel
korrigiert von Donau/Hofkirchen auf Donau/**Oberndorf**. Die No-op-Zeile
"Saar (Pegel Perl)" wurde entfernt (Perl ist ein **Mosel**-Pegel, keine Saar-Station);
der echte Saar→Mosel-Anschluss ist jetzt Fremersdorf→Cochem. Die Ruhr/Villigst-Notiz
wurde korrigiert (Villigst liegt ca. 50 km oberhalb der eigentlichen Ruhr-Mündung bei
Duisburg, nicht "an der Mündung").

**Ein Fall bleibt ein echter Datenkonflikt und damit bewusst Senke:** Zorge (Nordhausen,
304 km²) kann nicht gleichzeitig mit Thyra (32 km²) an Helme/Sundhausen (201 km²)
angeschlossen werden — schon Zorge allein übersteigt Sundhausens EZG. Sundhausen liegt
vermutlich oberhalb der Zorge-Mündung (Roßla) auf der Helme; ohne weiteren Helme-Pegel
unterhalb Roßla im Datensatz bleibt Zorge Senke.

**Ein Fall aus der Review-Vorgabe konnte nicht wie erwartet bestätigt werden:** Göltzsch
(Mylau, 156 km²) → Weiße Elster/Kleindalzig ergibt weiterhin eine leicht negative
Fläche (−23 km²), auch nachdem Kleindalzig selbst auf das korrigierte Ziel (Halle
Trotha UP) umgestellt wurde — das ist ein unabhängiges, oberhalb liegendes
Kapazitätsproblem an Kleindalzig selbst (Zeitz + Pleiße allein schöpfen die Fläche
schon fast aus). Göltzsch bleibt daher Senke; das Global-Constraint
"A_incremental ≥ 0, niemals clampen" hat Vorrang vor dem Review-Hinweis.

### Abgedeckte Flusssysteme (Auswahl)

Rhein (Main, Mosel, Neckar, Nahe, Sieg, Ahr, Wupper, Erft, Ruhr, Lippe, Kinzig/BW, Lahn,
Lenne direkt), Mosel (Saar, Blies, Prims), Neckar (Enz, Kocher, Schwarzbach/BW), Main
(Tauber, Fränkische Saale), Elbe (Havel, Vereinigte Mulde, Schwarze Elster, Ohre), Saale
(Unstrut, Bode, Weiße Elster, westl. Fuhne, Ilm/TH), Unstrut (Gera, Helbe, Wipper/TH,
Helme, Bode/Bleicherode), Helme (Thyra), Vereinigte Mulde (Zwickauer Mulde, Freiberger
Mulde), Zwickauer Mulde (Chemnitz-Fluss), Zschopau (Schwarze Pockau), Chemnitz
(Würschnitz), Weiße Elster (Pleiße), Oder (Lausitzer Neiße), Havel (Nuthe, Plane, Spree),
Weser (Fulda, Werra, Aller, Werre), Donau (Regen, Brenz, Günz, Iller, Wörnitz, Beuron),
Naab (Haidenaab, Waldnaab), Salzach (Saalach), Blies (Schwarzbach/SL).

## Plausibilisierung der Flächensumme

```
Σ a_incremental = 572.694 km²
```

Da sich `A_incremental` bei einer korrekt aufgebauten Baumstruktur zu den Flächen der
jeweiligen Wurzelknoten (= Senken) teleskopiert, entspricht die Summe exakt der Summe
der `catchment_area`-Rohwerte der 191 Senken-Stationen.

**Das liegt weiterhin über der Fläche Deutschlands (357.600 km²).** Aufschlüsselung der
191 Senken in drei Kategorien:

### (i) Echte Basin-Auslässe — 5 Stationen, 477.634 km²

Die Hauptstromgewässer ohne deutschen Empfänger im Datensatz:

| Station | Fluss | EZG (km²) |
|---|---|---|
| Rees | Rhein | 159.300 |
| Wittenberge | Elbe | 123.532 |
| Hohensaaten Finow | Oder | 109.564 |
| Hofkirchen | Donau | 47.518 |
| Intschede | Weser | 37.720 |

Diese fünf EZG-Werte enthalten planmäßig erhebliche **Auslandsanteile** (Schweiz,
Österreich, Frankreich, Tschechien, Polen) — das ist der dominante Grund, warum die
Gesamtsumme über der deutschen Landesfläche liegt, und ist laut Aufgabenstellung
erwartet/akzeptiert.

### (ii) Legitim eigenständige Systeme — 19 Stationen, 35.927 km²

Sinken, deren Fläche **nicht** bereits in einem der fünf Basin-Auslässe enthalten ist,
weil sie entweder ein eigenes Gewässersystem ohne Anschluss an die fünf Hauptströme
bilden, oder deren Mündung nachweislich *unterhalb* des jeweils letzten erfassten
Pegels der Empfängerkette liegt (ihre Fläche also additiv, nicht doppelt gezählt ist):

- **Eigene Meeres-/Grenzabflüsse:** Ems (4.851, Nordsee direkt), Rur (2.135, mündet in
  die Maas/Niederlande, nicht ins deutsche Rhein-Netz)
- **Bodensee-direkt** (vor jedem deutschen Rhein-Pegel): Schussen (782), Argen (648),
  Obere Argen (104)
- **Ostsee-/Nordsee-Küstensysteme ohne Anschluss an einen der fünf Ströme:** Uecker
  (1.431), Tollense (1.409, mündet in die ungegaugte Peene), Warnow (788), Treene
  (481), Soholmer Au (342)
- **Inn-System, Mündung unterhalb des einzigen Inn-Pegels (Wasserburg) bzw. unterhalb
  Hofkirchen:** Inn selbst (11.960 — mündet bei Passau, unterhalb Hofkirchen, daher
  nicht in dessen EZG enthalten), Salzach (6.655, mündet bei Burghausen unterhalb
  Wasserburg), Rott (529), Isen (548), Traun/Bayern (376) — alle münden unterhalb des
  Wasserburg-Pegels in den Inn
- **Donau-direkt bei Passau, unterhalb Hofkirchen:** Ilz (364), Wolfsteiner Ohe (371),
  Vils/Vilshofen (1.440)
- **Elbe-direkt, unterhalb Wittenberge:** Sude (713, mündet bei Boizenburg)

### (iii) Verbleibend verschachtelt/potenziell doppelt gezählt — 167 Stationen, 59.133 km²

Alle übrigen Senken. Der überwiegende Teil davon liegt hydrologisch **innerhalb** eines
bereits unter (i) gezählten Basin-Auslasses, kann aber mangels eigenem Pegel des
unmittelbaren Empfängers (v. a. Isar, Lech, Regnitz — keiner dieser drei Flüsse hat
einen NIWIS-Q-Pegel) nicht direkt angeschlossen werden. Beispiele: alle Isar-Zubringer
(Amper, Paar, Loisach, Ammer, Abens, Schmutter — Isar mündet oberhalb Hofkirchen in die
Donau), alle Regnitz-Zubringer (Pegnitz, Aisch, Schwabach, Bibert, Rodach, Haßlach —
Main-Mündung der Regnitz liegt oberhalb des Main-Pegels Raunheim), sowie diverse kleine
Berlin-Spree-Havel-Kanalzubringer (Müggelspree, Dahme, Teltowkanal, Buckau u. a. — Spree
selbst ist inzwischen an Havel/Ketzin angeschlossen, ihre eigenen Oberlieger aber nicht).

**Diese 167-Stationen-Bucket ist nicht abschließend einzeln geprüft** (das würde den
gleichen Rechercheaufwand wie der gesamte Override-Aufbau erfordern) — er enthält mit
hoher Sicherheit überwiegend echte Verschachtelung, kann aber vereinzelt noch weitere,
bislang nicht identifizierte eigenständige (additive) Kleinsysteme enthalten. Die
Kategorisierung (ii) vs. (iii) ist daher als **belastbare Untergrenze für (ii)**, nicht
als abschließende Wahrheit zu verstehen.

### Kategorisierung jetzt versioniert

Die vorstehende Drei-Kategorien-Einteilung existierte zunächst nur als Text in diesem
Report. Sie ist jetzt maschinenlesbar in `config/sink_categories.csv` (Spalten
`station_id,category,note`, `category ∈ {outlet, standalone, nested}`) versioniert;
`scripts/categorize_sinks.py --propose` erzeugt einen Heuristik-Erstentwurf (Distanz-
/Flächenverhältnis-Heuristik) und ohne `--propose` läuft nur der Konsistenz-Check
gegen `data/interim/topology/stations_topology.parquet` (alle Senken kategorisiert,
keine Nicht-Senke in der CSV, keine unbekannte `station_id`, Kategorie-Flächensummen).

Gegenüber der ursprünglichen (ii)/(iii)-Aufteilung oben wurden im Zuge dieser
Versionierung die bei einer internen Prüfung benannten Grenzfälle von (iii) nach
`standalone` umkategorisiert — Gewässer, deren Abfluss Deutschland ohne weiteren
Pegel verlässt oder die nachweislich unterhalb eines Basin-Auslasses münden, statt
routinemäßig in dessen Kategorie (i)-Fläche enthalten zu sein: Rur, Niers, Schwalm,
Wurm, Urft, Inde (alle Maas-System), Berkel, Issel, Bocholter Aa, Dinkel (alle
IJssel-System), Welse, Wriezener Alte Oder (beide Oder unterhalb Hohensaaten),
Salzwedeler Dumme, Karthane, Bolter Kanal (alle Elbe unterhalb Wittenberge) und
Seefelder Aach (Bodensee-direkt). Ergebnis: **5 outlet / 34 standalone / 152 nested**
(191 Senken gesamt), Flächensummen 477.634 / 41.950 / 53.110 km² (Σ weiterhin
572.694 km², konsistent mit obiger Plausibilisierung — die Umkategorisierung
verschiebt Fläche zwischen (ii)/standalone und (iii)/nested, ändert aber nicht die
Gesamtsumme). Details sind im internen Umsetzungsprotokoll dokumentiert.

#### Nachträgliche Web-Verifikation der drei offenen Grenzfälle (25.08.2026)

Drei dieser Umkategorisierungen waren zunächst nur plausibel begründet, nicht belegt
(in der Spezifikation als „web-unsicher" geführt). Sie sind jetzt gegen amtliche bzw.
enzyklopädische Quellen geprüft — **alle drei bestätigen `standalone`, keine Kategorie
musste geändert werden**, die Kernzahlen bleiben unverändert:

| Senke | Pegel des Basin-Auslasses | Mündung | Befund |
|---|---|---|---|
| Karthane (`DESM_DEBB5930500`, 285 km²) | Wittenberge, Elbe-km 453,9 (Undine/BfG) | über die Stepenitz bei Elbe-km 454,9 | rund 1 km **unterhalb** des Pegels → `standalone` |
| Bolter Kanal (`DESM_DEMV58110.0`, 3 km²) | Wittenberge, Elbe-km 453,9 | Müritz-Elde-Wasserstraße bei Dömitz, Elbe-km 504,1 | rund 50 km **unterhalb** → `standalone` |
| Wriezener Alte Oder (`DESM_DEBB6940000`, 1.084 km²) | Hohensaaten-Finow, Oder-km 664,95 | Abfluss in die Hohensaaten-Friedrichsthaler Wasserstraße, die die Oder erst bei Friedrichsthal/Westoder wieder erreicht | Pegel wird **umgangen** → `standalone` |

Quellen (abgerufen 25.08.2026): Undine/BfG, Pegel Wittenberge
(<https://undine.bafg.de/elbe/pegel/elbe_pegel_wittenberge.html>, „453,9 (unterhalb
Grenze D / CZ)"); dewiki „Karthane" (<https://dewiki.de/Lexikon/Karthane>, Mündung in
die Stepenitz am Stadtrand von Wittenberge, Stepenitz bei km 454,9 in die Elbe);
Wikivoyage „Müritz-Elde-Wasserstraße"
(<https://de.wikivoyage.org/wiki/M%C3%BCritz-Elde-Wasserstra%C3%9Fe>, MEW-km 0,0 in
Dömitz bei Elbe-km 504,1); dewiki „Alte Oder" (<https://dewiki.de/Lexikon/Alte_Oder>,
„Der Wasserablauf erfolgt jedoch in die Hohensaaten-Friedrichsthaler Wasserstraße");
Wikipedia „Pegel Hohensaaten-Finow"
(<https://de.wikipedia.org/wiki/Pegel_Hohensaaten-Finow>, Oder-km 664,95, Einzugsgebiet
109.564 km²).

Restunsicherheit bei der Wriezener Alten Oder: die Verifikation bestätigt die
**Kategorie** (`standalone` — der Pegel Hohensaaten-Finow wird über die
Hohensaaten-Friedrichsthaler Wasserstraße umgangen), sie löst aber die
**Flächenfrage** nicht. Das amtliche EZG des Pegels Hohensaaten-Finow (109.564 km²)
ist ein Gebietswert der Oder oberhalb des Pegels; ob die 1.084 km² der Wriezener
Alten Oder darin bereits enthalten sind, ist aus den herangezogenen Quellen nicht
zu entscheiden. Sind sie es, zählt diese Fläche im flächengewichteten Index doppelt
— rund 0,21 % der maximalen Gewichtungsmasse des primary-Sets, also in derselben
Größenordnung wie der Urft-/Wurm-/Inde-Doppelzähler (888 km², 0,17 %).
Ergebnisrelevanz vernachlässigbar, aber offen; beide Fälle sind als bekannte
Limitation in `docs/methods.md` dokumentiert (Abschnitt „Bekannte Restunschärfe:
`standalone`-Senken oberhalb eines anderen Pegels").

Restunsicherheit beim Bolter Kanal: die Müritz ist Wasserscheide zwischen Elde/Elbe
(nach Norden) und Havel/Spree (nach Osten), und die Quellenlage zur Fließrichtung im
Kanal selbst ist dünn. Der Befund oben stützt sich deshalb **allein** auf den
Elde-/MEW-Weg — der trägt für sich, ist aber der einzige Beleg. Ein Alternativweg über
die Havel würde die Kategorie **kippen**: die Havel erreicht die Elbe über den
Gnevsdorfer Vorfluter bei **Elbe-km 438**, also rund 16 km **oberhalb** des Pegels
Wittenberge (453,9); die Topologie dieses Repos bildet das selbst ab
(`Havelberg Stadt` → `downstream_id = Wittenberge`). Auf dem Havel-Weg wäre der Bolter
Kanal also `nested`, nicht `standalone`. Bei 3 km² Fläche hat das keine messbare Folge
für irgendeine Kennzahl — die Unsicherheit ist gewichtslos, aber nicht folgenlos.

*(Korrektur 25.08.2026: Hier stand zunächst, die Havel münde bei Elbe-km 522,9 und damit
ebenfalls unterhalb von Wittenberge — das war falsch, 522,9 ist Hitzacker. Der
Fallback-Beleg entfällt damit ersatzlos; der Hauptbefund über die MEW bleibt unberührt.)*

### Konsequenz für Phase 3 (national gewichtete Aggregation)

**Wichtig für die Weiterverarbeitung:** Bei der Berechnung der nationalen Gewichte
`w_i = A_incremental(i) / Σ A_incremental` dürfen die verschachtelten Senken aus (iii)
**nicht einfach zusätzlich zu ihrem umfassenden Unterlieger gezählt werden** — sie
stellen bereits im übergeordneten Basin-Auslass (Kategorie i) enthaltene Fläche dar,
und ihre isolierte Aufnahme in die Gewichtssumme würde denselben Grund/Boden doppelt
gewichten (das im Vorfeld befürchtete "Rhein zwölffach gewichten"-Szenario aus F4 ist
strukturell genau diese Doppelzählung, nur eben bei kleineren Teilflächen statt beim
Rhein selbst). Diese Fix-Runde behebt nur den in F4 beschriebenen akuten Bug
(TopologyError wurde verschluckt); die grundsätzliche Frage, wie mit Kategorie (iii)
bei der Gewichtsbildung umzugehen ist (ignorieren / anteilig zurechnen / gesondert
flaggen), ist eine **Entscheidung für Phase 3** und wird hier bewusst nur dokumentiert,
nicht vorweggenommen.

## Bekannte Unsicherheiten

- **`gkz` unzuverlässig** — Topologie wurde primär über Flussname + EZG + bekannte
  Geographie aufgebaut, nicht über `gkz`.
- **Mündungspositionen approximiert**: wo kein `river_km` vorlag (v. a. am Rhein),
  wurden bekannte Ortsnamen/Flusskilometer aus allgemeinem hydrologischem Wissen
  verwendet, nicht aus einer amtlichen Gewässerstationierung.
- **150-km-Guard ist eine notwendige, keine hinreichende Absicherung** gegen
  Flussnamens-Kollisionen (siehe oben, Schwarzbach/Vils/Bode lagen darunter und
  mussten manuell per Override getrennt werden). Bei künftigen Ingest-Läufen mit
  neuen/geänderten Stationen sollte die Senken-Liste erneut auf Namenskollisionen
  gesichtet werden.
- **NIWIS-EZG-Werte nicht immer streng stufenweise kumulativ** entlang eines Flusses
  (Lippe/Wesel-Befund) — Downstream-Kandidaten wurden deshalb iterativ gegen
  `build_topology` geprüft statt rein algorithmisch gewählt.
- **Kategorie (ii)/(iii)-Grenze ist eine belastbare Untergrenze für (ii)**, keine
  erschöpfende Einzelprüfung aller 186 verbliebenen Senken (siehe oben).

## Persistenz

- `downstream_id` in DuckDB `stations`-Tabelle aktualisiert (170 von 361 Stationen mit
  gesetztem `downstream_id`, 191 Senken mit `NULL`).
- Vollständiger topologischer Stand: `data/interim/topology/stations_topology.parquet`.

## Änderungshistorie

- **2026-08-25, Erstfassung:** 52 Overrides, 198 Senken, Σ a_incremental = 622.536 km².
- **2026-08-25, Fix-Runde 1** (Review-Findings F1–F7): 150-km-Distanz-Guard gegen
  Flussnamens-Kollisionen in `chain_within_river` (F3, F7); 8 fälschlich verworfene
  Overrides mit korrigiertem Zielpegel wieder aufgenommen (F2); drei fehlerhafte
  Notes/Zuordnungen korrigiert (F6); `niedrigwasser ingest` bricht bei `TopologyError` jetzt
  hart ab statt still weiterzulaufen (F4); `--limit` überspringt die Topologie-Stufe
  statt an Overrides-ValueError zu scheitern (F5). Ergebnis: 65 Overrides, 191 Senken,
  Σ a_incremental = 572.694 km² (Senken-Aufschlüsselung (i)/(ii)/(iii) neu ergänzt).
