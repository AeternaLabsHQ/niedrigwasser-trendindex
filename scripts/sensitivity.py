"""Sensitivitaetslaeufe: Referenzperiode, Ereignis-Pooling und Homogenitaets-Flags.

Zwei Familien von Laeufen:

1. Metrik-Laeufe (`RUNS`, teuer - metrics wird neu gerechnet): Referenzperiode
   (WMO 1991-2020) und Ereignis-Pooling (3/7 Tage). Kette
   `niedrigwasser metrics --out-suffix X` -> `niedrigwasser aggregate --metrics-suffix X --out-suffix X`
   -> `niedrigwasser trend --agg-suffix X` (jeweils via `uv run`, echte CLI-Pfade, kein
   DB/CSV-Export der Sensitivitaetslaeufe - siehe Stage-Code). Vergleich der
   national_trends-Ergebnisse (Variante "primary") mit dem Hauptlauf.
   Ausgabe: `out/sensitivity.csv`.

2. Flags-Laeufe (`FLAGS_RUNS`, billig - metrics bleibt unangetastet, nur das
   Screening laeuft neu): klammern die Homogenitaets-Flags-Entscheidung von beiden
   Seiten ein (externe Methodenkritik - die Flags waren der groesste ungetestete Hebel).
   Kette `niedrigwasser screen --flags F --out-suffix X [--exclude-flags ...]` ->
   `niedrigwasser aggregate --screen-suffix X --out-suffix X` -> `niedrigwasser trend --agg-suffix X`.
   Ausgabe: `out/sensitivity_flags.csv`. Aufruf isoliert per `--flags-only`.

Kernkriterium beider Familien: Vorzeichen signifikanter Trends (p < 0.05)
duerfen sich zwischen den Laeufen nicht aendern (Exit 1 sonst).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import polars as pl

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from niedrigwasser.stages.trend import MIN_YEARS, WINDOW  # noqa: E402
from niedrigwasser.trend import mk_trend  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
INTERIM = REPO_ROOT / "data" / "interim"
OUT_DIR = REPO_ROOT / "out"

NATIONAL_METRICS = ["index_days", "index_deficit", "index_ssi"]

RUNS: dict[str, list[str]] = {
    "refwmo": ["--ref-start", "1991", "--ref-end", "2020"],
    "pool3": ["--inter-event", "3"],
    "pool7": ["--inter-event", "7"],
}

# --- Flags-Sensitivitaet (externe Methodenkritik) --------------------------
FLAGS_CSV = REPO_ROOT / "config" / "station_flags.csv"
SENS_DIR = INTERIM / "sensitivity"
LAX_FLAGS_CSV = SENS_DIR / "station_flags_lax.csv"
UNCERTAIN_PREFIX = "unsicher:"
ALL_FLAGS = "reservoir,transfer,mining,erosion"
FLAGS_RUNS = ["main", "flagslax", "flagsstrict"]
# Nur die Variante 'natural' haengt an den Flags: 'primary' wird in der
# aggregate-Stage mit natural_only=False gebildet und ist damit per Konstruktion
# flags-unabhaengig (check_primary_identity() verifiziert das am echten Output).
FLAGS_VARIANT = "natural"


def _run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def run_sensitivity_pipeline(suffix: str, metrics_args: list[str]) -> None:
    _run(["uv", "run", "niedrigwasser", "metrics", *metrics_args, "--out-suffix", suffix])
    _run([
        "uv", "run", "niedrigwasser", "aggregate",
        "--metrics-suffix", suffix, "--out-suffix", suffix,
    ])
    _run([
        "uv", "run", "niedrigwasser", "trend",
        "--agg-suffix", suffix, "--metrics-suffix", suffix,
    ])


def load_national_trends(agg_suffix: str, variant: str = "primary") -> pl.DataFrame:
    trend_dir = INTERIM / (f"trend-{agg_suffix}" if agg_suffix else "trend")
    df = pl.read_parquet(trend_dir / "national_trends.parquet")
    return df.filter(pl.col("variant") == variant).select(
        "metric", "trend", "p_value", "sens_slope"
    )


def load_primary_trends(agg_suffix: str) -> pl.DataFrame:
    return load_national_trends(agg_suffix, "primary")


def build_comparison(run_labels: list[str]) -> pl.DataFrame:
    parts = []
    for label in run_labels:
        agg_suffix = "" if label == "main" else label
        df = load_primary_trends(agg_suffix).with_columns(pl.lit(label).alias("run"))
        parts.append(df)
    combined = pl.concat(parts).select("run", "metric", "trend", "p_value", "sens_slope")
    return combined.sort(["metric", "run"])


def station_max_spell_trends(metrics_suffix: str) -> pl.DataFrame:
    """TFPW-MK + Sen-Slope auf der max_spell-Serie jeder Station (Fenster/
    Mindestjahre wie die trend-Stage: WINDOW=1992-2025, MIN_YEARS=25).

    max_spell ist die einzige Kennzahl, auf die das Inter-Event-Kriterium
    (Pooling) tatsaechlich wirkt (siehe docs/methods.md) - days_below,
    deficit_volume_m3, nm7q und ssi, und damit die national_trends-Metriken
    aus build_comparison(), sind pooling-invariant. Dies ist die Stelle, an
    der die Pooling-Sensitivitaet ueberhaupt etwas pruefen kann.
    """
    metrics_dir = INTERIM / (f"metrics-{metrics_suffix}" if metrics_suffix else "metrics")
    metrics = pl.read_parquet(metrics_dir / "station_year_metrics.parquet")
    df = metrics.filter(pl.col("water_year").is_between(*WINDOW))

    rows = []
    for (station,), grp in df.group_by("station_id", maintain_order=True):
        g = grp.filter(pl.col("max_spell").is_not_null()).sort("water_year")
        if g.height < MIN_YEARS:
            continue
        vals = [float(v) for v in g["max_spell"].to_list()]
        res = mk_trend(vals)
        rows.append({
            "station_id": station, "n_years": g.height,
            "trend": res["trend"], "p_value": res["p_value"], "sens_slope": res["sens_slope"],
        })
    return pl.DataFrame(rows) if rows else pl.DataFrame(
        schema={
            "station_id": pl.String, "n_years": pl.Int64,
            "trend": pl.String, "p_value": pl.Float64, "sens_slope": pl.Float64,
        }
    )


def station_max_spell_summary(run_labels: list[str]) -> pl.DataFrame:
    """Aggregiert station_max_spell_trends() je Lauf zu zwei Vergleichszeilen
    (share signifikant steigender Stationen, Median-Sen-Slope), im selben
    run/metric/trend/p_value/sens_slope-Schema wie build_comparison(), damit
    beide Tabellen zusammen in out/sensitivity.csv passen."""
    rows = []
    for label in run_labels:
        suffix = "" if label == "main" else label
        station_trends = station_max_spell_trends(suffix)
        n_total = station_trends.height
        sig = station_trends.filter(
            (pl.col("trend") == "increasing") & (pl.col("p_value") < 0.05)
        )
        share = (sig.height / n_total) if n_total else None
        median_sen = (
            float(station_trends["sens_slope"].drop_nulls().median())
            if station_trends.height else None
        )
        rows.append({
            "run": label, "metric": "station_max_spell_share_increasing",
            "trend": None, "p_value": None, "sens_slope": share,
        })
        rows.append({
            "run": label, "metric": "station_max_spell_median_sen",
            "trend": None, "p_value": None, "sens_slope": median_sen,
        })
    return pl.DataFrame(rows, schema={
        "run": pl.String, "metric": pl.String, "trend": pl.String,
        "p_value": pl.Float64, "sens_slope": pl.Float64,
    })


def check_sign_stability(comparison: pl.DataFrame) -> list[str]:
    """Prueft, ob sich das Vorzeichen signifikanter Trends (p < 0.05) je Metrik
    zwischen den Laeufen aendert. Gibt eine Liste von Problembeschreibungen zurueck
    (leer = stabil)."""
    problems = []
    for metric in NATIONAL_METRICS:
        sub = comparison.filter(pl.col("metric") == metric)
        sig = sub.filter(pl.col("p_value") < 0.05)
        signs = set()
        for row in sig.iter_rows(named=True):
            sign = "increasing" if row["sens_slope"] > 0 else "decreasing"
            signs.add(sign)
        if len(signs) > 1:
            problems.append(
                f"{metric}: widerspruechliche Vorzeichen bei signifikanten Trends "
                f"({sig.select('run', 'trend', 'sens_slope').to_dicts()})"
            )
    return problems


POOLING_RUNS = ["main", "pool3", "pool7"]


# --- Flags-Sensitivitaet ----------------------------------------------------

def lax_flags(flags: pl.DataFrame) -> pl.DataFrame:
    """Entfernt alle Flag-Zeilen, deren note mit 'unsicher:' beginnt.

    Reine Funktion (deterministisch, ordnungserhaltend) - das ist die
    Konstruktionsvorschrift der Variante 'flagslax': unsichere Flags gelten als
    nicht gesetzt, das naturnahe Subset wird dadurch groesser. Ein null-note
    zaehlt als 'nicht unsicher' und bleibt erhalten.
    """
    return flags.filter(
        ~pl.col("note").str.starts_with(UNCERTAIN_PREFIX).fill_null(False)
    )


def write_lax_flags(src: Path = FLAGS_CSV, dest: Path = LAX_FLAGS_CSV) -> Path:
    """Erzeugt die flagslax-Variante deterministisch aus der Original-CSV."""
    flags = pl.read_csv(src, schema={"station_id": pl.Utf8, "flag": pl.Utf8, "note": pl.Utf8})
    lax = lax_flags(flags)
    dest.parent.mkdir(parents=True, exist_ok=True)
    lax.write_csv(dest)
    print(
        f"flagslax-CSV: {dest.relative_to(REPO_ROOT)} "
        f"({flags.height} -> {lax.height} Zeilen, {flags.height - lax.height} 'unsicher:' entfernt)"
    )
    return dest


def run_flags_pipeline(suffix: str, flags_path: Path, exclude: str | None) -> None:
    """screen -> aggregate -> trend fuer einen Flags-Lauf.

    metrics wird NICHT neu gerechnet: Flags beeinflussen ausschliesslich
    'is_near_natural' im Screening, nicht die Stations-Kennzahlen. aggregate
    liest deshalb ohne --metrics-suffix aus interim/metrics/ (Hauptlauf).
    Alle Outputs landen in Suffix-Verzeichnissen - kein DB-Insert, kein
    Ueberschreiben von interim/screen/ oder out/.
    """
    cmd = [
        "uv", "run", "niedrigwasser", "screen",
        "--flags", str(flags_path), "--out-suffix", suffix,
    ]
    if exclude:
        cmd += ["--exclude-flags", exclude]
    _run(cmd)
    _run(["uv", "run", "niedrigwasser", "aggregate", "--screen-suffix", suffix, "--out-suffix", suffix])
    _run(["uv", "run", "niedrigwasser", "trend", "--agg-suffix", suffix])


def n_natural(screen_suffix: str) -> int:
    """Groesse des naturnahen Subsets eines Screening-Laufs."""
    screen_dir = INTERIM / (f"screen-{screen_suffix}" if screen_suffix else "screen")
    df = pl.read_parquet(screen_dir / "usable_stations.parquet")
    return df.filter(pl.col("is_near_natural")).height


def check_primary_identity(suffixes: list[str]) -> list[str]:
    """Verifiziert, dass die Variante 'primary' flags-unabhaengig ist.

    'primary' wird mit natural_only=False gebildet, die Flags koennen sie also
    per Konstruktion nicht beruehren. Diese Pruefung haelt das am echten Output
    fest: national_index_primary.parquet der Flags-Laeufe muss bit-gleich zum
    Hauptlauf sein. Rueckgabe: Liste von Problembeschreibungen (leer = ok).
    """
    problems = []
    base = pl.read_parquet(INTERIM / "aggregate" / "national_index_primary.parquet")
    for suffix in suffixes:
        other = pl.read_parquet(
            INTERIM / f"aggregate-{suffix}" / "national_index_primary.parquet"
        )
        if base.equals(other):
            print(f"primary-Identitaet {suffix}: OK ({base.height} Zeilen identisch zum Hauptlauf)")
        else:
            problems.append(
                f"{suffix}: national_index_primary weicht vom Hauptlauf ab "
                f"(erwartet: flags-unabhaengig)"
            )
    return problems


def build_flags_comparison(run_labels: list[str]) -> pl.DataFrame:
    """Vergleichstabelle der Flags-Laeufe, nur Variante 'natural'."""
    parts = []
    for label in run_labels:
        agg_suffix = "" if label == "main" else label
        df = load_national_trends(agg_suffix, FLAGS_VARIANT).with_columns(
            pl.lit(label).alias("run"), pl.lit(FLAGS_VARIANT).alias("variant"),
        )
        parts.append(df)
    combined = pl.concat(parts).select(
        "run", "variant", "metric", "trend", "p_value", "sens_slope"
    )
    return combined.sort(["metric", "run"])


def run_flags_sensitivity() -> int:
    """Fuehrt flagslax/flagsstrict aus und schreibt out/sensitivity_flags.csv."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lax_path = write_lax_flags()

    run_flags_pipeline("flagslax", lax_path, None)
    run_flags_pipeline("flagsstrict", FLAGS_CSV, ALL_FLAGS)

    comparison = build_flags_comparison(FLAGS_RUNS)
    comparison.write_csv(OUT_DIR / "sensitivity_flags.csv")

    counts = {label: n_natural("" if label == "main" else label) for label in FLAGS_RUNS}
    print("\nGroesse des naturnahen Subsets je Lauf:")
    for label, n in counts.items():
        print(f"  n_natural[{label}] = {n}")

    with pl.Config(tbl_rows=-1, tbl_width_chars=140):
        print()
        print("Flags-Sensitivitaet (nationale Trends, Variante 'natural'):")
        print(comparison)

    print()
    identity_problems = check_primary_identity(["flagslax", "flagsstrict"])
    # Plausibilitaet: laxere Flags -> groesseres, striktere Flags -> kleineres Subset.
    plausibility = []
    if counts["flagslax"] <= counts["main"]:
        plausibility.append(
            f"flagslax n_natural={counts['flagslax']} ist nicht groesser als "
            f"main n_natural={counts['main']}"
        )
    if counts["flagsstrict"] >= counts["main"]:
        plausibility.append(
            f"flagsstrict n_natural={counts['flagsstrict']} ist nicht kleiner als "
            f"main n_natural={counts['main']}"
        )

    problems = check_sign_stability(comparison) + identity_problems + plausibility
    if problems:
        print("\nSTOPP - Flags-Sensitivitaet:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("\nFlags-Sensitivitaet: OK (Vorzeichen stabil, primary identisch, Subset-Groessen "
          "plausibel)")
    return 0


def run_metrics_sensitivity() -> int:
    """Fuehrt die (teuren) metrics-basierten Laeufe aus und schreibt out/sensitivity.csv."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for suffix, metrics_args in RUNS.items():
        run_sensitivity_pipeline(suffix, metrics_args)

    comparison = build_comparison(["main", *RUNS.keys()])
    max_spell_summary = station_max_spell_summary(POOLING_RUNS)
    full = pl.concat([comparison, max_spell_summary])
    full.write_csv(OUT_DIR / "sensitivity.csv")

    with pl.Config(tbl_rows=-1, tbl_width_chars=140):
        print()
        print(comparison)
        print()
        print("Stations-max_spell-Sensitivitaet (Pooling wirkt hier tatsaechlich):")
        print(max_spell_summary)

    problems = check_sign_stability(comparison)
    if problems:
        print("\nSTOPP - Vorzeichen-Instabilitaet bei signifikanten Trends:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("\nVorzeichen-Stabilitaet: OK (keine Widersprueche bei signifikanten Trends)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sensitivity.py", description="Sensitivitaetslaeufe der niedrigwasser-Pipeline",
    )
    parser.add_argument(
        "--flags-only", action="store_true",
        help="nur die (billigen) Flags-Laeufe flagslax/flagsstrict ausfuehren; "
             "die metrics-basierten Laeufe (refwmo/pool3/pool7) werden uebersprungen",
    )
    args = parser.parse_args(argv)

    if args.flags_only:
        return run_flags_sensitivity()

    # Default: beide Familien. Die Flags-Laeufe sind billig (kein metrics-Rerun)
    # und laufen deshalb mit; out/sensitivity.csv bleibt inhaltlich unveraendert.
    rc = run_metrics_sensitivity()
    rc_flags = run_flags_sensitivity()
    return rc or rc_flags


if __name__ == "__main__":
    sys.exit(main())
