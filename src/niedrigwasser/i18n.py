"""Sprachkataloge fuer site/template.html.

Das Template ist sprachneutral und traegt nur Schluessel; die Prosa steht in
``site/text.<lang>.json``. Das folgt der Konvention der Website, die ebenfalls
nur Inhalt je Sprache haelt und Struktur und Logik teilt.

Jede Regelverletzung ist ein harter Abbruch. Ein stiller Rueckfall auf Deutsch
waere der schlimmste Ausgang: Die englische Seite saehe heil aus und traege
deutschen Text.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Schluessel am Element: ersetzt den gesamten inneren Inhalt.
RE_INHALT = re.compile(r'data-i18n="([^"]+)"')
# Schluessel fuer Attribute: 'aria-label:schluessel' oder mehrere per Komma.
RE_ATTRIBUT = re.compile(r'data-i18n-attr="([^"]+)"')
# Datenplatzhalter, die das JavaScript spaeter fuellt. Nur ein eigenstaendiges
# 'id'-Attribut zaehlt: \b allein matcht auch das 'id' in 'data-id', weil die
# Wortgrenze zwischen '-' und 'i' liegt. Negative Lookbehind schliesst jedes
# Zeichen aus, das ein zusammengesetztes Attribut (data-id, aria-id, ...) bildet.
RE_ID = re.compile(r'(?<![\w-])id="([^"]+)"')

# Reservierter Schluessel: traegt die Format-Einstellungen der Sprache als
# Objekt (Dezimaltrenner, Monatsnamen, ...), keinen Text. Wird von allen
# Text-Pruefungen ausgenommen -- sonst gilt er als unbenutzter Schluessel.
LOCALE_SCHLUESSEL = "__locale__"

# Textschluessel, aus dem das lang-Attribut des <html>-Elements gefuellt wird
# (data-i18n-attr="lang:doc.lang" in site/template.html). Er sagt dasselbe aus
# wie '__locale__.lang' -- siehe die Gegenpruefung in pruefe_locale.
DOC_LANG_SCHLUESSEL = "doc.lang"


class I18nFehler(RuntimeError):
    """Harter Abbruch: ein Katalog verletzt eine Regel."""


def lade_katalog(pfad: Path) -> dict[str, str]:
    """Liest einen Katalog und erzwingt ein flaches dict von str auf str.

    Ausnahme: ``LOCALE_SCHLUESSEL`` darf ein Objekt tragen (siehe oben).
    """
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError as fehler:
        # Ohne diesen Fang bricht eine leere oder syntaktisch kaputte Datei mit
        # einem rohen Traceback ab, der die Datei nicht nennt -- Widerspruch zur
        # sonstigen Linie dieses Moduls (harter Abbruch mit brauchbarer Meldung).
        raise I18nFehler(f"{pfad}: kein gueltiges JSON ({fehler})") from fehler
    if not isinstance(daten, dict):
        raise I18nFehler(f"{pfad}: Katalog muss ein Objekt sein")
    for schluessel, wert in daten.items():
        if schluessel == LOCALE_SCHLUESSEL and isinstance(wert, dict):
            continue
        if not isinstance(wert, str):
            raise I18nFehler(
                f"{pfad}: Katalog muss flach sein, {schluessel!r} ist kein Text"
            )
    return daten


# Namenskonvention der Sprachkataloge dieses Projekts: text.<sprache>.json,
# <sprache> als zweibuchstabiger Code (heute de/en). Traegt die Geschwister-
# suche fuer die Kreuzpruefung zwischen den Sprachen.
_SPRACHCODE = r"[a-z]{2}"
RE_KATALOGNAME = re.compile(rf"^text\.({_SPRACHCODE})\.json$")

# Derselbe Code fuer sich genommen. Gebraucht, wo eine Sprachangabe von
# aussen kommt und erst geprueft werden muss, ob sie ueberhaupt eine ist:
# lade_kataloge_fuer_pruefung schluesselt Kataloge ausserhalb der Konvention
# unter ihrem Dateinamen, und der ist keine Sprache.
RE_SPRACHCODE = re.compile(rf"^{_SPRACHCODE}$")

# Bekannte Sprachpaare dieses Projekts. Eine dritte Sprache braeuchte eine
# allgemeinere Geschwistersuche (z.B. ueber alle text.*.json im Verzeichnis)
# statt einer festen Gegenstueck-Tabelle.
_GEGENSPRACHE = {"de": "en", "en": "de"}


def katalog_sprache(text_path: Path) -> str | None:
    """Sprachcode aus dem Dateinamen, oder None ausserhalb der Konvention."""
    treffer = RE_KATALOGNAME.match(text_path.name)
    return treffer.group(1) if treffer else None


def geschwister_katalog(text_path: Path) -> Path | None:
    """Pfad des Katalogs der anderen Sprache, falls es ihn gibt.

    Einzige Stelle, die aus einem Katalogpfad den der Gegensprache ableitet.
    Beide Nutzer fragen hier: die Kreuzpruefung (lade_kataloge_fuer_pruefung)
    und die zweite Sprachausgabe der render-Stage. Ein zusaetzliches
    CLI-Argument fuer den zweiten Katalog waere ein zweiter Weg zur selben
    Datei -- und zwei Wege koennen auseinanderlaufen: Wer --site-text-en auf
    eine andere Datei zeigen liesse, bekaeme eine englische Seite, deren
    Katalog nie gegen den deutschen kreuzgeprueft wurde. Genau die stille
    Luecke, gegen die pruefe_kataloge gebaut ist.

    Rueckgabe: None, wenn ``text_path`` nicht der Namenskonvention
    ``text.<sprache>.json`` folgt, die Sprache kein bekanntes Gegenstueck hat
    oder die Geschwisterdatei fehlt.
    """
    andere = gegensprache(text_path)
    if not andere:
        return None
    geschwister = text_path.with_name(f"text.{andere}.json")
    return geschwister if geschwister.exists() else None


def gegensprache(text_path: Path) -> str | None:
    """Sprachcode der Gegensprache laut Namenskonvention -- ohne Dateizugriff.

    Getrennt von geschwister_katalog, weil die Aufrufer beides brauchen und
    es NICHT dasselbe ist: "welche zweite Sprache waere hier vorgesehen" gilt
    auch dann, wenn der Katalog fehlt. Genau dieser Fall muss unterscheidbar
    bleiben -- wer nur ein None von geschwister_katalog sieht, weiss nicht, ob
    der Katalog fehlt oder ob dieser Pfad ueberhaupt keine zweite Sprache hat,
    und kann deshalb auch keine veraltete Ausgabedatei aufraeumen.
    """
    return _GEGENSPRACHE.get(katalog_sprache(text_path) or "")


def sprachvariante(pfad: Path, sprache: str) -> Path:
    """Name derselben Ausgabedatei in einer anderen Sprache.

    ``site/index.html`` + ``"en"`` -> ``site/index.en.html``. Dieselbe
    Konvention wie bei den Katalogen, nur fuer Ausgabedateien, und bewusst
    hier neben ihr: sonst driften Katalog- und Ausgabenamen auseinander.

    Abgeleitet statt literal, weil ein Literal wie "site/index.en.html" gegen
    das Arbeitsverzeichnis aufloest -- aus einem Testlauf heraus zeigt es
    damit in die echte Repo-Datei.
    """
    return pfad.with_name(f"{pfad.stem}.{sprache}{pfad.suffix}")


def lade_kataloge_fuer_pruefung(text_path: Path) -> dict[str, dict]:
    """Laedt ``text_path`` und, falls vorhanden, seinen Geschwisterkatalog.

    Zentrale Ladestelle fuer die Kreuzpruefung (pruefe_kataloge/pruefe_locale)
    zwischen den Sprachen -- absichtlich hier bei den Lade-Funktionen und
    nicht an einer einzelnen Aufrufstelle im Code, das ueber embed_site() eine
    Seite baut (render-Stage, scripts/build_site.py, ...). Sonst haengt die
    Absicherung daran, welchen Bauweg jemand waehlt, und ist keine.

    Der Geschwisterkatalog ist optional -- fehlt er, oder folgt ``text_path``
    nicht der Namenskonvention ``text.<sprache>.json``, enthaelt das Ergebnis
    nur die eine Sprache; pruefe_kataloge greift konstruktionsbedingt erst ab
    zwei Katalogen, ein einzelner ist also kein Fehler.
    """
    sprache = katalog_sprache(text_path)
    kataloge = {sprache or text_path.name: lade_katalog(text_path)}
    geschwister = geschwister_katalog(text_path)
    if geschwister is not None:
        kataloge[katalog_sprache(geschwister)] = lade_katalog(geschwister)
    return kataloge


# Schluessel, die die Formatierer im Client aus dem Locale-Block lesen
# (fmt/fmtP/pText/fmtFlow/dayLabel in site/template.html). Fehlt einer, faellt
# das im Browser nicht auf einen Fehler, sondern auf den woertlichen String
# 'undefined' in einer Zahl -- deshalb hier geprueft, beim Laden des Katalogs,
# nicht erst dort, wo er verwendet wird.
# Der Abstand vor dem Prozentzeichen ist eine Locale-Entscheidung: Deutsch setzt
# ihn, Englisch nicht. Es gibt ihn zweimal, und der Unterschied ist NICHT der
# Kontext (HTML vs. Text), sondern ob der Abstand geschuetzt ist:
#   percentSpaceNoBreak  -- geschuetzt, deutsch '&nbsp;' (Tooltips der Seite)
#   percentSpaceBreaking -- ungeschuetzt, deutsch ein normales Leerzeichen
# Dass die deutsche Seite an unterschiedlichen Stellen unterschiedlich setzt,
# ist aelter als die Auslagerung der JS-Strings; siehe den Hinweis im
# '__locale__'-Block von site/text.de.json. Eine Sprache ohne Abstand vor dem
# Prozentzeichen traegt in beiden Feldern den leeren String.
LOCALE_PFLICHTFELDER = (
    "decimal",
    "thousands",
    "percentSpaceNoBreak",
    "percentSpaceBreaking",
    "months",
    "monthsDate",
    "dateFormat",
    "dateRange",
    "pLess",
    "pLessValue",
)


def pruefe_locale(katalog: dict, sprache: str | None = None) -> dict:
    """Extrahiert den Locale-Block aus ``katalog`` und erzwingt Vollstaendigkeit.

    Harter Abbruch, wenn der Block fehlt oder einer der Pflichtschluessel
    fehlt; die Meldung nennt, welcher. Gehoert dorthin, wo der Katalog geladen
    wird -- nicht in die Formatierer, die sich auf das Ergebnis blind
    verlassen koennen sollen.

    ``sprache`` ist optional und geht, wenn gesetzt, mit in die Meldung ein --
    genau wie pruefe_kataloge Schluessel UND Sprache nennt. Ohne Sprachbezug
    (Einzelkatalog-Aufrufe, die die Sprache nicht kennen) bleibt die Meldung
    wie bisher.

    Prueft ausserdem, dass alle Sprachangaben des Katalogs dasselbe sagen --
    Dateiname, __locale__.lang und doc.lang; siehe pruefe_sprachkennung.
    """
    praefix = f"Katalog {sprache!r}: " if sprache else ""
    locale = katalog.get(LOCALE_SCHLUESSEL)
    if not isinstance(locale, dict):
        raise I18nFehler(f"{praefix}Katalog ohne {LOCALE_SCHLUESSEL!r}-Block")
    fehlend = [feld for feld in LOCALE_PFLICHTFELDER if feld not in locale]
    if fehlend:
        raise I18nFehler(
            f"{praefix}{LOCALE_SCHLUESSEL!r}-Block unvollstaendig, es fehlt: "
            + ", ".join(fehlend)
        )
    pruefe_sprachkennung(katalog, locale, sprache)
    return locale


def pruefe_sprachkennung(
    katalog: dict, locale: dict, sprache: str | None = None
) -> None:
    """Erzwingt, dass alle Sprachangaben eines Katalogs dasselbe sagen.

    Ein Katalog traegt seinen Sprachcode bis zu dreimal:

    * im **Dateinamen** (``text.en.json``) -- das ist der einzige, der
      Wirkung hat: er bestimmt, welche Ausgabedatei geschrieben wird
      (``index.en.html``). Er kommt als ``sprache`` herein.
    * als ``__locale__.lang`` -- Metadatum des Locale-Blocks.
    * als Textschluessel ``doc.lang`` -- fuellt das lang-Attribut des
      <html>-Elements.

    Die beiden letzten beschreiben nur sich selbst. Sie gegeneinander zu
    pruefen faengt den widerspruechlichen Fall, nicht den gefaehrlicheren:
    ``text.en.json`` mit ``doc.lang = "de"`` UND ``__locale__.lang = "de"``
    ist in sich stimmig und ergibt trotzdem ``index.en.html`` mit
    ``<html lang="de">`` und englischem Text. Konsistent falsch statt
    widerspruechlich falsch -- und ohne den Dateinamen im Vergleich faellt es
    durch jedes Netz. Deshalb ist er hier die dritte Quelle.

    Uebersprungen wird jede Quelle, die fehlt oder keine Sprachangabe ist:

    * ``sprache`` nur, wenn es ein Sprachcode nach RE_SPRACHCODE ist --
      lade_kataloge_fuer_pruefung schluesselt Kataloge ausserhalb der
      Namenskonvention unter ihrem Dateinamen, und daraus liesse sich keine
      Sprache ableiten.
    * ``__locale__.lang`` steht bewusst nicht in LOCALE_PFLICHTFELDER, weil
      die Formatierer im Client es nicht lesen.
    * ``doc.lang`` erzwingt bereits ``wende_an`` (das Template benutzt den
      Schluessel, ein fehlender bricht dort ab, und zwar auf jedem Bauweg mit
      Katalog -- nicht pruefe_kataloge, die greift erst ab zwei Katalogen).

    Bleibt danach hoechstens ein Wert uebrig, gibt es nichts zu vergleichen.
    """
    quellen: list[tuple[str, str]] = []
    if isinstance(sprache, str) and RE_SPRACHCODE.match(sprache):
        quellen.append(("Dateiname", sprache))
    locale_lang = locale.get("lang")
    if isinstance(locale_lang, str):
        quellen.append((f"{LOCALE_SCHLUESSEL}.lang", locale_lang))
    doc_lang = katalog.get(DOC_LANG_SCHLUESSEL)
    if isinstance(doc_lang, str):
        quellen.append((DOC_LANG_SCHLUESSEL, doc_lang))

    if len({wert for _, wert in quellen}) <= 1:
        return

    # Die Meldung nennt jede Quelle mit ihrem Wert UND die betroffene Sprache:
    # Bei zwei Katalogen in einer Schleife waere sonst offen, welcher gemeint
    # ist und welche der Angaben danebenliegt.
    betroffen = sprache or quellen[0][1]
    raise I18nFehler(
        f"Katalog {betroffen!r}: Sprachkennung widerspruechlich -- "
        + ", ".join(f"{name}={wert!r}" for name, wert in quellen)
    )


def _attribut_schluessel(rohwert: str) -> list[tuple[str, str]]:
    """Zerlegt 'aria-label:a,title:b' in [('aria-label','a'), ('title','b')]."""
    paare = []
    for teil in rohwert.split(","):
        teil = teil.strip()
        if not teil:
            continue
        if ":" not in teil:
            raise I18nFehler(f"data-i18n-attr ohne Doppelpunkt: {teil!r}")
        attribut, schluessel = teil.split(":", 1)
        paare.append((attribut.strip(), schluessel.strip()))
    return paare


# Aufrufe der Form t("schluessel") oder t("schluessel", {...}) im Skriptbereich.
RE_JS_SCHLUESSEL = re.compile(r'\bt\(\s*"([^"]+)"')


def _skript_bereiche(html: str) -> str:
    """Nur die ausfuehrbaren Skriptbloecke, ohne die JSON-Datenbloecke."""
    return "".join(
        re.findall(
            r"<script(?![^>]*application/json)[^>]*>(.*?)</script>", html, flags=re.S
        )
    )


def sammle_js_schluessel(html: str) -> set[str]:
    """Alle Katalog-Schluessel, die das Skript zur Laufzeit nachschlaegt."""
    return set(RE_JS_SCHLUESSEL.findall(_skript_bereiche(html)))


def sammle_schluessel(html: str) -> set[str]:
    """Alle im Template verwendeten Katalog-Schluessel.

    Markup (data-i18n, data-i18n-attr) und Skript (t("...")) zusammen: die
    Paritaetspruefungen sollen beide Quellen abdecken, sonst faellt ein nur im
    JavaScript benutzter Schluessel durch jedes Netz.
    """
    schluessel = set(RE_INHALT.findall(html))
    for rohwert in RE_ATTRIBUT.findall(html):
        schluessel.update(s for _, s in _attribut_schluessel(rohwert))
    return schluessel | sammle_js_schluessel(html)


def _ids(wert: str) -> set[str]:
    return set(RE_ID.findall(wert))


# Benannte Platzhalter in Katalogwerten, die das Skript per t() fuellt.
# Bewusst ASCII (re.ASCII): Das JavaScript im Template benutzt dasselbe Muster,
# und \w ist dort immer ASCII. Ein Platzhalter mit Umlaut im Namen wuerde vom
# Client gar nicht erst gesehen und bliebe woertlich im Text stehen.
RE_PLATZHALTER = re.compile(r"\{(\w+)\}", re.ASCII)


def _platzhalter(wert: str) -> set[str]:
    return set(RE_PLATZHALTER.findall(wert))


def pruefe_kataloge(html: str, kataloge: dict[str, dict[str, str]]) -> None:
    """Faehrt alle harten Regeln. Wirft beim ersten Verstoss."""
    # LOCALE_SCHLUESSEL vor allen Pruefungen heraus -- er ist kein Textschluessel
    # und darf weder als unbenutzt noch als fehlend gelten.
    kataloge = {
        sprache: {k: v for k, v in katalog.items() if k != LOCALE_SCHLUESSEL}
        for sprache, katalog in kataloge.items()
    }
    benutzt = sammle_schluessel(html)

    for sprache, katalog in kataloge.items():
        fehlend = sorted(benutzt - set(katalog))
        if fehlend:
            raise I18nFehler(
                f"Schluessel fehlt in Katalog {sprache!r}: {', '.join(fehlend)}"
            )
        unbenutzt = sorted(set(katalog) - benutzt)
        if unbenutzt:
            raise I18nFehler(
                f"Schluessel unbenutzt in Katalog {sprache!r}: {', '.join(unbenutzt)}"
            )
        for schluessel, wert in katalog.items():
            if "<script" in wert.lower():
                raise I18nFehler(
                    f"Katalog {sprache!r}, {schluessel!r}: script im Wert verboten"
                )

    # id-Paritaet: jede Sprache muss dieselben Datenplatzhalter tragen.
    # Text-Paritaet: dasselbe fuer die benannten {platzhalter}, die t() fuellt.
    # Ohne diese Pruefung waeren beide Ausgaenge still: Ein weggelassener
    # Platzhalter laesst den Wert verschwinden -- der Satz klingt vollstaendig,
    # nennt aber die Zahl nicht mehr. Ein umbenannter laesst '{peak}' sichtbar
    # auf der Seite stehen.
    sprachen = sorted(kataloge)
    if len(sprachen) > 1:
        referenz = sprachen[0]
        for sprache in sprachen[1:]:
            for schluessel in sorted(benutzt):
                a = _ids(kataloge[referenz][schluessel])
                b = _ids(kataloge[sprache][schluessel])
                if a != b:
                    fehlt = ", ".join(sorted(a ^ b))
                    raise I18nFehler(
                        f"{schluessel!r}: Datenplatzhalter unterscheiden sich "
                        f"zwischen {referenz!r} und {sprache!r}: {fehlt}"
                    )
                a = _platzhalter(kataloge[referenz][schluessel])
                b = _platzhalter(kataloge[sprache][schluessel])
                if a != b:
                    fehlt = ", ".join(sorted(a ^ b))
                    raise I18nFehler(
                        f"{schluessel!r}: Platzhalter unterscheiden sich "
                        f"zwischen {referenz!r} und {sprache!r}: {fehlt}"
                    )


def _element_ende(html: str, start: int) -> tuple[int, int, str]:
    """Findet zu einem Start-Tag ab ``start`` die Grenzen seines Inhalts.

    Gibt (inhalt_start, inhalt_ende, tagname) zurueck. Zaehlt gleichnamige
    verschachtelte Tags mit, damit ein <div> in einem <div> nicht zu frueh
    schliesst.
    """
    tag_ende = html.index(">", start)
    tagname = re.match(r"<([a-zA-Z][\w-]*)", html[start:]).group(1)
    tiefe, i = 1, tag_ende + 1
    oeffnend = re.compile(rf"<{tagname}\b", re.I)
    schliessend = re.compile(rf"</{tagname}\s*>", re.I)
    letztes = None
    while tiefe:
        auf = oeffnend.search(html, i)
        zu = schliessend.search(html, i)
        if zu is None:
            raise I18nFehler(f"Kein schliessendes </{tagname}> ab Position {start}")
        if auf is not None and auf.start() < zu.start():
            tiefe += 1
            i = auf.end()
            continue
        tiefe -= 1
        letztes = zu
        i = zu.end()
    return tag_ende + 1, letztes.start(), tagname


def wende_an(html: str, katalog: dict[str, str]) -> str:
    """Setzt Katalogwerte in Inhalte und Attribute ein."""
    fehlend = sorted(sammle_schluessel(html) - set(katalog))
    if fehlend:
        raise I18nFehler(f"Schluessel fehlt im Katalog: {', '.join(fehlend)}")

    # Attribute zuerst: sie aendern keine Laengenverhaeltnisse im Inhalt.
    for rohwert in set(RE_ATTRIBUT.findall(html)):
        # Erwartete Trefferzahl: wie oft dieser exakte Rohwert im Dokument
        # vorkommt. Der Suchstring ist beidseitig durch Anfuehrungszeichen
        # begrenzt (RE_ATTRIBUT kann selbst keine Anfuehrungszeichen im
        # Rohwert liefern), daher kein Risiko eines Teilstring-Treffers auf
        # einen laengeren Rohwert.
        erwartete = html.count(f'data-i18n-attr="{rohwert}"')
        for attribut, schluessel in _attribut_schluessel(rohwert):
            muster = re.compile(
                rf'(data-i18n-attr="{re.escape(rohwert)}"[^>]*?\s{re.escape(attribut)}=")[^"]*(")'
            )
            neu, anzahl = muster.subn(
                lambda m: m.group(1) + katalog[schluessel] + m.group(2), html
            )
            if anzahl != erwartete:
                raise I18nFehler(
                    f"data-i18n-attr={rohwert!r}: erwartet {erwartete} Ersetzungen "
                    f"fuer Attribut {attribut!r}, gefunden {anzahl} "
                    "(Reihenfolge im Tag pruefen: das Zielattribut muss hinter "
                    "data-i18n-attr stehen)"
                )
            html = neu

    # Inhalte von hinten nach vorn, damit fruehere Positionen gueltig bleiben.
    starts = [m.start() for m in re.finditer(r"<[a-zA-Z][^>]*data-i18n=\"", html)]
    grenzen = []
    for start in starts:
        tag_ende = html.index(">", start)
        schluessel = RE_INHALT.search(html, start, tag_ende).group(1)
        inhalt_start, inhalt_ende, _ = _element_ende(html, start)
        grenzen.append((start, inhalt_start, inhalt_ende, schluessel))

    for i, (start_a, _, ende_a, _) in enumerate(grenzen):
        for start_b, _, _, _ in grenzen[i + 1:]:
            if start_a < start_b < ende_a:
                raise I18nFehler(
                    "data-i18n-Elemente duerfen nicht verschachtelt sein "
                    f"(Position {start_a} enthaelt {start_b})"
                )

    for _, inhalt_start, inhalt_ende, schluessel in sorted(grenzen, reverse=True):
        html = html[:inhalt_start] + katalog[schluessel] + html[inhalt_ende:]
    return html


# Die Markierungen sind Build-Metadaten. In der ausgelieferten Seite haben sie
# nichts verloren -- deshalb entfernt die Ausgabestufe sie wieder, samt des
# fuehrenden Leerzeichens, mit dem sie eingefuegt wurden.
RE_MARKIERUNG = re.compile(r'\s+data-i18n(?:-attr)?="[^"]*"')


def entferne_markierungen(html: str) -> str:
    """Entfernt data-i18n und data-i18n-attr aus der fertigen Seite."""
    return RE_MARKIERUNG.sub("", html)
