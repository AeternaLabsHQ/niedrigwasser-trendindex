import argparse
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from niedrigwasser.stages.metrics import run
from niedrigwasser.store import connect


def _seed(db: Path, interim: Path) -> None:
    con = connect(db)
    rows = []
    # Station A: WY 1992-2020 voll, konstant 20 ausser 10 Tage Sommer-Tief (5.0) ab WY 2015
    for wy in range(1992, 2021):
        start = date(wy - 1, 11, 1)
        n = (date(wy, 10, 31) - start).days + 1
        for i in range(n):
            d = start + timedelta(days=i)
            q = 5.0 if (wy >= 2015 and d.month == 8 and d.day <= 10) else 20.0
            rows.append(("A", d, q, None))
    # Station B: nur 5 verwertbare Jahre (< 25-Jahre-Kriterium) -- muss aus dem
    # Stage-Output herausfallen, obwohl sie in usable_station_years steht.
    for wy in range(1992, 1997):
        start = date(wy - 1, 11, 1)
        n = (date(wy, 10, 31) - start).days + 1
        for i in range(n):
            d = start + timedelta(days=i)
            rows.append(("B", d, 20.0, None))
    df = pl.DataFrame({"station_id": [r[0] for r in rows], "date": [r[1] for r in rows],
                       "q": [r[2] for r in rows], "quality_flag": [r[3] for r in rows]}
                      ).with_columns(pl.col("date").cast(pl.Date))
    con.execute("INSERT INTO discharge_daily SELECT * FROM df")
    con.close()
    usable = pl.DataFrame({
        "station_id": ["A"] * 29 + ["B"] * 5,
        "water_year": list(range(1992, 2021)) + list(range(1992, 1997)),
        "summer_days_present": [184] * 34, "total_days_present": [365] * 34,
        "summer_coverage": [1.0] * 34, "data_completeness": [1.0] * 34,
    })
    (interim / "screen").mkdir(parents=True)
    usable.write_parquet(interim / "screen" / "usable_station_years.parquet")
    # Nur Station A erfuellt das 25-Jahre-Stationskriterium.
    usable_stations = pl.DataFrame({"station_id": ["A"], "n_usable_years": [29]})
    usable_stations.write_parquet(interim / "screen" / "usable_stations.parquet")


def test_metrics_stage_end_to_end(tmp_path: Path):
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    _seed(db, interim)
    rc = run(argparse.Namespace(
        db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
        ref_start=1992, ref_end=2011, inter_event=5, out_suffix="",
    ))
    assert rc == 0

    m = pl.read_parquet(interim / "metrics" / "station_year_metrics.parquet")
    assert m.columns == ["station_id", "water_year", "days_below", "max_spell",
                         "deficit_volume_m3", "nm7q", "ssi", "data_completeness"]
    assert m.height == 29
    # Station B hat nur 5 verwertbare Jahre (< 25) und muss trotz Eintrag in
    # usable_station_years komplett aus dem Output herausfallen.
    assert m.filter(pl.col("station_id") == "B").height == 0
    assert m["station_id"].unique().to_list() == ["A"]
    # Referenzjahre ohne Tief: days_below == 0; ab 2015: 10 Tage unter Q95
    assert m.filter(pl.col("water_year") == 2000)["days_below"][0] == 0
    assert m.filter(pl.col("water_year") == 2018)["days_below"][0] == 10
    assert m.filter(pl.col("water_year") == 2018)["max_spell"][0] == 10
    # DuckDB-Load erfolgt
    con = connect(db)
    assert con.execute("SELECT COUNT(*) FROM station_year_metrics").fetchone()[0] == 29
    # Thresholds werden pro Station mit Daten berechnet (nicht auf usable_stations
    # gefiltert) -- Station B taucht hier weiterhin auf.
    assert con.execute("SELECT COUNT(*) FROM station_thresholds").fetchone()[0] == 2
    con.close()


def test_metrics_stage_suffix_skips_db(tmp_path: Path):
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    _seed(db, interim)
    rc = run(argparse.Namespace(
        db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
        ref_start=1991, ref_end=2020, inter_event=3, out_suffix="ref1991-2020",
    ))
    assert rc == 0
    assert (interim / "metrics-ref1991-2020" / "station_year_metrics.parquet").exists()
    con = connect(db)
    assert con.execute("SELECT COUNT(*) FROM station_year_metrics").fetchone()[0] == 0
    con.close()
