import json
import re

import pytest

from niedrigwasser.i18n import (
    I18nFehler,
    entferne_markierungen,
    lade_katalog,
    pruefe_kataloge,
    pruefe_locale,
    sammle_schluessel,
)


def _schreib(tmp_path, name, inhalt):
    p = tmp_path / name
    p.write_text(json.dumps(inhalt, ensure_ascii=False), encoding="utf-8")
    return p


def test_lade_katalog_liest_flaches_dict(tmp_path):
    p = _schreib(tmp_path, "text.de.json", {"hero.lede": "Hallo <b>Welt</b>"})
    assert lade_katalog(p) == {"hero.lede": "Hallo <b>Welt</b>"}


def test_lade_katalog_bricht_bei_verschachtelung_ab(tmp_path):
    p = _schreib(tmp_path, "text.de.json", {"hero": {"lede": "x"}})
    with pytest.raises(I18nFehler, match="flach"):
        lade_katalog(p)


def test_sammle_schluessel_findet_inhalt_und_attribute():
    html = (
        '<p data-i18n="hero.lede">Text</p>'
        '<button data-i18n-attr="aria-label:karte.label,title:karte.titel">x</button>'
    )
    assert sammle_schluessel(html) == {"hero.lede", "karte.label", "karte.titel"}


def test_pruefe_kataloge_akzeptiert_vollstaendige_saetze():
    html = '<p data-i18n="a">x</p>'
    pruefe_kataloge(html, {"de": {"a": "deutsch"}, "en": {"a": "english"}})


def test_pruefe_kataloge_bricht_bei_fehlendem_schluessel_ab():
    html = '<p data-i18n="a">x</p>'
    with pytest.raises(I18nFehler, match="fehlt.*en"):
        pruefe_kataloge(html, {"de": {"a": "deutsch"}, "en": {}})


def test_pruefe_kataloge_bricht_bei_totem_schluessel_ab():
    html = '<p data-i18n="a">x</p>'
    with pytest.raises(I18nFehler, match="unbenutzt"):
        pruefe_kataloge(html, {"de": {"a": "d", "tot": "x"}, "en": {"a": "e", "tot": "y"}})


def test_pruefe_kataloge_bricht_bei_script_im_wert_ab():
    html = '<p data-i18n="a">x</p>'
    with pytest.raises(I18nFehler, match="script"):
        pruefe_kataloge(html, {"de": {"a": "<script>x</script>"}, "en": {"a": "e"}})


def test_pruefe_kataloge_bricht_bei_abweichenden_ids_ab():
    """Der gefaehrlichste Fehler: die Uebersetzung verliert einen Datenplatzhalter.

    Die Seite sieht heil aus, aber die Kennzahl bleibt leer.
    """
    html = '<p data-i18n="a">x</p>'
    with pytest.raises(I18nFehler, match="k-median"):
        pruefe_kataloge(
            html,
            {"de": {"a": 'bis zu <span id="k-median">…</span> Tage'},
             "en": {"a": "up to … days"}},
        )


def test_pruefe_kataloge_akzeptiert_gleiche_ids_in_anderer_reihenfolge():
    html = '<p data-i18n="a">x</p>'
    pruefe_kataloge(
        html,
        {"de": {"a": '<span id="x"></span> und <span id="y"></span>'},
         "en": {"a": '<span id="y"></span> and <span id="x"></span>'}},
    )


def test_pruefe_kataloge_toleriert_abweichende_data_id_attribute():
    """'data-id' ist kein Datenplatzhalter -- der Regex darf nicht auf \b hereinfallen."""
    html = '<p data-i18n="a">x</p>'
    pruefe_kataloge(
        html,
        {"de": {"a": '<a data-id="fn1">Text</a>'},
         "en": {"a": '<a data-id="fn2">Text</a>'}},
    )


def test_pruefe_kataloge_erkennt_echtes_id_trotz_gleichem_data_id():
    """Ein echter 'id'-Unterschied muss weiter abbrechen, auch wenn 'data-id' gleich bleibt."""
    html = '<p data-i18n="a">x</p>'
    with pytest.raises(I18nFehler, match="k-median"):
        pruefe_kataloge(
            html,
            {"de": {"a": '<a data-id="fn1"><span id="k-median">1</span></a>'},
             "en": {"a": '<a data-id="fn1"><span id="anders">1</span></a>'}},
        )


from niedrigwasser.i18n import wende_an


def test_wende_an_ersetzt_inneren_inhalt():
    html = '<p data-i18n="a">alter Text</p>'
    assert wende_an(html, {"a": "neu"}) == '<p data-i18n="a">neu</p>'


def test_wende_an_ersetzt_inhalt_mit_markup():
    html = '<div data-i18n="a">x</div>'
    ergebnis = wende_an(html, {"a": 'bis zu <span id="k">…</span> Tage'})
    assert ergebnis == '<div data-i18n="a">bis zu <span id="k">…</span> Tage</div>'


def test_wende_an_ersetzt_attribute():
    html = '<button data-i18n-attr="aria-label:a" aria-label="alt">x</button>'
    ergebnis = wende_an(html, {"a": "neu"})
    assert 'aria-label="neu"' in ergebnis
    assert 'aria-label="alt"' not in ergebnis


def test_wende_an_ersetzt_mehrere_attribute():
    html = '<b data-i18n-attr="aria-label:a,title:t" aria-label="x" title="y">z</b>'
    ergebnis = wende_an(html, {"a": "A", "t": "T"})
    assert 'aria-label="A"' in ergebnis and 'title="T"' in ergebnis


def test_wende_an_laesst_unmarkierte_elemente_unberuehrt():
    html = '<p>unberuehrt</p><p data-i18n="a">x</p>'
    assert "<p>unberuehrt</p>" in wende_an(html, {"a": "y"})


def test_wende_an_bricht_bei_fehlendem_schluessel_ab():
    with pytest.raises(I18nFehler, match="fehlt"):
        wende_an('<p data-i18n="a">x</p>', {})


def test_wende_an_bricht_bei_verschachtelten_i18n_elementen_ab():
    """Verschachtelung waere mehrdeutig: der aeussere Wert ueberschriebe den inneren."""
    html = '<div data-i18n="a"><p data-i18n="b">x</p></div>'
    with pytest.raises(I18nFehler, match="verschachtelt"):
        wende_an(html, {"a": "A", "b": "B"})


