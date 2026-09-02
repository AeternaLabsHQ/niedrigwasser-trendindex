# Recherche: Auslandsanteile der Einzugsgebiete an den fünf Basin-Auslässen

**Stand / Abrufdatum aller Quellen: 2026-08-25**
**Ergebnisdatei:** `config/basin_domestic_area.csv`

## Warum diese Recherche

Der aggregierte Index (`primary`-Set) gewichtet die pro Jahr verfügbaren
**192–208 nicht-verschachtelten Stationen** mit inkrementellen Einzugsgebietsflächen
(`a_incremental`). Die abgedeckte Fläche ist deshalb **jahresabhängig und liegt zwischen
453.778 und 511.744 km²/Jahr** (siehe `docs/ergebnisse-phase4.md`). Schon das **Maximum von
511.744 km²** übersteigt die Fläche Deutschlands (**357.600 km²**) um rund 154.000 km².

Der Grund ist kein Fehler in der Topologie, sondern eine Eigenschaft der Daten: die fünf
Basin-Auslässe (Rhein/Rees, Elbe/Wittenberge, Oder/Hohensaaten-Finow, Donau/Hofkirchen,
Weser/Intschede) bringen — verteilt über ihre jeweilige Pegelkette — die **vollständigen**
Einzugsgebiete ihrer Ströme in die Gewichtungsmasse ein, und diese reichen weit ins Ausland.

Zusammensetzung der maximalen Coverage:

| Block | km² |
|---|---:|
| Summe `a_incremental` über die fünf Basin-Ketten (= Summe der fünf Pegel-EZG) | 477.634 |
| Rest-Term: `standalone`-Senken mit Daten im betreffenden Jahr | 34.110 |
| **Coverage-Maximum** | **511.744** |

> **Wichtig:** Das ist eine Aussage über **Becken**, nicht über einzelne Stationen. Der Pegel
> Hohensaaten-Finow selbst bekommt im Index nicht 109.564 km² Gewicht, sondern seine
> Inkrementalfläche `a_incremental = 57.531 km²`; der Rest des Oder-EZG verteilt sich auf die
> übrigen Pegel der Oder-Kette. Analog: Rees 307 km², Wittenberge 1.939 km², Hofkirchen
> 9.743 km², Intschede 878 km². Die Summe über die jeweilige Kette ergibt das Pegel-EZG.
> (Nachgerechnet aus `data/interim/topology/stations_topology.parquet` +
> `config/sink_categories.csv`.)

Anlass war eine externe Methodenkritik: den Auslandsanteil beziffern statt ihn nur
zu erwähnen.
Diese Recherche liefert für jeden der fünf Auslässe einen **belegten deutschen Flächenanteil
bis zum jeweiligen Pegel** — und quantifiziert zusätzlich den Auslandsanteil im Rest-Term.

## Methodik und Konvention

Es gibt praktisch keine Quelle, die "deutscher Flächenanteil am Einzugsgebiet bis Pegel X"
direkt ausweist. Alle amtlichen Quellen geben entweder (a) Länderanteile am **Gesamt**flussgebiet
oder (b) Flächen der WRRL-**Bearbeitungsgebiete**. Die Werte in der CSV sind deshalb *abgeleitet* —
nach folgenden zwei Regeln:

1. **Ableitung über das Ausland, nicht über das Inland.** Für den Pegel gilt
   `EZG(Pegel) = Inland_oberhalb + Ausland_oberhalb`. Wenn sich zeigen lässt, dass der
   **gesamte** Auslandsanteil eines Stroms oberhalb des Pegels liegt, ist
   `Inland_oberhalb = EZG(Pegel) − Ausland_gesamt` **exakt** — unabhängig davon, wie groß der
   deutsche Anteil unterhalb des Pegels ist. Das gilt für Rhein und Elbe.
2. **Sonst: dokumentierte obere Schranke für `domestic_km2`.** Wo die Lage einzelner Teilflächen
   relativ zum Pegel nicht belegbar ist (Oder) oder wo kleine Auslandsanteile nicht quantifizierbar
   sind (Donau), wird `domestic_km2` bewusst als **obere Schranke** gesetzt. Das ist in beide
   relevante Richtungen konservativ:
   - Der ausgewiesene **Auslandsanteil** (`EZG − domestic`) wird dadurch zur **unteren Schranke** —
     eine Aussage "mindestens X km² liegen im Ausland" ist damit verteidigbar.
   - Der **Plausibilitätscheck** (Σ Inland ≤ Fläche Deutschlands) wird dadurch zum
     **schärfsten** Test.

Wikipedia wurde nur als Wegweiser benutzt; jede Zahl unten stammt aus einer amtlichen bzw.
kommissionellen Primärquelle (IKSR, IKSE, IKSO/FGG Oder, BfG, HND Bayern, FGG Donau).

---

## Rhein — Pegel Rees (DESM_DEXX2790010)

**EZG laut NIWIS: 159.300 km² — bestätigt.**

