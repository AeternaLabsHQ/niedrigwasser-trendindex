"""Einbettung von site/data.json (+ site/geo.json) in site/template.html.

site/template.html ist die gepflegte Quelle; sie enthaelt die Marker
``/*__DATA__*/`` und ``/*__GEO__*/`` in je einem
``<script type="application/json">``-Block. Diese Funktion ersetzt die Marker
durch das kompakte JSON und schreibt das Ergebnis als self-contained HTML
(funktioniert per file://-Doppelklick, kein fetch).

``geo.json`` (Deutschland-Basemap, Natural Earth) ist optional: fehlt die
Datei oder der Marker, wird nur data.json eingebettet — ein GEO-Marker ohne
Datei wird als leeres Objekt ``{}`` gefuellt, damit kein Marker im Output
verbleibt.

Aufrufbar ueber ``uv run niedrigwasser render --embed`` (render-Stage) oder direkt via
``uv run python scripts/build_site.py``.

Zwei Ebenen:

* ``embed_site`` baut GENAU EINE Seite aus genau einem Katalog.
* ``embed_alle_sprachen`` baut die Seite in allen Sprachen, die es gibt --
  das ist der vollstaendige Bauweg, den beide Einstiege benutzen. Wer nur
  ``embed_site`` ruft, baut die zweite Sprachfassung nicht mit und laesst eine
  veraltete liegen.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

MARKER = "/*__DATA__*/"
GEO_MARKER = "/*__GEO__*/"
TEXT_MARKER = "/*__TEXT__*/"


def _payload(data_path: Path) -> str:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # '</script>' (oder jedes '</...') im Payload wuerde den Script-Block
    # beenden -> als '<\/' escapen; JSON.parse liest das identisch.
    return payload.replace("</", "<\\/")


def embed_site(
    template_path: Path,
    data_path: Path,
    out_path: Path,
    geo_path: Path | None = None,
    text_path: Path | None = None,
) -> int:
    """Erzeugt ``out_path`` aus Template + JSON; gibt die Dateigroesse zurueck.

    Ist ``text_path`` gesetzt, werden zuvor die Katalogwerte in Inhalte und
    Attribute eingesetzt (siehe niedrigwasser.i18n).
    """
    template = template_path.read_text(encoding="utf-8")
    if MARKER not in template:
        raise ValueError(f"Marker {MARKER} fehlt in {template_path}")

    katalog = None
    katalog_sprache = None
    primaer_locale_geprueft = False
    if text_path is not None:
        from niedrigwasser.i18n import (
            entferne_markierungen,
            lade_kataloge_fuer_pruefung,
            pruefe_kataloge,
            pruefe_locale,
            wende_an,
        )

        # Kreuzpruefung zwischen den Sprachen -- ueber lade_kataloge_fuer_pruefung()
        # verdrahtet, nicht an dieser einzelnen Aufrufstelle allein: so greift sie
        # auf jedem Weg, der embed_site() aufruft (render-Stage,
        # scripts/build_site.py, ...), nicht nur auf einem. Der Geschwisterkatalog
        # (Namenskonvention text.<sprache>.json) ist optional; fehlt er, heisst
        # das "keine englische Ausgabe", nicht "Fehler". Ist er da, muessen beide
        # Kataloge ihren __locale__-Block tragen (Sprache geht in die Meldung
        # ein) und Schluessel-, id- und Platzhalter-Paritaet halten, sonst
        # bricht der Build hier ab.
        # kataloge haelt text_path selbst immer als ersten (und ggf. einzigen)
        # Eintrag -- kein zweites Laden derselben Datei noetig.
        kataloge = lade_kataloge_fuer_pruefung(text_path)
        sprachen = list(kataloge)
        katalog_sprache = sprachen[0]
        katalog = kataloge[katalog_sprache]
        if len(kataloge) > 1:
            for sprache in sprachen:
                pruefe_locale(kataloge[sprache], sprache)
            pruefe_kataloge(template, kataloge)
            # Primaerer Katalog ist hier schon geprueft -- der Blob-Bau unten
            # (falls TEXT_MARKER im Template steht) prueft ihn sonst ein
            # zweites Mal. Idempotent, aber unnoetige Doppelarbeit bei jedem
            # echten Build.
            primaer_locale_geprueft = True

        template = entferne_markierungen(wende_an(template, katalog))

    if TEXT_MARKER in template:
        if text_path is None:
            raise ValueError(f"Marker {TEXT_MARKER} ohne --site-text")
        locale = (
            katalog["__locale__"]
            if primaer_locale_geprueft
            else pruefe_locale(katalog, katalog_sprache)
        )
        blob = {
            "LOCALE": locale,
            "TEXTE": {k: v for k, v in katalog.items() if k != "__locale__"},
        }
        nutz = json.dumps(blob, ensure_ascii=False, separators=(",", ":"))
        template = template.replace(TEXT_MARKER, nutz.replace("</", "<\\/"), 1)

    html = template.replace(MARKER, _payload(data_path), 1)

    if GEO_MARKER in html:
        if geo_path is not None and geo_path.exists():
            html = html.replace(GEO_MARKER, _payload(geo_path), 1)
        else:
            html = html.replace(GEO_MARKER, "{}", 1)

    out_path.write_text(html, encoding="utf-8")
    return out_path.stat().st_size


def embed_alle_sprachen(
    template_path: Path,
    data_path: Path,
    out_path: Path,
    geo_path: Path | None = None,
    text_path: Path | None = None,
    out_path_zweit: Path | None = None,
    melde: Callable[[str], None] | None = None,
) -> dict[Path, int]:
    """Baut ALLE Sprachfassungen einer Seite; gibt {Pfad: Groesse} zurueck.

    Der vollstaendige Bauweg -- primaere Sprache aus ``text_path``, zweite aus
    dem Geschwisterkatalog (Namenskonvention ``text.<sprache>.json``, siehe
    niedrigwasser.i18n.geschwister_katalog). Fehlt der Geschwisterkatalog,
    entsteht keine zweite Datei, und eine aus einem frueheren Lauf liegen
    gebliebene wird entfernt: Sie waere von nichts mehr gedeckt, der Export
    kopierte sie mit, build_embed.py baute daraus ein gate-sauberes Fragment,
    und der Herkunfts-Hash zeigte korrekt auf eine veraltete Quelle -- nur
    vergleicht ihn nichts.

    Diese Funktion existiert, damit es genau EINEN vollstaendigen Bauweg gibt.
    Vorher stand die Ableitung der zweiten Sprache allein in der render-Stage;
    scripts/build_site.py verdrahtete ``text.de.json`` fest und fasste
    ``index.en.html`` nie an -- nach einem Lauf stand eine frische deutsche
    neben einer veralteten englischen Seite, ohne Log-Zeile. Dasselbe Skript
    steht in der Export-Allow-Liste und in der README namentlich als Bau-Weg;
    es hat auf demselben Weg schon zweimal einen Defekt geschluckt (die
    fehlende ``text_path``-Uebergabe in Task 4, die umgangene Katalogpruefung
    in Task 7). Ein zweiter, halber Bauweg ist keiner.

    ``out_path_zweit`` ueberschreibt den abgeleiteten Ausgabepfad der zweiten
    Sprache (CLI-Argument ``--site-html-en``). ``melde`` nimmt die
    Protokollzeilen entgegen (``log.info`` in der Stage, ``print`` im Skript);
    ohne Rueckruf laeuft der Bau stumm.
    """
    from niedrigwasser.i18n import (
        gegensprache,
        geschwister_katalog,
        sprachvariante,
    )

    sag = melde or (lambda zeile: None)
    groessen: dict[Path, int] = {}

    groessen[out_path] = embed_site(
        template_path, data_path, out_path, geo_path=geo_path, text_path=text_path
    )
    sag(f"site-html eingebettet: {out_path} ({groessen[out_path]} bytes)")

    if text_path is None:
        return groessen

    zweit_sprache = gegensprache(text_path)
    if zweit_sprache is None:
        sag(
            f"{text_path.name} folgt nicht der Konvention "
            "text.<sprache>.json -- keine zweite Sprachfassung"
        )
        return groessen

    # Ausgabepfad: --site-html-en, sonst aus out_path und dem Sprachcode
    # abgeleitet. Ein Literal-Default ("site/index.en.html") loeste gegen das
    # Arbeitsverzeichnis auf und schriebe aus jedem Testlauf heraus in die
    # echte Repo-Datei.
    out_zweit = out_path_zweit or sprachvariante(out_path, zweit_sprache)

    geschwister = geschwister_katalog(text_path)
    if geschwister is not None:
        groessen[out_zweit] = embed_site(
            template_path, data_path, out_zweit,
            geo_path=geo_path, text_path=geschwister,
        )
        sag(
            f"site-html zweite Sprache ({geschwister.name}): "
            f"{out_zweit} ({groessen[out_zweit]} bytes)"
        )
        return groessen

    sag(
        f"kein Katalog text.{zweit_sprache}.json neben {text_path.name} "
        "-- keine zweite Sprachfassung"
    )
    if out_zweit.exists():
        out_zweit.unlink()
        sag(f"veraltete zweite Sprachfassung entfernt: {out_zweit}")
    return groessen