def test_wende_an_bricht_bei_attribut_vor_data_i18n_attr_ab():
    """Reihenfolgeregel, Einzelfall: das Zielattribut steht vor data-i18n-attr."""
    html = '<button aria-label="alt" data-i18n-attr="aria-label:a">x</button>'
    with pytest.raises(I18nFehler, match="erwartet"):
        wende_an(html, {"a": "neu"})


def test_wende_an_bricht_bei_stillem_reihenfolgeverstoss_im_duplikat_ab():
    """Zwei Elemente mit gleichem Rohwert: ein korrekt geordnetes Element darf die
    Pruefung nicht mehr zufriedenstellen, wenn ein zweites falsch geordnet ist."""
    html = (
        '<button data-i18n-attr="aria-label:a" aria-label="alt">x</button>'
        '<button aria-label="alt2" data-i18n-attr="aria-label:a">y</button>'
    )
    with pytest.raises(I18nFehler, match="erwartet"):
        wende_an(html, {"a": "neu"})


def test_entferne_markierungen_raeumt_beide_formen_weg():
    html = '<p data-i18n="a">x</p><b data-i18n-attr="aria-label:k" aria-label="y">z</b>'
    ergebnis = entferne_markierungen(html)
    assert "data-i18n" not in ergebnis
    assert ergebnis == '<p>x</p><b aria-label="y">z</b>'


def test_entferne_markierungen_laesst_andere_attribute_unberuehrt():
    html = '<p class="lede" data-i18n="a" id="k">x</p>'
    assert entferne_markierungen(html) == '<p class="lede" id="k">x</p>'


def test_pruefe_kataloge_ignoriert_den_locale_block():
    html = '<p data-i18n="a">x</p>'
    pruefe_kataloge(
        html,
        {"de": {"a": "d", "__locale__": {"decimal": ","}},
         "en": {"a": "e", "__locale__": {"decimal": "."}}},
    )


def test_lade_katalog_erlaubt_den_locale_block_als_objekt(tmp_path):
    p = _schreib(tmp_path, "text.de.json", {"a": "x", "__locale__": {"decimal": ","}})
    katalog = lade_katalog(p)
    assert katalog["__locale__"]["decimal"] == ","


def test_lade_katalog_bricht_bei_kaputtem_json_mit_i18nfehler_ab(tmp_path):
    """Fix-Runde 2, Minor: eine leere oder syntaktisch kaputte Datei brach

    bisher mit einem rohen json.JSONDecodeError ab -- Widerspruch zur sonstigen
    Linie dieses Moduls (harter Abbruch mit brauchbarer, dateibezogener
    Meldung). Muss als I18nFehler durchkommen und die Datei nennen.
    """
    p = tmp_path / "text.en.json"
    p.write_text("", encoding="utf-8")
    with pytest.raises(I18nFehler, match=re.escape(str(p))):
        lade_katalog(p)


def test_pruefe_locale_bricht_bei_fehlendem_block_ab():
    with pytest.raises(I18nFehler, match="__locale__"):
        pruefe_locale({"a": "x"})


def test_pruefe_locale_bricht_bei_unvollstaendigem_block_ab_und_nennt_schluessel():
    katalog = {"a": "x", "__locale__": {"decimal": ",", "thousands": "."}}
    with pytest.raises(I18nFehler, match="percentSpaceNoBreak"):
        pruefe_locale(katalog)


def test_pruefe_locale_gibt_vollstaendigen_block_zurueck():
    locale = {
        "decimal": ",",
        "thousands": ".",
        "percentSpaceNoBreak": "&nbsp;",
        "percentSpaceBreaking": " ",
        "months": ["Jan"],
        "monthsDate": ["Jan."],
        "dateFormat": "{d}. {m}.",
        "dateRange": "{a}.\u2013{b}. {m}.",
        "pLess": "p &lt; 0,001",
        "pLessValue": "&lt; 0,001",
    }
    assert pruefe_locale({"a": "x", "__locale__": locale}) == locale


def _vollstaendiges_locale() -> dict:
    """Locale-Block mit allen LOCALE_PFLICHTFELDERn, ohne 'lang'.

    'lang' setzen die Tests unten selbst -- es ist der Wert, um den es dort
    geht, und steht bewusst nicht in den Pflichtfeldern.
    """
    return {
        "decimal": ",",
        "thousands": ".",
        "percentSpaceNoBreak": "&nbsp;",
        "percentSpaceBreaking": " ",
        "months": ["Jan"],
        "monthsDate": ["Jan."],
        "dateFormat": "{d}. {m}.",
        "dateRange": "{a}.–{b}. {m}.",
        "pLess": "p &lt; 0,001",
        "pLessValue": "&lt; 0,001",
    }


def test_pruefe_locale_bricht_bei_widerspruechlicher_sprachkennung_ab():
    """Zwei Quellen fuer dieselbe Wahrheit muessen uebereinstimmen.

    '__locale__.lang' und der Textschluessel 'doc.lang' sagen beide den
    Sprachcode des Katalogs. Laufen sie auseinander, traegt die ausgelieferte
    Seite eine andere Sprachkennung, als ihr Katalog behauptet -- jeder Wert
    fuer sich plausibel, im Browser faellt nichts auf.
    """
    locale = _vollstaendiges_locale()
    locale["lang"] = "en"
    katalog = {"doc.lang": "de", "__locale__": locale}

    with pytest.raises(I18nFehler) as fehler:
        pruefe_locale(katalog, "en")

    # Die Meldung muss beide Werte UND die betroffene Sprache nennen.
    text = str(fehler.value)
    assert "'en'" in text
    assert "'de'" in text
    assert "__locale__" in text
    assert "doc.lang" in text


def test_pruefe_locale_laesst_uebereinstimmende_sprachkennung_durch():
    locale = _vollstaendiges_locale()
    locale["lang"] = "de"
    assert pruefe_locale({"doc.lang": "de", "__locale__": locale}, "de") == locale


