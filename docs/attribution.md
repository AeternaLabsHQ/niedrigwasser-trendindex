# Datenquellen und Attribution

**Generierte Datei** — erzeugt von `scripts/build_attribution.py` aus den Feldern `license` und `source` der `stations`-Tabelle in `data/niedrigwasser.duckdb`. Nicht von Hand bearbeiten; nach Datenänderungen `uv run python scripts/build_attribution.py` neu laufen lassen.

Die Abfluss-Tageswerte kommen über die NIWIS-API der Bundesanstalt für Gewässerkunde (BfG), die 361 Messstellen selbst werden von den zuständigen Bundes- und Landesbehörden betrieben. **Es gibt keine einheitliche Lizenz für den Gesamtdatensatz** — maßgeblich ist immer die Lizenz der jeweiligen Station.

## Lizenzen im Stationsbestand

| Lizenz | Stationen | Namensnennung | Share-Alike |
|---|---:|---|---|
| `dl-zero-de/2.0` — [Datenlizenz Deutschland - Zero - Version 2.0](https://www.govdata.de/dl-de/zero-2-0) | 140 | nein | nein |
| `dl-by-de/2.0` — [Datenlizenz Deutschland - Namensnennung - Version 2.0](https://www.govdata.de/dl-de/by-2-0) | 115 | ja | nein |
| `cc-by/4.0` — [Creative Commons Namensnennung 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) | 99 | ja | nein |
| `cc by-sa 3.0` — [Creative Commons Namensnennung - Weitergabe unter gleichen Bedingungen 3.0 (CC BY-SA 3.0)](https://creativecommons.org/licenses/by-sa/3.0/) | 5 | ja | ja |
| `dl-de/by-2-0` — [Datenlizenz Deutschland - Namensnennung - Version 2.0](https://www.govdata.de/dl-de/by-2-0) | 2 | ja | nein |
| **Summe** | **361** | | |

## Lizenz × Betreiber

`source` ist der Betreiber-Kurzname, wie ihn NIWIS ausliefert — Schreibweisen werden bewusst unverändert übernommen (das sächsische LfULG/LHWZ erscheint deshalb in mehreren Varianten).

| Lizenz | Betreiber (`source`) | Stationen |
|---|---|---:|
| `dl-zero-de/2.0` | LANUV NRW | 46 |
| `dl-zero-de/2.0` | LfU Brandenburg | 15 |
| `dl-zero-de/2.0` | HLNUG | 13 |
| `dl-zero-de/2.0` | WSA Elbe | 12 |
| `dl-zero-de/2.0` | WSA Weser | 11 |
| `dl-zero-de/2.0` | WSA Rhein | 9 |
| `dl-zero-de/2.0` | WSA Spree-Havel | 8 |
| `dl-zero-de/2.0` | LUA | 5 |
| `dl-zero-de/2.0` | WSA Mosel-Saar-Lahn | 5 |
| `dl-zero-de/2.0` | WSA Donau MDK | 3 |
| `dl-zero-de/2.0` | WSA Ems-Nordsee | 3 |
| `dl-zero-de/2.0` | WSA Main | 3 |
| `dl-zero-de/2.0` | WSA Oberrhein | 3 |
| `dl-zero-de/2.0` | WSA Oder-Havel | 3 |
| `dl-zero-de/2.0` | WSA Neckar | 1 |
| `dl-by-de/2.0` | TLUBN | 61 |
| `dl-by-de/2.0` | LfULG LHWZ | 29 |
| `dl-by-de/2.0` | LHW LSA | 19 |
| `dl-by-de/2.0` | LfULG_LHWZ | 3 |
| `dl-by-de/2.0` | LFULG LHWZ | 1 |
| `dl-by-de/2.0` | LfULG – LHWZ | 1 |
| `dl-by-de/2.0` | SenUMVK | 1 |
| `cc-by/4.0` | LfU BY | 51 |
| `cc-by/4.0` | LUBW | 26 |
| `cc-by/4.0` | LfU RP | 22 |
| `cc by-sa 3.0` | LUNG MV | 5 |
| `dl-de/by-2-0` | LLUR | 2 |

## Namensnennungspflicht

**221 von 361 Stationen** stehen unter einer Lizenz mit Namensnennungspflicht. Aufschlüsselung:

- `dl-by-de/2.0`: 115 Stationen
- `cc-by/4.0`: 99 Stationen
- `cc by-sa 3.0`: 5 Stationen
- `dl-de/by-2-0`: 2 Stationen

Wer einzelne Stationsreihen oder daraus abgeleitete Werte weiterverwendet, muss den jeweiligen Betreiber aus der Tabelle oben nennen — eine pauschale Quellenangabe „NIWIS/BfG“ genügt für diese Stationen nicht. Die Grafiken und die Ergebnisseite dieses Projekts führen die Quellenzeile (`SOURCE_LINE` in `src/niedrigwasser/stages/render.py`) entsprechend mit.

## Share-Alike: Stationen unter CC BY-SA 3.0

5 Stationen stehen unter [Creative Commons Namensnennung - Weitergabe unter gleichen Bedingungen 3.0 (CC BY-SA 3.0)](https://creativecommons.org/licenses/by-sa/3.0/) — Betreiber: LUNG MV (Landesamt für Umwelt, Naturschutz und Geologie Mecklenburg-Vorpommern).

| Station-ID | Name | Gewässer | Betreiber (Namensnennung) |
|---|---|---|---|
| `DESM_DEMV58110.0` | Bolt | Bolter Kanal | LUNG MV |
| `DESM_DEMV59810.0` | Garlitz | Sude | LUNG MV |
| `DESM_DEMV04408.1` | Groß Görnow | Warnow | LUNG MV |
| `DESM_DEMV04803.5` | Klempenow_Straßenbrücke | Tollense | LUNG MV |
| `DESM_DEMV04907.1` | Pasewalk Bollwerk | Uecker | LUNG MV |

**Konsequenz für Ableitungen:** Die aus diesen Stationen abgeleiteten Reihen — Kennzahlen in `out/`, die Stationseinträge in `site/data.json` und alles, was daraus sichtbar wird — unterliegen den Share-Alike-Bedingungen. Wer sie publiziert oder weiterverarbeitet, muss das Ergebnis unter einer CC-BY-SA-kompatiblen Lizenz weitergeben und LUNG MV als Quelle nennen. Für die 356 übrigen Stationen gilt diese Pflicht nicht; die aggregierten Bundeskennzahlen beruhen auf allen Stationen gemeinsam.

## Weitere Quellen

- **Kartengrundlage:** [Natural Earth](https://www.naturalearthdata.com/) 10m (Landesumriss, Bundeslandgrenzen, Flussachsen), gemeinfrei (public domain). Abgeleitet und vereinfacht durch `scripts/fetch_geodata.py` nach `site/geo.json`.
