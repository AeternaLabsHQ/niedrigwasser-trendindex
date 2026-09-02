# Homogenitäts-Recherche — Befüllungsvorschlag für `config/station_flags.csv`

*Recherche-Stand 2026-08-25, **Rev. 2** nach adversarialem Review („Übernahme mit Korrekturen").
Ergebnis: `docs/homogenitaet-flags-vorschlag.csv`.
Diese Datei ist ein **Vorschlag**; `config/station_flags.csv` wurde nicht verändert.*

> **Änderungen Rev. 2** (Details jeweils am Ort): Ruhr Meschede jetzt `reservoir` (meine
> GKZ-Herleitung in Rev. 1 war falsch, §5.1); Aller Rethem neu mit `reservoir`+`transfer`
> (Harzwasserwerke, blinder Fleck Niedersachsen); Emmer Schieder, Erft Bliesheim und
> Neckar Rockenau gestrichen; Fredersdorfer Fließ aus den Flags entfernt; Volme-Note
> korrigiert; Hohenbinde `transfer` ergänzt; Brigach Donaueschingen `transfer` ergänzt;
> `mining`-Mengenstandard und `transfer`-Fremdwasserschwelle als explizite Regeln
> aufgenommen; Vorschlag zur Nachschärfung der `erosion`-Definition in `methods.md`.

---

## 1. Auftrag und Zielgröße

Nach der Spezifikation und `docs/methods.md` sind
361 NIWIS-Pegel auf dominante anthropogene Steuerung zu prüfen und mit
`reservoir` / `transfer` / `mining` / `erosion` zu kennzeichnen. Naturnahes Subset =
Stationen ohne `reservoir`/`transfer`/`mining`; `erosion` ist reiner Hinweis.

Referenzsystematik ist das **UK Benchmark Network (UKBN2)**. Dessen Kernlogik wurde
übernommen: nicht „ist der Pegel unberührt?", sondern „**ist das Niedrigwasserregime
dieser Reihe über den Analysezeitraum homogen und klimagetrieben?**". UKBN2 schließt
konsequent alle großen regulierten Hauptstromgewässer aus — das ist hier ebenso
gehandhabt worden und erklärt einen erheblichen Teil der Flags.

Zielkorridor laut Spezifikation: grob 150–280 naturnahe Stationen. **Ergebnis: 236.**

---

## 2. Datenquellen

### 2.1 Primärquelle: `bemerkung` aus den NIWIS-Stammdaten

Systematisch ausgewertet wurden alle 361 Dateien `data/raw/niwis/stammdaten/<id>.json`,
Feld `bemerkung`. Verteilung:

| Kategorie | Stationen |
|---|---:|
| Feld leer (`null`) | 262 |
| Platzhalter `"0"` (inhaltsleer) | 16 |
| Substanzieller Text | 83 |
| davon: **Hinweis auf anthropogene Beeinflussung** (Talsperre/Speicher, Tagebau/Sümpfung, Überleitung/Beileitung, Stauhaltung/Wehr, Kläranlagenanteil, Kraftwerksbetrieb) | **42** |
| davon: reine Mess-/Datengüte (Verkrautung, Pegelumbau, Geschiebe, Vereisung, Sedimentation, „W erst ab …", „GlW 2010") | 38 |
| davon: sonstiger Kontext (Grundmessstelle des Landes, WRRL-Planungseinheit, Niederung) | 11 |

*(Kategorien überlappen; Summe > 83.)*

**Wichtige Einschränkung — die `bemerkung` ist unvollständig und länderabhängig.**
NRW, Brandenburg und Sachsen-Anhalt pflegen das Feld intensiv (NRW nennt sogar
Inbetriebnahmejahre einzelner Talsperren); Sachsen, Thüringen, Baden-Württemberg,
Rheinland-Pfalz, **Niedersachsen** und die Bundes-Pegel (`DEXX`) lassen es fast
durchgängig leer. Die Talsperren an Saale, Weißer Elster, Zschopau, Mulde und Apfelstädt
sind hydrologisch mindestens so dominant wie die NRW-Fälle, tauchen in `bemerkung` aber
nicht auf. Die `bemerkung` ist deshalb ein **starker positiver, aber kein negativer
Nachweis**: ihr Fehlen belegt keine Naturnähe.

**Blinder Fleck Niedersachsen/Harz (in Rev. 1 übersehen, Rev. 2 korrigiert).** Das
Harzwasserwerke-System — Oker-, Grane-, Söse-, Oder-, Innerste- und Eckertalsperre,
zusammen rund 180 hm³ — betreibt dokumentierte Niedrigwasseraufhöhung und exportiert
Fernwasser nach Hannover, Bremen und Göttingen. Kein einziger Pegel im Aller-/Leine-EZG
trägt dazu eine `bemerkung`. Der einzige Pegel im Datensatz, der dieses System integriert,
ist **Aller Rethem (14 730 km²)** — in Rev. 1 fälschlich naturnah, jetzt `reservoir` +
`transfer`. Lehre daraus: bei jedem Pegel > ~5 000 km² muss unabhängig von der `bemerkung`
aktiv nach einem Speichersystem gesucht werden; Rev. 1 hat das bei Rhein/Elbe/Weser/Donau/
Saale getan, bei der Aller nicht.

### 2.2 Sekundärquellen

- Stammdaten-Felder `ezgGroesse`, `gewaesser`, `gkz`, `lageGewaesser`, `laenge`/`breite`
  zur Klärung, ob ein Pegel ober- oder unterhalb eines Bauwerks/einer Mündung liegt.
  Beispiel: Pegel Meschede (Ruhr) trägt GKZ 27615.1, die Henne-Mündung liegt bei
  GKZ 27616 → der Pegel liegt **oberhalb** der Hennetalsperre und bleibt naturnah.
- Gezielte Web-Recherche zu vier strittigen Komplexen: Sümpfungswasser Niers/Schwalm
  (Tagebau Garzweiler), Lage Pegel Meschede/Hennetalsperre, Salzabwassereinleitung
  K+S in die Werra, Wasserentnahme Ems → Dortmund-Ems-Kanal/Speicherbecken Geeste.
- Fachliches Domänenwissen zu den in der Spezifikation benannten Großsystemen
  (Lausitzer Revier, Rheinisches Revier, Ruhrverband, Edersee/Diemelsee, Saale-Kaskade,
  Rappbode, Moldau-Kaskade, Alpenspeicher, Donau-Main-Überleitung).

---

## 3. Flag-Kriterien (verbindlich angewandt)

Ein Flag wird **nur** gesetzt, wenn die Steuerung das **Niedrigwasserregime** prägt —
nicht bei bloßer Stau- oder Abflussmodulation.

### `reservoir` — gesetzt, wenn eines gilt
1. Die `bemerkung` nennt explizit Talsperren-/Speicherbeeinflussung; **oder**
2. oberhalb liegt ein Speicher mit **dokumentierter Niedrigwasseraufhöhung,
   Mindestabgabe oder saisonaler Umverteilung**; **oder**
3. das gesteuerte Teil-Einzugsgebiet beträgt ≳ 10 % des Pegel-EZG bzw. die garantierte
   Abgabe ≳ 10 % des MNQ; **oder**
4. der Pegel ist selbst Referenz-/Steuerpegel eines Talsperrenverbands.

Entscheidend ist die **absolute Abgabemenge in m³/s**, nicht der Flächenanteil:
Niedrigwasseraufhöhung ist eine additive Größe. Deshalb sind auch sehr große Hauptströme
geflaggt, obwohl der gesteuerte Flächenanteil dort klein wirkt (Elbe/Moldau-Kaskade,
Weser/Edersee, Rhein/Alpenspeicher).

**Gate zu Kriterium 1 (neu in Rev. 2).** Eine `bemerkung`, die eine Talsperre nennt,
reicht **allein nicht**, wenn ein Gegenbeleg vorliegt oder die Menge das Kriterium
verfehlt. Kein Flag, wenn
- (a) die `bemerkung` selbst belegt, dass der Pegel **oberhalb** des Bauwerks liegt
  („Oberwasserpegel …", „Zulaufpegel"), **oder**
- (b) der Stauraum < 5 hm³ bei einem Pegel-EZG in der Größenordnung mehrerer hundert km²
  beträgt, also selbst bei vollständiger Abgabe kein MNQ-relevanter Beitrag entstünde.

Nach diesem Gate sind in Rev. 2 **Emmer Schieder** (Fall a) und **Erft Bliesheim**
(Fall b) gestrichen. Die Rev.-1-Begründung „im Zweifel flaggen" trägt hier nicht: die
Spezifikation meint Zweifel bei *fehlender* Evidenz, nicht bei *vorliegendem Gegenbeleg*.

### `transfer` — gesetzt bei
Nachweisbarem Wassertransfer über Einzugsgebietsgrenzen: Fernwasser-/Trinkwasserausleitung
aus einer Talsperre, Beileitungssysteme, Kanalspeisung aus einem Fluss, staugeregelte
Bundeswasserstraßen mit Querverbindungen zwischen Flusssystemen, Donau-Main-Überleitung.

**Schwelle für Kläranlagen-/Fremdwasseranteil (neu in Rev. 2):** ein in der `bemerkung`
**dokumentierter** Abwasser-/Fremdwasseranteil von **≥ 20 % bei Niedrigwasser** ⇒ `transfer`.
Begründung: bei diesem Anteil ist der NM7Q-/Q95-Bereich zu einem Fünftel oder mehr eine
Einleitungsgröße und damit nicht mehr klimagetrieben, unabhängig davon, ob die Herkunft
des Wassers im Einzelfall belegbar ist. Betroffen sind exakt zwei Stationen:
**Rems Schorndorf** (ca. 40 %) und **Brigach Donaueschingen** (ca. 20 %, Grenzfall).
Geprüft und **ohne** dokumentierten Anteil: Fils Salach, Enz Pforzheim, Neckar Wendlingen,
Kocher Kocherstetten, Jagst Jagstzell — bei allen fünf ist die `bemerkung` entweder leer
oder nennt nur Verkrautung; keine Flags. **Neckar Rockenau** wurde in Rev. 2 gestrichen:
die Rev.-1-Begründung (Bodensee-Wasserversorgung) war eine Inferenz ohne Beleg im
Datensatz oder in einer zitierbaren Quelle.

### `mining` — gesetzt bei
Berg- oder Tagebaubedingter Entnahme/Einleitung, die den Abfluss trägt oder trug:
Sümpfungswassereinleitung, Restseeflutung, Grubenwasserhaltung, bergbaubedingte
Flussverlegung. Besonders gewichtet, weil diese Einflüsse **über den Analysezeitraum
systematisch abnehmen** (Auslaufen der Sümpfung) und damit einen künstlichen
Abwärtstrend erzeugen, der wie ein Klimasignal aussieht.

**Mengenstandard (neu in Rev. 2), zweistufig:**
1. **Menge quantifizierbar und < ~10 % des MNQ ⇒ kein Flag.** Die Zahl schlägt die Vermutung.
   Angewandt auf Werra/K+S (§5.2) und Blies Reinheim (§5.8).
2. **Menge nicht quantifizierbar, Verdacht aber plausibel und ortsspezifisch ⇒ Flag**,
   mit `note`-Präfix **`unsicher:`**. So bleibt der Vorbehalt maschinenlesbar und der
   Vorschlag lässt sich in einer Sensitivitätsrechnung mit einem Filter auf `unsicher:`
   auf den harten Kern zurückfahren.

In Rev. 2 tragen **30 Zeilen** dieses Präfix. Der Marker ist dabei **kanonisiert**: er
steht immer am Zeilenanfang, nie nur im Fließtext, damit `note LIKE 'unsicher:%'` den
weichen Rand vollständig erfasst. Ein zusätzlicher, im Zeilenrumpf konkretisierter
Vorbehalt ist einheitlich als `(Vorbehalt: …)` notiert. Betroffen sind:
Oder (2 Pegel × `mining` + `reservoir`), Saar (`mining`, 2), Mosel (`reservoir`, 2;
`mining`, 1 — Cochem), Lausitzer Neiße Zittau (`mining`), Salzach Burghausen
(`reservoir`), Zschopau Lichtenwalde (`reservoir`), Brigach Donaueschingen (`transfer`),
Donau ab Kelheim (`transfer`, 4), Lippe (`transfer`, 2), Weser ab Liebenau
(`transfer`, 3) sowie die Kanalpegel mit variablem Spreewasseranteil
(Dahme ×2, Havel ×4, Wernsdorf, Kleinmachnow — `mining`).

### `erosion` — reiner Hinweis, kein Ausschluss
Bekannte Sohlerosionsstrecken sowie `bemerkung`-Hinweise auf Sedimentation, Geschiebe
und Pegel-Standortwechsel. Betrifft die W-Q-Beziehung, nicht Q direkt.

> **Änderungsvorschlag für `docs/methods.md` (bitte separat übernehmen).**
> Die dortige Definition lautet aktuell:
> `erosion` — *bekannte Sohlerosion; nur Hinweis, kein Ausschluss (betrifft W, nicht Q)*.
> Drei der zwölf vorgeschlagenen `erosion`-Zeilen fallen darunter nicht wörtlich:
> Golzow (Pegel-Standortwechsel), Zeitz (Verkrautung + Wehre) und Eschelbronn
> (Sedimentation). Alle drei beschreiben aber **dasselbe Problem** — eine über die Zeit
> driftende W-Q-Beziehung — nur mit anderem physikalischen Mechanismus als Erosion.
> Statt drei sachlich richtige Hinweise zu verwerfen, sollte die Definition erweitert
> werden auf:
>
> > `erosion` — **instabile W-Q-Beziehung** (Sohlerosion, Sedimentation, Geschiebe,
> > Pegel-Standortwechsel); reiner Hinweis, kein Ausschluss.
>
> Der Flag-Name bleibt aus Kompatibilitätsgründen `erosion`.

### Bewusst **nicht** geflaggt
- **Hochwasserrückhaltebecken (HRB).** Grüne Becken stehen im Niedrigwasser leer und
  beeinflussen MNQ/NM7Q nicht (z. B. Lippe Bentfeld, Unstrut Straußfurt, Erft-HRB).
- **Stauhaltung/Wehrsteuerung in Tieflandgewässern ohne Speicher.** 20 `bemerkung`-Einträge
  („durch Stauhaltung beeinflusst", „Beeinflussung durch Wehrsteuerungen oberhalb")
  betreffen Brandenburg, NRW-Westmünsterland und Sachsen-Anhalt. Wehrstau verschiebt
  Wasserstände und Retention, entnimmt aber kein Wasser; auf die Jahres-Niedrigwasser-
  Kennzahlen wirkt er zweiter Ordnung. Diese Stationen bleiben naturnah — das ist die
  am ehesten diskutable Einzelentscheidung dieses Vorschlags (siehe 5.6).
- **Verkrautung, Pegelumbau, Vereisung, „GlW 2010", „W erst ab …".** Mess- und
  Datengütethemen, nicht Homogenität. Gehören in die Vollständigkeits-/Qualitätsstufe.
- **Kläranlagenanteil unterhalb 20 %** — oberhalb der Schwelle greift die `transfer`-Regel
  (siehe oben); im Datensatz gibt es keinen dokumentierten Fall zwischen 0 und 20 %.

---

## 4. Systematik je Flusssystem

### 4.1 Hauptströme (Bundeswasserstraßen)

| System | Stationen | Flags | Begründung |
|---|---:|---|---|
| Rhein Maxau–Rees | 12 | `reservoir` (alle), `transfer` (ab Mainz), `mining` (ab Düsseldorf), `erosion` (5) | Alpenspeicher CH/AT > 2 km³ verschieben Abfluss Sommer→Winter; ab Mainz Donauwasser aus der Donau-Main-Überleitung; ab Erft-Mündung Sümpfungswässer des Rheinischen Reviers |
| Elbe Schöna–Wittenberge | 9 | `reservoir` (alle), `mining` (ab Wittenberg), `erosion` (3) | Moldau-Kaskade wird explizit zur Niedrigwasseraufhöhung für die Schifffahrt gefahren; ab Schwarze-Elster-/Mulde-/Saale-Mündung Bergbauwasser |
| Donau Donauwörth–Hofkirchen | 6 | `reservoir` (alle), `transfer` (ab Kelheim) | unterhalb Lech-Mündung Forggensee (168 hm³, EZG 1592 km²) + Iller-/Wertach-Speicher; ab Entnahme Bad Gögging Abgabe an die Donau-Main-Überleitung |
| Weser Hann. Münden–Intschede | 7 | `reservoir` (alle), `transfer` (ab Liebenau) | Edersee (202 hm³) + Diemelsee mit dokumentierter Abgaberegel zur Oberweser-Niedrigwasseraufhöhung; ab Minden Speisung des Mittellandkanals |
| Oder (2) | 2 | `reservoir`, `mining` | polnisch/tschechische Kaskaden (Nysa Kłodzka, Turawa) mit Schifffahrtsabgabe; oberschlesische Grubenwasserhaltung — beide mit Unsicherheitsvermerk |
| Mosel (2), Saar (2) | 4 | `reservoir`, `mining` | Nonnweiler/Vieux-Pré-Niedrigwasserstützung, durchgehende Staustufenketten, Saar-Grubenwasserhaltung |
| Main (3 von 4) | 3 | `transfer` | Donau-Main-Überleitung, bis 21 m³/s exakt in Trockenperioden. **Kemmern (4250 km²) liegt oberhalb der Regnitz-Mündung → naturnah.** |
| Saale (8 von 9) | 8 | `reservoir`, unten zusätzlich `mining` | Saale-Kaskade Bleiloch + Hohenwarte (397 hm³), größtes deutsches Speichersystem |
| Aller Rethem | 1 | `reservoir`, `transfer` | sechs Harzwasserwerke-Talsperren (Oker, Grane, Söse, Oder, Innerste, Ecker; ~180 hm³) mit Niedrigwasseraufhöhung und Fernwasserexport nach Hannover/Bremen/Göttingen (Rev. 2 ergänzt, siehe §2.1) |

Die Donau bei **Beuron (BW)** bleibt ungeflaggt: die Donauversickerung
(Immendingen/Fridingen → Aachtopf → Rheineinzugsgebiet) prägt dort das Niedrigwasser
extrem, ist aber ein **natürlicher** Karstprozess. Der Fall gehört in die Ergebnis-
diskussion, nicht ins anthropogene Flag-Schema — als Hinweis hier festgehalten.

### 4.2 Talsperrenverbände NRW (bemerkung-getragen)

Ruhrverband/Wupperverband/Aggerverband/WVER sind der am besten dokumentierte Block:
Sieg (4 Pegel), Agger, Dhünn, Wupper (2), Lenne, Ennepe, Volme, Ruhr Villigst,
**Ruhr Meschede** (Rev. 2 ergänzt, §5.1), Diemel, Urft, Rur (2), Stever — alle direkt
aus `bemerkung` belegt bzw. über die Talsperrenlage. In Rev. 2 gestrichen: Emmer Schieder
und Erft Bliesheim (§5.5).
Besonderheiten: Agger→Dhünn-Überleitung **seit 01.04.1992** und Wuppertalsperre
**seit 01.11.1987** liegen als Stufenwechsel direkt im Analysezeitraum ab 1992 —
diese Reihen sind selbst mit Flag als Trendreihen wertlos.

### 4.3 Rheinisches Braunkohlerevier → `mining`

Erft Neubrück (`bemerkung`: Sümpfungswässer), Inde Eschweiler (Flussverlegung für
Tagebau Inden), Rur Stah, Niers Goch, Schwalm Landesgrenze, Rhein ab Düsseldorf.
Die Niers ist der Extremfall: die Quelle bei Kuckum ist durch die Sümpfung versiegt,
der Fluss wird seither aus Einleitungen gespeist — der Niedrigwasserabfluss ist dort
zu 100 % anthropogen. Für die Schwalm laufen RWE-Einleitmaßnahmen mit befristeter
wasserrechtlicher Erlaubnis (aktuell ~1,7 Mio m³/a bis 2030), d. h. eine geplante
Abschaltung mitten in künftigen Fortschreibungen.

### 4.4 Lausitzer Revier → `mining` (+ `reservoir`/`transfer`)

Der stärkste Homogenitätsbruch im gesamten Datensatz. Geflaggt:
- **Schwarze Elster:** Neuwiese, Biehlen 1 (`bemerkung`: „unterhalb Talsperre"),
  Bad Liebenwerda, Löben — durchgehend `mining`.
- **Spree:** Leibsch (`bemerkung`: „stromunterhalb Talsperre" = Spremberg), Beeskow,
  Hohenbinde, Große Tränke, Berlin-Sophienwerder.
- **Zubringer/Nebensysteme:** Hoyerswerdaer Schwarzwasser (Zescha), Schwarzer Schöps
  (Jänkendorf, zusätzlich TS Quitzdorf), Weißer Schöps (Särichen), Pließnitz (Tauchritz,
  direkt am Berzdorfer See).
- **Lausitzer Neiße:** Zittau, Görlitz, Schlagsdorf — Grubenwasser Tagebau Turów (PL)
  und Entnahme zur Flutung des Berzdorfer Sees 2002–2013. Zittau mit Unsicherheitsvermerk.
- **Berliner/Havelländer Wasserstraßen:** Teltowkanal, Spree-Oder-Wasserstraße,
  Dahme-Wasserstraße, Dahme (Umflutkanal Märkisch Buchholz), Havel-Oder-Wasserstraße,
  Untere Havel (4 Pegel) — `transfer` (Schleusen-/Kanalbetrieb, künstliche
  Abflussaufteilung) plus anteilig `mining` (Spreewasser).

**Spree Bautzen1 bleibt naturnah**: der Pegel liegt in der Stadt Bautzen, also
*oberhalb* der Talsperre Bautzen und oberhalb des Bergbaugebiets.

### 4.5 Mitteldeutschland / Erzgebirge / Thüringen

- **Weiße Elster:** Greiz, Gera-Langenberg, Zeitz, Kleindalzig → `reservoir` (TS Pöhl/Pirk);
  Kleindalzig zusätzlich `mining` (Flutung Zwenkauer/Cospudener See aus der Weißen Elster).
  **Adorf1 (Oberlauf) bleibt naturnah.**
- **Thüringer Trinkwassertalsperren** → jeweils `reservoir` + `transfer`, weil das Wasser
  das Einzugsgebiet über das Fernwassernetz verlässt: Apfelstädt Ingersleben (Ohra/
  Schmalwasser — die Apfelstädt fällt unterhalb regelmäßig trocken), Gera Erfurt-Möbisburg
  (erbt Apfelstädt), Schwarza Schwarzburg (Leibis-Lichte, **in Betrieb seit 2005**),
  Schleuse Rappelsdorf (Schönbrunn), Weida (Zeulenroda/Weida).
- **Sachsen:** Zwickauer Mulde Wechselburg (Eibenstock), Vereinigte Mulde Golzern,
  Zschopau Lichtenwalde (Flöha-System) → `reservoir` + `transfer`.
- **Bode Hadmersleben** → `bemerkung`: „Beeinflussung durch TS Wendefurth", Rappbode-System
  (~165 hm³) mit Fernwasserlieferung nach Halle/Magdeburg → `reservoir` + `transfer`.
- Alle Oberlaufpegel oberhalb der jeweiligen Sperren bleiben naturnah: Saale
  Blankenstein-Rosenthal (oberhalb Bleiloch), Schwarza Katzhütte, Wilde Weißeritz
  Ammelsdorf (Zulaufpegel TS Lehnmühle), Loquitz, Ilm, Zorge, Helme Sundhausen.

### 4.6 Übrige Transfers

- **Ems Rheine US und Lingen-Darme** → `transfer`: die Ems speist am Nassen Dreieck den
  Dortmund-Ems-Kanal; aus dem DEK wird Wasser im Speicherbecken Geeste bevorratet und
  der Ems **gezielt bei Niedrigwasser** wieder zugegeben (Antrag bis 23 Mio m³/a). Das ist
  aktive Niedrigwasserbewirtschaftung. Ems oberhalb (Rheda, Einen, Fuestrup, Greven) naturnah.
- **Lippe Leven und Schermbeck** → `transfer` (Speisung DEK/Wesel-Datteln-Kanal), Bentfeld naturnah.
- **Stever Olfen** → `reservoir` + `transfer` (Halterner Stausee, Gelsenwasser-Förderung ins Ruhrgebiet).
- **Inn Wasserburg** → `bemerkung`: „Zu- und Ableitungen außerhalb Deutschlands"; plus
  alpine Speicherkraftwerke → `transfer` + `reservoir`. **Salzach Burghausen** analog
  `reservoir` (unsicher).
- **Vils Grafenmühle** → `bemerkung` beziffert den Vilstalsee selbst: AEo 666 km² von
  1440 km² Pegel-EZG = 46 %, ab 1976 → `reservoir`, ein Musterfall für Kriterium 3.
- **Neckar Rockenau** und **Rems Schorndorf** → `transfer` (Bodensee-Wasserversorgung führt
  dauerhaft Fremdwasser ins Neckar-EZG; bei Schorndorf laut `bemerkung` 40 % Kläranlagen-
  anteil bei Niedrigwasser). Beide mit Unsicherheitsvermerk.
- **Bolter Kanal (MV)** → `transfer`; ein ausgewiesenes EZG von 3 km² belegt, dass der
  „Abfluss" reiner Schleusen- und Seenbewirtschaftungsvorgang ist.

---

## 5. Grenzfälle mit Begründung

### 5.1 Ruhr Meschede — **geflaggt** `reservoir` (Korrektur gegenüber Rev. 1)
426 km², `bemerkung` nennt nur „Grundmessstelle des Landes". Die Frage ist, ob die
Hennetalsperre (Ruhrverband, 38 hm³) oberhalb liegt.

**Rev. 1 hat das falsch entschieden.** Die dort angeführte Herleitung stützte sich auf
eine Gewässerkennzahl „27615.1", die es im Rohdatensatz gar nicht gibt: das Stammdatenfeld
`gkz` des Pegels enthält lediglich `276`. Die verwendete Zahl stammte aus der internen
NRW-Messstellennummer, nicht aus der Gewässerkennzahl. Zusätzlich war die Leserichtung
falsch: nach dem LAWA-Paritätsschema liegt der Abschnitt 27615 **unterhalb** des Zuflusses
27614 (= Henne), nicht oberhalb.

Drei unabhängige Belege für die Lage **unterhalb**:
- **Kilometrierung:** Pegel bei Ruhr-km 178,34, Henne-Mündung bei Ruhr-km 182,3
  (Ruhr-km wird von der Mündung aufwärts gezählt → kleinere km = weiter flussab).
- **LAWA-Paritätsregel:** Abschnittskennzahl 27615 folgt auf den Zufluss 27614.
- **EZG-Arithmetik:** 426 km² ≈ 329 km² (Ruhr oberhalb) + 97 km² (Henne).

**Entscheidung: `reservoir`.** Das Argument „NRW hätte es sonst in die `bemerkung`
geschrieben" trägt nicht — es ist genau der negative Schluss aus einem lückenhaften
Feld, vor dem §2.1 warnt, und Rev. 1 hat ihn hier trotzdem gezogen.

### 5.2 Werra (10 Pegel) — **nicht geflaggt**, obwohl im Auftrag erwogen
Die Werra ist durch die K+S-Salzabwassereinleitung (Werke Werra/Neuhof-Ellers) massiv
beeinträchtigt — aber **stofflich, nicht mengenmäßig**. Größenordnung: die Erlaubnis
2022–2027 deckelt auf 5,0 Mio m³/a ≈ 0,16 m³/s; auch die historisch höheren Mengen
liegen bei < 1 m³/s gegenüber einem Werra-MNQ von mehreren m³/s bis über 10 m³/s bei
Gerstungen/Allendorf. Nach dem Kriterium „prägt die Steuerung das Niedrigwasser*regime*
(Q)?" ist das zu wenig. Große Talsperren gibt es an der Werra nicht.
**Entscheidung: keine Flags.** Falls die Analyse an der Werra Auffälligkeiten zeigt,
ist die Versenkung/Einleitung als Erklärung zweiter Ordnung zu prüfen. Bewusst
dokumentiert, weil „Werra = Kali = geflaggt" die naheliegende Fehlentscheidung wäre —
sie hätte 10 Stationen ohne mengenmäßige Grundlage entfernt.

### 5.3 Untere Donau (Ingolstadt–Hofkirchen) — geflaggt trotz kleinem Flächenanteil
Der gesteuerte Anteil (Forggensee 1592 km²) sinkt von 10,5 % bei Donauwörth auf 3,4 %
bei Hofkirchen. Nach einem reinen Flächenkriterium wären die unteren Pegel naturnah —
was absurd wäre für eine durchgehend staustufenregulierte Wasserstraße, der zudem ab
Bad Gögging bis 21 m³/s für die Donau-Main-Überleitung entnommen werden.
**Entscheidung:** Flächenanteil als Kriterium verworfen zugunsten der absoluten
Abgabe-/Entnahmemenge relativ zum MNQ; alle sechs bayerischen Donau-Pegel geflaggt,
Donau Beuron (BW, Karst) ausgenommen.

### 5.4 Berliner und Havelländer Wasserstraßen — als `transfer` geflaggt
Teltowkanal, Spree-Oder-Wasserstraße, Dahme-Wasserstraße, Havel-Oder-Wasserstraße,
Untere Havel-Wasserstraße: das Flag-Schema kennt keine Kategorie „künstliche
Wasserstraße". `transfer` ist die sachlich richtigste Zuordnung, weil diese Kanäle
tatsächlich Wasser zwischen Spree-, Havel- und Odereinzugsgebiet verschieben (der
Teltowkanal ist in der `bemerkung` von Sophienwerder sogar als alternativer Abflussweg
genannt). Die ausgewiesenen `ezgGroesse`-Werte dieser Pegel (70 km² für Wernsdorf,
205 km² für Kleinmachnow) sind hydrologisch bedeutungslos — sie würden auch die
inkrementelle Flächengewichtung in Phase 3 verzerren. **Empfehlung über das Flagging
hinaus: diese Pegel auch in der Topologie/Gewichtung gesondert behandeln.**

### 5.5 Erft Bliesheim und Emmer Schieder — **gestrichen** (Korrektur gegenüber Rev. 1)
Beide waren in Rev. 1 mit dem Argument „im Zweifel flaggen" gesetzt. Das war eine
Fehlanwendung der Spezifikations-Regel: gemeint ist Zweifel bei *fehlender* Evidenz, hier liegt
jeweils ein *Gegenbeleg* vor.

- **Emmer Schieder:** die `bemerkung` sagt wörtlich „Oberwasserpegel für den Emmer-Stausee".
  Der Pegel liegt damit **oberhalb** des Bauwerks — ein Speicher flussabwärts kann das
  Niedrigwasser am Pegel nicht beeinflussen. Gegenbeleg, kein Zweifel.
- **Erft Bliesheim:** Steinbachtalsperre ~1 hm³ auf 604 km² Pegel-EZG. Selbst eine
  vollständige Entleerung über das Sommerhalbjahr entspräche ~0,06 m³/s — weit unter
  jeder MNQ-Relevanzschwelle. Der mitgenannte HRB-Anteil ist ohnehin ausgeschlossen
  (grüne Becken, siehe §3). Verfehlt jedes Mengenkriterium.

Aus beiden Fällen ist das **Gate zu Kriterium 1** in §3 abgeleitet worden.
Erft Neubrück (`mining`, Sümpfungswasser) ist davon nicht berührt und bleibt geflaggt.

### 5.6 Stauhaltungs-`bemerkungen` in Brandenburg/Westmünsterland — **nicht geflaggt**
20 Stationen tragen „durch Stauhaltung beeinflusst" bzw. „Beeinflussung durch
Wehrsteuerungen oberhalb" (Nuthe Babelsberg-Drewitz, Plane Golzow, Buckau Neue Mühle,
Welse Blumenhagen, Issel, Bocholter Aa, Berkel, Dinkel ×2, Ems Rheda, Ohre Wolmirstedt,
Großer Graben u. a.). Wehrstau ohne Speicher entnimmt kein Wasser und hebt das
Niedrigwasser nicht auf; er verändert vor allem Wasserstand und lokale Retention.
**Entscheidung: naturnah, aber als Sensitivitätsblock markieren.** Das ist die größte
Einzelgruppe im naturnahen Subset, die man mit anderer Auslegung verlieren würde: ein
Ausschluss dieser 20 senkte das naturnahe Subset auf ~216 — immer noch im Korridor.
Empfohlene Prüfung in Phase 3: streuen diese 20 systematisch anders als der Rest?

### 5.7 Fredersdorfer Fließ — **aus den Flags entfernt** (Korrektur gegenüber Rev. 1)
`bemerkung`: „fällt trocken, daher keine korrekten Hauptwerte". Das ist keine
anthropogene Steuerung, sondern eine explizite Warnung des Betreibers vor unbrauchbaren
Kennwerten. Rev. 1 hat den Fall als `erosion` mitgeführt, „damit die Information nicht
verlorengeht" — das widersprach dem eigenen Befund im selben Absatz und hätte die
Flags-Datei zum Ablageort für sachfremde Hinweise gemacht.

**Entscheidung: keine Flag-Zeile.** Der Fall gehört in die Vollständigkeits-/Qualitäts-
stufe: dauerbasierte Kennzahlen sättigen dort (`days_below` → 365),
und `deficit_volume_m3` wird bei Q = 0 zur reinen Schwellenfunktion.
**Offener Punkt für die Pipeline:** `DESM_DEBB5860800` als Qualitätsausschluss vormerken
(§7, Punkt 4) — die Information ist damit nicht verloren, sondern nur am richtigen Ort.

### 5.8 Blies Reinheim — **nicht geflaggt**, Anwendungsfall des `mining`-Mengenstandards
Die Blies (1798 km²) durchfließt das östliche Saarrevier; die Grubenwasserhaltung am
Standort Reden hebt Wasser, das über Blies/Saar abgeführt wird. Das ist der Typ Verdacht,
der in Rev. 1 an anderen Stellen zum Flag geführt hat. Hier ist die Menge aber bekannt:
rund **13,9 Mio m³/a ≈ 0,44 m³/s**. Das MNQ der Blies bei Reinheim liegt in der
Größenordnung mehrerer m³/s, der Anteil damit klar **unter der 10-%-Schwelle**.
**Entscheidung: kein Flag** — Stufe 1 des Mengenstandards (§3). Dasselbe gilt für die
übrigen saarländischen Nebengewässer (Ill Eppelborn, Theel Lebach, Schwarzbach Einöd).

Der Kontrast zu Saar und Mosel ist beabsichtigt und methodisch sauber: dort ist die
Gesamtmenge der Grubenwasserhaltung des Reviers **nicht** belastbar quantifizierbar,
weshalb Stufe 2 greift (Flag mit `unsicher:`-Präfix). Wo eine Zahl vorliegt, schlägt sie
die Vermutung; wo keine vorliegt, bleibt der Vorbehalt im Datensatz sichtbar.

---

## 6. Ergebnis und Sanity-Check

| Größe | Wert |
|---|---:|
| Stationen gesamt | 361 |
| Stationen mit `bemerkung` (nicht leer, nicht `"0"`) | 83 |
| davon mit Hinweis auf anthropogene Beeinflussung | 42 |
| Vorschlagszeilen in der CSV | 205 |
| Stationen mit mindestens einem Flag | 128 |
| `reservoir` | 88 Stationen |
| `transfer` | 57 Stationen |
| `mining` | 48 Stationen |
| `erosion` (kein Ausschluss) | 12 Stationen |
| davon Zeilen mit `unsicher:`-Präfix | 30 |
| **Stationen mit ausschließendem Flag** | **125** |
| **Naturnahes Subset** | **236 / 361 (65 %)** |

Rev. 2 hat die Gesamtzahl der ausschließend geflaggten Stationen nicht verändert (125):
drei Streichungen (Emmer Schieder, Erft Bliesheim, Neckar Rockenau) stehen drei Zugängen
gegenüber (Ruhr Meschede, Aller Rethem, Brigach Donaueschingen). Die Zusammensetzung ist
dadurch aber deutlich besser belegt — jede Streichung beruht auf einem Gegenbeleg, jeder
Zugang auf einem positiven Nachweis.

236 liegt im Zielkorridor 150–280, näher am oberen Rand. Das ist beabsichtigt: die
Kriterien sind so gefasst, dass jedes Flag benennbar begründet ist. Wo die Evidenz nur
in „das ist ein großer Fluss, da ist bestimmt was" bestand (Werra, Wurm, Amper, Lahn,
Blies/Ill/Theel, Regen, Loisach, Freiberger Mulde), wurde **nicht** geflaggt.

Die Struktur ist plausibel: geflaggt sind die Hauptströme, die Talsperrenverbands-
gewässer und die beiden Braunkohlereviere; naturnah bleibt weit überwiegend die
Mittelgebirgs- und Tiefland-Nebengewässerschicht mit 20–1500 km² — genau die Schicht,
in der ein Klimasignal überhaupt sauber messbar ist.

**Verzerrungshinweis für Phase 3:** das naturnahe Subset ist systematisch kleinflächiger
als der Gesamtdatensatz. Alle geflaggten Hauptströme tragen in der inkrementellen
Flächengewichtung große Gewichte. Der Vergleich „alle vs. naturnah" ist deshalb
**nicht** nur ein Homogenitäts-, sondern zwangsläufig auch ein Skalenvergleich; das muss
bei der Interpretation einer Divergenz explizit mitgesagt werden.

---

## 7. Nächste Schritte

1. Vorschlag prüfen, insbesondere die Abschnitte 5.2 (Werra), 5.3 (Donau) und 5.6
   (Stauhaltung) — dort liegen die diskutabelsten Entscheidungen.
2. `docs/homogenitaet-flags-vorschlag.csv` nach `config/station_flags.csv` übernehmen
   (Format ist identisch: `station_id,flag,note`).
3. **`docs/methods.md` an zwei Stellen nachziehen:**
   - `erosion`-Definition erweitern auf „instabile W-Q-Beziehung (Sohlerosion,
     Sedimentation, Geschiebe, Pegel-Standortwechsel)" — Wortlaut siehe §3.
   - Stationszahl korrigieren: `methods.md` („Datengrundlage") und
     die Spezifikation nennen weiterhin **356** Messstellen; der real
     ingestierte Datensatz und alle Zahlen dieses Reports beziehen sich auf **361**.
     356 ist die CORRECTIV-Zahl aus dem Fluss-Atlas, nicht die des NIWIS-Abzugs.
     Beide liegen außerhalb des Auftragsumfangs dieser Recherche und wurden
     nicht angefasst.
4. `uv run niedrigwasser screen` erneut laufen lassen und die Zahlen in `docs/methods.md`
   Abschnitt „Screening-Ergebnis" fortschreiben.
5. Fredersdorfer Fließ (`DESM_DEBB5860800`) als Qualitätsausschluss vormerken (§5.7) —
   trägt in Rev. 2 bewusst keine Flag-Zeile mehr.
6. Kanalpegel (Abschnitt 5.4) in der Topologie/Gewichtung gesondert behandeln.
7. Sensitivitätsrechnung mit Filter auf `note LIKE 'unsicher:%'` — die 30 so markierten
   Zeilen sind der weiche Rand des Vorschlags.
8. Brigach Donaueschingen (§3, `transfer` bei genau 20 % Kläranlagenanteil) gegenprüfen:
   die Station war im ursprünglichen Prüfumfang nicht genannt, ergibt sich aber zwingend aus der
   dort beschlossenen ≥-20-%-Regel. Falls die Schwelle als „echt größer 20 %" gemeint
   war, ist diese eine Zeile zu streichen (naturnah stiege dann auf 237).
