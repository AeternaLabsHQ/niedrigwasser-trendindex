import re
from pathlib import Path

import pytest

from niedrigwasser.embed_fragment import (
    DARK_HOST,
    FragmentFehler,
    ROOT_CLASS,
    scope_css,
    scope_selector,
    split_selectors,
    strip_comments,
)

WURZEL = Path(__file__).resolve().parents[1]


def test_strip_comments_respektiert_zeichenketten():
    css = '.a { content: "/* kein Kommentar */"; } /* echter */ .b { color: red; }'
    ohne = strip_comments(css)
    assert '"/* kein Kommentar */"' in ohne
    assert "echter" not in ohne


def test_strip_comments_bricht_bei_unbeendetem_kommentar_ab():
    with pytest.raises(FragmentFehler, match="Kommentar"):
        strip_comments(".a { color: red; } /* offen")


def test_split_selectors_teilt_nur_auf_oberster_ebene():
    assert split_selectors("a, b") == ["a", "b"]
    assert split_selectors(":is(a, b) c, d") == [":is(a, b) c", "d"]


def test_scope_selector_sonderfaelle():
    assert scope_selector("*") == f"{ROOT_CLASS} *"
    assert scope_selector("body") == ROOT_CLASS
    assert scope_selector(":root") == ROOT_CLASS
    assert scope_selector(".wrap h2") == f"{ROOT_CLASS} .wrap h2"


def test_scope_selector_konditioniert_dark_auf_den_host():
    assert scope_selector(':root[data-theme="dark"]') == f"{DARK_HOST} {ROOT_CLASS}"
    assert (
        scope_selector(':root[data-theme="dark"] .seg button[aria-pressed="true"]')
        == f'{DARK_HOST} {ROOT_CLASS} .seg button[aria-pressed="true"]'
    )


def test_scope_selector_bricht_bei_unbekannter_root_form_ab():
    with pytest.raises(FragmentFehler, match="kapselbar"):
        scope_selector(':root:has(.x)')


def test_scope_css_verwirft_html_regeln():
    assert scope_css("html { scroll-behavior: smooth; }").strip() == ""


def test_scope_css_bricht_bei_gemischter_html_liste_ab():
    with pytest.raises(FragmentFehler, match="kapselbar"):
        scope_css("html, .wrap { margin: 0; }")


def test_scope_css_verwirft_prefers_color_scheme():
    css = "@media (prefers-color-scheme: dark) { :root { --page: #000; } }"
    assert scope_css(css).strip() == ""


def test_scope_css_verwirft_prefers_color_scheme_auch_ohne_leerzeichen():
    css = "@media(prefers-color-scheme:light){ :root { --page: #fff; } }"
    assert scope_css(css).strip() == ""


def test_scope_css_bricht_bei_kombinierter_farbschema_query_ab():
    # Der stille Verwerfer waere hier am teuersten: die Query traegt AUCH die
    # responsive Bedingung; sie kommentarlos fallen zu lassen naehme dem
    # Fragment einen kompletten Mobil-Block.
    css = "@media (max-width: 720px) and (prefers-color-scheme: dark) { .wrap { padding: 0; } }"
    with pytest.raises(FragmentFehler, match="Farbschema"):
        scope_css(css)


def test_scope_css_bricht_bei_negierter_farbschema_query_ab():
    css = "@media not all and (prefers-color-scheme: dark) { .wrap { padding: 0; } }"
    with pytest.raises(FragmentFehler, match="Farbschema"):
        scope_css(css)


def test_scope_css_erhaelt_responsive_query_und_kapselt_innen():
    ergebnis = scope_css("@media (max-width: 720px) { .wrap { padding: 0; } }")
    assert "@media (max-width: 720px)" in ergebnis
    assert f"{ROOT_CLASS} .wrap" in ergebnis


def test_scope_css_bricht_bei_unbekannter_at_regel_ab():
    with pytest.raises(FragmentFehler, match="At-Regel"):
        scope_css("@supports (display: grid) { .a { display: grid; } }")


def test_scope_css_bricht_bei_unbalancierten_klammern_ab():
    with pytest.raises(FragmentFehler, match="Klammern"):
        scope_css(".a { color: red;")


