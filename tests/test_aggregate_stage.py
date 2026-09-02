import argparse
from pathlib import Path

import polars as pl

from niedrigwasser.stages.aggregate import run
from niedrigwasser.store import connect


def _seed(db: Path, interim: Path, sinks_path: Path) -> None:
    con = connect(db)
    # A -> B (B ist Auslass, kein downstream_id). C ist eine separate,
    # verschachtelte Senke (kein downstream_id, category=nested).
    stations_df = pl.DataFrame({
        "station_id": ["A", "B", "C"],
        "name": ["A", "B", "C"],
        "river": ["r", "r", "r2"],
        "lat": [1.0, 1.0, 2.0],
        "lon": [1.0, 1.0, 2.0],
        "catchment_area": [100.0, 150.0, 50.0],
        "downstream_id": ["B", None, None],
        "gauge_datum": [None, None, None],
        "source": ["x", "x", "x"],
        "river_km": [None, None, None],
        "gkz": [None, None, None],
        "license": [None, None, None],
    })
    con.execute("INSERT INTO stations SELECT * FROM stations_df")
    con.close()

    # is_near_natural: A=True, B=False, C=True (C aber ueber sink_categories
    # als 'nested' markiert und faellt in primary/natural trotzdem raus).
    usable_stations = pl.DataFrame({
        "station_id": ["A", "B", "C"],
        "n_usable_years": [2, 2, 2],
        "flags": [[], ["reservoir"], []],
        "is_near_natural": [True, False, True],
    })
    (interim / "screen").mkdir(parents=True)
    usable_stations.write_parquet(interim / "screen" / "usable_stations.parquet")

    metrics = pl.DataFrame({
        "station_id": ["A", "A", "B", "B", "C", "C"],
        "water_year": [2000, 2001, 2000, 2001, 2000, 2001],
        "days_below": [10, 0, 20, 5, 30, 0],
        "max_spell": [5, 0, 10, 3, 15, 0],
        "deficit_volume_m3": [1000.0, 0.0, 2000.0, 500.0, 3000.0, 0.0],
        "nm7q": [1.0, 2.0, 1.5, 2.5, 0.5, 3.0],
        "ssi": [-1.0, 0.0, -1.5, -0.2, -2.0, 0.1],
        "data_completeness": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    })
    (interim / "metrics").mkdir(parents=True)
    metrics.write_parquet(interim / "metrics" / "station_year_metrics.parquet")

    sinks_path.write_text(
        "station_id,category,note\nB,outlet,Auslass\nC,nested,verschachtelte Senke\n",
        encoding="utf-8",
    )


