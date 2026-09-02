"""Erzeugt docs/attribution.md aus den Lizenzangaben der stations-Tabelle.

Die NIWIS-Stationsdaten stehen NICHT unter einer einheitlichen Lizenz: jede
Messstelle bringt die Lizenz ihres betreibenden Landes-/Bundesamtes mit
(Spalten ``license`` und ``source`` in ``stations``). Dieses Skript liest die
DuckDB **read-only** und schreibt daraus die Attribution-Uebersicht, die bei
einer Veroeffentlichung des Projekts die Namensnennungs- und
Share-Alike-Pflichten belegt.

Deterministisch: sortierte Ausgabe, KEIN Zeitstempel im Ergebnis. Ein Lauf ohne
Datenaenderung erzeugt eine bit-gleiche Datei (leerer git-Diff).

Aufruf:  uv run python scripts/build_attribution.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

# Anzeigename + Lizenztext-URL je NIWIS-Lizenzstring. Die Strings kommen
# unveraendert aus der API (inkl. uneinheitlicher Schreibweise, z. B.
# "dl-by-de/2.0" vs. "dl-de/by-2-0" fuer dieselbe Datenlizenz Deutschland).
LICENSE_INFO: dict[str, tuple[str, str, bool, bool]] = {
    # key: (Anzeigename, URL, Namensnennung noetig, Share-Alike)
    "dl-zero-de/2.0": (
        "Datenlizenz Deutschland - Zero - Version 2.0",
        "https://www.govdata.de/dl-de/zero-2-0",
        False,
        False,
    ),
    "dl-by-de/2.0": (
        "Datenlizenz Deutschland - Namensnennung - Version 2.0",
        "https://www.govdata.de/dl-de/by-2-0",
        True,
        False,
    ),
    "dl-de/by-2-0": (
        "Datenlizenz Deutschland - Namensnennung - Version 2.0",
        "https://www.govdata.de/dl-de/by-2-0",
        True,
        False,
    ),
    "cc-by/4.0": (
        "Creative Commons Namensnennung 4.0 International (CC BY 4.0)",
        "https://creativecommons.org/licenses/by/4.0/",
        True,
        False,
    ),
    "cc by-sa 3.0": (
        "Creative Commons Namensnennung - Weitergabe unter gleichen "
        "Bedingungen 3.0 (CC BY-SA 3.0)",
        "https://creativecommons.org/licenses/by-sa/3.0/",
        True,
        True,
    ),
}

SHARE_ALIKE_LICENSE = "cc by-sa 3.0"


def _fetch(db_path: Path) -> tuple[list[tuple[str, str, int]], list[tuple[str, str, str, str]]]:
    """Liest (license, source, count) und die Share-Alike-Stationen read-only."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        pairs = con.execute(
            "select license, source, count(*) from stations group by 1, 2"
        ).fetchall()
        sa_rows = con.execute(
            "select station_id, name, river, source from stations "
            "where license = ? order by name, station_id",
            [SHARE_ALIKE_LICENSE],
        ).fetchall()
    finally:
        con.close()
    return [(str(a), str(b), int(c)) for a, b, c in pairs], [
        tuple(str(x) for x in row) for row in sa_rows  # type: ignore[misc]
    ]


def _info(license_key: str) -> tuple[str, str, bool, bool]:
    """Fallback fuer unbekannte Lizenzstrings: konservativ als pflichtig werten."""
    return LICENSE_INFO.get(
        license_key, (license_key, "", True, False)
    )


def _sort_licenses(counts: dict[str, int]) -> list[str]:
    # Haeufigste zuerst; bei Gleichstand alphabetisch -> deterministisch.
    return sorted(counts, key=lambda k: (-counts[k], k))