BfG/Undine, Pegelstammdaten Rees: Einzugsgebietsgröße 159.300 km², Lage Rhein-km **837,4**
(gerechnet ab Rheinbrücke Konstanz), MQ 2.260 m³/s.
<https://undine.bafg.de/rhein/pegel/rhein_pegel_rees.html> (Abruf 2026-08-25)

**Staatenanteile am Rheineinzugsgebiet** — IKSR, *Internationaler Bewirtschaftungsplan 2022–2027
für die IFGE Rhein*, Kapitel 1, Tabelle 2 ("Wichtigste Kenndaten der IFGE Rhein (Staaten)").
Ausgewiesen wird dort die Spalte *** = "Rheineinzugsgebiet (ohne Wattenmeer und Küstengewässer)"
mit **188.715 km²**:

| Staat | km² |
|---|---:|
| Deutschland | 105.751 |
| Niederlande | 25.452 |
| Schweiz | 27.835 |
| Frankreich | 23.831 |
| Luxemburg | 2.527 |
| Österreich | 2.386 |
| Belgien | 771 |
| Liechtenstein | 160 |
| Italien | 2 |
| **Summe** | **188.715** |

<https://www.iksr.org/fileadmin/user_upload/DKDM/Dokumente/BWP-HWRMP/DE/bwp_De_BWP_2021.pdf>
(Abruf 2026-08-25; die Einzelwerte summieren sich exakt auf die ausgewiesene Gesamtfläche.)

### Ableitung

Rees liegt bei Rhein-km 837,4; die deutsch-niederländische Grenze liegt bei rund km 865. Damit
liegen **alle** nicht-niederländischen Auslandsanteile des Rheineinzugsgebiets oberhalb von Rees:

- **Schweiz, Liechtenstein, Italien, Österreich** — Alpenrhein, Bodensee, Aare/Hochrhein: sämtlich
  oberhalb von Basel und damit weit oberhalb von Rees.
- **Frankreich** — Ill und elsässische Zuflüsse (Oberrhein) sowie der französische Anteil an
  Mosel/Saar/Meurthe: alle münden oberhalb von Koblenz bzw. Karlsruhe.
- **Luxemburg** — praktisch das gesamte Staatsgebiet entwässert über Sauer/Our in die Mosel,
  Mündung bei Koblenz (Rhein-km 592).
- **Belgien** — Quellgebiete von Our und Sauer in den Ardennen, ebenfalls über die Mosel.

Der **niederländische** Anteil (25.452 km²) liegt vollständig im Delta, also unterhalb Rees.

```
Ausland oberhalb Rees = 27.835 + 23.831 + 2.527 + 2.386 + 771 + 160 + 2 = 57.512 km²
domestic(Rees)        = 159.300 − 57.512                               = 101.788 km²
```

### Gegenprobe

Der deutsche Gesamtanteil am Rheineinzugsgebiet beträgt 105.751 km². Die Differenz
105.751 − 101.788 = **3.963 km²** müsste deutsche Fläche *unterhalb* von Rees sein. Genau das
passt zu den bekannten deutschen Teilgebieten im Delta-Rhein: deutscher Anteil an Vechte/Dinkel
(rd. 2.000 km²), deutscher Anteil an Issel/Bocholter Aa (rd. 1.400 km²) und der Uferstreifen
Rees–Grenze. Die Größenordnung stimmt; die Ableitung ist in sich konsistent.

**Konfidenz: hoch.** Unsicherheit im Bereich weniger 10er km² (winzige niederländische Parzellen
oberhalb Rees bei Elten wurden vernachlässigt).

---

## Elbe — Pegel Wittenberge (DESM_DEXX503050)

**EZG laut NIWIS: 123.532 km² — bestätigt.**

BfG/Undine, Pegelstammdaten Wittenberge: Einzugsgebietsgröße 123.532 km², Elbe-km **453,9**
(unterhalb Grenze D/CZ), MQ 669 m³/s.
<https://undine.bafg.de/elbe/pegel/elbe_pegel_wittenberge.html> (Abruf 2026-08-25)

**Staatenanteile am Elbeeinzugsgebiet** — IKSE-Flyer *Die Elbe und ihr Einzugsgebiet*,
Tabelle "Allgemeine Beschreibung der internationalen Flussgebietseinheit Elbe":

| Angabe | Wert |
|---|---:|
| Fläche des Einzugsgebiets der Elbe | 148.268 km² |
| Anteil Deutschland | 65,54 % = 97.175 km² |
| Anteil Tschechische Republik | 33,68 % = 49.937 km² |
| Anteil Österreich | 0,62 % = 919 km² |
| Anteil Polen | 0,16 % = 237 km² |

<https://www.ikse-mkol.org/fileadmin/media/user_upload/D/06_Publikationen/08_IKSE_Flyer/2015_IKSE-Flyer_Die_Elbe_und_ihr_Einzugsgebiet.pdf>
(Abruf 2026-08-25)

### Ableitung