def test_pruefe_locale_bricht_wenn_der_dateiname_widerspricht():
    """Fix-Runde 2: Der Dateiname ist die einzige Angabe mit Wirkung.

    'doc.lang' und '__locale__.lang' beschreiben nur sich selbst; der Name
    'text.en.json' bestimmt, dass daraus 'index.en.html' wird. Ein Katalog, in
    dem beide inneren Angaben uebereinstimmend 'de' sagen, ist in sich stimmig
    und trotzdem falsch -- er ergaebe eine englische Datei mit
    <html lang="de">. Ohne den Dateinamen im Vergleich faellt genau dieser Fall
    durch jedes Netz.
    """
    locale = _vollstaendiges_locale()
    locale["lang"] = "de"
    katalog = {"doc.lang": "de", "__locale__": locale}

    with pytest.raises(I18nFehler) as fehler:
        pruefe_locale(katalog, "en")

    text = str(fehler.value)
    assert "Dateiname" in text
    assert "'en'" in text and "'de'" in text
    assert "__locale__" in text and "doc.lang" in text


def test_pruefe_locale_ueberspringt_quellen_die_keine_sprache_sind():
    """Fehlende Angaben werden uebersprungen, ebenso ein Nicht-Sprachcode.

    'doc.lang' erzwingt wende_an, '__locale__.lang' steht bewusst nicht in
    LOCALE_PFLICHTFELDER, und lade_kataloge_fuer_pruefung schluesselt Kataloge
    ausserhalb der Namenskonvention unter ihrem Dateinamen -- der ist keine
    Sprache und darf nicht als dritte Quelle gelten. Bleibt hoechstens ein
    Wert uebrig, gibt es nichts zu vergleichen.
    """
    ohne_locale_lang = _vollstaendiges_locale()
    assert pruefe_locale({"doc.lang": "de", "__locale__": ohne_locale_lang}, "de") == (
        ohne_locale_lang
    )

    mit_locale_lang = _vollstaendiges_locale()
    mit_locale_lang["lang"] = "de"
    assert pruefe_locale({"a": "x", "__locale__": mit_locale_lang}, "de") == mit_locale_lang

    # 'sprache' ist hier ein Dateiname, kein Sprachcode: Er darf den Vergleich
    # nicht ausloesen, sonst braeche jeder Katalog ausserhalb der Konvention.
    kein_code = _vollstaendiges_locale()
    kein_code["lang"] = "de"
    assert pruefe_locale(
        {"doc.lang": "de", "__locale__": kein_code}, "kein-text.de.json"
    ) == kein_code


from niedrigwasser.i18n import sammle_js_schluessel


def test_sammle_js_schluessel_findet_aufrufe():
    js = '<script>var a = t("heatmap.spitzenwert", {x: 1}); var b = t("legende.steigend");</script>'
    assert sammle_js_schluessel(js) == {"heatmap.spitzenwert", "legende.steigend"}


def test_sammle_js_schluessel_ignoriert_json_bloecke():
    """Der Datenblock enthaelt beliebigen Text; dort steht kein Aufruf.

    Die Fixture traegt einen woertlich passenden Aufruf im JSON-Block -- mit
    escapten Anfuehrungszeichen griffe der Regex ohnehin nicht, und der Test
    waere auch ohne den Ausschluss gruen. So faellt der Ausschluss auf, wenn
    ihn jemand entfernt.
    """
    js = (
        '<script type="application/json">'
        '{"name": "Elster t("kein.schluessel") im Datenblock"}'
        "</script>"
        '<script>var s = t("echt.schluessel");</script>'
    )
    assert sammle_js_schluessel(js) == {"echt.schluessel"}


def test_sammle_schluessel_vereinigt_markup_und_js():
    html = '<p data-i18n="a">x</p><script>var s = t("b");</script>'
    assert sammle_schluessel(html) == {"a", "b"}


import json
import re
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
TEMPLATE = WURZEL / "site" / "template.html"
KATALOG = WURZEL / "site" / "text.de.json"


def _js_literale(js: str) -> list[str]:
    """Alle String-Literale eines Skripts, Kommentare ausgenommen.

    Zeichenweiser Durchlauf statt Regex: Ein Regex ueber gemischte
    Anfuehrungszeichen paart ueber Zeilen hinweg falsch und liefert
    Code-Fragmente als vermeintliche Literale. Backticks zaehlen mit --
    ein Template-Literal ist JavaScript-Text wie jedes andere auch.
    """
    literale: list[str] = []
    i, n = 0, len(js)
    while i < n:
        zeichen = js[i]
        if js.startswith("/*", i):
            ende = js.find("*/", i + 2)
            i = n if ende == -1 else ende + 2
        elif js.startswith("//", i):
            ende = js.find("\n", i)
            i = n if ende == -1 else ende
        elif zeichen in "\"'`":
            j, puffer = i + 1, []
            while j < n and js[j] != zeichen:
                if js[j] == "\\":
                    j += 2
                    continue
                if js[j] == "\n" and zeichen != "`":
                    break  # unterminiert: kein Literal
                puffer.append(js[j])
                j += 1
            if j < n and js[j] == zeichen:
                literale.append("".join(puffer))
                i = j + 1
            else:
                i += 1
        else:
            i += 1
    return literale


# Heuristik, kein Beweis. Zwei Gruppen mit unterschiedlicher Gross-/Klein-
# schreibung, und das ist Absicht:
#   - Funktionswoerter und Adjektive stehen am Satzanfang gross ("Kein ...",
#     "Signifikant steigend") -- deshalb (?i:...).
#   - Nomen sind im Deutschen IMMER gross, CSS-Klassen und Datenwerte nie.
#     'Trend' gross faengt "Trend der Niedrigwassertage", laesst aber
#     'st-trend', 't-trend' und den Datenwert 'no trend' in Ruhe.
# Wortstaemme statt Vollformen: 'Tag\w*' faengt auch Tage/Tagen, 'Jahr\w*'
# auch Jahre/Jahren.
# Gruppe 1: Funktionswoerter und Adjektive. Als einzige der drei Gruppen auch
# im englischen Katalog brauchbar (siehe _DEUTSCH_IM_ENGLISCHEN) -- keines
# dieser Woerter ist englisch, und keines steht in der uebersetzten Prosa.
_DEUTSCHE_WOERTER = (
    r"(?i:\b(?:der|die|das|dem|den|des|ein|eine|einen|einem|einer|und|oder|"
    r"nicht|kein\w*|von|vom|mit|ohne|bei|beim|zur|zum|als|auch|noch|nur|im|"
    r"bis|zu|je|schon|mehr|allein|dass|"
    r"signifikant\w*|statistisch\w*|gesichert|naturnah\w*|meldend\w*|"
    r"steigend|fallend|hervorgehoben|dimensionslos|mindestens|weiterhin|"
    r"gefunden|angezeigt|korrigiert)\b)"
)

