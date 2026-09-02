"""Baut site/index.html und site/index.en.html aus Template, Daten und Katalogen.

Duennner Wrapper um ``niedrigwasser.site_embed.embed_alle_sprachen`` — dieselbe
Logik laeuft in der render-Stage hinter ``uv run niedrigwasser render --embed``.
Kennt nur die Pfade, die Arbeit (Marker ersetzen, Katalog einsetzen und pruefen,
zweite Sprachfassung ableiten) macht das Paket.

Der Unterschied zur render-Stage ist allein, dass hier nichts neu gerechnet
wird: ``site/data.json`` wird gelesen, nicht geschrieben, ``meta.generated``
bleibt also stehen. Der gebaute HTML-Stand ist derselbe.

Aufruf:  uv run python scripts/build_site.py
"""

from __future__ import annotations

from pathlib import Path

from niedrigwasser.site_embed import embed_alle_sprachen


def main(root: Path | None = None) -> Path:
    """Baut alle Sprachfassungen unter ``root`` (Default: Repo-Wurzel).

    Rueckgabe ist die primaere Ausgabedatei (``site/index.html``); die zweite
    Sprachfassung nennt die Protokollzeile.

    ``root`` ist als Parameter da, damit die Funktion in Tests gegen ein
    ``tmp_path``-Fixture laufen kann, ohne die echten Repo-Dateien anzufassen.
    """
    root = root or Path(__file__).resolve().parents[1]
    out = root / "site" / "index.html"
    embed_alle_sprachen(
        root / "site" / "template.html",
        root / "site" / "data.json",
        out,
        geo_path=root / "site" / "geo.json",
        text_path=root / "site" / "text.de.json",
        melde=print,
    )
    return out


if __name__ == "__main__":
    main()