Alle drei Auslandsanteile liegen im tschechischen Oberlauf und damit oberhalb der Grenze bei
Schöna (Elbe-km 0), also **rund 454 Flusskilometer oberhalb von Wittenberge**:

- **Tschechien** — gesamtes Gebiet von Elbe/Labe, Moldau/Vltava, Eger/Ohře oberhalb Schöna.
- **Österreich** — Lainsitz/Lužnice im Waldviertel, Zufluss zur Moldau; oberhalb Prag.
- **Polen** — kleine Quellgebiete in den Sudeten/Riesengebirge, die nach Süden zur tschechischen
  Elbe bzw. Iser/Jizera entwässern; ebenfalls oberhalb der Grenze.

```
Ausland gesamt = 49.937 + 919 + 237 = 51.093 km²   (alles oberhalb Wittenberge)
domestic(Wittenberge) = 123.532 − 51.093 = 72.439 km²
```

### Gegenprobe

Deutscher Gesamtanteil 97.175 km², davon 72.439 km² oberhalb Wittenberge → **24.736 km²**
deutsche Fläche unterhalb. Das deckt sich mit `148.268 − 123.532 = 24.736 km²`
(Elde, Sude, Jeetzel, Ilmenau, Oste, Stör, Tideelbe, Küstengewässer 2.558 km²). Beide Rechenwege
liefern denselben Wert — die Zerlegung ist widerspruchsfrei.

Wichtig für die Einordnung: Die **Havel** (rd. 24.100 km²) mündet bei Havelberg, Elbe-km 422,9 —
also *oberhalb* von Wittenberge — und ist im Pegel-EZG bereits enthalten.

**Konfidenz: hoch.**

---

## Oder — Pegel Hohensaaten-Finow (DESM_DEXX603080)

**EZG laut NIWIS: 109.564 km² — bestätigt.**

BfG/Undine, Pegelstammdaten Hohensaaten-Finow: Einzugsgebietsgröße 109.564 km²,
Oder-km **664,951**, Messstellennummer 6030800.
<https://undine.bafg.de/oder/pegel/oder_pegel_hohensaaten_finow.html> (Abruf 2026-08-25)