# Gruppe 2: Nomen. Nur im deutschen Kontext brauchbar -- Trend, Median, Design,
# Station, Minimum und Maximum sind auch englische Woerter, die Gruppe schlaegt
# auf englischem Text also breit fehl.
_DEUTSCHE_NOMEN = (
    r"\b(?:Tag\w*|Jahr\w*|Pegel\w*|Wasserjahr\w*|Trend\w*|Anteil\w*|Median\w*|"
    r"Prozent\w*|Auswahl\w*|Dekade\w*|Netz\w*|Heatmap\w*|Kart\w*|"
    r"Niedrigwasser\w*|Spitze\w*|Mittel\w*|Wert\w*|Steigung|Verfahren|Fenster|"
    r"Dunkel|Hell|Design|Zeitreihe\w*|Station\w*|Abfluss\w*|Grundlage\w*|"
    r"Korrektur\w*|Zusammenfassung\w*|Hinweis\w*|Suche|Einzugsgebiet\w*|"
    r"Minimum|Maximum|Tsd|Klick|Defizit\w*|Schwelle\w*|Tastatur\w*|"
    r"Detailansicht|Vorlage)\b"
)

# Gruppe 3 (Umlaute) plus beide Wortgruppen: die volle Heuristik fuer das
# deutsche Skript und den deutschen Katalog.
_DEUTSCH = re.compile(r"[äöüÄÖÜß]|" + _DEUTSCHE_WOERTER + r"|" + _DEUTSCHE_NOMEN)

# Der Abstand vor dem Prozentzeichen ist eine Locale-Entscheidung. Beide
# Schreibweisen zaehlen: das Zeichen selbst und die Entity-Form.
_PROZENTABSTAND = re.compile(r"(?:\s|&nbsp;|&thinsp;|&#160;)%")

# Genau EINE namentliche Ausnahme vom Waechter, kein Sammelbecken: Dieser
# Hinweis erscheint per Konstruktion nur, wenn die Marker im Template noch
# stehen -- dann ist auch der Katalog-Blob ungefuellt und t() gaebe es nicht.
# Er kann also prinzipiell nicht aus dem Katalog kommen und bleibt deutsch wie
# jeder andere entwicklerseitige Text dieses Repos.
_BAUHINWEIS = (
    '<p style="padding:20px;font-family:monospace">template.html ist die ungebaute '
    "Vorlage: bitte scripts/build_site.py ausf\u00fchren und site/index.html "
    "\u00f6ffnen.</p>"
)

# Zwei Katalogwerte tragen ueberhaupt kein deutsches Wort: eine englische
# Fachbezeichnung und ein Akronym mit Platzhaltern. Dass die Heuristik dort
# nichts findet, ist keine Luecke -- es ist nichts da. Namentlich gefuehrt,
# damit die Liste nicht still waechst.
_OHNE_DEUTSCHES_WORT = {
    "index.kennzahl.ssi.label",  # "Standardized Streamflow Index"
    "station.fdr.nm7q",          # "NM7Q {pwert} {status}"
}


def _ohne_fehlermeldungen(js: str) -> str:
    """Schneidet 'throw new Error(...);'-Anweisungen heraus.

    Kein Namenslisten-Schlupfloch, sondern eine strukturelle Grenze: Eine
    Fehlermeldung erreicht keinen Leser, sie erreicht den Entwickler -- und sie
    kann prinzipiell nicht aus dem Katalog kommen, weil t() genau der Ort ist,
    der den Katalog liest. Sie bleibt deutsch wie Kommentare und Docstrings.
    Greift der Schnitt einmal nicht, bleibt die Meldung im Text und der
    Waechter schlaegt an -- die Ungenauigkeit faellt also zur sicheren Seite.
    """
    return re.sub(r"throw new Error\([^;]*\);", "", js)


def _skript() -> str:
    from niedrigwasser.i18n import _skript_bereiche

    return _skript_bereiche(TEMPLATE.read_text(encoding="utf-8"))


def test_kein_deutscher_text_mehr_in_den_js_literalen():
    from niedrigwasser.i18n import sammle_js_schluessel

    # Katalog-Schluessel sind Bezeichner, keine Prosa. Sie stehen zwangslaeufig
    # als Literal im Skript und werden anderswo auf Paritaet geprueft.
    schluessel = sammle_js_schluessel(TEMPLATE.read_text(encoding="utf-8"))
    treffer = [
        s for s in _js_literale(_ohne_fehlermeldungen(_skript()))
        if len(s.strip()) >= 3
        and _DEUTSCH.search(s)
        and s not in schluessel
        and s != _BAUHINWEIS
    ]
    assert treffer == [], f"Deutscher Text im JS geblieben: {treffer[:5]}"


def test_waechter_uebergeht_nur_die_fehlermeldung_selbst():
    """Der Schnitt darf nur die Meldung treffen, nicht die Zeile danach."""
    js = ('throw new Error("Textschluessel fehlt: " + k); '
          'var s = "Kein Pegel gefunden";')
    treffer = [x for x in _js_literale(_ohne_fehlermeldungen(js)) if _DEUTSCH.search(x)]
    assert treffer == ["Kein Pegel gefunden"]


def test_waechter_sieht_template_literale():
    """Backticks sind JavaScript-Text wie Anfuehrungszeichen auch.

    Heute steht dort nichts -- der Waechter soll trotzdem hinsehen, sonst ist
    der naechste Rueckfall nur ein Backtick weit entfernt.
    """
    js = "var s = `Kein signifikanter Trend der Niedrigwassertage`;"
    treffer = [s for s in _js_literale(js) if _DEUTSCH.search(s)]
    assert treffer == ["Kein signifikanter Trend der Niedrigwassertage"]


