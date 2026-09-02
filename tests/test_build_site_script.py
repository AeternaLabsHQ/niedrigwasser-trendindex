"""Testet scripts/build_site.py -- den duennen Wrapper um embed_site.

scripts/ ist kein Paket (kein __init__.py); geladen wird deshalb per
importlib ueber den Dateipfad, nicht per regulaerem Import. scripts/build_site.py
steht in der Export-Allow-Liste (scripts/export_public.py) und ist damit Teil
der oeffentlichen Fassung -- ein Import von hier bricht die Suite dort nicht.
"""

import importlib.util
import json
from pathlib import Path

import pytest

from niedrigwasser.i18n import I18nFehler

SKRIPT_PFAD = Path(__file__).resolve().parents[1] / "scripts" / "build_site.py"


def _lade_build_site_skript():
    spec = importlib.util.spec_from_file_location("build_site_skript", SKRIPT_PFAD)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _lokale_locale_stub() -> dict:
    return {
        "decimal": ",",
        "thousands": ".",
        "percentSpaceNoBreak": "&nbsp;",
        "percentSpaceBreaking": " ",
        "months": ["Jan"],
        "monthsDate": ["Jan."],
        "dateFormat": "{d}. {m}.",
        "dateRange": "{a}\u2013{b}. {m}.",
        "pLess": "p &lt; 0,001",
        "pLessValue": "&lt; 0,001",
    }


def test_build_site_main_erzeugt_index_html_mit_katalog(tmp_path):
    """Regression: main() rief embed_site() bisher ohne text_path auf.

    Seit das Template den /*__TEXT__*/-Marker traegt, brach das mit
    'ValueError: Marker /*__TEXT__*/ ohne --site-text' ab -- genau der
    Absturz, den scripts/build_site.py als dokumentierter Befehl (README,
    Export-Allow-Liste) nicht zeigen darf.
    """
    modul = _lade_build_site_skript()

    site = tmp_path / "site"
    site.mkdir()
    (site / "template.html").write_text(
        '<script id="t" type="application/json">/*__TEXT__*/</script>'
        '<script id="d" type="application/json">/*__DATA__*/</script>',
        encoding="utf-8",
    )
    (site / "data.json").write_text('{"x": 1}', encoding="utf-8")
    (site / "text.de.json").write_text(
        json.dumps({"a": "x", "__locale__": _lokale_locale_stub()}),
        encoding="utf-8",
    )

    out = modul.main(root=tmp_path)

    assert out == site / "index.html"
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "/*__TEXT__*/" not in html
    assert "/*__DATA__*/" not in html
    assert '"LOCALE"' in html and '"TEXTE"' in html


def test_build_site_main_bricht_bei_fehlendem_datenplatzhalter_in_en_ab(tmp_path):
    """Fix-Runde 1 zu Task 7: die Kreuzpruefung muss auf JEDEM Bauweg greifen.

    Bisher lief pruefe_kataloge nur, wenn render.run() den Aufruf vorschaltete
    -- scripts/build_site.py rief embed_site() direkt auf und lief an der
    Pruefung vorbei durch. Reproduziert exakt den vom Reviewer gefundenen Fall:
    ein Datenplatzhalter (id) fehlt in der englischen Fassung.
    """
    modul = _lade_build_site_skript()

    site = tmp_path / "site"
    site.mkdir()
    (site / "template.html").write_text(
        '<div data-i18n="a"><span id="k-x">0</span></div>'
        '<script id="d" type="application/json">/*__DATA__*/</script>',
        encoding="utf-8",
    )
    (site / "data.json").write_text('{"x": 1}', encoding="utf-8")
    (site / "text.de.json").write_text(
        json.dumps({"a": '<span id="k-x">Wert</span>', "__locale__": _lokale_locale_stub()}),
        encoding="utf-8",
    )
    (site / "text.en.json").write_text(
        json.dumps({"a": "<span>Value</span>", "__locale__": _lokale_locale_stub()}),
        encoding="utf-8",
    )

    with pytest.raises(I18nFehler, match="Datenplatzhalter"):
        modul.main(root=tmp_path)

    assert not (site / "index.html").exists()


def _zweisprachiges_site(tmp_path):
    """Template plus zwei gueltige Kataloge, wie im echten Repo."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "template.html").write_text(
        '<div data-i18n="a"><span id="k-x">0</span></div>'
        '<script id="d" type="application/json">/*__DATA__*/</script>',
        encoding="utf-8",
    )
    (site / "data.json").write_text('{"x": 1}', encoding="utf-8")
    (site / "text.de.json").write_text(
        json.dumps({"a": '<span id="k-x">Wert</span>',
                    "__locale__": _lokale_locale_stub()}),
        encoding="utf-8",
    )
    (site / "text.en.json").write_text(
        json.dumps({"a": '<span id="k-x">Value</span>',
                    "__locale__": _lokale_locale_stub()}),
        encoding="utf-8",
    )
    return site


def test_build_site_main_schreibt_beide_sprachfassungen(tmp_path):
    """Das Skript muss ein gleichwertiger Bauweg sein, kein halber.

    Vorher verdrahtete es text.de.json fest und fasste index.en.html nie an --
    nach einem Lauf stand eine frische deutsche neben einer veralteten
    englischen Seite, ohne Log-Zeile. Das Skript steht in der
    Export-Allow-Liste und wird in der README namentlich empfohlen.
    """
    modul = _lade_build_site_skript()
    site = _zweisprachiges_site(tmp_path)

    out = modul.main(root=tmp_path)

    assert out == site / "index.html"
    deutsch = (site / "index.html").read_text(encoding="utf-8")
    englisch = (site / "index.en.html").read_text(encoding="utf-8")
    assert '<span id="k-x">Wert</span>' in deutsch and "Value" not in deutsch
    assert '<span id="k-x">Value</span>' in englisch and "Wert" not in englisch


def test_build_site_main_entfernt_veraltete_zweitsprache(tmp_path):
    """Ohne Geschwisterkatalog darf keine alte zweite Fassung liegen bleiben.

    Dieselbe Regel wie in der render-Stage -- sonst haengt die Absicherung
    daran, welchen Bauweg jemand waehlt.
    """
    modul = _lade_build_site_skript()
    site = _zweisprachiges_site(tmp_path)
    veraltet = site / "index.en.html"
    veraltet.write_text("<p>Stand von gestern</p>", encoding="utf-8")
    (site / "text.en.json").unlink()

    modul.main(root=tmp_path)

    assert (site / "index.html").exists()
    assert not veraltet.exists(), "veraltete zweite Sprachfassung blieb liegen"
