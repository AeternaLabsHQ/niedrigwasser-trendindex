import json

import pytest

from niedrigwasser.i18n import I18nFehler
from niedrigwasser.site_embed import GEO_MARKER, MARKER, TEXT_MARKER, embed_site


def test_embed_site_replaces_marker_and_escapes(tmp_path):
    template = tmp_path / "template.html"
    template.write_text(
        f'<script id="d" type="application/json">{MARKER}</script>',
        encoding="utf-8",
    )
    data = {"meta": {"note": "a</script><b>"}, "years": [1992, 2025]}
    data_path = tmp_path / "data.json"
    data_path.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "index.html"

    size = embed_site(template, data_path, out)

    html = out.read_text(encoding="utf-8")
    assert size == out.stat().st_size
    assert MARKER not in html
    # kein rohes '</' im Payload — der Script-Block darf nicht vorzeitig enden
    assert "a</script><b>" not in html
    assert "a<\\/script><b>" in html
    # Roundtrip: der eingebettete Payload parst zurueck zu den Originaldaten
    payload = html.split('type="application/json">', 1)[1].split("</script>", 1)[0]
    assert json.loads(payload.replace("<\\/", "</")) == data


def test_embed_site_embeds_geo(tmp_path):
    template = tmp_path / "template.html"
    template.write_text(
        f'<script id="d" type="application/json">{MARKER}</script>'
        f'<script id="g" type="application/json">{GEO_MARKER}</script>',
        encoding="utf-8",
    )
    (tmp_path / "data.json").write_text('{"a":1}', encoding="utf-8")
    geo = {"land": [[[6.0, 50.0], [7.0, 51.0]]], "rivers": []}
    geo_path = tmp_path / "geo.json"
    geo_path.write_text(json.dumps(geo), encoding="utf-8")
    out = tmp_path / "index.html"

    embed_site(template, tmp_path / "data.json", out, geo_path=geo_path)

    html = out.read_text(encoding="utf-8")
    assert MARKER not in html and GEO_MARKER not in html
    payload = html.split('id="g" type="application/json">', 1)[1].split("</script>", 1)[0]
    assert json.loads(payload.replace("<\\/", "</")) == geo


def test_embed_site_geo_marker_without_file_yields_empty_object(tmp_path):
    template = tmp_path / "template.html"
    template.write_text(
        f'<script id="d" type="application/json">{MARKER}</script>'
        f'<script id="g" type="application/json">{GEO_MARKER}</script>',
        encoding="utf-8",
    )
    (tmp_path / "data.json").write_text('{"a":1}', encoding="utf-8")
    out = tmp_path / "index.html"

    # geo_path=None und geo_path auf nicht existente Datei -> beides '{}'
    embed_site(template, tmp_path / "data.json", out, geo_path=None)
    html = out.read_text(encoding="utf-8")
    assert GEO_MARKER not in html
    assert 'id="g" type="application/json">{}</script>' in html

    embed_site(template, tmp_path / "data.json", out, geo_path=tmp_path / "fehlt.json")
    html = out.read_text(encoding="utf-8")
    assert 'id="g" type="application/json">{}</script>' in html


def test_embed_site_requires_marker(tmp_path):
    template = tmp_path / "template.html"
    template.write_text("<html>kein Marker</html>", encoding="utf-8")
    data_path = tmp_path / "data.json"
    data_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Marker"):
        embed_site(template, data_path, tmp_path / "index.html")


def test_embed_site_setzt_katalogwerte_ein(tmp_path):
    template = tmp_path / "template.html"
    template.write_text(
        '<p data-i18n="a">alt</p>'
        f'<script id="d" type="application/json">{MARKER}</script>',
        encoding="utf-8",
    )
    (tmp_path / "data.json").write_text('{"x":1}', encoding="utf-8")
    text = tmp_path / "text.de.json"
    text.write_text('{"a": "neu"}', encoding="utf-8")
    out = tmp_path / "index.html"

    embed_site(template, tmp_path / "data.json", out, text_path=text)

    html = out.read_text(encoding="utf-8")
    # Die Markierung ist Build-Metadatum und wird von der Ausgabestufe entfernt.
    assert "<p>neu</p>" in html
    assert ">alt<" not in html
    assert "data-i18n" not in html


def test_embed_site_ohne_katalog_verhaelt_sich_wie_bisher(tmp_path):
    template = tmp_path / "template.html"
    template.write_text(
        f'<p data-i18n="a">alt</p><script id="d" type="application/json">{MARKER}</script>',
        encoding="utf-8",
    )
    (tmp_path / "data.json").write_text('{"x":1}', encoding="utf-8")
    out = tmp_path / "index.html"

    embed_site(template, tmp_path / "data.json", out)

    assert '<p data-i18n="a">alt</p>' in out.read_text(encoding="utf-8")


