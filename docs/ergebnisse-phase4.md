# Ergebnisse Phase 3+4 — Niedrigwasser-Trendindex für das deutsche NIWIS-Messnetz

*Ergebnisdokumentation zur nationalen Aggregation und Trendstatistik. Methodik:
`methods.md`. Reproduzierbarkeit: jede Zahl in diesem Dokument stammt unverändert aus
`out/national_index.csv`, `out/station_trends.csv`, `out/sensitivity.csv` oder den
Parquet-Reports unter `data/interim/trend/` bzw. `data/interim/aggregate/` — keine
Neuberechnung, siehe Konsistenz-Check am Ende.*

## 1. Nationale Kernzeitreihe (`national_index`, Variante `primary`)

Gewichtetes Mittel über alle screening-überlebenden, nicht-verschachtelten Stationen
(`include_nested=False`, `natural_only=False`; 192–208 Stationen/Jahr,
Einzugsgebietsabdeckung 453.778–511.744 km²/Jahr — siehe „Nesting-Auflösung" in
`methods.md`). Trend-Fenster für alle Aussagen dieses Dokuments: **Wasserjahre
1992–2025 (n=34)**; Wasserjahr 1991 ist in den Parquet-/CSV-Dateien
enthalten, fließt aber nicht in die Trendtests ein: es ist unvollständig (304 statt
365 Tage, siehe „Grenzen und offene Punkte").

| Wasserjahr | index_days | index_deficit (mm) | index_ssi | n_stations | coverage_area_km² |
|---:|---:|---:|---:|---:|---:|
| 1991 | 37,97 | 1,772 | −0,993 | 203 | 506.648 |
| 1992 | 62,81 | 2,301 | −1,032 | 204 | 506.307 |
| 1993 | 15,81 | 0,346 | −0,347 | 206 | 506.991 |
| 1994 | 10,64 | 0,252 | 0,016 | 207 | 511.579 |
| 1995 | 2,36 | 0,075 | 0,914 | 208 | 511.744 |
| 1996 | 12,34 | 0,680 | 0,262 | 208 | 511.744 |
| 1997 | 10,82 | 0,488 | 0,302 | 208 | 511.744 |
| 1998 | 17,31 | 0,777 | 0,044 | 206 | 510.439 |
| 1999 | 5,76 | 0,105 | 0,318 | 207 | 511.741 |
| 2000 | 4,51 | 0,086 | −0,005 | 205 | 453.778 |
| 2001 | 4,62 | 0,089 | 0,638 | 207 | 460.353 |
| 2002 | 0,81 | 0,028 | 0,999 | 207 | 505.294 |
| 2003 | 60,85 | 3,211 | −1,512 | 208 | 511.744 |
| 2004 | 43,04 | 1,355 | −0,653 | 207 | 500.415 |
| 2005 | 9,25 | 0,297 | −0,233 | 207 | 500.415 |
| 2006 | 32,67 | 2,709 | 0,145 | 207 | 500.415 |
| 2007 | 7,15 | 0,248 | 0,266 | 207 | 500.415 |
| 2008 | 14,63 | 0,330 | −0,418 | 207 | 500.415 |
| 2009 | 19,61 | 1,029 | −0,285 | 207 | 500.415 |
| 2010 | 7,63 | 0,366 | 1,091 | 206 | 499.225 |
| 2011 | 16,02 | 0,793 | −0,513 | 205 | 499.193 |
| 2012 | 22,79 | 1,507 | −0,358 | 206 | 500.064 |
| 2013 | 3,78 | 0,130 | 1,456 | 206 | 500.064 |
| 2014 | 6,94 | 0,289 | 0,020 | 208 | 511.744 |
| 2015 | 62,50 | 2,497 | −1,219 | 208 | 511.744 |
| 2016 | 41,56 | 2,227 | −0,120 | 208 | 511.744 |
| 2017 | 25,79 | 2,171 | −0,299 | 207 | 510.264 |
| **2018** | **93,49** | **5,772** | **−1,874** | 207 | 511.552 |
| **2019** | **89,38** | **5,164** | −1,085 | 207 | 511.552 |
| 2020 | 50,80 | 1,940 | −1,021 | 208 | 511.744 |
| 2021 | 17,03 | 0,605 | 0,316 | 205 | 511.088 |
| 2022 | 65,92 | 4,120 | −1,627 | 202 | 509.370 |
| 2023 | 47,64 | 1,693 | −0,905 | 197 | 505.139 |
| 2024 | 8,85 | 0,163 | 0,846 | 192 | 502.065 |
| 2025 | 53,51 | 2,177 | −1,390 | 204 | 508.249 |

`index_days` = flächengewichtetes mittleres `days_below` (Tage < Q95 der
Referenzperiode); `index_deficit` = flächengewichtetes mittleres Defizitvolumen,
auf Einzugsgebietsfläche normiert (mm); `index_ssi` = flächengewichteter mittlerer
Standardized Streamflow Index (negativ = trockener als Referenzklima). Formel und
Gewichtung: Abschnitt „Nationale Aggregation" in `methods.md`.

### Extremjahre

Die zehn Jahre mit dem höchsten `index_days` im gesamten Datensatz (1991–2025) sind,
absteigend: **2018 (93,49) > 2019 (89,38) > 2022 (65,92) > 1992 (62,81) > 2015 (62,50)
> 2003 (60,85) > 2025 (53,51) > 2020 (50,80) > 2023 (47,64) > 2004 (43,04)** — sieben
der zehn höchsten Werte liegen in den elf Jahren 2015–2025. 2018 ist zugleich das Jahr mit dem höchsten `index_deficit` (5,77 mm) und
dem betragsmäßig niedrigsten `index_ssi` (−1,87) im gesamten Datensatz — alle drei
Metriken stimmen für 2018 überein, es ist im Beobachtungszeitraum kein Grenzfall
einzelner Metriken, sondern ein durchgängig extremes Jahr. 2019 folgt unmittelbar
danach mit dem zweithöchsten `index_deficit` (5,16 mm). Die trockenste Phase der
gesamten Reihe ist damit die zusammenhängende Sequenz 2018–2020 (Ausnahme 2021, das
wieder in den Bereich der 2000er/2010er-Jahre zurückfällt), gefolgt von einem erneuten
Extremjahr 2022 und einem weiteren hohen Wert 2025 (aktuellster Datenrand). Die
feuchtesten Jahre sind 2002 (index_days 0,81, ssi +0,999), 1995 (2,36, +0,914) und 2024
(8,85, +0,846) — 2024 zeigt, dass auch innerhalb der jüngeren, insgesamt trockeneren
Dekade einzelne nasse Jahre auftreten; der Trend ist eine Verschiebung der Verteilung,
kein monotoner Jahr-für-Jahr-Anstieg (siehe Dekadenvergleich, Abschnitt 3).

Stationsseitig bestätigt sich das Muster: **250 von 359 Stationen (69,6 %)** haben ihr
NM7Q-Allzeitminimum (`min_year` in `out/station_trends.csv`) in einem Wasserjahr
2018–2025 — nahe an den ~68 %, die der CORRECTIV-Fluss-Atlas
(correctiv.org, veröffentlicht 20.08.2026) unabhängig ermittelt hat.

## 2. Trend-Kernaussagen je Metrik und Variante

TFPW-Mann-Kendall-Test + Sen-Slope, Fenster 1992–2025 (n=34), für die vier
Aggregationsvarianten (siehe „Nationale Aggregation" in `methods.md` für die
Definition von `include_nested`/`natural_only`):

| Variante | index_days (Trend, p, Sen [d/a]) | index_deficit (Trend, p, Sen [mm/a]) | index_ssi (Trend, p, Sen [1/a]) |
|---|---|---|---|
| **primary** (192–208 St./Jahr, alle nicht-verschachtelt) | increasing, p=0,0013, +0,853 | increasing, p=0,0025, +0,0452 | decreasing, p=0,0365, −0,0310 |
| **natural** (naturnah, nicht-verschachtelt, ~99–107 St.) | increasing, p=0,0001, +1,344 | increasing, p=0,0011, +0,0544 | decreasing, p=0,0267, −0,0392 |
| **allsinks** (alle Stationen inkl. verschachtelt, 339–360 St.) | increasing, p=0,0018, +0,815 | increasing, p=0,0020, +0,0462 | decreasing, p=0,0365, −0,0312 |
| **allsinks_natural** (naturnah inkl. verschachtelt, 225–236 St.) | increasing, p=0,0001, +1,286 | increasing, p=0,0003, +0,0539 | decreasing, p=0,0338, −0,0350 |

Quelle: `data/interim/trend/national_trends.parquet`.

**Kernaussage: Alle vier Varianten zeigen dasselbe Bild — `index_days` und
`index_deficit` signifikant steigend, `index_ssi` signifikant fallend (in allen 4
Varianten p < 0,05).** Kein Vorzeichenwechsel zwischen den Varianten.

**Divergenz alle vs. naturnah, explizit bewertet:** Die naturnahen Varianten
(`natural`, `allsinks_natural`) zeigen durchgehend **stärkere** Trends als ihre
„alle Stationen"-Pendants — bei `index_days` etwa +1,34 bzw. +1,29 d/a gegenüber
+0,85 bzw. +0,82 d/a, bei `index_ssi` −0,039/−0,035 gegenüber −0,031 in beiden
Fällen. Das ist eine erwartbare und inhaltlich sinnvolle Richtung, kein
Widerspruch: gesteuerte Stationen (Talsperren, Überleitungen, Bergbau-Einflüsse —
die vom naturnahen Subset ausgeschlossenen Kategorien, siehe
„Homogenitäts-Screening" in `methods.md`) dämpfen Niedrigwasserextreme
tendenziell (Speicherbewirtschaftung, Mindestabgaben) oder überlagern das
Klimasignal mit Bewirtschaftungsentscheidungen, die keinem Trend folgen müssen.
Die naturnahe Teilmenge zeigt also das ungedämpfte, rein hydro-klimatische Signal
etwas deutlicher — **beide Varianten zeigen dieselbe Richtung, die naturnahe
Variante lediglich mit größerer Amplitude.** Wichtige Einschränkung dazu: das
naturnahe Subset deckt nur rund 64.602–71.177 km² ab (`natural`-Coverage, Minimum in
den Jahren 2000/2002 — Ausreißer nach unten durch reduzierte Stationsverfügbarkeit in
diesen beiden Jahren), gegenüber rund 453.778–511.744 km² bei `primary` — also
jahresabhängig nur etwa **12,8–15,5 % der Einzugsgebietsfläche** der Vollvariante
(Median der Jahresquote nahe 14 %). Die stärkeren naturnahen Trends beruhen
damit auf einer deutlich kleineren, geografisch nicht repräsentativen Stichprobe von
99–107 Stationen und sollten nicht als „der wahre, unverzerrte Trend" gegenüber
`primary` interpretiert werden, sondern als zusätzliche, richtungsgleiche Evidenz.

**allsinks-Sensitivität eingeordnet:** `allsinks` unterscheidet sich von `primary`
nur durch das Einbeziehen der 152 als „nested" kategorisierten Stationen (5 outlet /
34 standalone / 152 nested von 191 Senken insgesamt, siehe „Nesting-Auflösung" und
`docs/topologie-report.md`), deren Einzugsgebietsfläche bereits im jeweiligen
Basin-Auslass enthalten ist — Einbeziehung führt zu Doppelzählung von Fläche
(Coverage 506.261–564.227 km² statt 453.778–511.744 km² bei `primary`). Die
Trendrichtung und Signifikanz ändern sich dadurch **nicht** (increasing/increasing/
decreasing, alle p < 0,05), die Sen-Slopes verschieben sich nur geringfügig
(index_days +0,815 statt +0,853, index_deficit +0,0462 statt +0,0452, index_ssi
−0,0312 statt −0,0310). Das bestätigt, dass die Kernaussage nicht von der
Nesting-Entscheidung abhängt — `primary` (ohne Doppelzählung) bleibt aber die
methodisch sauberere und daher maßgebliche Variante.

## 3. Stationsebene

TFPW-MK + Sen je Station auf `days_below` und `nm7q`, Fenster 1992–2025, Stationen mit
≥ 25 Jahren im Fenster (`out/station_trends.csv`, 359 Stationen):

- **`days_below` signifikant (p<0,05) steigend: 224 / 359 (62,4 %)**
- **`nm7q` signifikant (p<0,05) fallend: 222 / 359 (61,8 %)**
- `max_spell` (gepoolte Ereignis-Spannweite) signifikant steigend, je nach
  Pooling-Fenster: 61,3 % (main, 5 Tage) / 63,2 % (pool3, 3 Tage) / 61,8 % (pool7, 7
  Tage) — Details siehe Abschnitt 4.

**Nach Multiplizitätskorrektur** (Benjamini-Hochberg-FDR, je Kennzahl separat über die
359 Tests; Spalten `days_below_p_fdr` / `nm7q_p_fdr`, Methodik in `docs/methods.md`):

- **`days_below` steigend: 211 / 359 (58,8 %)** statt roh 224 / 359 — 13 Stationen weniger
- **`nm7q` fallend: 197 / 359 (54,9 %)** statt roh 222 / 359 — 25 Stationen weniger

Ohne Korrektur wären bei 359 parallelen Tests und α = 0,05 rein zufällig höchstens ≈ 18
Falsch-Positive je Kennzahl zu erwarten (359 × 0,05) — diese Obergrenze gilt nur, wenn
kein einziger Trend echt wäre. Realistisch ist die Erwartung m₀ × α mit m₀ = Zahl der
trendfreien Stationen: bei einer Trefferquote über 60 % sind das eher 135–150 Stationen
und damit ≈ 7 Falsch-Positive. Dieselbe hohe Trefferquote erklärt auch, warum die
Korrektur nur wenige Stationen kostet — BH ist umso milder, je mehr echte Effekte in der
Familie stecken. Die Kernaussage (deutliche Mehrheit signifikant) hält also auch der
Korrektur stand.

Diese Quoten liegen nahe an der Referenzgröße des CORRECTIV-Fluss-Atlas (~60 %
signifikant fallend für NM7Q); der Sentinel-Fix (siehe `methods.md`) hat die
Übereinstimmung zusätzlich verbessert.

## 4. Dekadenvergleich

Über alle Station-Jahre (nicht flächengewichtet, reine Verteilungsstatistik je Kennzahl
über die drei Dekaden 1992–2001, 2002–2013, 2014–2025; Quelle:
`data/interim/trend/decade_stats.parquet`):

| Metrik | Dekade | n | Mittel | Median | P90 | Anteil Nullwerte |
|---|---|---:|---:|---:|---:|---:|
| days_below | 1992–2001 | 3576 | 16,10 | **5,0** | 48,0 | 36,8 % |
| days_below | 2002–2013 | 4295 | 18,96 | **6,0** | 57,0 | 35,5 % |
| days_below | 2014–2025 | 4252 | 55,71 | **45,0** | 127,0 | 14,9 % |
| deficit_mm | 1992–2001 | 3576 | 0,73 | 0,059 | 1,66 | 36,8 % |
| deficit_mm | 2002–2013 | 4295 | 0,79 | 0,076 | 2,30 | 35,5 % |
| deficit_mm | 2014–2025 | 4252 | 3,43 | 1,326 | 8,28 | 14,9 % |
| nm7q | 1992–2001 | 3576 | 47,96 | 1,069 | 66,39 | 0,08 % |
| nm7q | 2002–2013 | 4295 | 43,26 | 1,051 | 61,59 | 0,07 % |
| nm7q | 2014–2025 | 4252 | 38,78 | 0,833 | 54,79 | 0,21 % |

**Die relevante Aussage laut Spezifikation: Verschiebung von Mittel *und* Extremschwanz,
nicht symmetrisch.** Der Median `days_below` verneunfacht sich fast von 5–6 Tagen
(1992–2013) auf 45 Tage (2014–2025) — eine Verschiebung des typischen Jahres, nicht
nur der Ausreißer. Gleichzeitig wächst auch das P90 (48/57 → 127 Tage) und der Anteil
Nullwert-Jahre (keine einzige Unterschreitung) fällt von rund 37/36 % auf 15 % — die
Verteilung verschiebt sich insgesamt nach rechts, das mittlere Jahr wird „trockener"
und Jahre ganz ohne Niedrigwasser werden seltener. Das Mittel (16,1/19,0 → 55,7 Tage)
steigt relativ stärker als der Median, was auf zusätzlich schwerere Extremjahre in der
letzten Dekade hindeutet (konsistent mit den 2018/2019/2022-Extremen aus Abschnitt 1).
`nm7q` (m³/s, absolute Abflussgröße, nicht auf Fläche normiert — kleine Bäche und der
Rhein gehen mit demselben Gewicht ein) fällt in Mittel und Median über alle drei
Dekaden monoton; die relative Verschiebung ist geringer als bei `days_below`, weil
`nm7q` durch den absoluten Maßstab von großen Flüssen dominiert wird.

## 5. GEV-Extremwertanalyse (`index_deficit`, primary)

Nicht-stationäre GEV (`μ(t) = μ0 + μ1·t`, `σ`, `ξ` konstant) an die nationale
`index_deficit`-Zeitreihe (34 Werte, 1992–2025) gefittet, Likelihood-Ratio-Test der
Trendkomponente `μ1` gegen die stationäre GEV. Zwei Parametrisierungen:
`ξ`-beschränkt (`|ξ| ≤ 0,5`, numerisch stabil bei n=34) und frei (unrestringiert).
Quelle: `data/interim/trend/gev_deficit.parquet`.

| | bounded (ξ ≤ 0,5) | free (ξ unrestringiert) |
|---|---:|---:|
| ξ | 0,500 (am Rand der Schranke) | 1,049 |
| μ1 (Trendkoeffizient) | +0,00864/a | +0,00468/a |
| LR-Test p-Wert | 0,234 | 0,236 |
| RP für WY 2018 (1992, Fit-Anfang) | 34,8 Jahre | 12,5 Jahre |
| RP für WY 2018 (2025, Fit-Ende) | 31,9 Jahre | 12,2 Jahre |
| Empirisches Weibull-RP (verteilungsfrei) | 35,0 Jahre | 35,0 Jahre |

**Der LR-Test ist bei n=34 in beiden Parametrisierungen nicht signifikant (p ≈ 0,23
sowohl bounded als auch free) — das wird hier als Ergebnis berichtet, nicht
dramatisiert.** Die ehrliche Aussage: **Es gibt bei 34 Jahren Datenbasis keinen
statistisch gesicherten Nachweis einer Nicht-Stationarität in der
Extremwertverteilung von `index_deficit` (GEV-Lageparameter).** Der in Abschnitt 2
gezeigte, robuste Trend in `index_deficit` (TFPW-MK, p=0,0025 über alle vier
Varianten) ist ein Trend im *typischen* Jahresverlauf der Kennzahl, kein signifikant
nachgewiesener Trend in der *Extremverteilung* — beide Aussagen sind methodisch
unterschiedlich und dürfen nicht vermischt werden. Bei n=34 ist die statistische
Power für einen GEV-Trendtest (4 Parameter für die nicht-stationäre, 3 für die
stationäre Variante, gefittet an 34 Werten) grundsätzlich gering; ein
nicht-signifikantes Ergebnis ist bei dieser Stichprobengröße nicht überraschend und
sollte nicht als „kein Trend" fehlinterpretiert werden — korrekt ist „kein
statistisch abgesicherter Nachweis bei dieser Stichprobengröße".

Zur Wiederkehrintervall-Punktschätzung für Wasserjahr 2018 (`index_deficit`=5,77 mm,
der höchste Wert der Reihe): **die Schätzung ist stark parametrisierungsabhängig
(12–35 Jahre je nach ξ-Behandlung und Fit-Zeitpunkt) und wird hier bewusst nicht als
belastbare Einzelzahl verkauft.** Der bounded-Fit (ξ=0,5, exakt am Rand der
Schranke — ein Hinweis, dass die Schranke selbst die Schätzung trägt) liefert
RP≈32–35 Jahre, nahe am verteilungsfreien empirischen Weibull-RP von 35,0 Jahren
(Rang 1 von 34 Werten plus Buchhaltungs-Eins: `(34+1)/1`). Der unrestringierte Fit
(ξ≈1,05, deutlich außerhalb des für Abflussextreme physikalisch plausiblen Bereichs)
liefert dagegen RP≈12 Jahre. Dass ξ im bounded-Fit exakt an der 0,5-Schranke
gefunden wird und im freien Fit auf über 1,0 wegläuft, zeigt, dass 34 Jahre zu wenig
Information enthalten, um den Formparameter der Extremwertverteilung verlässlich zu
schätzen — die Punktschätzung reagiert empfindlich auf eine Modellentscheidung
(Schranke ja/nein), die inhaltlich nicht aus den Daten selbst folgt. Die belastbare
Aussage ist daher ausschließlich die verteilungsfreie: **2018 war (Stand 2025) das
Jahr mit dem höchsten `index_deficit` in einer 35-jährigen Reihe**, keine
GEV-gestützte Vorher/Nachher-Wiederkehrintervall-Aussage im Sinne von „unter dem
Klima der 90er ein X-Jahres-Ereignis, heute ein Y-Jahres-Ereignis" — dafür reicht die
Datenbasis (n=34, nicht-signifikanter LR-Test) nicht aus.

## 6. Sensitivitätsfazit

Fünf Sensitivitätsläufe gegen den Hauptlauf verglichen — drei metrik-basierte
(Referenzperiode WMO 1991–2020 statt fix 1992–2011; Inter-Event-Kriterium 3/7 statt
5 Tage; `out/sensitivity.csv`) und zwei Flags-Läufe (Abschnitt 6a;
`out/sensitivity_flags.csv`); Details und Einordnung in `methods.md` Abschnitt
„Sensitivitätsanalysen":

- **Vorzeichen- und Signifikanz-stabil über alle Läufe**: `index_days`/
  `index_deficit` bleiben increasing, `index_ssi` bleibt decreasing, alle p < 0,05,
  in main/pool3/pool7/refwmo.
- `pool3`/`pool7` sind für die drei nationalen Indizes strukturell identisch zu
  `main` (das Inter-Event-Kriterium wirkt nur auf `max_spell`, nicht auf die in
  `national_index` verwendeten Kennzahlen).
- Die stations-`max_spell`-Sensitivität (die einzige Kennzahl, die das
  Pooling-Fenster tatsächlich prüft) bleibt robust: 61,3 %/63,2 %/61,8 % signifikant
  steigend über main/pool3/pool7, Median-Sen-Slope 0,50–0,62.
- `refwmo` zeigt niedrigere absolute Sen-Slopes bei gleichbleibender Richtung und
  Signifikanz — plausibel durch niedrigere Schwellenwerte (die WMO-Referenzperiode
  1991–2020 schließt die niedrigwasserreichen 2010er/2020er in die Schwellenbildung
  ein), keine Abweichung in der Kernaussage.

### 6a. Flags-Sensitivität (naturnahes Subset)

Zwei zusätzliche Läufe klammern die Homogenitäts-Flags — den bis dahin größten
ungetesteten Hebel der Analyse — von beiden Seiten ein (`out/sensitivity_flags.csv`,
Konstruktion in `methods.md`, Abschnitt „Flags-Sensitivität"; Aufruf
`uv run python scripts/sensitivity.py --flags-only`): **`flagslax`** entfernt die 30
mit `unsicher:` markierten Flag-Zeilen (205 → 175), **`flagsstrict`** schließt
zusätzlich das sonst nur hinweisende `erosion`-Flag aus. Verglichen wird ausschließlich
die Variante `natural` — `primary` ist per Konstruktion flags-unabhängig, was der Lauf
verifiziert hat (`national_index_primary.parquet` beider Läufe identisch zum Hauptlauf).

| Lauf          | n_natural (Screening) | n_stations (`natural`-Index) | index_days | index_deficit | index_ssi |
|---------------|-----------------------|------------------------------|------------|---------------|-----------|
| `main`        | 236 / 360             | 99–107                       | increasing, p=0,00011, Sen=+1,344 | increasing, p=0,0011, Sen=+0,0544 | decreasing, p=0,0267, Sen=−0,0392 |
| `flagslax`    | 245 / 360             | 106–115                      | increasing, p=0,0015, Sen=+0,789  | increasing, p=0,00086, Sen=+0,0331 | decreasing, p=0,0081, Sen=−0,0320 |
| `flagsstrict` | 233 / 360             | 97–105                       | increasing, p=0,00013, Sen=+1,371 | increasing, p=0,0012, Sen=+0,0537 | decreasing, p=0,0267, Sen=−0,0382 |

Die Spalte `n_stations` ist eine **Spanne über die Wasserjahre 1992–2025**, nicht eine
feste Stationszahl — je Jahr fällt unterschiedlich viel Reihe durch das Vollständigkeits-
Kriterium.

**Vorzeichen und Signifikanz sind über alle drei Flags-Varianten stabil**: `index_days`
und `index_deficit` bleiben in jedem Lauf signifikant steigend, `index_ssi` signifikant
fallend, alle p < 0,05 — die Trendaussage des naturnahen Subsets hängt also nicht an den
strittigen Flags. Das absolute Niveau tut es allerdings deutlich: `flagsstrict` liegt
praktisch auf dem Hauptlauf (nur 3 Stationen fallen weg), während `flagslax` die
`index_days`-Sen-Slope um rund 41 % senkt (+1,344 → +0,789). Der Grund ist nicht
statistisches Rauschen, sondern die Struktur der Stationen, die tatsächlich kippen:
`flagslax` nimmt neun zusätzliche Stationen auf, und **92,6 % der dadurch hinzukommenden
Fläche entfallen auf nur vier davon** (126.522 von 136.664 km² inkrementeller Fläche) —
allesamt große grenzüberschreitende Ströme, deren Regulierung im Ausland liegt: Oder bei
Hohensaaten-Finow (109.564 km²) und Eisenhüttenstadt (52.033 km²), Mosel bei Cochem
(27.088 km²) und Perl (11.522 km²). Die übrigen fünf (Salzach/Burghausen, zweimal Lippe,
Lausitzer Neiße, Brigach) tragen zusammen nur rund 10.000 km² bei. Lässt man die neun
zu, verdreifacht sich die flächengewichtete Coverage des naturnahen Index
(64.602–71.177 km² → 201.266–207.841 km²), und die vier Grenzströme dominieren ihn.
`flagslax` ist damit kein „etwas größeres" Subset, sondern ein qualitativ anderes; die
konservative Voreinstellung (unsichere Flags gelten) ist die begründetere Wahl.

**Fazit: Die drei nationalen Trendaussagen (index_days/index_deficit steigend,
index_ssi fallend) sind robust gegenüber den geprüften Methodenentscheidungen**
(Referenzperiode, Pooling-Fenster, Nesting-Behandlung, naturnah vs. alle Stationen,
Homogenitäts-Flags lax/strikt).

## 7. Bekannte Limitationen (konsolidiert)

- **Restverschachtelung / Senken-Klassifikation**: 152 von 191 Senken-Stationen sind
  als „nested" klassifiziert (Fläche bereits im jeweiligen Basin-Auslass enthalten)
  und werden in der maßgeblichen `primary`-Variante ausgeschlossen. Diese
  Klassifikation beruht auf der in `docs/topologie-report.md` dokumentierten
  Kategorisierung (5 outlet / 34 standalone / 152 nested); Fehlklassifikationen
  einzelner Grenzfälle sind nicht auszuschließen, die `allsinks`-Sensitivität zeigt
  aber, dass die Kernaussage robust gegenüber dieser Entscheidung ist (Abschnitt 2).
  Nicht jede Station ist an das Netz angeschlossen — Hauptstromgewässer ohne
  deutschen Empfänger (Rhein, Elbe, Oder, Weser, Donau) sowie Zubringer ohne
  gepegelten Empfängerfluss bleiben bewusst Senken, wodurch `Σ a_incremental` über
  allen Stationen die Fläche Deutschlands übersteigen kann (siehe „Topologie-
  Konstruktion" in `methods.md`). **Materialität in km²:** Die 152 `nested`-Senken
  tragen 53.110 km² Brutto-Einzugsgebietsfläche (netto, nach Abzug der Flächen ihrer
  jeweiligen Oberlieger: 52.483 km² inkrementelle Fläche), von Σ 572.694 km²
  inkrementeller Fläche über die volle Stationstopologie (361 Stationen, vor
  Screening) — entsprechend **~9 % der Gesamt-Topologiefläche** bzw. **~10–12 % der
  jahresabhängigen `primary`-Coverage** (453.778–511.744 km²) als quantifiziertes
  Doppelzählungsrisiko, würden sie zusätzlich zu ihrem jeweiligen Basin-Auslass
  gezählt.
- **Flags-Unsicherheit (Homogenitäts-Screening)**: Das naturnahe Subset (236/360
  Stationen vor, 99–107 nach dem Trend-Fenster-Filter je Jahr) beruht auf
  Rechercheflags (`reservoir`/`transfer`/`mining`/`erosion`) mit dokumentierter, aber
  nicht lückenloser Quellenlage je Station (`docs/homogenitaet-recherche.md`).
  Einzelne Flags könnten bei genauerer Prüfung anders ausfallen — die
  Flags-Sensitivitätsläufe `flagslax`/`flagsstrict` (Abschnitt 6a) zeigen, dass
  Vorzeichen und Signifikanz das aushalten, das absolute Slope-Niveau des naturnahen
  Index aber nicht (rund −41 % bei `index_days`, wenn die unsicheren Flags fallen); die
  naturnahe Coverage-Fläche (64.602–71.177 km², 12,8–15,5 % der `primary`-Fläche je nach
  Jahr) ist zudem so klein und geografisch selektiv, dass sie nicht als unabhängige,
  repräsentative Validierungsstichprobe für ganz Deutschland gelten kann — nur als
  richtungsbestätigende Zusatzevidenz (Abschnitt 2).
- **1991 als Datenrand / Beginn der Zeitreihe**: NIWIS liefert ab dem 1.1.1991, das
  Wasserjahr 1991 beginnt aber am 1.11.1990. Ihm fehlen November und Dezember 1990
  vollständig: 304 statt 365 Tage. Als unvollständiges Jahr ist es mit den übrigen
  nicht vergleichbar und wird aus allen Trendtests ausgeschlossen (Fenster 1992–2025,
  n=34). Der Schnitt ändert den Trend sichtbar — ohne ihn zieht der 1991-Wert den
  TFPW-MK vor allem bei `index_ssi` Richtung „no trend" (Kommentar `F1` in
  `src/niedrigwasser/stages/trend.py`) —; das ist seine Wirkung, nicht seine
  Begründung. Die Zeitreihe selbst beginnt damit real erst 1992 für
  alle hier berichteten Trend- und Dekadenkennzahlen; eine längere Vorperiode (z. B.
  über GRDC) wurde in der Spezifikation als offene Frage benannt, aber nicht umgesetzt.
- **GEV-Stichprobengröße**: 34 Jahreswerte sind für eine 3–4-Parameter-GEV-Anpassung
  eine kleine Stichprobe; der Formparameter ξ ist entsprechend instabil (0,5 bounded
  vs. 1,05 free), die Wiederkehrintervall-Punktschätzung für 2018 schwankt je nach
  Parametrisierung zwischen 12 und 35 Jahren (Abschnitt 5). Der LR-Test für
  Nicht-Stationarität ist nicht signifikant (p≈0,23) — dies ist bei n=34 ein Power-
  Problem, kein belastbarer Nicht-Befund über die tatsächliche Stationarität der
  Extremverteilung.
- **NIWIS-Datenqualität (Sentinel-Werte)**: `-777`-Sentinels (Fehl-/Unplausibelwerte)
  wurden per Fix in `normalize_discharge` als `null` behandelt statt als Tiefstwerte
  eingerechnet (siehe „Sentinel-Behandlung im Ingest" in `methods.md`); der Fix wurde
  gegen die Zahlen des CORRECTIV-Fluss-Atlas validiert und verbessert die
  Übereinstimmung, schließt aber nicht aus, dass weitere,
  unerkannte Datenqualitätsprobleme in den NIWIS-Rohdaten verbleiben.
- **Keine Kausalanalyse**: Die Ergebnisse zeigen einen statistisch robusten Trend in
  Niedrigwasserkennzahlen, keine Attribution auf Klimawandel, Landnutzung oder
  Wassernutzung — das war nicht Gegenstand dieser Auswertung.

## 8. Konsistenz-Check

Stichprobenartig gegen die Quelldateien nachgerechnet, u. a.:
- `out/national_index.csv` Zeile WY2018: `index_days=93.4935431784061`,
  `index_deficit=5.772039498732856`, `index_ssi=-1.8738545538448688` — identisch zu
  `data/interim/trend/gev_deficit.parquet` (`value=5.772039498732856` für
  `target_year=2018`).
- `out/sensitivity.csv` main-Zeile `index_ssi`: p=0,0365, Sen=−0,0310 — identisch zu
  `data/interim/trend/national_trends.parquet` Variante `primary`/Metrik `index_ssi`.
- `out/station_trends.csv`: `224/359=62,4%` signifikant steigende `days_below`,
  `222/359=61,8%` signifikant fallende `nm7q`, `250/359=69,6%` `min_year≥2018` — direkt
  aus der CSV nachgezählt (`polars`-Filter über die Spalten dieser Datei).
  Nach BH-FDR (Spalten `days_below_p_fdr` / `nm7q_p_fdr`, gleiche Filter):
  `211/359=58,8%` bzw. `197/359=54,9%`.
- Dekaden-Median `days_below`: 5,0 → 6,0 → 45,0 — direkt aus
  `data/interim/trend/decade_stats.parquet` gelesen, keine Rundungsdifferenz zur
  Quelle.

## 9. Darstellung (Phase 5)

Die Ergebnisse dieses Dokuments sind zusätzlich als interaktive, self-contained
Ergebnisseite unter `site/index.html` aufbereitet (Heatmap, nationale Zeitreihe,
Dekaden-Verteilungen, Stationskarte, Methodik-Abschnitt — Kennzahl-Definition und
bewusste Darstellungs-Entscheidungen: „Phase 5: Darstellung" in `methods.md`) sowie als
statische Grafiken unter `out/figures/heatmap.png` (Anteil Stationen unter Q95 je Tag
und Wasserjahr) und `out/figures/ridgeline.png` (Dekaden-Verteilung von `days_below`).
Beide Darstellungen ziehen ihre Zahlen unverändert aus denselben Quelldateien wie dieses
Dokument (`out/national_index.csv`, `out/station_trends.csv`,
`data/interim/trend/decade_stats.parquet`) — keine im Frontend neu berechneten
Statistiken.
