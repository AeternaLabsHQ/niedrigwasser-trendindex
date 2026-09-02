import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="niedrigwasser", description="Niedrigwasser-Trendindex-Pipeline")
    sub = parser.add_subparsers(dest="stage", required=True)

    from niedrigwasser.stages import aggregate as aggregate_stage
    from niedrigwasser.stages import ingest as ingest_stage
    from niedrigwasser.stages import metrics as metrics_stage
    from niedrigwasser.stages import render as render_stage
    from niedrigwasser.stages import screen as screen_stage
    from niedrigwasser.stages import trend as trend_stage

    p_ingest = sub.add_parser("ingest", help="NIWIS-Daten laden und normalisieren")
    p_ingest.add_argument("--raw-dir", default="data/raw/niwis")
    p_ingest.add_argument("--interim-dir", default="data/interim")
    p_ingest.add_argument("--db", default="data/niedrigwasser.duckdb")
    p_ingest.add_argument("--log-dir", default="logs")
    p_ingest.add_argument("--refresh", action="store_true")
    p_ingest.add_argument("--limit", type=int, default=None,
                          help="nur die ersten N Stationen (Smoke-Test)")
    p_ingest.add_argument("--topology-overrides", default="config/topology_overrides.csv",
                          help="CSV mit manuellen downstream_id-Overrides")
    p_ingest.set_defaults(run=ingest_stage.run)

    p_screen = sub.add_parser("screen", help="Vollständigkeits- und Homogenitäts-Screening")
    p_screen.add_argument("--db", default="data/niedrigwasser.duckdb")
    p_screen.add_argument("--interim-dir", default="data/interim")
    p_screen.add_argument("--log-dir", default="logs")
    p_screen.add_argument("--flags", default="config/station_flags.csv")
    p_screen.add_argument("--out-suffix", default="",
                          help="Sensitivitaetslauf: eigener interim-Ordner "
                               "interim/screen-<suffix>/")
    p_screen.add_argument("--exclude-flags", default=None,
                          help="kommaseparierte Flags, die eine Station aus dem "
                               "naturnahen Subset ausschliessen (Default: "
                               "reservoir,transfer,mining)")
    p_screen.set_defaults(run=screen_stage.run)

    p_metrics = sub.add_parser("metrics", help="Kennzahlen pro Station und Wasserjahr")
    p_metrics.add_argument("--db", default="data/niedrigwasser.duckdb")
    p_metrics.add_argument("--interim-dir", default="data/interim")
    p_metrics.add_argument("--log-dir", default="logs")
    p_metrics.add_argument("--ref-start", type=int, default=1992)
    p_metrics.add_argument("--ref-end", type=int, default=2011)
    p_metrics.add_argument("--inter-event", type=int, default=5)
    p_metrics.add_argument("--out-suffix", default="",
                           help="Sensitivitaetslauf: eigener interim-Ordner, kein DB-Load")
    p_metrics.set_defaults(run=metrics_stage.run)

    p_aggregate = sub.add_parser("aggregate", help="Nationaler Niedrigwasser-Index (4 Varianten)")
    p_aggregate.add_argument("--db", default="data/niedrigwasser.duckdb")
    p_aggregate.add_argument("--interim-dir", default="data/interim")
    p_aggregate.add_argument("--log-dir", default="logs")
    p_aggregate.add_argument("--sinks", default="config/sink_categories.csv")
    p_aggregate.add_argument("--metrics-suffix", default="",
                             help="Sensitivitaetslauf: liest interim/metrics-<suffix>/")
    p_aggregate.add_argument("--screen-suffix", default="",
                             help="Sensitivitaetslauf: liest interim/screen-<suffix>/ statt "
                                  "interim/screen/ (Default: leer, entkoppelt von "
                                  "--metrics-suffix)")
    p_aggregate.add_argument("--out-suffix", default="",
                             help="Sensitivitaetslauf: eigener interim-Ordner, kein DB/CSV-Export")
    p_aggregate.set_defaults(run=aggregate_stage.run)

    p_trend = sub.add_parser("trend", help="TFPW-MK-Trends, Dekaden, nicht-stationaere GEV")
    p_trend.add_argument("--db", default="data/niedrigwasser.duckdb")
    p_trend.add_argument("--interim-dir", default="data/interim")
    p_trend.add_argument("--log-dir", default="logs")
    p_trend.add_argument("--agg-suffix", default="",
                         help="liest interim/aggregate-<suffix>/")
    p_trend.add_argument("--metrics-suffix", default="",
                         help="Sensitivitaetslauf: liest interim/metrics-<suffix>/ statt "
                              "interim/metrics/ (Default: leer, entkoppelt von --agg-suffix)")
    p_trend.add_argument("--out-dir", default="out")
    p_trend.set_defaults(run=trend_stage.run)

    p_render = sub.add_parser("render", help="PNGs + Site-Datenexport (data.json)")
    p_render.add_argument("--db", default="data/niedrigwasser.duckdb")
    p_render.add_argument("--interim-dir", default="data/interim")
    p_render.add_argument("--log-dir", default="logs")
    p_render.add_argument("--out-dir", default="out")
    p_render.add_argument("--site-data", default="site/data.json")
    p_render.add_argument("--sinks", default="config/sink_categories.csv")
    p_render.add_argument("--basin-areas", default="config/basin_domestic_area.csv",
                          help="CSV mit recherchierten Inlandsanteilen der "
                               "Basin-Auslass-Einzugsgebiete; fehlt sie, faellt der "
                               "ausgewiesene Auslandsanteil auf coverage minus "
                               "Flaeche Deutschlands zurueck")
    p_render.add_argument("--embed", action="store_true",
                          help="bettet data.json nach dem Export in site/template.html "
                               "ein und schreibt site/index.html (self-contained)")
    p_render.add_argument("--site-template", default="site/template.html")
    p_render.add_argument("--site-html", default="site/index.html")
    p_render.add_argument("--site-geo", default="site/geo.json",
                          help="Basemap-GeoJSON (Natural Earth), wird bei --embed "
                               "zusaetzlich eingebettet (optional)")
    p_render.add_argument("--site-text", default="site/text.de.json",
                          help="Sprachkatalog fuer die Seite; wird bei --embed "
                               "in Inhalte und Attribute eingesetzt")
    # Nur der AUSGABEPFAD der zweiten Sprache. Welcher Katalog sie speist,
    # steht bewusst nicht hier: den leitet niedrigwasser.i18n.geschwister_katalog
    # aus --site-text ab (Namenskonvention text.<sprache>.json). Ein zweites
    # --site-text-en waere ein zweiter Weg zur selben Datei und koennte von der
    # kreuzgeprueften Fassung abweichen.
    # Ohne Literal-Default: der loeste gegen das Arbeitsverzeichnis auf. Fehlt
    # das Argument, leitet die render-Stage den Pfad aus --site-html und dem
    # Sprachcode ab (site/index.html -> site/index.en.html) -- er kann damit
    # nur dorthin zeigen, wohin auch die erste Sprachfassung geht.
    p_render.add_argument("--site-html-en", default=None,
                          help="Ausgabepfad der zweiten Sprachfassung (bei --embed); "
                               "Default: aus --site-html abgeleitet, also "
                               "site/index.en.html. Gebaut wird sie nur, wenn der "
                               "Geschwisterkatalog zu --site-text existiert")
    p_render.set_defaults(run=render_stage.run)

    args = parser.parse_args(argv)
    return args.run(args)