def test_aggregate_stage_end_to_end(tmp_path: Path):
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    sinks_path = tmp_path / "sink_categories.csv"
    _seed(db, interim, sinks_path)

    cwd = Path.cwd()
    import os
    os.chdir(tmp_path)
    try:
        rc = run(argparse.Namespace(
            db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
            sinks=str(sinks_path), metrics_suffix="", screen_suffix="", out_suffix="",
        ))
    finally:
        os.chdir(cwd)
    assert rc == 0

    agg_dir = interim / "aggregate"
    for variant in ["primary", "natural", "allsinks", "allsinks_natural"]:
        assert (agg_dir / f"national_index_{variant}.parquet").exists()

    primary = pl.read_parquet(agg_dir / "national_index_primary.parquet")
    assert primary.columns == [
        "water_year", "index_days", "index_deficit", "index_ssi",
        "n_stations", "coverage_area_km2",
    ]
    # primary: C (nested) raus -> A, B bleiben. a_incremental: A=100, B=50.
    row2000 = primary.filter(pl.col("water_year") == 2000)
    assert row2000["n_stations"][0] == 2
    assert row2000["coverage_area_km2"][0] == 150.0
    expected_index_days = (10 * 100 + 20 * 50) / 150
    assert row2000["index_days"][0] == expected_index_days

    natural = pl.read_parquet(agg_dir / "national_index_natural.parquet")
    # natural: C raus (nested), B raus (nicht naturnah) -> nur A bleibt.
    row2000n = natural.filter(pl.col("water_year") == 2000)
    assert row2000n["n_stations"][0] == 1
    assert row2000n["coverage_area_km2"][0] == 100.0
    assert row2000n["index_days"][0] == 10.0

    allsinks = pl.read_parquet(agg_dir / "national_index_allsinks.parquet")
    # allsinks: A, B, C alle drin.
    row2000a = allsinks.filter(pl.col("water_year") == 2000)
    assert row2000a["n_stations"][0] == 3
    assert row2000a["coverage_area_km2"][0] == 200.0

    allsinks_natural = pl.read_parquet(agg_dir / "national_index_allsinks_natural.parquet")
    # allsinks_natural: B raus (nicht naturnah), A + C bleiben.
    row2000an = allsinks_natural.filter(pl.col("water_year") == 2000)
    assert row2000an["n_stations"][0] == 2
    assert row2000an["coverage_area_km2"][0] == 150.0

    # DuckDB-Load (nur primary, kein out-suffix)
    con = connect(db)
    db_rows = con.execute(
        "SELECT water_year, n_stations, coverage_area_km2 FROM national_index ORDER BY water_year"
    ).fetchall()
    con.close()
    assert db_rows == [(2000, 2, 150.0), (2001, 2, 150.0)]

    # CSV-Export
    csv_path = tmp_path / "out" / "national_index.csv"
    assert csv_path.exists()
    csv_df = pl.read_csv(csv_path)
    assert csv_df.height == 2
    assert csv_df.columns == [
        "water_year", "index_days", "index_deficit", "index_ssi",
        "n_stations", "coverage_area_km2",
    ]


def test_aggregate_stage_out_suffix_skips_db(tmp_path: Path):
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    sinks_path = tmp_path / "sink_categories.csv"
    _seed(db, interim, sinks_path)

    cwd = Path.cwd()
    import os
    os.chdir(tmp_path)
    try:
        rc = run(argparse.Namespace(
            db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
            sinks=str(sinks_path), metrics_suffix="", screen_suffix="", out_suffix="sens1",
        ))
    finally:
        os.chdir(cwd)
    assert rc == 0
    assert (interim / "aggregate-sens1" / "national_index_primary.parquet").exists()
    con = connect(db)
    assert con.execute("SELECT COUNT(*) FROM national_index").fetchone()[0] == 0
    con.close()
    assert not (tmp_path / "out" / "national_index.csv").exists()


def test_aggregate_stage_screen_suffix_reads_suffix_dir(tmp_path: Path):
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    sinks_path = tmp_path / "sink_categories.csv"
    _seed(db, interim, sinks_path)

    # Sonde: im Suffix-Screening ist is_near_natural genau umgekehrt zum
    # Default-Screening (A=False, B=True, C=True).
    probe = pl.DataFrame({
        "station_id": ["A", "B", "C"],
        "n_usable_years": [2, 2, 2],
        "flags": [["reservoir"], [], []],
        "is_near_natural": [False, True, True],
    })
    (interim / "screen-s1").mkdir(parents=True)
    probe.write_parquet(interim / "screen-s1" / "usable_stations.parquet")

    rc = run(argparse.Namespace(
        db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
        sinks=str(sinks_path), metrics_suffix="", screen_suffix="s1", out_suffix="s1",
    ))
    assert rc == 0

    natural = pl.read_parquet(interim / "aggregate-s1" / "national_index_natural.parquet")
    row2000 = natural.filter(pl.col("water_year") == 2000)
    # Mit dem Suffix-Screening bleibt in 'natural' nur B (a_incremental=50),
    # mit dem Default-Screening waere es A (a_incremental=100).
    assert row2000["n_stations"][0] == 1
    assert row2000["coverage_area_km2"][0] == 50.0
    assert row2000["index_days"][0] == 20.0