def test_waechter_erkennt_die_deutschen_katalogwerte():
    """Gegenprobe gegen den eigenen Katalog.

    Jeder Wert, den das Skript per t() holt, waere als Literal ein Rueckfall.
    Was die Heuristik dort nicht erkennt, wuerde sie auch im Skript nicht
    erkennen -- der gruene Waechter waere dann eine Beruhigung, kein Nachweis.
    Platzhalter zaehlen nicht mit: ein Rueckfall traegt sie nicht.
    """
    from niedrigwasser.i18n import lade_katalog, sammle_js_schluessel

    katalog = lade_katalog(KATALOG)
    blind = []
    for schluessel in sorted(sammle_js_schluessel(TEMPLATE.read_text(encoding="utf-8"))):
        if schluessel in _OHNE_DEUTSCHES_WORT:
            continue
        text = re.sub(r"\{\w+\}", " ", katalog[schluessel])
        if len(text.strip()) >= 3 and not _DEUTSCH.search(text):
            blind.append((schluessel, katalog[schluessel]))
    assert blind == [], f"Waechter blind fuer {len(blind)} Katalogwerte: {blind[:5]}"


def test_bauhinweis_bleibt_deutsch():
    """Die einzige Wächter-Ausnahme muss auch wirklich im Template stehen.

    Sonst veraltet sie still und deckt irgendwann nichts mehr ab.
    """
    assert _BAUHINWEIS in TEMPLATE.read_text(encoding="utf-8")


# ------------------------------------------- Waechter ueber den EN-Katalog

KATALOG_EN = WURZEL / "site" / "text.en.json"

# Der Waechter fuer den englischen Katalog. Nur die Wortgruppe, ohne Umlaute
# und ohne die Nomen:
#   * Umlaute stehen legitim im englischen Text -- die Seite handelt von
#     deutschen Fluessen und Behoerden ("Laenderarbeitsgemeinschaft Wasser").
#   * Die Nomen-Gruppe traefe Trend, Median, Design, Station, Minimum und
#     Maximum, alles auch englische Woerter (zwoelf Fehlalarme im heutigen
#     Katalog).
# Uebrig bleibt eine Gruppe, von der kein Wort englisch ist. Sie ist grob --
# kurze Beschriftungen ohne Funktionswort laufen durch (siehe die Gegenprobe
# test_englischer_waechter_erkennt_lange_deutsche_werte) -- aber sie faengt den
# Ausgang, den der Modul-Docstring von niedrigwasser.i18n als schlimmsten
# benennt: ein spaeter ergaenzter Schluessel, dessen englischer Wert der
# kopierte deutsche Satz ist. Der besteht heute jede Paritaetspruefung.
_DEUTSCH_IM_ENGLISCHEN = re.compile(_DEUTSCHE_WOERTER)

# Genau eine namentliche Ausnahme, und zwar EIN WORT, nicht ein ganzer Wert:
# In diesen beiden Werten steht "Oder" als Name des Flusses, nicht als deutsche
# Konjunktion. Ausgenommen wird nur das Wort selbst -- der Rest beider Werte
# bleibt unter Beobachtung.
_EN_FLUSSNAME_ODER = {"hero.tile.flaeche.text", "methodik.national.text"}


def _en_pruefwert(schluessel: str, wert: str) -> str:
    """Katalogwert, wie ihn der englische Waechter sieht.

    Platzhalternamen sind Bezeichner, keine Prosa: {von}, {bis} und {jahr}
    heissen in beiden Sprachen gleich (das erzwingt pruefe_kataloge) und sind
    deshalb kein deutscher Text im englischen Wert.
    """
    text = re.sub(r"\{\w+\}", " ", wert)
    if schluessel in _EN_FLUSSNAME_ODER:
        text = re.sub(r"\bOder\b", " ", text)
    return text


def test_kein_deutscher_text_im_englischen_katalog():
    """Der Waechter zeigte bisher nur auf das Template und text.de.json.

    text.en.json sah er nie. Ein spaeter ergaenzter Schluessel mit kopiertem
    deutschem Wert haette jede Paritaetspruefung bestanden: Schluessel da,
    Datenplatzhalter da, benannte Platzhalter da -- nur die Sprache falsch.
    """
    katalog = lade_katalog(KATALOG_EN)
    treffer = []
    for schluessel, wert in sorted(katalog.items()):
        if schluessel == "__locale__" or not isinstance(wert, str):
            continue
        gefunden = _DEUTSCH_IM_ENGLISCHEN.findall(_en_pruefwert(schluessel, wert))
        if gefunden:
            treffer.append((schluessel, sorted(set(gefunden))))
    assert treffer == [], f"Deutscher Text im englischen Katalog: {treffer[:5]}"


def test_die_oder_ausnahme_betrifft_wirklich_den_fluss():
    """Die Ausnahme darf nicht still veralten oder mehr abdecken als gemeint.

    Beide Schluessel muessen den Flussnamen weiterhin tragen, und ohne die
    Ausnahme muesste der Waechter dort anschlagen -- sonst ist sie ein
    Freibrief fuer einen Wert, der ihn nicht mehr braucht.
    """
    katalog = lade_katalog(KATALOG_EN)
    for schluessel in sorted(_EN_FLUSSNAME_ODER):
        wert = katalog[schluessel]
        assert re.search(r"\bOder\b", wert), (
            f"{schluessel!r} traegt kein 'Oder' mehr -- Ausnahme entfernen"
        )
        ohne_ausnahme = re.sub(r"\{\w+\}", " ", wert)
        assert _DEUTSCH_IM_ENGLISCHEN.findall(ohne_ausnahme) == ["Oder"], (
            f"{schluessel!r}: Ausnahme deckt mehr als den Flussnamen ab"
        )