def build_markdown(
    pairs: list[tuple[str, str, int]], sa_rows: list[tuple[str, str, str, str]]
) -> str:
    per_license: dict[str, int] = {}
    per_pair: dict[str, list[tuple[str, int]]] = {}
    for lic, src, n in pairs:
        per_license[lic] = per_license.get(lic, 0) + n
        per_pair.setdefault(lic, []).append((src, n))

    total = sum(per_license.values())
    attrib_licenses = [k for k in per_license if _info(k)[2]]
    n_attrib = sum(per_license[k] for k in attrib_licenses)
    order = _sort_licenses(per_license)

    out: list[str] = []
    add = out.append

    add("# Datenquellen und Attribution")
    add("")
    add(
        "**Generierte Datei** — erzeugt von `scripts/build_attribution.py` aus den "
        "Feldern `license` und `source` der `stations`-Tabelle in "
        "`data/niedrigwasser.duckdb`. Nicht von Hand bearbeiten; nach Datenänderungen "
        "`uv run python scripts/build_attribution.py` neu laufen lassen."
    )
    add("")
    add(
        f"Die Abfluss-Tageswerte kommen über die NIWIS-API der Bundesanstalt für "
        f"Gewässerkunde (BfG), die {total} Messstellen selbst werden von den "
        "zuständigen Bundes- und Landesbehörden betrieben. **Es gibt keine "
        "einheitliche Lizenz für den Gesamtdatensatz** — maßgeblich ist immer die "
        "Lizenz der jeweiligen Station."
    )
    add("")

    # --- Uebersicht je Lizenz ---
    add("## Lizenzen im Stationsbestand")
    add("")
    add("| Lizenz | Stationen | Namensnennung | Share-Alike |")
    add("|---|---:|---|---|")
    for lic in order:
        name, url, attrib, sa = _info(lic)
        label = f"[{name}]({url})" if url else name
        add(
            f"| `{lic}` — {label} | {per_license[lic]} | "
            f"{'ja' if attrib else 'nein'} | {'ja' if sa else 'nein'} |"
        )
    add(f"| **Summe** | **{total}** | | |")
    add("")

    # --- Lizenz x Betreiber ---
    add("## Lizenz × Betreiber")
    add("")
    add(
        "`source` ist der Betreiber-Kurzname, wie ihn NIWIS ausliefert — "
        "Schreibweisen werden bewusst unverändert übernommen (das sächsische "
        "LfULG/LHWZ erscheint deshalb in mehreren Varianten)."
    )
    add("")
    add("| Lizenz | Betreiber (`source`) | Stationen |")
    add("|---|---|---:|")
    for lic in order:
        entries = sorted(per_pair[lic], key=lambda t: (-t[1], t[0]))
        for src, n in entries:
            add(f"| `{lic}` | {src} | {n} |")
    add("")

    # --- Pflichten ---
    add("## Namensnennungspflicht")
    add("")
    add(
        f"**{n_attrib} von {total} Stationen** stehen unter einer Lizenz mit "
        "Namensnennungspflicht. Aufschlüsselung:"
    )
    add("")
    for lic in _sort_licenses({k: per_license[k] for k in attrib_licenses}):
        add(f"- `{lic}`: {per_license[lic]} Stationen")
    add("")
    add(
        "Wer einzelne Stationsreihen oder daraus abgeleitete Werte weiterverwendet, "
        "muss den jeweiligen Betreiber aus der Tabelle oben nennen — eine pauschale "
        "Quellenangabe „NIWIS/BfG“ genügt für diese Stationen nicht. Die Grafiken "
        "und die Ergebnisseite dieses Projekts führen die Quellenzeile "
        "(`SOURCE_LINE` in `src/niedrigwasser/stages/render.py`) entsprechend mit."
    )
    add("")

    # --- Share-Alike ---
    add("## Share-Alike: Stationen unter CC BY-SA 3.0")
    add("")
    sa_name, sa_url, _, _ = _info(SHARE_ALIKE_LICENSE)
    if sa_rows:
        operators = sorted({row[3] for row in sa_rows})
        add(
            f"{len(sa_rows)} Stationen stehen unter [{sa_name}]({sa_url}) — "
            f"Betreiber: {', '.join(operators)} "
            "(Landesamt für Umwelt, Naturschutz und Geologie Mecklenburg-Vorpommern)."
        )
        add("")
        add("| Station-ID | Name | Gewässer | Betreiber (Namensnennung) |")
        add("|---|---|---|---|")
        for sid, name, river, src in sa_rows:
            add(f"| `{sid}` | {name} | {river} | {src} |")
        add("")
        add(
            "**Konsequenz für Ableitungen:** Die aus diesen Stationen abgeleiteten "
            "Reihen — Kennzahlen in `out/`, die Stationseinträge in "
            "`site/data.json` und alles, was daraus sichtbar wird — unterliegen "
            "den Share-Alike-Bedingungen. Wer sie publiziert oder weiterverarbeitet, "
            "muss das Ergebnis unter einer CC-BY-SA-kompatiblen Lizenz "
            f"weitergeben und {', '.join(operators)} als Quelle nennen. Für die "
            f"{total - len(sa_rows)} übrigen Stationen gilt diese Pflicht nicht; "
            "die aggregierten Bundeskennzahlen beruhen auf allen Stationen gemeinsam."
        )
    else:
        add("Keine Station unter CC BY-SA im aktuellen Bestand.")
    add("")

    # --- Weitere Quellen ---
    add("## Weitere Quellen")
    add("")
    add(
        "- **Kartengrundlage:** [Natural Earth](https://www.naturalearthdata.com/) "
        "10m (Landesumriss, Bundeslandgrenzen, Flussachsen), gemeinfrei "
        "(public domain). Abgeleitet und vereinfacht durch "
        "`scripts/fetch_geodata.py` nach `site/geo.json`."
    )
    return "\n".join(out).rstrip("\n") + "\n"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    db_path = root / "data" / "niedrigwasser.duckdb"
    if not db_path.exists():
        print(
            f"FEHLER: {db_path} fehlt — zuerst `uv run niedrigwasser ingest` laufen lassen.",
            file=sys.stderr,
        )
        return 1
    pairs, sa_rows = _fetch(db_path)
    target = root / "docs" / "attribution.md"
    # newline="\n": auch unter Windows LF schreiben, sonst waere die Ausgabe
    # plattformabhaengig und der git-Diff nicht reproduzierbar.
    target.write_text(build_markdown(pairs, sa_rows), encoding="utf-8", newline="\n")
    print(f"docs/attribution.md geschrieben ({len(pairs)} Lizenz/Betreiber-Kombinationen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
