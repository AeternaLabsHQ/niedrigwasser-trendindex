"""Macht aus der exportierten Seite ein in aeternalabs.io einbettbares Fragment.

Die Analyse-Seite ist self-contained: eigener Dokumentrahmen, eigene
Design-Tokens, eigener Theme-Umschalter. Fuer die Einbettung unter dem
Menueband der Website muss daraus ein Fragment werden, das die Stile des Hosts
nicht beruehrt und dessen Theme-Zustand folgt.

Kapselungs-Regel: Jeder Selektor wird auf ``.nw-root`` gekapselt; jede Regel,
die vorher an ``:root[data-theme="dark"]`` hing, wird auf
``:root:not([data-theme="light"])`` konditioniert. Das ist exakt der
Dunkel-Zustand der Website (kein Attribut ODER Attribut "dark"). Der helle Satz
bleibt Basis — die naheliegende Umkehrung (dunkel als Basis) waere falsch,
weil sie Regeln wie ``.seg button[aria-pressed="true"]`` bei gleicher
Spezifitaet ueberschriebe und damit auch im Hellmodus griffe.

Jede Regel, die sich nicht sicher kapseln laesst, ist ein harter Abbruch.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterator

ROOT_CLASS = ".nw-root"
DARK_HOST = ':root:not([data-theme="light"])'
DARK_PREFIX = ':root[data-theme="dark"]'

# Erkennt ":root" als eigenstaendiges Token (nicht als Teil von z.B. ":rooted"
# oder "data-root") — Sicherheitsnetz fuer scope_selector, siehe dort.
_ROOT_TOKEN = re.compile(r"(?<![\w-]):root(?![\w-])")

# Farbschema-Bedingung als Substring — nur zum Erkennen, nicht zum Verwerfen.
_FARBSCHEMA = "prefers-color-scheme"

# Eine At-Regel darf nur verworfen werden, wenn sie AUSSCHLIESSLICH aus der
# Farbschema-Bedingung besteht. Eine kombinierte Query wie
# "@media (max-width: 720px) and (prefers-color-scheme: dark)" traegt auch
# responsive Regeln; sie stillschweigend fallen zu lassen waere genau der
# leise Verwerfer, den dieses Modul sonst ueberall vermeidet.
_NUR_FARBSCHEMA = re.compile(
    r"^@media\s*\(\s*prefers-color-scheme\s*:\s*(?:dark|light)\s*\)$",
    re.IGNORECASE,
)


class FragmentFehler(RuntimeError):
    """Harter Abbruch: eine Regel liess sich nicht sicher kapseln."""


def strip_comments(css: str) -> str:
    """Entfernt CSS-Kommentare; Kommentar-Syntax in Zeichenketten bleibt stehen."""
    teile: list[str] = []
    i, n, quote = 0, len(css), ""
    while i < n:
        ch = css[i]
        if quote:
            teile.append(ch)
            if ch == "\\" and i + 1 < n:
                teile.append(css[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            teile.append(ch)
            i += 1
            continue
        if css.startswith("/*", i):
            ende = css.find("*/", i + 2)
            if ende == -1:
                raise FragmentFehler("Unbeendeter CSS-Kommentar")
            i = ende + 2
            continue
        teile.append(ch)
        i += 1
    return "".join(teile)


def _zeichenketten_maske(s: str) -> list[bool]:
    """Markiert je Index, ob das Zeichen Teil einer Zeichenkette ist.

    Gleiche Quote-Verfolgung wie ``strip_comments`` (inkl. Backslash-Escapes),
    als gemeinsame Grundlage fuer ``iter_blocks`` und ``split_selectors`` —
    beide muessen Klammern/Kommas in Zeichenketten ignorieren, sonst
    desynchronisiert das Tiefen-Zaehlen still statt kontrolliert abzubrechen.
    """
    maske = [False] * len(s)
    i, n, quote = 0, len(s), ""
    while i < n:
        ch = s[i]
        if quote:
            maske[i] = True
            if ch == "\\" and i + 1 < n:
                maske[i + 1] = True
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            maske[i] = True
            i += 1
            continue
        i += 1
    return maske


def iter_blocks(css: str) -> Iterator[tuple[str, str]]:
    """Zerlegt einen Stylesheet-Text in (kopf, rumpf)-Paare der obersten Ebene."""
    maske = _zeichenketten_maske(css)
    i, n, start = 0, len(css), 0
    while i < n:
        if css[i] == "{" and not maske[i]:
            kopf = css[start:i]
            tiefe, j = 1, i + 1
            while j < n and tiefe:
                if css[j] == "{" and not maske[j]:
                    tiefe += 1
                elif css[j] == "}" and not maske[j]:
                    tiefe -= 1
                j += 1
            if tiefe:
                raise FragmentFehler(
                    f"Unbalancierte Klammern ab {kopf.strip()[:60]!r}"
                )
            yield kopf.strip(), css[i + 1 : j - 1]
            i = start = j
            continue
        i += 1
    rest = css[start:].strip()
    if rest:
        raise FragmentFehler(f"CSS-Rest ohne Block: {rest[:60]!r}")


def split_selectors(liste: str) -> list[str]:
    """Teilt eine Selektorliste an den Kommas der obersten Ebene."""
    maske = _zeichenketten_maske(liste)
    teile: list[str] = []
    tiefe, puffer = 0, ""
    for idx, ch in enumerate(liste):
        in_string = maske[idx]
        if not in_string:
            if ch == "(":
                tiefe += 1
            elif ch == ")":
                tiefe -= 1
        if ch == "," and tiefe == 0 and not in_string:
            teile.append(puffer)
            puffer = ""
            continue
        puffer += ch
    teile.append(puffer)
    return [t for t in (x.strip() for x in teile) if t]


def _ist_html_selektor(sel: str) -> bool:
    return sel == "html" or sel.startswith(("html ", "html.", "html:", "html["))


def scope_selector(sel: str) -> str:
    """Kapselt einen einzelnen Selektor auf den Container."""
    s = " ".join(sel.split())
    if not s:
        raise FragmentFehler("Leerer Selektor")
    if s == "*":
        return f"{ROOT_CLASS} *"
    if s in ("body", ":root"):
        return ROOT_CLASS
    if s.startswith(DARK_PREFIX):
        rest = s[len(DARK_PREFIX) :].strip()
        return f"{DARK_HOST} {ROOT_CLASS} {rest}".strip()
    if s.startswith(":root") or _ist_html_selektor(s):
        raise FragmentFehler(f"Nicht sicher kapselbar: {s!r}")
    if _ROOT_TOKEN.search(s):
        # Sicherheitsnetz: ":root" versteckt in einer funktionalen
        # Pseudoklasse wie :is(:root, .foo) oder :where(:root) ist von
        # keinem der obigen Faelle abgedeckt und darf nicht durchrutschen.
        raise FragmentFehler(f"Nicht sicher kapselbar: {s!r}")
    return f"{ROOT_CLASS} {s}"


def scope_css(css: str, _bereits_entkommentiert: bool = False) -> str:
    """Kapselt ein vollstaendiges Stylesheet auf ``.nw-root``."""
    if not _bereits_entkommentiert:
        css = strip_comments(css)
    ausgabe: list[str] = []
    for kopf, rumpf in iter_blocks(css):
        if kopf.startswith("@"):
            if _FARBSCHEMA in kopf:
                if not _NUR_FARBSCHEMA.match(" ".join(kopf.split())):
                    raise FragmentFehler(
                        "Farbschema-Bedingung in kombinierter At-Regel, nicht "
                        f"sicher verwerfbar: {kopf[:80]!r}"
                    )
                # Der Host wertet die Systemeinstellung nicht aus; sein
                # Dunkel-Zustand steht im data-theme-Attribut.
                continue
            if not kopf.startswith("@media"):
                raise FragmentFehler(f"Unbekannte At-Regel: {kopf[:60]!r}")
            innen = scope_css(rumpf, _bereits_entkommentiert=True)
            if innen.strip():
                ausgabe.append(f"{kopf} {{\n{innen}\n}}")
            continue
        selektoren = split_selectors(kopf)
        if selektoren and all(_ist_html_selektor(s) for s in selektoren):
            # Gehoert dem Dokument, nicht dem Fragment.
            continue
        gekapselt = ", ".join(scope_selector(s) for s in selektoren)
        ausgabe.append(f"{gekapselt} {{{rumpf}}}")
    return "\n".join(ausgabe)


# Exakte Marken der Seite. Jede muss treffen, sonst harter Abbruch — damit die
# Transformation nicht still zum No-Op wird, wenn sich das Template aendert.
# Der seiteneigene Theme-Umschalter. Erkannt wird er an seiner id, nicht an
# seiner Beschriftung: die steht seit der Zweisprachigkeit im Sprachkatalog
# ("Design: Auto" bzw. "Theme: Auto") und ist damit kein stabiles Merkmal mehr.
# Ein Literal traefe nur eine der beiden Fassungen und braeche auf der anderen
# ab -- immerhin sichtbar, aber trotzdem falsch: derselbe Bau muss fuer jede
# Sprache gelten. Die Strenge bleibt: genau ein Treffer, sonst Abbruch.
TOGGLE_MUSTER = re.compile(r'<button id="theme-btn"[^>]*>.*?</button>', re.S)
TIP_ALT = "position: fixed; z-index: 50; pointer-events: none"
TIP_NEU = "position: fixed; z-index: 40; pointer-events: none"
THEME_BLOCK_START = "/* ---------- Theme ---------- */"
THEME_BLOCK_ENDE = 'if (mq.addEventListener) mq.addEventListener("change", redrawCanvases);'

THEME_BRUECKE = """/* ---------- Theme (eingebettete Fassung) ---------- */
/* Der Host schaltet: dunkel, solange kein data-theme="light" gesetzt ist —
   dieselbe Bedingung wie in den CSS-Regeln dieses Fragments. Der seiteneigene
   Umschalter entfaellt; stattdessen zeichnen die Canvases neu, sobald das
   Menueband das Attribut aendert. */