**Deutsche Flächenanteile** — *Aktualisierter Bewirtschaftungsplan für den deutschen Teil der
IFGE Oder 2021–2027*, Kap. 1.1.1 und Tabelle 1.1 ("Bearbeitungsgebiete mit deutschen Teilen in der
IFGE Oder", Flächen nach IKSO 2020):

| Bearbeitungsgebiet | Gesamt (km²) | davon Deutschland (km²) | DE-Anteil |
|---|---:|---:|---:|
| Stettiner Haff (STH) | 5.114 | 3.914 | 76 % |
| Untere Oder (UOD) | 10.913 | 3.689 | 34 % |
| Mittlere Oder (MOD) | 31.180 | 692 | 2 % |
| Lausitzer Neiße (LAN) | 4.386 | 1.403 | 32 % |
| **Summe DE** | | **9.698** | |

Gesamtfläche IFGE Oder 124.146 km²; davon Polen 107.208 km² (86 %), Tschechien 7.240 km² (6 %),
Deutschland 9.698 km² (8 %).
<https://mleuv-daten.brandenburg.de/w/kfge-oder/BWP-2021-27-deutscher-Teil/ODER-Bewirtschaftungsplan-2021-2027.pdf>
(Abruf 2026-08-25; Einstieg über <https://mluk.brandenburg.de/w/kfge-oder/BWP-2021-27-deutscher-Teil/>
leitet per 301 auf diese Adresse um. Die zuvor benutzte wasserblick-BfG-URL ist tot (404) und
wurde ersetzt; alle Zahlen wurden im hier verlinkten PDF erneut verifiziert.)

### Ableitung

Die Oder ist der Extremfall: Ihr Einzugsgebiet ist zu ~92 % polnisch/tschechisch, und der
deutsche Anteil ist ein schmaler Streifen westlich des Stroms.

Vom deutschen Gesamtanteil (9.698 km²) ist ein Teil **unterhalb** des Pegels bei Oder-km 664,95
sicher auszuschließen:

- **Bearbeitungsgebiet Stettiner Haff (3.914 km² deutsch)** umfasst laut Tabelle 1.1 ausdrücklich
  "das Einzugsgebiet von Ucker, Randow und Zarow". Diese Gewässer entwässern **direkt in das
  Stettiner Haff**, nicht in die Oder oberhalb Hohensaaten. → vollständig abziehen.

Sicher **oberhalb** des Pegels liegen:

- **Lausitzer Neiße (1.403 km² deutsch)** — die Neiße mündet bei Ratzdorf, Oder-km 542.
- **Mittlere Oder (692 km² deutsch)** — definiert als "Mündung Glatzer Neiße bis Mündung Warthe",
  endet also bei Kostrzyn (Oder-km 617,6).

Unklar ist die Aufteilung des Bearbeitungsgebiets **Untere Oder** (3.689 km² deutsch), das von der
Warthemündung (km 617,6) bis Trzebież reicht und damit den Pegel (km 664,95) *überspannt*. Es
enthält oberhalb des Pegels Oderbruch/Alte Oder und Finow, unterhalb Welse und unteres Odertal.
Eine amtliche Aufteilung dieser Fläche am Pegel wurde nicht gefunden.

Nach Regel 2 der Methodik wird die Untere Oder deshalb **vollständig dem Oberlauf zugeschlagen**:

```
domestic(Hohensaaten-Finow) ≤ 1.403 + 692 + 3.689 = 5.784 km²   (obere Schranke)
Ausland oberhalb Pegel      ≥ 109.564 − 5.784     = 103.780 km²  (untere Schranke)
```

**Bester Schätzwert:** rund **4.600 km²**. Der deutsche Anteil der Unteren Oder unterhalb des
Pegels (Welse rd. 700–800 km², unteres Odertal/Gartz/Schwedt) dürfte bei 1.000–1.200 km² liegen,
was 3.689 − ~1.100 ≈ 2.600 km² oberhalb ergäbe. Diese Schätzung ist jedoch **nicht belegt** und
steht daher nicht in der CSV.

**Konfidenz: mittel.** Bandbreite der Unsicherheit: `domestic` zwischen ~2.100 km² (falls die
gesamte Untere Oder unterhalb läge) und 5.784 km². Die Unsicherheit von ±1.800 km² ist gemessen
an der maximalen Gewichtungsmasse (511.744 km²) klein (0,35 %) und ändert die Kernaussage nicht:
**über 100.000 km² des Oder-Gewichts liegen in Polen und Tschechien.**

---

## Donau — Pegel Hofkirchen (DESM_DEXX10088003)

**EZG laut NIWIS: 47.518 km² — bestätigt.**

HND Bayern, Stammdaten Hofkirchen/Donau: Einzugsgebiet **47.517,80 km²**, Donau-km **2.256,86**,
Betreiber WSA Donau MDK.
<https://www.hnd.bayern.de/pegel/donau_bis_passau/hofkirchen-10088003/stammdaten> (Abruf 2026-08-25)

**Deutsches Donaueinzugsgebiet** — FGG Donau: "Das deutsche Donaueinzugsgebiet umfasst eine
Fläche von 56.200 km²" (rd. 7 % des Donaubeckens), davon Baden-Württemberg rd. 8.050 km²,
Bayern rd. 48.200 km².
<https://www.fgg-donau.bayern.de/die_donau/das_dt_einzugsgebiet/index.htm> (Abruf 2026-08-25)

**Österreichischer Lech-Anteil** — HND Bayern, Gebietsdaten Pegel Füssen/Lech:
Einzugsgebiet **1.416,20 km²**; die nächsten Oberlieger-Pegel sind **Lechaschau/Lech** (Tirol) und
**Vils (Lände)/Vils** (Tirol).
<https://www.hnd.bayern.de/pegel/iller_lech/fuessen-12001006/gebiet> (Abruf 2026-08-25)

### Ableitung

Entscheidend ist die Lage des Pegels: Hofkirchen liegt bei Donau-km 2.256,86, die **Inn-Mündung
bei Passau bei km ~2.225**. Der Pegel liegt also **oberhalb des Inn** — der große
österreichisch-schweizerische Inn/Salzach-Anteil (Engadin, Tirol, Salzburg) zählt **nicht** zum
Pegel-Einzugsgebiet. Das ist der Grund, warum die Donau hier — anders als es die Intuition nahelegt —
fast vollständig inländisch ist.

Belegbar oberhalb Hofkirchen im Ausland liegen:

- **Lech oberhalb Füssen: 1.416,2 km²**, praktisch vollständig in Vorarlberg/Tirol (Quellgebiet
  Lechquellengebirge; die Oberlieger-Pegel Lechaschau und Vils liegen in Österreich). Der Lech
  mündet bei Marxheim, Donau-km 2.404 — weit oberhalb Hofkirchen.

Nicht quantifiziert (und daher **nicht** abgezogen):

- **Breitach / Kleinwalsertal (Österreich)** — Quellast der Iller, rd. 100 km².
- **Chamb (Kouba) und Quellgebiete des Regen (Tschechien)** — grob 200–400 km².

```
domestic(Hofkirchen) ≤ 47.518 − 1.416 = 46.102 km²   (obere Schranke)
```

**Bester Schätzwert:** rund **45.700–45.800 km²**, wenn man die nicht belegten Klein-Anteile
(zusammen ~300–500 km²) mitzählt.

**Konfidenz: mittel.** Der Wert ist als obere Schranke sicher; der ausgewiesene Auslandsanteil
(1.416 km², ~3 % des Pegel-EZG) ist eine untere Schranke. Die absolute Unsicherheit (~400 km²)
ist für die Gesamtaussage irrelevant.

*Nebenbemerkung:* Der deutsche Anteil oberhalb Hofkirchen (rd. 46.000 km²) passt zum
FGG-Donau-Gesamtwert von 56.200 km² — die Differenz von rd. 10.000 km² entfällt auf das deutsche
Inn-Gebiet (Alz/Chiemsee, Salzach-Westufer, Rott, Mangfall) sowie auf Vils und Ilz, die alle
unterhalb von Hofkirchen münden.

---

## Weser — Pegel Intschede (DESM_DEXX49100101)

**EZG laut NIWIS: 37.720 km².** BfG/Undine nennt 37.718 km² (Weser-km 331,28 unterhalb
Zusammenfluss Werra/Fulda, MQ 317 m³/s). Differenz 2 km² — vernachlässigbar.
<https://undine.bafg.de/weser/pegel/weser_pegel_intschede.html> (Abruf 2026-08-25)

**Kein Auslandsanteil.** BfG/Undine, Wesergebiet: Das Einzugsgebiet umfasst rund 49.000 km²,
"Dieses Gebiet liegt vollständig in Deutschland". Die Anteile verteilen sich ausschließlich auf
Bundesländer: Niedersachsen 60,1 %, Hessen 18,4 %, Nordrhein-Westfalen 10,1 %, Thüringen 9,1 %,
dazu kleinere Anteile Sachsen-Anhalt, Bremen, Bayern.
<https://undine.bafg.de/weser/wesergebiet.html> (Abruf 2026-08-25)

### Ableitung

```
domestic(Intschede) = 37.720 km²   (= EZG, Auslandsanteil 0)
```

Die Weser ist der einzige der fünf Ströme ohne grenzüberschreitendes Einzugsgebiet. Sie ist
damit auch der einzige Auslass, dessen Gewicht im Index vollständig deutsches Gebiet abbildet.

**Konfidenz: hoch.**

---

## Der Rest-Term (34.110 km²) — NICHT vollständig im Inland

Der Task-Brief ging davon aus, dass die übrigen inkrementellen Flächen
(511.744 − 477.634 = 34.110 km²) "alle im Inland" liegen. **Das ist falsch.** Nachgeprüft an
`data/interim/topology/stations_topology.parquet` + `config/sink_categories.csv`:

Der Rest-Term besteht aus den `standalone`-Senken — 34 Stationen, die zu keinem der fünf
Basin-Auslässe entwässern (Σ Einzugsgebiet 41.950 km²; im Coverage-Maximum-Jahr sind davon
34.110 km² durch Daten belegt). Darunter sind **zwei alpine Senken mit großem Auslandsanteil**:

### Inn / Wasserburg (`DESM_DEBY18003004`, 11.960 km²)

Der Inn kommt aus dem Engadin (CH) und Tirol (AT). Am Pegel **Oberaudorf**, Inn-km 211,00 —
also unmittelbar nach dem Grenzübertritt — beträgt das Einzugsgebiet **9.713,20 km²**
(HND Bayern, Betreiber WWA Rosenheim).
<https://www.hnd.bayern.de/pegel/inn/oberaudorf-18000403/stammdaten> (Abruf 2026-08-25)

→ Auslandsanteil (CH + AT) rund **9.713 km²**, deutscher Anteil bis Wasserburg rund 2.247 km²
(Mangfall, Rosenheimer Becken). In `config/sink_categories.csv` ist die Station als `standalone`
geführt ("Inn muendet bei Passau unterhalb Donau/Hofkirchen"), in `config/station_flags.csv`
zusätzlich mit `reservoir` und `transfer` ("alpine Speicherkraftwerke im
oesterreichisch-schweizerischen …") — der Auslandsbezug ist im Projekt also bereits bekannt,
war nur nie in Fläche umgerechnet.

### Salzach / Burghausen (`DESM_DEBY18606000`, 6.655 km²)

Die Salzach ist bis Burghausen ganz überwiegend österreichisch (Pinzgau, Pongau, Salzburg);
HND nennt für den Pegel Burghausen ein EZG von 6.649 km². Der deutsche Anteil beschränkt sich
auf das Berchtesgadener Land und schmale Grenzstreifen: Berchtesgadener Ache, der deutsche Teil
der Saalach (die Saalach führt am Pegel **Unterjettenberg**, Saalach-km 26, bereits
**940,60 km²** — weit überwiegend österreichisches Gebiet des Pinzgau/Lofer)
sowie Sur und Götzinger Achen.
<https://www.hnd.bayern.de/pegel/inn/unterjettenberg-18642003/stammdaten>,
<https://www.hnd.bayern.de/pegel/inn/burghausen-18606000/gebiet> (Abruf 2026-08-25)

→ deutscher Anteil grob **700–1.200 km²**, Auslandsanteil damit rund **5.450–5.950 km²**;
Arbeitswert **5.700 km²**. Eine amtliche Aufteilung wurde nicht gefunden — dies ist die
schwächste Einzelzahl dieser Recherche.

### Weitere `standalone`-Senken

Systematisch durchgesehen (alle 34, sortiert nach Fläche). Nennenswert ist nur noch:

- **Rur / Stah (2.135 km²)** — Quellgebiet im belgischen Hohen Venn, Auslandsanteil grob 200 km².

Alle übrigen liegen vollständig in Deutschland, auch wenn sie Deutschland verlassen: Ems
(4.851), Niers (1.203), Urft (345), Wurm (311), Schwalm (253), Inde (232), Issel (258),
Bocholter Aa (242), Berkel (351), Dinkel (183) entwässern in die Niederlande bzw. über
Rur/Maas, ihr **Einzugsgebiet bis zum jeweiligen Pegel** ist aber deutsch. Ebenso
Uecker (1.431), Tollense (1.409), Warnow (788), Sude (713), Treene (481), Soholmer Au (342),
Wriezener Alte Oder (1.084), Welse (808), Karthane (285), Salzwedeler Dumme (194), Bolter
Kanal (3) sowie die bayerische Vils (1.440 — die zweite bayerische Vils, Dietldorf mit
1.101 km², ist `nested` und gehört nicht ins `primary`-Set), Isen (548), Rott (529), Ilz
(364), Wolfsteiner Ohe (371), Traun (376, Chiemgauer Traun — nicht die oberösterreichische)
und die Bodensee-Zuflüsse Schussen (782), Argen (648), Obere Argen (104), Seefelder Aach
(271).

Gegenprobe: Diese 31 Senken summieren sich auf **21.200 km²**; zusammen mit Rur/Stah
(2.135) sowie Inn/Wasserburg (11.960) und Salzach/Burghausen (6.655) aus dem Rest-Term
ergeben sich die 41.950 km² aller 34 `standalone`-Senken (`config/sink_categories.csv`).

Wichtig: Die alpinen Senken mit hohem Auslandsanteil **Tiroler Achen** (945 km²) und **Loisach**
(638 km²) sind in `config/sink_categories.csv` als `nested` geführt und gehören damit **nicht**
zum `primary`-Set — sie erhöhen den Auslandsanteil nicht.

### Bilanz des Rest-Terms

```
Ausland im Rest-Term ≈ 9.713 (Inn) + ~5.700 (Salzach) + ~200 (Rur/BE) ≈ 15.600 km²
                       Bandbreite ~15.300 – 16.100 km²
Inland im Rest-Term  ≈ 34.110 − 15.600                                ≈ 18.500 km²
```

**Vorbehalt:** Welche `standalone`-Senken in einem konkreten Jahr Daten haben, ergibt sich erst
aus dem Pipeline-Lauf. Die Rechnung oben unterstellt, dass Wasserburg und Burghausen im
Coverage-Maximum-Jahr enthalten sind (zusammen 18.615 km² von 34.110 km² — die beiden mit
Abstand größten `standalone`-Senken; die 7.840 km² Differenz zwischen 41.950 und 34.110 lassen
sich durch die kleineren Senken erklären). Fehlten sie, wäre der Auslandsanteil entsprechend
kleiner — und die Coverage ebenfalls.

---

## Plausibilitätscheck

Geforderte Bedingung aus der externen Methodenkritik (mit korrigierter Prämisse — der Rest-Term liegt
**nicht** vollständig im Inland, siehe oben):

> Σ `domestic_km2` über die 5 Auslässe + Inlandsanteil der übrigen inkrementellen Flächen
> muss ≤ 357.600 km² sein.

| Basin | EZG bis Pegel (km²) | Inland (km²) | Ausland (km²) | Auslandsanteil |
|---|---:|---:|---:|---:|
| Rhein / Rees | 159.300 | 101.788 | 57.512 | 36,1 % |
| Elbe / Wittenberge | 123.532 | 72.439 | 51.093 | 41,4 % |
| Oder / Hohensaaten-Finow | 109.564 | 5.784 | 103.780 | 94,7 % |
| Donau / Hofkirchen | 47.518 | 46.102 | 1.416 | 3,0 % |
| Weser / Intschede | 37.720 | 37.720 | 0 | 0,0 % |
| **Summe 5 Auslässe** | **477.634** | **263.833** | **213.801** | **44,8 %** |
| Rest-Term (`standalone`) | 34.110 | ~18.500 | ~15.600 | ~46 % |
| **Coverage-Maximum gesamt** | **511.744** | **~282.300** | **~229.400** | **~44,8 %** |

```
Σ domestic (5 Auslässe)              =  263.833 km²
+ Inland im Rest-Term                =  ~18.500 km²
-------------------------------------------------------
= erfasste deutsche Fläche           = ~282.300 km²
Fläche Deutschlands                  =  357.600 km²
-------------------------------------------------------
Differenz (nicht erfasstes Inland)   =  ~75.300 km²   → Check BESTANDEN (282.300 ≤ 357.600)
```

**Der Check ist bestanden, und zwar mit einer Reserve von rund 75.300 km².** Die Korrektur des
Rest-Terms macht den Check *leichter*, nicht schwerer: die linke Seite ist um rund 15.600 km²
kleiner als in der ursprünglichen Rechnung (297.943 km²). Die Reserve ist inhaltlich zu erwarten —
es gibt reichlich deutsche Fläche, die von keiner Station des `primary`-Sets erfasst wird, u. a.

- Elbe unterhalb Wittenberge (Tideelbe, Elde, Ilmenau, Oste, Stör): rd. 24.700 km²
- Weser unterhalb Intschede, Teile des Ems-Gebiets
- Küstengebiete Nord- und Ostsee (Eider, Trave, Peene, Schlei)
- Rhein unterhalb Rees (rd. 4.000 km²), Oder unterhalb Hohensaaten, Donau unterhalb Hofkirchen
- deutsches Inn-/Salzach-Gebiet unterhalb Wasserburg bzw. Burghausen
- alle Gebiete ohne Pegel im `primary`-Set (in schwächeren Jahren bis zu ~58.000 km² mehr,
  da die Coverage dann auf 453.778 km² fällt)

### Richtung der Schranken

Alle Unsicherheiten wurden so gelegt, dass die **Auslandszahl eine untere Schranke** ist:

- `domestic_km2` ist bei Oder und Donau eine **obere** Schranke → der daraus abgeleitete
  Auslandsanteil ist eine **untere** Schranke.
- Beim Rest-Term wurde nur belegtes bzw. gut begründbares Ausland gezählt (Inn exakt,
  Rur grob). Bei der Salzach liegt der Arbeitswert von 5.700 km² allerdings **in der
  Mitte** der Bandbreite 5.450–5.950 km², nicht am unteren Rand — die maximale Abweichung
  nach unten beträgt 250 km² und ist gegenüber der Oder-/Donau-Reserve (dort ist
  `domestic_km2` als obere Schranke angesetzt, was tausende km² Puffer schafft)
  vernachlässigbar.

Deshalb ist die zu kommunizierende Formulierung **"mindestens rund 229.000 km²"**, nicht
"genau 229.400 km²". Der wahre Wert liegt eher bei 230.000–232.000 km².

Zusätzliche Gegenprobe gegen die triviale Schranke aus dem Task-Brief: dort war als quellenfreies
Minimum "mindestens 511.744 − 357.600 ≈ 154.000 km² im Ausland" angesetzt. Die Recherche liefert
**mindestens ~229.400 km²** — deutlich mehr, aber in derselben Richtung. Kein Widerspruch.

## Fazit-Tabelle

| station_id | Basin / Pegel | EZG (km²) | `domestic_km2` | Charakter des Werts | Konfidenz |
|---|---|---:|---:|---|---|
| DESM_DEXX2790010 | Rhein / Rees | 159.300 | 101.788 | exakte Ableitung (gesamtes Ausland oberhalb) | hoch |
| DESM_DEXX503050 | Elbe / Wittenberge | 123.532 | 72.439 | exakte Ableitung (gesamtes Ausland oberhalb) | hoch |
| DESM_DEXX603080 | Oder / Hohensaaten-Finow | 109.564 | 5.784 | obere Schranke (Schätzwert ~4.600) | mittel |
| DESM_DEXX10088003 | Donau / Hofkirchen | 47.518 | 46.102 | obere Schranke (Schätzwert ~45.750) | mittel |
| DESM_DEXX49100101 | Weser / Intschede | 37.720 | 37.720 | exakt (kein Auslandsanteil) | hoch |

Ergänzend, außerhalb der fünf Auslässe (Rest-Term, alle 34 `standalone`-Senken, Σ 41.950 km²;
davon im Coverage-Maximum-Jahr 34.110 km² mit Daten belegt):

| Senke | Fläche (km²) | Inland (km²) | Ausland (km²) | Charakter |
|---|---:|---:|---:|---|
| Inn / Wasserburg | 11.960 | ~2.247 | **9.713** | belegt (Pegel Oberaudorf, HND) |
| Salzach / Burghausen | 6.655 | ~950 | **~5.700** | Schätzung, Bandbreite 5.450–5.950 |
| Rur / Stah | 2.135 | ~1.935 | ~200 | grobe Schätzung (Hohes Venn, BE) |
| übrige 31 Senken | 21.200 | 21.200 | 0 | vollständig inländisch |
| **Summe `standalone`** | **41.950** | **~26.330** | **~15.610** | |

Die 7.840 km² Differenz zwischen 41.950 km² und dem Rest-Term von 34.110 km² entfallen auf
`standalone`-Senken ohne Daten im betreffenden Jahr; sie liegen der Größe nach bei den kleineren,
durchweg inländischen Senken — der Auslandsbetrag von ~15.610 km² bleibt davon unberührt, der
Inlandsbetrag sinkt entsprechend auf ~18.500 km².

### Kernaussagen für die Darstellung

1. **Mindestens rund 229.000 km² — knapp 45 % der maximalen Gewichtungsmasse von 511.744 km² —
   liegen außerhalb Deutschlands.** In Jahren mit geringerer Coverage (bis hinunter auf
   453.778 km²) verschiebt sich der absolute Wert, die Größenordnung bleibt. Der Index ist damit
   kein reiner "Deutschland-Index", sondern gewichtet Niedrigwasser an Strömen, deren Wasser
   überwiegend aus dem Ausland kommt.
2. **Die Oder dominiert den Auslandsanteil**: allein 103.780 km² (45 % des gesamten
   Auslandsanteils) liegen in Polen und Tschechien. Formuliert wird das über das **Becken**,
   nicht über die Station: *Das Oder-Becken bringt sein gesamtes Einzugsgebiet von 109.564 km²
   in die Gewichtungsmasse ein — verteilt über die fünf Pegel der Oder-Kette —, obwohl höchstens
   rund 5 % davon deutsches Gebiet sind.* (Der Pegel Hohensaaten-Finow selbst trägt
   `a_incremental = 57.531 km²`.)
3. **Umgekehrt erfasst der Index höchstens rund 282.000 km² deutscher Fläche — höchstens
   etwa 79 % Deutschlands.** Das ist das Spiegelbild der Ausland-Untergrenze: weil
   `domestic_km2` bei Oder und Donau als *obere* Schranke angesetzt ist, ist die deutsche
   Fläche eine obere und die Auslandsfläche eine untere Schranke. Auch als Obergrenze ist
   die Aussage ehrlich und gut belegbar.
4. **Die Donau ist die Ausnahme**: weil Hofkirchen oberhalb der Inn-Mündung liegt, ist ihr
   Auslandsanteil mit ~3 % minimal — anders als man es beim "internationalsten" Fluss Europas
   erwarten würde. Der große alpine Auslandsanteil steckt stattdessen in den beiden
   `standalone`-Senken Inn/Wasserburg und Salzach/Burghausen.

## Offene Punkte / Grenzen der Recherche

- **Oder, Bearbeitungsgebiet Untere Oder:** keine amtliche Aufteilung der deutschen 3.689 km² am
  Pegel Hohensaaten-Finow gefunden. Eine genauere Zahl wäre nur über eine GIS-Verschneidung der
  IKSO-Teileinzugsgebietsgrenzen mit dem Pegelstandort zu bekommen — das wäre der nächste Schritt,
  falls die Genauigkeit je gebraucht wird.
- **Donau:** die kleinen Auslandsanteile (Breitach/Kleinwalsertal, Chamb/Regen) sind in keiner
  auffindbaren Quelle mit Flächenangabe versehen. Der Effekt liegt bei ~0,1 % der
  maximalen Gewichtungsmasse.
- **Salzach / Burghausen:** keine amtliche Aufteilung des Einzugsgebiets nach D/AT gefunden.
  Die ~5.700 km² Ausland sind eine begründete Schätzung (Bandbreite 5.450–5.950 km²), gestützt
  auf das Saalach-EZG am Pegel Unterjettenberg (940,60 km², weit überwiegend österreichisch) und
  die bekannte Ausdehnung des Berchtesgadener Landes. Das ist die schwächste Einzelzahl dieser
  Recherche; sie betrifft rund 1,1 % der maximalen Gewichtungsmasse.
- **Zusammensetzung des Rest-Terms pro Jahr:** welche `standalone`-Senken in einem konkreten Jahr
  Daten liefern, ist ohne Pipeline-Lauf nicht bestimmbar. Die Aufteilung 34.110 = ~15.600 Ausland
  + ~18.500 Inland unterstellt, dass Wasserburg und Burghausen enthalten sind.
- **Quellen-URL Oder:** die ursprünglich benutzte Adresse
  `wasserblick.bafg.de/servlet/is/206126/BP-Oder-final.pdf` liefert inzwischen 404. Ersetzt durch
  die Brandenburger Fassung desselben Plans (mleuv-daten.brandenburg.de); alle zitierten Zahlen
  wurden dort erneut geprüft (124.146 / 107.208 / 9.698 / 3.914 / 3.689 / 692 / 1.403).
- **Bezugsjahre:** IKSR-Werte Stand 2022 (BWP 2022–2027), IKSE-Flyer Stand 2015, IKSO-Flächen
  Stand 2020, Pegel-Stammdaten BfG/HND laufend. Einzugsgebietsgrenzen ändern sich praktisch nicht;
  die Mischung der Stände ist unkritisch.
- **Flächendefinitionen:** Die IKSR-Zahl bezieht sich auf das *Rheineinzugsgebiet ohne* Wattenmeer
  und Küstengewässer (188.715 km²) — das ist die für unseren Zweck richtige Abgrenzung. Die oft
  zitierten 197.283 km² bzw. "ca. 200.000 km²" enthalten Küstengewässer bis zur 12-Meilen-Zone und
  wären hier falsch. Analog: IFGE Oder 124.146 km² enthält Haff und Küstengewässer, das
  hydrologische Odergebiet ist kleiner.