def test_scope_selector_bricht_bei_root_in_funktionaler_pseudoklasse_ab():
    with pytest.raises(FragmentFehler, match="kapselbar"):
        scope_selector(":is(:root, .foo)")
    with pytest.raises(FragmentFehler, match="kapselbar"):
        scope_selector(":where(:root)")


def test_split_selectors_ignoriert_komma_in_zeichenkette():
    assert split_selectors('[data-x="a,b"] , .c') == ['[data-x="a,b"]', ".c"]


def test_scope_css_zaehlt_klammern_in_zeichenketten_nicht():
    css = '.a { content: "}"; } .b { color: red; }'
    ergebnis = scope_css(css)
    assert ROOT_CLASS + ' .a { content: "}"; }' in ergebnis
    assert ROOT_CLASS + " .b { color: red; }" in ergebnis


from niedrigwasser.embed_fragment import build_fragment, quell_hash

SEITE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Titel</title>
<style>
:root { --page: #fff; }
:root[data-theme="dark"] { --page: #000; }
#tip {
  position: fixed; z-index: 50; pointer-events: none; display: none;
  max-width: 320px;
}
</style>
</head>
<body>
<button id="theme-btn" type="button" aria-live="polite">Design: Auto</button>
<div id="tip" role="tooltip"></div>
<main>Inhalt</main>
<script>
/* ---------- Theme ---------- */
var mq = window.matchMedia("(prefers-color-scheme: dark)");
function isDark() {
  var t = document.documentElement.getAttribute("data-theme");
  if (t === "dark") return true;
  if (t === "light") return false;
  return mq.matches;
}
var themeBtn = document.getElementById("theme-btn");
var themeOrder = ["auto", "light", "dark"], themeNames = { auto: "Auto", light: "Hell", dark: "Dunkel" };
var themeState = "auto";
themeBtn.addEventListener("click", function () {
  themeState = themeOrder[(themeOrder.indexOf(themeState) + 1) % 3];
  if (themeState === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", themeState);
  themeBtn.textContent = "Design: " + themeNames[themeState];
  redrawCanvases();
});
if (mq.addEventListener) mq.addEventListener("change", redrawCanvases);
function redrawCanvases() { }
</script>
</body>
</html>
"""


def test_build_fragment_entfernt_den_dokumentrahmen():
    frag = build_fragment(SEITE, "de")
    for verboten in ("<!DOCTYPE", "<html", "<head", "<body", "<title"):
        assert verboten not in frag, verboten
    # Vor dem Container steht nur die Herkunftsmarkierung.
    rumpf = frag.split("-->\n", 1)[1]
    assert rumpf.startswith(f'<div class="{ROOT_CLASS.lstrip(".")}">')
    assert frag.rstrip().endswith("</div>")
    assert "Inhalt" in frag


def test_build_fragment_traegt_eine_herkunftsmarkierung():
    frag = build_fragment(SEITE, "de")
    assert frag.startswith("<!--\n")
    kopf = frag.split("-->", 1)[0]
    # Generiert, von wem, wie neu zu erzeugen, und dass Handarbeit verloren geht.
    assert "Generiert" in kopf
    assert "scripts/build_embed.py" in kopf
    assert "verloren" in kopf
    # Der Hash bindet das Fragment an einen konkreten Quell-Stand ...
    assert quell_hash(SEITE) in kopf
    # ... ein Zeitstempel wuerde den Determinismus brechen und fehlt darum.
    assert not re.search(r"\d{4}-\d{2}-\d{2}", kopf)


def test_herkunftsmarkierung_folgt_der_quelle():
    andere = SEITE.replace("Inhalt", "Anderer Inhalt")
    assert quell_hash(SEITE) != quell_hash(andere)
    assert quell_hash(andere) in build_fragment(andere, "de").split("-->", 1)[0]


def test_build_fragment_kapselt_das_css_und_dreht_die_polaritaet():
    flach = " ".join(build_fragment(SEITE, "de").split())
    # Der helle Satz bleibt Basis ...
    assert f"{ROOT_CLASS} {{ --page: #fff; }}" in flach
    # ... der dunkle wird auf den Dunkel-Zustand des Hosts konditioniert.
    assert f"{DARK_HOST} {ROOT_CLASS} {{ --page: #000; }}" in flach


def test_build_fragment_senkt_die_tooltip_ebene_unter_das_menueband():
    frag = build_fragment(SEITE, "de")
    assert "z-index: 50" not in frag
    assert "position: fixed; z-index: 40; pointer-events: none" in frag


def test_build_fragment_entfernt_den_seiteneigenen_umschalter():
    frag = build_fragment(SEITE, "de")
    assert 'id="theme-btn"' not in frag
    assert "themeBtn" not in frag
    assert "themeOrder" not in frag


def test_build_fragment_entfernt_den_umschalter_in_jeder_sprache():
    """Der Umschalter wird an seiner id erkannt, nicht an seiner Beschriftung.

    Seine Beschriftung kommt aus dem Sprachkatalog. Ein Literal wuerde auf der
    englischen Seite mit 'toggle-markup: 0 Treffer' abbrechen -- genau das ist
    beim ersten englischen Fragmentbau passiert.
    """
    englisch = SEITE.replace(">Design: Auto<", ">Theme: Auto<")
    assert ">Theme: Auto<" in englisch
    frag = build_fragment(englisch, "en")
    assert 'id="theme-btn"' not in frag
    assert "Theme: Auto" not in frag


def test_build_fragment_setzt_die_theme_bruecke():
    frag = build_fragment(SEITE, "de")
    # isDark folgt jetzt derselben Bedingung wie die CSS-Regeln
    assert 'getAttribute("data-theme") !== "light"' in frag
    assert "mq.matches" not in frag
    # Attributwechsel im Menueband loest ein Neuzeichnen aus
    assert "MutationObserver" in frag
    assert 'attributeFilter: ["data-theme"]' in frag


def test_build_fragment_bricht_ab_wenn_eine_marke_fehlt():
    with pytest.raises(FragmentFehler, match="theme-block"):
        build_fragment(SEITE.replace("/* ---------- Theme ---------- */", "/* weg */"), "de")


def test_build_fragment_bricht_bei_mehrfachtreffer_der_marke_ab():
    # Ein zweites <style>...</style>-Paar macht die Marke "style" mehrdeutig.
    # _schneide darf dann nicht still das erste Paar nehmen, sondern muss
    # hart abbrechen -- dieselbe Strenge wie ersetze_genau.
    seite = SEITE.replace(
        "</style>\n</head>",
        "</style>\n<style>/* zweites Vorkommen */</style>\n</head>",
    )
    with pytest.raises(FragmentFehler, match="2 Treffer"):
        build_fragment(seite, "de")


from pathlib import Path

from niedrigwasser.embed_build import baue_embed, pruefe_gates

# An der Repo-Wurzel verankert statt am Arbeitsverzeichnis (wie in
# scripts/build_embed.py): sonst haengt der Skip-Grund vom Aufrufort ab und
# "Export nicht gebaut" kann in Wahrheit "falsches Arbeitsverzeichnis"
# bedeuten -- beides sieht von aussen wie ein normaler Skip aus.
_REPO_WURZEL = Path(__file__).resolve().parents[1]
EXPORT = _REPO_WURZEL.parent / "niedrigwasser-trendindex-public" / "site" / "index.html"


@pytest.mark.skipif(not EXPORT.exists(), reason="Export nicht gebaut")
def test_fragment_aus_dem_echten_export():
    frag = build_fragment(EXPORT.read_text(encoding="utf-8"), "de")

    # Dokumentrahmen ist weg
    for verboten in ("<!DOCTYPE", "<html", "<head>", "</head>", "<body", "</body>", "<title>"):
        assert verboten not in frag, verboten

    # Der Seiteninhalt hat den Schnitt ueberlebt. Diese Zeile ist zugleich der
    # Grund, warum oben "<head>" und nicht "<head" geprueft wird: <header> ist
    # legitimer Inhalt.
    assert '<header class="hero">' in frag

    # Kein nackter Element-Selektor: jede Regel haengt am Container
    for zeile in frag.split("</style>", 1)[0].splitlines():
        if "{" in zeile and not zeile.lstrip().startswith("@"):
            selektor = zeile.split("{", 1)[0].strip()
            if selektor:
                assert ".nw-root" in selektor, selektor

    # Die vier responsiven Queries stehen unveraendert
    assert "@media (max-width: 900px)" in frag
    assert frag.count("@media (max-width: 720px)") == 3
    assert "prefers-color-scheme" not in frag

    # Der Sonderfall, an dem die naive Umkehrung gebrochen waere:
    # hell bleibt #fff, dunkel ist konditioniert.
    flach = " ".join(frag.split())
    assert ".nw-root .seg button[aria-pressed=\"true\"] { background: var(--accent); color: #fff; }" in flach
    assert ':root:not([data-theme="light"]) .nw-root .seg button[aria-pressed="true"] { color: #12100d; }' in flach

    # Kollisionen aufgeloest
    assert "z-index: 50" not in frag
    assert 'id="theme-btn"' not in frag

    # Die Daten sind noch da
    assert 'id="nw-data"' in frag and 'id="nw-geo"' in frag


@pytest.mark.skipif(not EXPORT.exists(), reason="Export nicht gebaut")
def test_fragment_ist_deterministisch(tmp_path):
    """Zwei vollstaendige Laeufe ueber den Schreibweg ergeben byte-identische Dateien.

    Zweimal dieselbe reine Funktion im selben Prozess aufzurufen waere
    tautologisch. Gemeint ist die Zusicherung, die im Website-Repo zaehlt: ein
    erneuter Bau erzeugt keinen Diff. Darum ueber baue_embed nach tmp_path und
    Byte-Vergleich. Muster ist leer -- die Gates sind Gegenstand des Tests
    darunter, hier geht es allein um den Determinismus.
    """
    erst = tmp_path / "lauf-a" / "fragment.html"
    zweit = tmp_path / "lauf-b" / "fragment.html"

    assert baue_embed(EXPORT, erst, [], "de") == 0
    assert baue_embed(EXPORT, zweit, [], "de") == 0
    assert erst.read_bytes() == zweit.read_bytes()


# Die echten Verbots-Muster liegen in der Publikationsschicht, die nicht Teil
# der oeffentlichen Fassung ist. Sie wird per Pfad geladen statt importiert:
# ein Import auf Modulebene wuerde die Suite im exportierten Repo schon beim
# Einsammeln brechen. Fehlt die Schicht, ist der Test gegenstandslos -- deshalb
# haengt der Skip an beidem, Export UND Publikationsschicht.
PUBLIKATIONSSCHICHT = _REPO_WURZEL / "scripts" / "export_public.py"


def _lade_verbots_muster() -> list[tuple[str, str]]:
    import importlib.util

    spec = importlib.util.spec_from_file_location("_gates", PUBLIKATIONSSCHICHT)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul.VERBOTS_MUSTER


@pytest.mark.skipif(
    not EXPORT.exists() or not PUBLIKATIONSSCHICHT.exists(),
    reason="Export nicht gebaut oder Publikationsschicht nicht vorhanden",
)
def test_die_echten_gates_laufen_ueber_das_echte_fragment():
    """Die teuerste denkbare Regression: ein Leck im ausgelieferten Fragment.

    Geprueft werden die echten Muster gegen das echte, aus dem echten Export
    gebaute Fragment -- nicht gegen synthetische Zeichenketten.
    """
    muster = _lade_verbots_muster()
    assert len(muster) == 16, "Musterliste hat sich geaendert -- Zahl mitfuehren"

    frag = build_fragment(EXPORT.read_text(encoding="utf-8"), "de")
    assert pruefe_gates(frag, muster) == []


# --- Sprachkennung und zweite Sprachfassung -------------------------------

EXPORT_EN = EXPORT.parent / "index.en.html"


def test_herkunftskopf_nennt_die_sprache():
    """Der Kopf ist das einzige, woran ein Mensch die Fassung erkennt.

    Ohne die Sprache im Kopf traegen beide Fragmente denselben Text und
    unterscheiden sich nur im Hash -- unbrauchbar fuer den, der im
    Website-Repo nachsieht, welche Datei welche ist.
    """
    frag_de = build_fragment(SEITE, "de")
    frag_en = build_fragment(SEITE, "en")
    assert "Sprache: de" in frag_de
    assert "Sprache: en" in frag_en
    # Auch das Neu-Erzeugen-Kommando muss die Sprache tragen, sonst baut, wer
    # es kopiert, die falsche Fassung ueber die richtige.
    assert "--lang de" in frag_de
    assert "--lang en" in frag_en
    assert frag_de != frag_en


def test_build_fragment_verlangt_die_sprache():
    """Kein Default: ein stiller Rueckfall waere im Kopf nicht sichtbar."""
    with pytest.raises(TypeError):
        build_fragment(SEITE)


@pytest.mark.skipif(
    not EXPORT_EN.exists() or not PUBLIKATIONSSCHICHT.exists(),
    reason="Englischer Export nicht gebaut oder Publikationsschicht nicht vorhanden",
)
def test_die_echten_gates_laufen_auch_ueber_das_englische_fragment():
    """Dieselbe Zusicherung wie fuer das deutsche Fragment.

    Die englische Fassung ist eine eigene Datei aus einem eigenen Katalog --
    ein Leck kann dort stehen, ohne dass es im deutschen auftaucht.
    """
    frag = build_fragment(EXPORT_EN.read_text(encoding="utf-8"), "en")
    assert pruefe_gates(frag, _lade_verbots_muster()) == []


@pytest.mark.skipif(not EXPORT_EN.exists(), reason="Englischer Export nicht gebaut")
def test_englisches_fragment_ist_deterministisch(tmp_path):
    erst = tmp_path / "lauf-a" / "fragment.html"
    zweit = tmp_path / "lauf-b" / "fragment.html"

    assert baue_embed(EXPORT_EN, erst, [], "en") == 0
    assert baue_embed(EXPORT_EN, zweit, [], "en") == 0
    assert erst.read_bytes() == zweit.read_bytes()


# Inhaltsanker, die es je nur in einer Sprachfassung gibt. Beide stammen aus
# demselben Katalogschluessel (hero.kicker) und stehen im sichtbaren Text wie
# im eingebetteten Katalog-Blob.
ANKER_DE = "Niedrigwasser-Trendindex"
ANKER_EN = "Low-flow trend index"


@pytest.mark.skipif(
    not EXPORT.exists() or not EXPORT_EN.exists(),
    reason="Export nicht in beiden Sprachen gebaut",
)
def test_beide_fragmente_unterscheiden_sich():
    """Der teuerste stille Fehler waere zweimal dieselbe Sprache.

    ``de != en`` allein beweist das NICHT: Die Herkunftskoepfe tragen
    "Sprache: de" bzw. "Sprache: en" und machen zwei aus derselben deutschen
    Seite gebaute Fragmente schon deshalb ungleich. Genau der Fall, den dieser
    Test abdecken soll, kaeme also durch. Deshalb Inhaltsanker: Jede Fassung
    muss ihren eigenen Text tragen UND den der anderen nicht.

    Zusaetzlich der Datenblock -- ein leeres oder halbes Fragment waere sonst
    auch "verschieden".
    """
    de = build_fragment(EXPORT.read_text(encoding="utf-8"), "de")
    en = build_fragment(EXPORT_EN.read_text(encoding="utf-8"), "en")

    assert de != en
    assert ANKER_DE in de and ANKER_DE not in en
    assert ANKER_EN in en and ANKER_EN not in de
    assert 'id="nw-data"' in de and 'id="nw-data"' in en


def test_template_loest_css_variablen_nicht_an_root_auf():
    """Guard gegen den Rueckfall, der die eingebettete Heatmap entfaerbt hat.

    Die Fragment-CSS wird auf .nw-root gekapselt; damit liegen die Custom
    Properties dort und nicht mehr auf :root. Wer sie mit
    getComputedStyle(document.documentElement) liest, bekommt eingebettet den
    leeren String -- und Canvas verwirft eine ungueltige fillStyle-Zuweisung
    still, statt zu werfen. Der Fehler war deshalb nur im Browser zu sehen:
    grauer Canvas-Hintergrund, keine Jahres- und Monatsbeschriftung.

    Das data-theme-Attribut ist ausgenommen: es sitzt in beiden Fassungen auf
    :root, isDark() liest es dort zu Recht.
    """
    template = (WURZEL / "site" / "template.html").read_text(encoding="utf-8")
    treffer = re.findall(
        r"getComputedStyle\(\s*document\.documentElement\s*\)", template
    )
    assert not treffer, (
        "CSS-Variablen werden an :root aufgeloest; eingebettet liegen sie auf "
        f"{ROOT_CLASS!r}. An einem Element im Inhalt lesen (Vererbung). "
        f"Treffer: {treffer}"
    )
