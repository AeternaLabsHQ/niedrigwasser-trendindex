"""Regressionstests gegen die reale JS-Quelle in site/template.html.

Diese Tests sind eine bewusste Ausnahme von der sonstigen Konvention dieses
Projekts, ausschliesslich mit synthetischen Fixtures zu testen: die
Formatierer fmt/fmtP/pText/fmtFlow/dayLabel leben ausschliesslich als
Inline-JavaScript im gepflegten Template (site/template.html), es gibt keine
extrahierbare, aus Python aufrufbare Funktion dafuer. Ein synthetisches
Duplikat der Logik koennte von der echten Quelle abweichen, ohne dass ein
Test es merkt -- deshalb wird hier direkt gegen die Quelldatei geprueft.

Zwei Sorten Test stehen hier:

* **Strukturell** -- Zeichenketten im Template, gegen genau benannte
  Rueckfaelle (hartkodiertes Dezimalkomma, Regex-Ableitung aus pLess).
* **Ausgefuehrt** -- die Funktionen laufen unter node mit den ECHTEN
  ``__locale__``-Bloecken beider Kataloge und werden gegen erwartete Ausgaben
  geprueft. Das verlangt die Spec unter Verifikation, und es ist keine
  Formalie: Der Fehler in Task 4 (Monatstabelle in Wasserjahr- statt
  Kalenderreihenfolge, rund 10148 falsch beschriftete Tooltips) haette genau
  hier auffallen muessen und wurde stattdessen von Hand gefunden.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
TEMPLATE = (WURZEL / "site" / "template.html").read_text(encoding="utf-8")

_NODE = shutil.which("node")

# Echtes Minuszeichen und Halbgeviertstrich -- in beiden Sprachen dieselben
# Zeichen (siehe Spec, "Sprachabhaengige Formatierung"). Hier als Name statt
# als Literal, damit die Erwartungswerte unten lesbar bleiben.
MINUS = "−"
GEDANKENSTRICH = "–"


# ------------------------------------------------------------ strukturell

def test_fmtflow_nullfall_traegt_kein_fest_codiertes_komma():
    """fmtFlow(0) darf nicht unabhaengig vom Locale-Satz '0,0' liefern.

    Eine Sen-Steigung von exakt 0 erschiene sonst auf jeder Sprache mit
    deutschem Dezimalkomma, auch auf einer englischen Seite.
    """
    assert '"0,0"' not in TEMPLATE
    assert 's = "0" + L.decimal + "0";' in TEMPLATE


def test_fmtp_leitet_seinen_wert_nicht_per_regex_aus_pless_ab():
    """fmtP darf seinen Kurzwert nicht aus L.pLess herausschneiden.

    Die Ableitung per Regex (/^p.../) haelt nur, solange der Katalogwert mit
    einem literalen 'p' beginnt -- ein Katalog, der pLess anders aufbaut,
    wuerde still den ganzen Satz durchreichen statt nur den Vergleichsteil.
    Der Katalog muss stattdessen beide Formen eigenstaendig tragen.
    """
    assert "replace(/^p" not in TEMPLATE
    assert (
        "function fmtP(p) { return p < 0.001 ? L.pLessValue : fmt(p, 4); }"
        in TEMPLATE
    )


# -------------------------------------------------------------- ausgefuehrt

def _js_funktion(name: str) -> str:
    """Quelltext einer Top-Level-Funktion aus dem Template.

    Zwei Formen, beide kommen vor: einzeilig (fmtP, pText) und als Block, der
    mit einer schliessenden Klammer in Spalte 0 endet (fmt, fmtFlow,
    dayLabel). Findet sich keine, bricht der Test ab statt still nichts zu
    pruefen -- eine Umbenennung im Template muss hier auffallen.
    """
    einzeilig = re.search(rf"^function {name}\(.*\}}$", TEMPLATE, re.M)
    if einzeilig:
        return einzeilig.group(0)
    block = re.search(rf"^function {name}\(.*?^\}}", TEMPLATE, re.M | re.S)
    assert block, f"{name}() nicht im Template gefunden"
    return block.group(0)


def _js_konstante(name: str) -> str:
    treffer = re.search(rf"^var {name} = \[[^\]]*\];", TEMPLATE, re.M)
    assert treffer, f"{name} nicht im Template gefunden"
    return treffer.group(0)


def _locale(sprache: str) -> dict:
    """Der ECHTE Locale-Block des Katalogs, keine Nachbildung.

    Ein Stub im Test koennte von der ausgelieferten Sprache abweichen, ohne
    dass es jemandem auffaellt -- genau die Luecke, gegen die diese Datei
    ueberhaupt gebaut ist.
    """
    pfad = WURZEL / "site" / f"text.{sprache}.json"
    return json.loads(pfad.read_text(encoding="utf-8"))["__locale__"]


def _lauf(sprache: str, ausdruecke: list[str]) -> list[str]:
    """Wertet die Ausdruecke unter node aus, eine Zeile Ausgabe je Ausdruck."""
    skript = (
        "var L = " + json.dumps(_locale(sprache), ensure_ascii=False) + ";\n"
        + _js_funktion("fmt") + "\n"
        + _js_funktion("fmtP") + "\n"
        + _js_funktion("pText") + "\n"
        + _js_funktion("fmtFlow") + "\n"
        + _js_konstante("MONTH_LEN") + "\n"
        + _js_konstante("MONTH_IDX") + "\n"
        + _js_funktion("dayLabel") + "\n"
        + "var _aus = [];\n"
        + "".join(f"_aus.push(String({a}));\n" for a in ausdruecke)
        + "process.stdout.write(JSON.stringify(_aus));\n"
    )
    lauf = subprocess.run(
        [_NODE, "-e", skript], capture_output=True, text=True, encoding="utf-8"
    )
    assert lauf.returncode == 0, lauf.stderr
    return json.loads(lauf.stdout)


# Erwartete Ausgaben je Sprache. Ein Eintrag ist (Ausdruck, deutsch, englisch).
# Die Tabelle liest sich absichtlich wie die Tabelle in der Spec.
_FMT_FAELLE = [
    # Tausender- und Dezimaltrennung
    ("fmt(1234.5, 1)", "1.234,5", "1,234.5"),
    ("fmt(1234567, 0)", "1.234.567", "1,234,567"),
    ("fmt(92.1, 1)", "92,1", "92.1"),
    # Werte unter 1 (Spec: "inklusive ... Werten unter 1")
    ("fmt(0.05, 2)", "0,05", "0.05"),
    ("fmt(0.0123, 4)", "0,0123", "0.0123"),
    # Echtes Minuszeichen, in beiden Sprachen
    ("fmt(-10, 1)", MINUS + "10,0", MINUS + "10.0"),
    ("fmt(-1234.5, 1)", MINUS + "1.234,5", MINUS + "1,234.5"),
    # Fehlwert
    ("fmt(null, 1)", GEDANKENSTRICH, GEDANKENSTRICH),
    ("fmt(undefined, 1)", GEDANKENSTRICH, GEDANKENSTRICH),
]

_P_FAELLE = [
    ("fmtP(0.0005)", "&lt; 0,001", "&lt; 0.001"),
    ("fmtP(0.0123)", "0,0123", "0.0123"),
    ("pText(0.0005)", "p &lt; 0,001", "p &lt; 0.001"),
    ("pText(0.0123)", "p = 0,0123", "p = 0.0123"),
    # Genau auf der Schwelle: 0.001 ist NICHT kleiner als 0.001.
    ("pText(0.001)", "p = 0,0010", "p = 0.0010"),
]

_FLOW_FAELLE = [
    # Null: der Fall, der frueher "0,0" hartkodiert trug.
    ("fmtFlow(0)", "0,0", "0.0"),
    # Betrag >= 1: eine Nachkommastelle
    ("fmtFlow(-10)", MINUS + "10,0", MINUS + "10.0"),
    ("fmtFlow(2.34)", "2,3", "2.3"),
    # Betrag < 1: zwei signifikante Stellen (Spec: "Werten unter 1")
    ("fmtFlow(0.004)", "0,004", "0.004"),
    ("fmtFlow(0.0123)", "0,012", "0.012"),
    ("fmtFlow(-0.0123)", MINUS + "0,012", MINUS + "0.012"),
    ("fmtFlow(null)", GEDANKENSTRICH, GEDANKENSTRICH),
]

# Wasserjahr: doy 0 = 1. November. 2001 ist kein Schaltjahr, 2000 eines
# (dayLabel liest wy % 4 === 0; die Reihe 1992-2025 macht das eindeutig).
_TAG_FAELLE = [
    ("dayLabel(0, 2001)", "1. Nov.", "1 Nov"),
    ("dayLabel(29, 2001)", "30. Nov.", "30 Nov"),
    ("dayLabel(30, 2001)", "1. Dez.", "1 Dec"),
    ("dayLabel(75, 2001)", "15. Jan.", "15 Jan"),
    # Februar-Rand: derselbe doy bedeutet je nach Wasserjahr etwas anderes.
    ("dayLabel(119, 2001)", "28. Feb.", "28 Feb"),
    ("dayLabel(120, 2001)", "1. Mär.", "1 Mar"),
    ("dayLabel(120, 2000)", "29. Feb.", "29 Feb"),
    # Oktober-Rand. Im Schalt-Wasserjahr traegt der letzte Spaltenindex die
    # upstream auf Tag 365 gefalteten 30.+31. Oktober (siehe daily_share.py).
    ("dayLabel(364, 2001)", "31. Okt.", "31 Oct"),
    ("dayLabel(363, 2000)", "29. Okt.", "29 Oct"),
    ("dayLabel(364, 2000)", "30." + GEDANKENSTRICH + "31. Okt.",
     "30" + GEDANKENSTRICH + "31 Oct"),
]

_ALLE_FAELLE = _FMT_FAELLE + _P_FAELLE + _FLOW_FAELLE + _TAG_FAELLE


@pytest.mark.skipif(_NODE is None, reason="node nicht verfuegbar")
@pytest.mark.parametrize("sprache", ["de", "en"])
def test_formatierer_liefern_die_erwarteten_ausgaben(sprache: str):
    """fmt, fmtP, pText, fmtFlow und dayLabel je Sprache gegen feste Werte.

    Gefahren wird mit dem echten Locale-Block des jeweiligen Katalogs. Die
    Erwartungswerte stehen als Literale da: Wer sie aus dem Katalog ableitete,
    bekaeme einen Test, der jede Aenderung des Katalogs mitmacht.
    """
    spalte = 1 if sprache == "de" else 2
    ausdruecke = [fall[0] for fall in _ALLE_FAELLE]
    erwartet = [fall[spalte] for fall in _ALLE_FAELLE]
    ist = _lauf(sprache, ausdruecke)

    abweichungen = [
        (a, e, i) for a, e, i in zip(ausdruecke, erwartet, ist) if e != i
    ]
    assert abweichungen == [], f"Sprache {sprache!r}: {abweichungen}"


@pytest.mark.skipif(_NODE is None, reason="node nicht verfuegbar")
def test_beide_sprachen_unterscheiden_sich_wirklich():
    """Gegenprobe: der Locale-Schalter muss ueberhaupt etwas bewirken.

    Ohne diesen Test bliebe offen, ob die Tabelle oben zweimal dasselbe prueft
    -- ein Formatierer, der L ignoriert und fest deutsch formatiert, bestuende
    den deutschen Lauf und faellt nur im englischen auf, wenn sich die
    erwarteten Werte tatsaechlich unterscheiden.
    """
    verschieden = [f[0] for f in _ALLE_FAELLE if f[1] != f[2]]
    assert len(verschieden) >= 20, (
        f"nur {len(verschieden)} Faelle trennen die Sprachen"
    )


@pytest.mark.skipif(_NODE is None, reason="node nicht verfuegbar")
def test_dayLabel_deckt_das_wasserjahr_lueckenlos_ab():
    """365 Spalten, 365 verschiedene Beschriftungen, keine leere.

    Der Fehler aus Task 4 (MONTH_LEN/MONTH_IDX in Wasserjahr- statt
    Kalenderreihenfolge) hat rund 10148 Tooltips falsch beschriftet und wurde
    von Hand gefunden. Er zeigte sich als falscher Monatsname, nicht als
    Luecke -- deshalb prueft dieser Test zusaetzlich die Monatsfolge: ueber das
    Wasserjahr gelesen muessen die Monatsnamen in genau der Reihenfolge
    November bis Oktober auftreten.
    """
    labels = _lauf("de", [f"dayLabel({doy}, 2001)" for doy in range(365)])
    assert "" not in labels, "dayLabel liefert fuer mindestens einen Tag nichts"
    assert len(set(labels)) == 365, "doppelte Tagesbeschriftung"

    monate = []
    for label in labels:
        name = label.split(" ")[-1]
        if not monate or monate[-1] != name:
            monate.append(name)
    # Der Punkt sitzt im Monatsnamen (L.monthsDate), nicht in L.dateFormat --
    # deshalb traegt jede Abkuerzung ihren Abkuerzungspunkt, 'Mai' als
    # ungekuerztes Wort aber keinen. Solange der Punkt im Format sass, bekam
    # auch Mai einen ('15. Mai.').
    assert monate == [
        "Nov.", "Dez.", "Jan.", "Feb.", "Mär.", "Apr.",
        "Mai", "Jun.", "Jul.", "Aug.", "Sep.", "Okt.",
    ], monate


def test_dayLabel_setzt_den_abkuerzungspunkt_nur_bei_abkuerzungen():
    """'15. Mai' ohne Punkt, '15. Jan.' mit -- und Englisch ganz ohne.

    Regressionstest fuer die Trennung von L.months (Achsenbeschriftung, steht
    fuer sich) und L.monthsDate (steht in einer Datumsangabe). Wandert der
    Punkt zurueck nach L.dateFormat, faellt der Mai-Fall hier auf.
    """
    # Wasserjahr 2001 (kein Schaltjahr): doy 0 = 1. Nov, Januar beginnt bei 61.
    jan14, mai14 = _lauf("de", ["dayLabel(75, 2001)", "dayLabel(195, 2001)"])
    assert jan14 == "15. Jan.", jan14
    assert mai14 == "15. Mai", mai14

    en_jan, en_mai = _lauf("en", ["dayLabel(75, 2001)", "dayLabel(195, 2001)"])
    assert en_jan == "15 Jan", en_jan
    assert en_mai == "15 May", en_mai


def test_achsenbeschriftung_traegt_keinen_abkuerzungspunkt():
    """L.months bleibt punktlos -- die Monatsachse steht ohne Datum daneben."""
    for sprache in ("de", "en"):
        monate = json.loads(
            (WURZEL / "site" / f"text.{sprache}.json").read_text(encoding="utf-8")
        )["__locale__"]["months"]
        mit_punkt = [m for m in monate if m.endswith(".")]
        assert not mit_punkt, f"{sprache}: Achsenbeschriftung mit Punkt: {mit_punkt}"