def test_englischer_waechter_erkennt_lange_deutsche_werte():
    """Gegenprobe: was der Waechter durchliesse, ist keine Prosa.

    Gemessen wird gegen den echten deutschen Katalog -- jeder seiner Werte
    waere, in text.en.json kopiert, genau der Rueckfall, gegen den der Waechter
    steht. Kurze Beschriftungen ohne Funktionswort laufen durch ('Methodik &
    Grenzen', 'Hell', 'Dunkel'); das ist die bekannte Grenze der Heuristik.
    Ein kopierter SATZ darf nicht durchlaufen. Groesster blinder Wert heute:
    acht Woerter (index.mk.sen.info), die Schwelle liegt eine Stufe darueber.
    """
    katalog = lade_katalog(KATALOG)
    blind = []
    for schluessel, wert in sorted(katalog.items()):
        if schluessel == "__locale__" or not isinstance(wert, str):
            continue
        text = re.sub(r"<[^>]+>", " ", re.sub(r"\{\w+\}", " ", wert))
        if _DEUTSCH_IM_ENGLISCHEN.search(text):
            continue
        if len(text.split()) >= 9:
            blind.append((schluessel, len(text.split())))
    assert blind == [], f"Waechter blind fuer lange deutsche Werte: {blind}"


def test_template_traegt_keine_prosa_mehr():
    """Das Template darf zu keinem Schluessel noch einen Rueckfalltext tragen.

    Bis zur Abschluss-Review stand die deutsche Prosa doppelt: einmal als
    Inhalt der data-i18n-Elemente, einmal im Katalog. Beim Bauen gewinnt immer
    der Katalog, also merkte niemand, dass die beiden auseinanderliefen -- und
    sie taten es bereits an zwei Stellen (hero.sub trug die Fassung vor der
    NIWIS-Aufloesung, fuss.quelle das unaufgeloeste 'NIWIS (BfG/LAWA)').

    Statt beide Kopien gegeneinander zu pruefen, gibt es nur noch eine: Das
    Template traegt Struktur und Schluessel, die Prosa steht im Katalog. Wer
    template.html direkt oeffnet, bekommt den Bau-Hinweis
    (siehe test_bauhinweis_bleibt_deutsch), nicht eine zweite Wahrheit.
    """
    from niedrigwasser.i18n import RE_INHALT, _attribut_schluessel, _element_ende

    html = TEMPLATE.read_text(encoding="utf-8")

    gefuellt = []
    for treffer in re.finditer(r'<[a-zA-Z][^>]*data-i18n="', html):
        start = treffer.start()
        tag_ende = html.index(">", start)
        schluessel = RE_INHALT.search(html, start, tag_ende).group(1)
        inhalt_start, inhalt_ende, _ = _element_ende(html, start)
        inhalt = html[inhalt_start:inhalt_ende]
        if inhalt != "":
            gefuellt.append((schluessel, inhalt[:60]))
    assert gefuellt == [], f"Rueckfalltext im Template: {gefuellt[:5]}"

    gefuellte_attribute = []
    for treffer in re.finditer(r'<[a-zA-Z][^>]*data-i18n-attr="([^"]+)"[^>]*>', html):
        tag = treffer.group(0)
        for attribut, schluessel in _attribut_schluessel(treffer.group(1)):
            wert = re.search(rf'\s{re.escape(attribut)}="([^"]*)"', tag)
            if wert is None or wert.group(1) != "":
                gefuellte_attribute.append((schluessel, attribut, tag[:60]))
    assert gefuellte_attribute == [], (
        f"Rueckfalltext in einem Attribut: {gefuellte_attribute[:5]}"
    )


def test_locale_pflichtfelder_verlangt_beide_prozentabstaende():
    """Beide Formen sind Pflicht, geschuetzt und ungeschuetzt.

    Der Unterschied ist nicht der Kontext, sondern ob der Abstand einen
    Zeilenumbruch zulaesst -- die Namen sollen niemanden dazu verleiten, beim
    Schreiben von text.en.json einfach denselben Wert einzutragen.
    """
    from niedrigwasser.i18n import LOCALE_PFLICHTFELDER

    assert "percentSpaceNoBreak" in LOCALE_PFLICHTFELDER
    assert "percentSpaceBreaking" in LOCALE_PFLICHTFELDER


def test_pruefe_locale_bricht_ohne_ungeschuetzten_prozentabstand_ab():
    locale = {
        "lang": "de",
        "decimal": ",",
        "thousands": ".",
        "percentSpaceNoBreak": "&nbsp;",
        "months": ["Jan"],
        "monthsDate": ["Jan."],
        "dateFormat": "{d}. {m}.",
        "dateRange": "{a}.\u2013{b}. {m}.",
        "pLess": "p &lt; 0,001",
        "pLessValue": "&lt; 0,001",
    }
    with pytest.raises(I18nFehler, match="percentSpaceBreaking"):
        pruefe_locale({"a": "x", "__locale__": locale})


def test_kein_hartkodierter_prozentabstand_im_js():
    """Der Abstand vor dem Prozentzeichen ist eine Locale-Entscheidung.

    Deutsch setzt ihn, Englisch nicht. Steht er als Literal im Skript, wandert
    die deutsche Konvention still in die englische Fassung mit.
    """
    treffer = [s for s in _js_literale(_skript()) if _PROZENTABSTAND.search(s)]
    assert treffer == [], f"Prozentabstand hartkodiert: {treffer}"


def test_waechter_sieht_prozentabstand_auch_als_entity():
    """'&nbsp;%' ist derselbe Rueckfall, nur anders geschrieben."""
    assert _PROZENTABSTAND.search("12&nbsp;%")
    assert _PROZENTABSTAND.search("12 %")
    assert not _PROZENTABSTAND.search("max-width:100%")


# ---------------------------------------------------------------- Platzhalter

def test_pruefe_kataloge_bricht_bei_umbenanntem_platzhalter_ab():
    """{peak} statt {spitze}: t() laesst ihn stehen, auf der Seite steht '{peak}'."""
    html = '<script>var s = t("a");</script>'
    with pytest.raises(I18nFehler, match="spitze"):
        pruefe_kataloge(
            html,
            {"de": {"a": "Spitzenwert {spitze} Prozent"},
             "en": {"a": "peak value {peak} percent"}},
        )


def test_pruefe_kataloge_bricht_bei_verlorenem_platzhalter_ab():
    """Der gefaehrlichere Fall: die Uebersetzung laesst ihn weg.

    Der Wert verschwindet lautlos, der Satz klingt vollstaendig. Genau das
    duerfen blinde Leser der englischen Seite nicht erleben.
    """
    html = '<script>var s = t("a");</script>'
    with pytest.raises(I18nFehler, match="spitze"):
        pruefe_kataloge(
            html,
            {"de": {"a": "Spitzenwert {spitze} Prozent"},
             "en": {"a": "peak value in percent"}},
        )