def test_embed_site_bricht_bei_fehlendem_locale_block_ab(tmp_path):
    """Ein Katalog ohne __locale__ darf nicht still LOCALE={} einbetten.

    Sonst sind L.thousands/L.decimal im Browser undefined, und
    String.replace(regex, undefined) schreibt woertlich 'undefined' in jede
    Zahl -- kein Absturz, keine verstaendliche Meldung, nur eine kaputte Seite.
    """
    template = tmp_path / "template.html"
    template.write_text(
        f'<script id="t" type="application/json">{TEXT_MARKER}</script>'
        f'<script id="d" type="application/json">{MARKER}</script>',
        encoding="utf-8",
    )
    (tmp_path / "data.json").write_text('{"x":1}', encoding="utf-8")
    text = tmp_path / "text.de.json"
    text.write_text('{"a": "x"}', encoding="utf-8")

    with pytest.raises(I18nFehler, match="__locale__"):
        embed_site(template, tmp_path / "data.json", tmp_path / "index.html", text_path=text)


def test_embed_site_bricht_bei_unvollstaendigem_locale_block_ab(tmp_path):
    template = tmp_path / "template.html"
    template.write_text(
        f'<script id="t" type="application/json">{TEXT_MARKER}</script>'
        f'<script id="d" type="application/json">{MARKER}</script>',
        encoding="utf-8",
    )
    (tmp_path / "data.json").write_text('{"x":1}', encoding="utf-8")
    text = tmp_path / "text.de.json"
    text.write_text('{"a": "x", "__locale__": {"decimal": ","}}', encoding="utf-8")

    with pytest.raises(I18nFehler, match="thousands"):
        embed_site(template, tmp_path / "data.json", tmp_path / "index.html", text_path=text)


def _locale_stub() -> dict:
    """Vollstaendiger __locale__-Block fuer die Fix-Runde-2-Tests."""
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


def test_embed_site_locale_fehler_nennt_die_sprache(tmp_path):
    """Fix-Runde 2, Important: pruefe_locale nannte bisher nicht, welcher
    Katalog betroffen ist -- bei zwei Katalogen in einer Schleife erfaehrt man
    nur, dass IRGENDEINER ein Feld vermisst, nicht welcher. Hier fehlt
    'dateRange' in der englischen Fassung -- die Meldung muss 'en' nennen.
    """
    template = tmp_path / "template.html"
    template.write_text(
        f'<p data-i18n="a">alt</p><script id="d" type="application/json">{MARKER}</script>',
        encoding="utf-8",
    )
    (tmp_path / "data.json").write_text('{"x":1}', encoding="utf-8")
    (tmp_path / "text.de.json").write_text(
        json.dumps({"a": "x", "__locale__": _locale_stub()}), encoding="utf-8"
    )
    unvollstaendig = _locale_stub()
    del unvollstaendig["dateRange"]
    (tmp_path / "text.en.json").write_text(
        json.dumps({"a": "y", "__locale__": unvollstaendig}), encoding="utf-8"
    )

    with pytest.raises(I18nFehler, match="'en'.*dateRange"):
        embed_site(
            template, tmp_path / "data.json", tmp_path / "index.html",
            text_path=tmp_path / "text.de.json",
        )


def test_embed_site_bricht_bei_widerspruechlicher_sprachkennung_ab(tmp_path):
    """Fix-Runde 1 zu Task 8: doc.lang und __locale__.lang muessen zusammenpassen.

    Der Katalog traegt seinen Sprachcode zweimal -- einmal als Metadatum des
    Locale-Blocks, einmal als Textschluessel, aus dem das lang-Attribut des
    <html>-Elements gefuellt wird. Hier sagt der englische Katalog
    __locale__.lang = "en", setzt aber doc.lang = "de": Die gebaute Seite
    traege <html lang="de"> und englischen Text. Kein Absturz, keine sichtbare
    Auffaelligkeit -- deshalb muss der Build hier abbrechen, und die Meldung
    muss 'en' nennen.
    """
    template = tmp_path / "template.html"
    template.write_text(
        '<html data-i18n-attr="lang:doc.lang" lang="de">'
        f'<p data-i18n="a">alt</p><script id="d" type="application/json">{MARKER}</script>'
        "</html>",
        encoding="utf-8",
    )
    (tmp_path / "data.json").write_text('{"x":1}', encoding="utf-8")

    locale_de = _locale_stub()
    locale_de["lang"] = "de"
    (tmp_path / "text.de.json").write_text(
        json.dumps({"a": "x", "doc.lang": "de", "__locale__": locale_de}),
        encoding="utf-8",
    )
    locale_en = _locale_stub()
    locale_en["lang"] = "en"
    (tmp_path / "text.en.json").write_text(
        json.dumps({"a": "y", "doc.lang": "de", "__locale__": locale_en}),
        encoding="utf-8",
    )

    with pytest.raises(I18nFehler, match="'en'.*Sprachkennung"):
        embed_site(
            template, tmp_path / "data.json", tmp_path / "index.html",
            text_path=tmp_path / "text.de.json",
        )
    # Erst pruefen, dann schreiben -- die halbfertige Seite darf nicht liegen
    # bleiben.
    assert not (tmp_path / "index.html").exists()