function isDark() {
  return document.documentElement.getAttribute("data-theme") !== "light";
}
new MutationObserver(function () { redrawCanvases(); }).observe(
  document.documentElement,
  { attributes: true, attributeFilter: ["data-theme"] }
);"""


# Erste Zeile des Fragments. Ohne sie sieht, wer die Datei im Website-Repo
# oeffnet, 400 KB ohne jeden Hinweis auf ihre Herkunft. Bewusst OHNE
# Zeitstempel: bei gleicher Quelle muss das Fragment byte-identisch bleiben.
# Der Hash der Quelle macht den Bau-Stand trotzdem nachvollziehbar.
HERKUNFT_VORLAGE = (
    "<!--\n"
    "  Generiert - nicht von Hand bearbeiten.\n"
    "  Werkzeug: niedrigwasser-trendindex, scripts/build_embed.py\n"
    "  Sprache: {sprache}\n"
    "  Neu erzeugen: uv run python scripts/build_embed.py --lang {sprache} "
    "--target <diese Datei>\n"
    "  Quelle: exportierte oeffentliche Seite, sha256 (utf-8, LF) {hash}\n"
    "  Aenderungen an dieser Datei gehen beim naechsten Lauf verloren.\n"
    "-->\n"
)


def quell_hash(html: str) -> str:
    """SHA-256 des Quelltexts, so wie er hereinkommt (utf-8, LF-normalisiert)."""
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def herkunft(html: str, sprache: str) -> str:
    """Baut die Herkunftsmarkierung fuer eine Quelle.

    ``sprache`` hat bewusst keinen Default: Seit es zwei Sprachfassungen gibt,
    ist die Sprache das einzige Unterscheidungsmerkmal im Kopf, das ein Mensch
    ohne Hash-Vergleich lesen kann. Ein Default wuerde beide Fragmente
    denselben Kopf tragen lassen -- und der Fehler faellt erst auf, wenn jemand
    das falsche Fragment einbettet.
    """
    return HERKUNFT_VORLAGE.format(hash=quell_hash(html), sprache=sprache)


def ersetze_genau(text: str, alt: str, neu: str, marke: str) -> str:
    """Ersetzt genau ein Vorkommen und bricht ab, wenn es nicht genau eines ist."""
    anzahl = text.count(alt)
    if anzahl != 1:
        raise FragmentFehler(f"Marke {marke!r}: {anzahl} Treffer statt genau einem")
    return text.replace(alt, neu, 1)


def entferne_genau(text: str, muster: re.Pattern[str], marke: str) -> str:
    """Entfernt genau ein Vorkommen eines Musters; alles andere ist ein Abbruch.

    Regex-Gegenstueck zu ``ersetze_genau`` fuer Marken, deren Wortlaut
    sprachabhaengig ist und die deshalb ueber ihre Struktur erkannt werden.
    """
    anzahl = len(muster.findall(text))
    if anzahl != 1:
        raise FragmentFehler(f"Marke {marke!r}: {anzahl} Treffer statt genau einem")
    return muster.sub("", text, count=1)


def _schneide(text: str, start: str, ende: str, marke: str) -> str:
    """Schneidet den Bereich zwischen Start- und Endmarke heraus.

    Start- und Endmarke muessen je genau einmal vorkommen, sonst harter
    Abbruch -- analog zu ersetze_genau. Ein zweites Vorkommen duerfte sonst
    still zur falschen Stelle fuehren: schlimmer als ein No-Op, weil es wie
    ein Erfolg aussieht.
    """
    start_anzahl = text.count(start)
    if start_anzahl != 1:
        raise FragmentFehler(
            f"Marke {marke!r} (Start {start!r}): {start_anzahl} Treffer statt genau einem"
        )
    ende_anzahl = text.count(ende)
    if ende_anzahl != 1:
        raise FragmentFehler(
            f"Marke {marke!r} (Ende {ende!r}): {ende_anzahl} Treffer statt genau einem"
        )
    i = text.find(start)
    j = text.find(ende, i + len(start))
    if j == -1:
        raise FragmentFehler(f"Marke {marke!r}: Endmarke liegt vor der Startmarke")
    return text[i : j + len(ende)]


def build_fragment(html: str, sprache: str) -> str:
    """Macht aus der exportierten Seite ein einbettbares Fragment.

    ``sprache`` geht nur in den Herkunftskopf ein (siehe herkunft) und ist
    Pflicht, nicht Default -- sonst waeren die Fragmente beider Sprachen im
    Kopf nicht unterscheidbar.
    """
    css = _schneide(html, "<style>", "</style>", "style")[len("<style>") : -len("</style>")]
    rumpf = _schneide(html, "<body>", "</body>", "body")[len("<body>") : -len("</body>")]

    css = ersetze_genau(css, TIP_ALT, TIP_NEU, "tooltip-z-index")
    css = scope_css(css)

    rumpf = entferne_genau(rumpf, TOGGLE_MUSTER, "toggle-markup")
    theme_block = _schneide(rumpf, THEME_BLOCK_START, THEME_BLOCK_ENDE, "theme-block")
    rumpf = ersetze_genau(rumpf, theme_block, THEME_BRUECKE, "theme-bruecke")

    klasse = ROOT_CLASS.lstrip(".")
    return (
        f"{herkunft(html, sprache)}"
        f'<div class="{klasse}">\n'
        f"<style>\n{css}\n</style>\n"
        f"{rumpf.strip()}\n"
        f"</div>\n"
    )
