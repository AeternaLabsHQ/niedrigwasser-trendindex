"""Senken-Kategorisierung (outlet / standalone / nested) als Config.

Zwei Modi:

1. **Vorschlag generieren** (`--propose`): liest
   `data/interim/topology/stations_topology.parquet`, listet alle Senken
   (Stationen mit `downstream_id` null) und druckt einen Heuristik-Vorschlag
   fuer `standalone` vs. `nested`. `config/sink_categories.csv` wird dabei
   NUR geschrieben, wenn sie noch nicht existiert -- die Datei ist danach
   Handarbeit (siehe `docs/topologie-report.md`, Abschnitt "Plausibilisierung
   der Flaechensumme"), das Skript ueberschreibt eine bestehende, manuell
   kuratierte CSV nie automatisch.

   Heuristik: Senke S ist ein `nested`-Kandidat, wenn eine andere Station D
   existiert mit `catchment_area(D) > catchment_area(S) * 3` und
   Haversine-Distanz(S, D) < 250 km. Das ist NUR ein Vorschlag -- die
   tatsaechliche Entscheidung faellt manuell anhand der (i)/(ii)/(iii)-Listen
   im Topologie-Report inkl. der bei einer internen Pruefung benannten
   Grenzfaelle (Maas-/IJssel-Zubringer, Gewaesser unterhalb eines
   Basin-Auslasses etc.).

2. **Konsistenz-Check** (Default, auch nach `--propose`): validiert die
   vorhandene `config/sink_categories.csv` gegen das Parquet:
   - jede Senke aus dem Parquet ist kategorisiert,
   - keine Nicht-Senke (Station mit gesetztem `downstream_id`) steht in der
     CSV,
   - keine unbekannte `station_id` in der CSV,
   - Kategorie-Zaehlung und Flaechensumme je Kategorie werden gedruckt.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import polars as pl

TOPOLOGY_PARQUET = Path("data/interim/topology/stations_topology.parquet")
SINK_CATEGORIES_CSV = Path("config/sink_categories.csv")
VALID_CATEGORIES = {"outlet", "standalone", "nested"}

OUTLET_STATION_IDS = {
    "DESM_DEXX2790010",  # Rees, Rhein
    "DESM_DEXX503050",   # Wittenberge, Elbe
    "DESM_DEXX603080",   # Hohensaaten Finow, Oder
    "DESM_DEXX10088003", # Hofkirchen, Donau
    "DESM_DEXX49100101", # Intschede, Weser
}

AREA_RATIO = 3.0
MAX_DISTANCE_KM = 250.0
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def load_sinks() -> pl.DataFrame:
    df = pl.read_parquet(TOPOLOGY_PARQUET)
    return df.filter(pl.col("downstream_id").is_null())


def propose(df_all: pl.DataFrame, sinks: pl.DataFrame) -> None:
    """Print a heuristic outlet/standalone/nested proposal; write the CSV
    only if it does not exist yet."""
    candidates = df_all.select(["station_id", "catchment_area", "lat", "lon"]).to_dicts()
    rows = []
    for r in sinks.sort("catchment_area", descending=True).iter_rows(named=True):
        sid = r["station_id"]
        if sid in OUTLET_STATION_IDS:
            category = "outlet"
        else:
            nested_candidate = False
            for c in candidates:
                if c["station_id"] == sid:
                    continue
                if c["catchment_area"] is None or r["catchment_area"] is None:
                    continue
                if c["catchment_area"] > r["catchment_area"] * AREA_RATIO:
                    dist = haversine_km(r["lat"], r["lon"], c["lat"], c["lon"])
                    if dist < MAX_DISTANCE_KM:
                        nested_candidate = True
                        break
            category = "nested" if nested_candidate else "standalone"
        rows.append((sid, r["name"], r["river"], r["catchment_area"], category))

    print(f"{'station_id':<24} {'name':<26} {'river':<28} {'area_km2':>10}  proposal")
    for sid, name, river, area, category in rows:
        print(f"{sid:<24} {(name or ''):<26} {(river or ''):<28} {area:>10.1f}  {category}")

    n_outlet = sum(1 for r in rows if r[4] == "outlet")
    n_standalone = sum(1 for r in rows if r[4] == "standalone")
    n_nested = sum(1 for r in rows if r[4] == "nested")
    print(f"\nHeuristik-Vorschlag: {n_outlet} outlet / {n_standalone} standalone / {n_nested} nested")
    print("Hinweis: dies ist nur ein Vorschlag -- manuelle Kuration anhand von "
          "docs/topologie-report.md ist erforderlich.")

    if SINK_CATEGORIES_CSV.exists():
        print(f"\n{SINK_CATEGORIES_CSV} existiert bereits -- nicht ueberschrieben.")
        return

    SINK_CATEGORIES_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SINK_CATEGORIES_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["station_id", "category", "note"])
        for sid, _name, _river, _area, category in rows:
            w.writerow([sid, category, ""])
    print(f"Erstentwurf geschrieben nach {SINK_CATEGORIES_CSV} (manuelle Kuration noetig).")


def check(df_all: pl.DataFrame, sinks: pl.DataFrame) -> None:
    if not SINK_CATEGORIES_CSV.exists():
        raise SystemExit(f"{SINK_CATEGORIES_CSV} existiert nicht -- zuerst --propose ausfuehren.")

    cats = pl.read_csv(SINK_CATEGORIES_CSV)
    problems: list[str] = []

    bad_category = cats.filter(~pl.col("category").is_in(list(VALID_CATEGORIES)))
    if bad_category.height:
        problems.append(f"Unbekannte Kategorie(n): {bad_category['category'].unique().to_list()}")

    all_ids = set(df_all["station_id"].to_list())
    sink_ids = set(sinks["station_id"].to_list())
    csv_ids = set(cats["station_id"].to_list())

    unknown_ids = csv_ids - all_ids
    if unknown_ids:
        problems.append(f"{len(unknown_ids)} unbekannte station_id(s) in CSV: {sorted(unknown_ids)[:10]}")

    non_sink_ids = csv_ids & (all_ids - sink_ids)
    if non_sink_ids:
        problems.append(f"{len(non_sink_ids)} Nicht-Senken (mit downstream_id) in CSV: {sorted(non_sink_ids)[:10]}")

    missing_sinks = sink_ids - csv_ids
    if missing_sinks:
        problems.append(f"{len(missing_sinks)} Senken fehlen in CSV: {sorted(missing_sinks)[:10]}")

    dupes = cats.group_by("station_id").len().filter(pl.col("len") > 1)
    if dupes.height:
        problems.append(f"Doppelte station_id(s) in CSV: {dupes['station_id'].to_list()}")

    if problems:
        print("Konsistenz-Check FEHLGESCHLAGEN:")
        for p in problems:
            print(f"  - {p}")
        raise SystemExit(1)

    print("Konsistenz-Check OK: alle 191 Senken kategorisiert, keine Nicht-Senken, "
          "keine unbekannten IDs, keine Duplikate.")

    joined = cats.join(
        sinks.select(["station_id", "catchment_area"]), on="station_id", how="left"
    )
    summary = (
        joined.group_by("category")
        .agg(pl.len().alias("n"), pl.col("catchment_area").sum().alias("area_km2"))
        .sort("category")
    )
    total_n = summary["n"].sum()
    total_area = summary["area_km2"].sum()
    print("\nKategorie-Summen:")
    for row in summary.iter_rows(named=True):
        print(f"  {row['category']:<10} {row['n']:>4} Stationen  {row['area_km2']:>12,.0f} km2".replace(",", "."))
    print(f"  {'gesamt':<10} {total_n:>4} Stationen  {total_area:>12,.0f} km2".replace(",", "."))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--propose", action="store_true",
                         help="Heuristik-Vorschlag drucken (und CSV nur schreiben, falls sie fehlt)")
    args = parser.parse_args()

    df_all = pl.read_parquet(TOPOLOGY_PARQUET)
    sinks = df_all.filter(pl.col("downstream_id").is_null())

    if args.propose:
        propose(df_all, sinks)
        print()

    check(df_all, sinks)


if __name__ == "__main__":
    main()