def test_pruefe_kataloge_akzeptiert_platzhalter_in_anderer_reihenfolge():
    """Die Wortstellung darf sich aendern -- darum gibt es Platzhalter."""
    html = '<script>var s = t("a");</script>'
    pruefe_kataloge(
        html,
        {"de": {"a": "{jahr}: Spitzenwert {spitze}"},
         "en": {"a": "peak {spitze} in {jahr}"}},
    )


def test_platzhalternamen_sind_keine_einzelbuchstaben():
    """{a}/{b}/{c} sagt niemandem, was einzusetzen ist.

    Wer nur den englischen Katalog vor sich hat, muss aus dem Namen erschliessen
    koennen, welcher Wert gemeint ist.
    """
    from niedrigwasser.i18n import RE_PLATZHALTER

    katalog = json.loads(KATALOG.read_text(encoding="utf-8"))
    kurz = sorted(
        (k, name)
        for k, v in katalog.items()
        if isinstance(v, str)
        for name in RE_PLATZHALTER.findall(v)
        if len(name) < 2
    )
    assert kurz == [], f"Einzelbuchstaben als Platzhalter: {kurz}"


def test_auswahlhinweis_traegt_den_button_als_platzhalter():
    """Sonst muss die Uebersetzung den Gedankenstrich mitschleppen.

    Endet der Wert vor dem Button, kann keine Sprache ihn nach vorn ziehen.
    """
    katalog = json.loads(KATALOG.read_text(encoding="utf-8"))
    assert "{button}" in katalog["index.auswahl.hinweis"]


# ------------------------------ Platzhalter an der Aufrufstelle im Template

# pruefe_kataloge vergleicht Platzhalter nur ZWISCHEN den Sprachen. Wer {x}
# gleichmaessig in beide Kataloge eintraegt, ohne die Aufrufstelle anzufassen,
# haelt jeden Build-Waechter gruen -- und t() wirft erst zur Laufzeit, auf
# einem womoeglich selten geoeffneten Codepfad (Stations-Detail, Tooltip einer
# bestimmten Zelle). Deshalb hier die dritte Seite des Dreiecks: Katalogwert
# gegen das Objektliteral, das die Aufrufstelle uebergibt.

_STRING_START = "\"'`"


def _js_string_ende(js: str, i: int) -> int:
    """``i`` zeigt auf ein oeffnendes Anfuehrungszeichen; Position dahinter."""
    zeichen = js[i]
    j = i + 1
    while j < len(js):
        if js[j] == "\\":
            j += 2
            continue
        if js[j] == zeichen:
            return j + 1
        j += 1
    raise AssertionError(f"unterminierter String ab Position {i}")


def _js_kommentar_ende(js: str, i: int) -> int:
    """Position hinter einem Kommentar ab ``i``, sonst ``i`` selbst."""
    if js.startswith("/*", i):
        ende = js.find("*/", i + 2)
        return len(js) if ende == -1 else ende + 2
    if js.startswith("//", i):
        ende = js.find("\n", i)
        return len(js) if ende == -1 else ende
    return i


def _ohne_kommentare(js: str) -> str:
    """Kommentare zu Leerzeichen, Strings unangetastet.

    Positionen bleiben erhalten, damit Fehlermeldungen weiter passen. Der
    Zeichenlauf ist noetig, weil ein Regex ueber '//' auch in einem String
    zuschlagen wuerde -- 'https://...' waere dann ein Kommentar.
    """
    teile, i = [], 0
    while i < len(js):
        weiter = _js_kommentar_ende(js, i)
        if weiter != i:
            teile.append(" " * (weiter - i))
            i = weiter
            continue
        if js[i] in _STRING_START:
            weiter = _js_string_ende(js, i)
            teile.append(js[i:weiter])
            i = weiter
            continue
        teile.append(js[i])
        i += 1
    return "".join(teile)


def _objekt_ende(js: str, start: int) -> int:
    """``start`` zeigt auf '{'; Position hinter der passenden schliessenden."""
    tiefe, i = 0, start
    while i < len(js):
        if js[i] in _STRING_START:
            i = _js_string_ende(js, i)
            continue
        if js[i] in "{([":
            tiefe += 1
        elif js[i] in "})]":
            tiefe -= 1
            if tiefe == 0:
                return i + 1
        i += 1
    raise AssertionError(f"kein schliessendes '}}' ab Position {start}")


def _feldnamen(objekt: str) -> list[str]:
    """Top-Level-Feldnamen eines Objektliterals (mit seinen Klammern).

    Getrennt wird an Kommas der obersten Ebene, der Name ist alles vor dem
    ERSTEN Doppelpunkt des Segments -- so stoert ein Ternaer im Wert nicht,
    dessen Doppelpunkt auf derselben Ebene steht.
    """
    koerper = objekt[1:-1]
    segmente, tiefe, letzt, i = [], 0, 0, 0
    while i < len(koerper):
        if koerper[i] in _STRING_START:
            i = _js_string_ende(koerper, i)
            continue
        if koerper[i] in "{([":
            tiefe += 1
        elif koerper[i] in "})]":
            tiefe -= 1
        elif koerper[i] == "," and tiefe == 0:
            segmente.append(koerper[letzt:i])
            letzt = i + 1
        i += 1
    segmente.append(koerper[letzt:])

    namen = []
    for segment in segmente:
        if not segment.strip():
            continue
        name, trenner, _ = segment.partition(":")
        assert trenner, f"Feld ohne Doppelpunkt: {segment.strip()!r}"
        namen.append(name.strip().strip("\"'"))
    return namen