def test_embed_site_prueft_primaeren_locale_block_nur_einmal(tmp_path, monkeypatch):
    """Fix-Runde 2, Minor: pruefe_locale lief bisher zweimal fuer den primaeren
    Katalog -- einmal in der Kreuzpruef-Schleife, einmal beim Bau des
    Katalog-Blobs (TEXT_MARKER-Zweig). Idempotent, aber unnoetige Doppelarbeit
    bei jedem echten Build. Ein Spy um pruefe_locale zaehlt die Aufrufe je
    Sprache -- bei zwei Katalogen muessen es exakt zwei sein, nicht drei.
    """
    import niedrigwasser.i18n as i18n_mod

    aufrufe: list[str | None] = []
    original = i18n_mod.pruefe_locale

    def spion(katalog, sprache=None):
        aufrufe.append(sprache)
        return original(katalog, sprache)

    monkeypatch.setattr(i18n_mod, "pruefe_locale", spion)

    template = tmp_path / "template.html"
    template.write_text(
        '<p data-i18n="a">alt</p>'
        f'<script id="t" type="application/json">{TEXT_MARKER}</script>'
        f'<script id="d" type="application/json">{MARKER}</script>',
        encoding="utf-8",
    )
    (tmp_path / "data.json").write_text('{"x":1}', encoding="utf-8")
    (tmp_path / "text.de.json").write_text(
        json.dumps({"a": "x", "__locale__": _locale_stub()}), encoding="utf-8"
    )
    (tmp_path / "text.en.json").write_text(
        json.dumps({"a": "y", "__locale__": _locale_stub()}), encoding="utf-8"
    )

    embed_site(
        template, tmp_path / "data.json", tmp_path / "index.html",
        text_path=tmp_path / "text.de.json",
    )

    assert aufrufe == ["de", "en"]


def test_embed_site_bricht_bei_konsistent_falscher_sprachkennung_ab(tmp_path):
    """Fix-Runde 2 zu Task 8: der gefaehrlichere Fall ist der stimmige.

    text.en.json sagt in BEIDEN inneren Angaben "de" -- doc.lang und
    __locale__.lang stimmen also ueberein und faenden sich gegenseitig nie.
    Der Dateiname sagt "en", und er ist der einzige mit Wirkung: aus ihm wird
    index.en.html. Ohne ihn im Vergleich entstuende eine englische Datei mit
    <html lang="de">.
    """
    template = tmp_path / "template.html"
    template.write_text(
        '<html data-i18n-attr="lang:doc.lang" lang="de">'
        f'<p data-i18n="a">alt</p><script id="d" type="application/json">{MARKER}</script>'
        "</html>",
        encoding="utf-8",
    )
    (tmp_path / "data.json").write_text('{"x":1}', encoding="utf-8")

    locale_de = _locale_stub()
    locale_de["lang"] = "de"
    (tmp_path / "text.de.json").write_text(
        json.dumps({"a": "x", "doc.lang": "de", "__locale__": locale_de}),
        encoding="utf-8",
    )
    # In sich stimmig, zum Dateinamen aber falsch.
    locale_en = _locale_stub()
    locale_en["lang"] = "de"
    (tmp_path / "text.en.json").write_text(
        json.dumps({"a": "y", "doc.lang": "de", "__locale__": locale_en}),
        encoding="utf-8",
    )

    with pytest.raises(I18nFehler, match="'en'.*Dateiname"):
        embed_site(
            template, tmp_path / "data.json", tmp_path / "index.html",
            text_path=tmp_path / "text.de.json",
        )
    assert not (tmp_path / "index.html").exists()
