"""Baut das Einbettungs-Fragment aus der exportierten Seite und prueft die Gates.

``scripts/build_embed.py`` ist nur noch der Aufrufer -- dieselbe Rollenteilung
wie ``niedrigwasser.site_embed`` zu ``scripts/build_site.py``. Die Logik liegt
hier im Paket, damit sie ohne sys.path-Eingriff testbar ist und das Skript in
der oeffentlichen Fassung fehlen darf, ohne die Test-Suite zu brechen.

Die Verbots-Muster kommen als Parameter herein statt per Import: sie gehoeren
zur Publikationsschicht (``scripts/export_public.py``), die bewusst nicht Teil
der oeffentlichen Fassung ist. Ein Import an dieser Stelle wuerde das Paket
dort unimportierbar machen.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Sequence

from niedrigwasser.embed_fragment import build_fragment

# (Name, Regex) -- dieselbe Form wie VERBOTS_MUSTER in der Publikationsschicht.
Muster = Sequence[tuple[str, str]]

# Ein Fund im Fragment betrifft ein Dokument mit sehr langen Zeilen (eingebettetes
# JSON). Der Ausschnitt haelt die Meldung lesbar, die Zeilennummer macht sie
# auffindbar.
AUSSCHNITT_LAENGE = 120


def pruefe_gates(text: str, muster: Muster) -> list[str]:
    """Sucht die Verbots-Muster zeilenweise und meldet jede Fundstelle.

    Rueckgabe: Zeilennummer, Mustername und ein gekuerzter Ausschnitt -- dieselbe
    Auskunftstiefe wie ``export_public.pruefe_verbots_gates``. Der blosse
    Mustername waere in einem 400-KB-Dokument nicht auffindbar, ausgerechnet im
    Moment eines echten Lecks. Leere Liste = sauber.
    """
    treffer: list[str] = []
    for zeilennr, zeile in enumerate(text.splitlines(), start=1):
        for name, regex in muster:
            if re.search(regex, zeile, re.IGNORECASE):
                treffer.append(
                    f"Zeile {zeilennr}: [{name}] {zeile.strip()[:AUSSCHNITT_LAENGE]}"
                )
    return treffer


def baue_embed(quelle: Path, target: Path, muster: Muster, sprache: str) -> int:
    """Baut das Fragment aus ``quelle`` und schreibt es nach ``target``.

    Reihenfolge ist bindend: erst bauen, dann pruefen, erst danach schreiben.
    Ein Gate-Treffer darf weder Datei noch Zielverzeichnis hinterlassen.

    ``sprache`` wird nur durchgereicht; sie landet im Herkunftskopf des
    Fragments (siehe embed_fragment.herkunft) und ist dort Pflicht.

    Rueckgabe: 0 = geschrieben, 2 = Quelle fehlt, 3 = Verbots-Muster getroffen.
    Ein ``FragmentFehler`` aus dem Bau wird bewusst nicht gefangen -- er gehoert
    dem Aufrufer.
    """
    if not quelle.exists():
        print(
            f"FEHLER: {quelle} fehlt -- zuerst "
            "'uv run python scripts/export_public.py --force' laufen lassen.",
            file=sys.stderr,
        )
        return 2

    fragment = build_fragment(quelle.read_text(encoding="utf-8"), sprache)

    treffer = pruefe_gates(fragment, muster)
    if treffer:
        print("ABBRUCH: Verbots-Muster im Fragment:", file=sys.stderr)
        for t in treffer:
            print(f"  {t}", file=sys.stderr)
        return 3

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(fragment, encoding="utf-8", newline="\n")
    print(f"Fragment geschrieben: {target} ({target.stat().st_size} bytes)")
    print(f"Gates ({len(muster)} Muster): OK - keine Treffer")
    return 0