def _t_aufrufstellen(js: str) -> list[tuple[str, set[str] | None]]:
    """Jede t()-Aufrufstelle als (Schluessel, uebergebene Feldnamen).

    ``None`` statt der Menge heisst: zweites Argument ist kein Objektliteral,
    die Aufrufstelle ist statisch nicht auswertbar.
    """
    js = _ohne_kommentare(js)
    stellen: list[tuple[str, set[str] | None]] = []
    for treffer in re.finditer(r'\bt\(\s*"([^"]+)"', js):
        i = treffer.end()
        while i < len(js) and js[i].isspace():
            i += 1
        if i >= len(js) or js[i] != ",":
            stellen.append((treffer.group(1), set()))
            continue
        i += 1
        while i < len(js) and js[i].isspace():
            i += 1
        if i >= len(js) or js[i] != "{":
            stellen.append((treffer.group(1), None))
            continue
        objekt = js[i:_objekt_ende(js, i)]
        stellen.append((treffer.group(1), set(_feldnamen(objekt))))
    return stellen


def test_aufrufstellen_uebergeben_genau_die_platzhalter_ihres_wertes():
    """Die dritte Seite des Dreiecks Katalog-de / Katalog-en / Aufrufstelle.

    Fehlt ein uebergebener Wert, wirft t() zur Laufzeit ("Platzhalter ohne
    Wert"); ist einer zu viel, bleibt er wirkungslos und der naechste
    Uebersetzer fuegt ihn plausibel in den Text ein. Beides faellt statisch auf.
    """
    from niedrigwasser.i18n import RE_PLATZHALTER

    katalog = lade_katalog(KATALOG)
    abweichungen = []
    for schluessel, uebergeben in _t_aufrufstellen(_skript()):
        assert uebergeben is not None, (
            f"{schluessel!r}: zweites Argument ist kein Objektliteral -- "
            "statisch nicht pruefbar, bitte als Literal schreiben"
        )
        erwartet = set(RE_PLATZHALTER.findall(katalog[schluessel]))
        if uebergeben != erwartet:
            abweichungen.append(
                (schluessel, sorted(erwartet), sorted(uebergeben))
            )
    assert abweichungen == [], (
        f"Aufrufstelle passt nicht zum Katalogwert: {abweichungen[:5]}"
    )


def test_aufrufstellen_parser_findet_alle_schluessel():
    """Gegenprobe: der Parser darf keine Aufrufstelle uebersehen.

    Findet er weniger, als es Schluessel gibt, waere der Test oben still
    unvollstaendig -- gruen, weil er gar nicht hinsieht.
    """
    from niedrigwasser.i18n import sammle_js_schluessel

    gefunden = {schluessel for schluessel, _ in _t_aufrufstellen(_skript())}
    assert gefunden == sammle_js_schluessel(TEMPLATE.read_text(encoding="utf-8"))


def test_aufrufstellen_parser_liest_verschachtelte_werte():
    """Der Parser muss Ternaer, Aufruf und geschachteltes Objekt aushalten.

    Alles drei kommt im Template vor. Ein naiver Split an Kommas oder am
    ersten '}' zerlegte die Aufrufstelle falsch und der Test darueber waere
    zufaellig gruen oder zufaellig rot.
    """
    js = (
        'var a = t("x", { wert: b > 0 ? "+" : "-", tief: f(1, 2), '
        'roh: { i: 1 }, text: "a, b: c" });'
    )
    assert _t_aufrufstellen(js) == [("x", {"wert", "tief", "roh", "text"})]


def test_aufrufstellen_parser_ignoriert_kommentare():
    """Ein auskommentierter Aufruf ist keine Aufrufstelle."""
    js = '/* t("alt", { weg: 1 }) */ var a = t("neu", { da: 1 });'
    assert _t_aufrufstellen(js) == [("neu", {"da"})]


# ------------------------------------------------- t() im Template, ausgefuehrt

_NODE = shutil.which("node")


def _t_quelle() -> str:
    quelle = TEMPLATE.read_text(encoding="utf-8")
    treffer = re.search(r"function t\(schluessel, werte\) \{.*?\n\}", quelle, re.S)
    assert treffer, "t() nicht im Template gefunden"
    return treffer.group(0)


def _node_lauf(texte: dict, aufruf: str) -> str:
    """Fuehrt t() aus dem Template wirklich aus -- Quelle der Wahrheit ist das
    Template, nicht eine Nachbildung im Test."""
    skript = (
        "var T = { TEXTE: " + json.dumps(texte, ensure_ascii=False) + " };\n"
        + _t_quelle() + "\n"
        + "try { console.log('OK ' + (" + aufruf + ")); }\n"
        + "catch (e) { console.log('WURF ' + e.message); }\n"
    )
    lauf = subprocess.run(
        [_NODE, "-e", skript], capture_output=True, text=True, encoding="utf-8"
    )
    assert lauf.returncode == 0, lauf.stderr
    return lauf.stdout.strip()


@pytest.mark.skipif(_NODE is None, reason="node nicht verfuegbar")
def test_t_wirft_bei_unversorgtem_platzhalter():
    """Ein Platzhalter ohne Wert darf nicht sichtbar stehenbleiben."""
    ausgabe = _node_lauf({"a": "Spitzenwert {spitze} Prozent"}, 't("a", {})')
    assert ausgabe.startswith("WURF"), ausgabe
    assert "spitze" in ausgabe


@pytest.mark.skipif(_NODE is None, reason="node nicht verfuegbar")
def test_t_ersetzt_in_einem_durchgang():
    """Ein eingesetzter Wert darf nicht erneut durchsucht werden.

    Sonst frisst die zweite Ersetzung, was die erste eingesetzt hat -- dieselbe
    Falle wie bei einer Praefix-Umbenennung.
    """
    ausgabe = _node_lauf(
        {"a": "{eins}|{zwei}"}, 't("a", { eins: "{zwei}", zwei: "X" })'
    )
    assert ausgabe == "OK {zwei}|X", ausgabe


@pytest.mark.skipif(_NODE is None, reason="node nicht verfuegbar")
def test_t_wirft_bei_fehlendem_schluessel():
    ausgabe = _node_lauf({"a": "x"}, 't("fehlt.im.katalog")')
    assert ausgabe.startswith("WURF") and "fehlt.im.katalog" in ausgabe


@pytest.mark.skipif(_NODE is None, reason="node nicht verfuegbar")
def test_t_setzt_leere_werte_ein():
    """{zusatz} ist oft der leere String -- das ist ein Wert, kein fehlender."""
    ausgabe = _node_lauf({"a": "Prozent{zusatz}."}, 't("a", { zusatz: "" })')
    assert ausgabe == "OK Prozent.", ausgabe
