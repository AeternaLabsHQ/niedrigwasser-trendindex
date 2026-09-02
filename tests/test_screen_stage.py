import argparse
from datetime import date, timedelta
from pathlib import Path

import polars as pl
import pytest

from niedrigwasser.stages.screen import run
from niedrigwasser.store import connect


def _seed_db(db_path: Path) -> None:
    con = connect(db_path)
    # Station A: 26 volle Jahre -> bleibt; Station B: 2 Jahre -> fliegt
    rows = []
    for wy in range(1992, 2018):
        start = date(wy - 1, 11, 1)
        n = (date(wy, 10, 31) - start).days + 1
        rows += [("A", start + timedelta(days=i), 10.0, None) for i in range(n)]
    for wy in (2000, 2001):
        start = date(wy - 1, 11, 1)
        n = (date(wy, 10, 31) - start).days + 1
        rows += [("B", start + timedelta(days=i), 5.0, None) for i in range(n)]
    df = pl.DataFrame(
        {"station_id": [r[0] for r in rows], "date": [r[1] for r in rows],
         "q": [r[2] for r in rows], "quality_flag": [r[3] for r in rows]},
    ).with_columns(pl.col("date").cast(pl.Date))
    con.execute("INSERT INTO discharge_daily SELECT * FROM df")
    con.execute("""
        INSERT INTO stations VALUES
        ('A','Alpha','Inn',48.0,12.2,11960,NULL,420.4,'LfU BY',158.6,'18','cc-by/4.0'),
        ('B','Beta','Isar',48.1,11.5,300,NULL,500.0,'LfU BY',10.0,'16','cc-by/4.0')
    """)
    con.close()


def test_screen_stage_end_to_end(tmp_path: Path):
    db = tmp_path / "test.duckdb"
    _seed_db(db)
    flags_csv = tmp_path / "flags.csv"
    flags_csv.write_text("station_id,flag,note\nA,erosion,Hinweis\n", encoding="utf-8")

    rc = run(argparse.Namespace(
        db=str(db), interim_dir=str(tmp_path / "interim"),
        log_dir=str(tmp_path / "logs"), flags=str(flags_csv),
        out_suffix="", exclude_flags=None,
    ))
    assert rc == 0

    usable = pl.read_parquet(tmp_path / "interim" / "screen" / "usable_stations.parquet")
    assert usable["station_id"].to_list() == ["A"]
    assert usable["is_near_natural"].to_list() == [True]  # erosion schliesst nicht aus
    comp = pl.read_parquet(tmp_path / "interim" / "screen" / "completeness.parquet")
    assert set(comp["station_id"].to_list()) == {"A", "B"}
    log_text = (tmp_path / "logs" / "screen.log").read_text(encoding="utf-8")
    assert "usable_stations" in log_text


def test_screen_stage_out_suffix_isolates_outputs(tmp_path: Path):
    db = tmp_path / "test.duckdb"
    _seed_db(db)
    flags_csv = tmp_path / "flags.csv"
    flags_csv.write_text("station_id,flag,note\nA,erosion,Hinweis\n", encoding="utf-8")
    interim = tmp_path / "interim"

    rc = run(argparse.Namespace(
        db=str(db), interim_dir=str(interim),
        log_dir=str(tmp_path / "logs"), flags=str(flags_csv),
        out_suffix="s1", exclude_flags="reservoir,transfer,mining,erosion",
    ))
    assert rc == 0

    # Outputs liegen im Suffix-Ordner, der Default-Ordner bleibt unberuehrt.
    assert (interim / "screen-s1" / "usable_stations.parquet").exists()
    assert (interim / "screen-s1" / "completeness.parquet").exists()
    assert (interim / "screen-s1" / "usable_station_years.parquet").exists()
    assert not (interim / "screen").exists()

    usable = pl.read_parquet(interim / "screen-s1" / "usable_stations.parquet")
    assert usable["station_id"].to_list() == ["A"]
    # strengere Ausschlussmenge: 'erosion' schliesst A jetzt aus
    assert usable["is_near_natural"].to_list() == [False]

    # eigener StageLog-Name
    assert (tmp_path / "logs" / "screen-s1.log").exists()


def test_screen_stage_unknown_exclude_flag_fails(tmp_path: Path):
    db = tmp_path / "test.duckdb"
    _seed_db(db)
    flags_csv = tmp_path / "flags.csv"
    flags_csv.write_text("station_id,flag,note\nA,erosion,Hinweis\n", encoding="utf-8")

    with pytest.raises(ValueError):
        run(argparse.Namespace(
            db=str(db), interim_dir=str(tmp_path / "interim"),
            log_dir=str(tmp_path / "logs"), flags=str(flags_csv),
            out_suffix="", exclude_flags="reservoir,volcano",
        ))
