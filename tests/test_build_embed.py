"""Testet niedrigwasser.embed_build: Gate-Pruefung und die Ablaufpfade von baue_embed.

Zwei bewusste Entscheidungen in dieser Datei:

1. Importiert wird aus dem Paket, nicht aus ``scripts/``. Das Skript dort ist
   nur ein Aufrufer und gehoert nicht zur oeffentlichen Fassung -- ein Import
   von dort wuerde die Suite im exportierten Repo schon beim Einsammeln
   brechen. Darum auch kein sys.path-Eingriff.

2. Geprueft wird gegen eine kuenstliche Musterliste. Die echten Verbots-Muster
   als Literal in dieser Datei wuerden genau das Gate ausloesen, dessen Funktion
   sie beweisen sollen -- tests/ wird vollstaendig exportiert und mitgeprueft.
   Geprueft wird hier der Mechanismus; dass er mit den echten Mustern ueber das
   echte Fragment laeuft, prueft test_embed_fragment.py.
"""

from pathlib import Path

from niedrigwasser.embed_build import baue_embed, pruefe_gates

from test_embed_fragment import SEITE as GUELTIGE_SEITE

# Kuenstliche Verbots-Muster in der Form der echten: (Name, Regex).
MUSTER = [("kunstmarke", r"kunstmarke"), ("zweite", r"zweite-kunstmarke")]

# Dieselbe gueltige Seite wie in test_embed_fragment.py -- durchlaeuft
# build_fragment ohne FragmentFehler --, nur mit einer Marke, die eines der
# Muster trifft, damit baue_embed den Gate-Pfad tatsaechlich nimmt.
SEITE_MIT_LECK = GUELTIGE_SEITE.replace("Inhalt", "Hier steht KUNSTMARKE mittendrin.")


def test_pruefe_gates_findet_treffer_case_insensitiv():
    treffer = pruefe_gates("Hier steht KUNSTMARKE mittendrin.", MUSTER)
    assert len(treffer) == 1
    assert "[kunstmarke]" in treffer[0]


def test_pruefe_gates_nennt_zeile_und_ausschnitt():
    text = "harmlose Zeile\nnoch eine\nhier steht kunstmarke drin\n"
    treffer = pruefe_gates(text, MUSTER)
    assert treffer == ["Zeile 3: [kunstmarke] hier steht kunstmarke drin"]


def test_pruefe_gates_kuerzt_sehr_lange_zeilen():
    # Der Realfall: eingebettetes JSON in einer einzigen sehr langen Zeile.
    lange_zeile = "x" * 500 + "kunstmarke" + "y" * 500
    (treffer,) = pruefe_gates(lange_zeile, MUSTER)
    assert treffer.startswith("Zeile 1: [kunstmarke] ")
    assert len(treffer) < 200


def test_pruefe_gates_meldet_nichts_bei_sauberem_text():
    assert pruefe_gates("Ein voellig unverfaenglicher Text ueber Fluesse.", MUSTER) == []


def test_baue_embed_bricht_vor_dem_schreiben_ab_wenn_ein_gate_trifft(tmp_path, capsys):
    quelle = tmp_path / "quelle.html"
    quelle.write_text(SEITE_MIT_LECK, encoding="utf-8")
    target = tmp_path / "ziel" / "fragment.html"

    rc = baue_embed(quelle, target, MUSTER, "de")

    assert rc == 3
    # Reihenfolge "erst pruefen, dann schreiben": weder Datei noch
    # Zielverzeichnis duerfen entstanden sein.
    assert not target.exists()
    assert not target.parent.exists()
    fehler = capsys.readouterr().err
    assert "[kunstmarke]" in fehler


def test_baue_embed_meldet_fehlende_quelle_ohne_stacktrace(tmp_path, capsys):
    fehlende_quelle = tmp_path / "fehlt.html"
    target = tmp_path / "ziel" / "fragment.html"

    rc = baue_embed(fehlende_quelle, target, MUSTER, "de")

    assert rc == 2
    assert not target.exists()
    fehler = capsys.readouterr().err
    assert "Traceback" not in fehler
    assert str(fehlende_quelle) in fehler


def test_baue_embed_schreibt_bei_sauberem_fragment(tmp_path):
    quelle = tmp_path / "quelle.html"
    quelle.write_text(GUELTIGE_SEITE, encoding="utf-8")
    target = tmp_path / "ziel" / "fragment.html"

    rc = baue_embed(quelle, target, MUSTER, "de")

    assert rc == 0
    assert target.read_text(encoding="utf-8").lstrip().startswith("<!--")


def test_baue_embed_schreibt_zweimal_byte_identisch(tmp_path):
    """Determinismus ueber den echten Schreibweg, nicht ueber zwei Funktionsaufrufe."""
    quelle = tmp_path / "quelle.html"
    quelle.write_text(GUELTIGE_SEITE, encoding="utf-8")
    erst = tmp_path / "lauf-a" / "fragment.html"
    zweit = tmp_path / "lauf-b" / "fragment.html"

    assert baue_embed(quelle, erst, MUSTER, "de") == 0
    assert baue_embed(quelle, zweit, MUSTER, "de") == 0
    assert erst.read_bytes() == zweit.read_bytes()


def test_die_publikationsschicht_bleibt_ausserhalb_des_pakets():
    """Kein Modul unter src/ darf die Verbots-Muster importieren.

    Der Import laege sonst im oeffentlichen Export, wo scripts/export_public.py
    fehlt -- das Paket waere dort nicht mehr importierbar.
    """
    paket = Path(__file__).resolve().parents[1] / "src" / "niedrigwasser"
    for modul in paket.rglob("*.py"):
        text = modul.read_text(encoding="utf-8")
        assert "import export_public" not in text, modul
        assert "from export_public" not in text, modul
