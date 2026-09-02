from pathlib import Path

import polars as pl

from niedrigwasser.store import StageLog, connect, write_stage_parquet

EXPECTED_TABLES = {
    "stations",
    "discharge_daily",
    "station_thresholds",
    "station_year_metrics",
    "national_index",
}


def test_connect_creates_schema(tmp_path: Path):
    con = connect(tmp_path / "test.duckdb")
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    assert EXPECTED_TABLES <= tables
    columns = {r[0] for r in con.execute("DESCRIBE stations").fetchall()}
    assert {"river_km", "gkz", "license"} <= columns
    # Idempotenz: zweites connect auf dieselbe Datei darf nicht crashen
    con.close()
    con2 = connect(tmp_path / "test.duckdb")
    con2.close()


def test_discharge_daily_primary_key(tmp_path: Path):
    con = connect(tmp_path / "test.duckdb")
    con.execute("INSERT INTO discharge_daily VALUES ('X1', DATE '2020-01-01', 12.5, NULL)")
    import duckdb
    try:
        con.execute("INSERT INTO discharge_daily VALUES ('X1', DATE '2020-01-01', 99.0, NULL)")
        assert False, "PK-Verletzung wurde nicht erkannt"
    except duckdb.ConstraintException:
        pass


def test_write_stage_parquet_roundtrip_and_overwrite(tmp_path: Path):
    df = pl.DataFrame({"a": [1, 2, 3]})
    p = write_stage_parquet(df, tmp_path, "screen", "usable_years")
    assert p == tmp_path / "screen" / "usable_years.parquet"
    assert pl.read_parquet(p)["a"].to_list() == [1, 2, 3]
    # Überschreiben (Idempotenz)
    p2 = write_stage_parquet(pl.DataFrame({"a": [9]}), tmp_path, "screen", "usable_years")
    assert pl.read_parquet(p2)["a"].to_list() == [9]


def test_stage_log_writes_counts(tmp_path: Path):
    log = StageLog(stage="screen", log_dir=tmp_path)
    log.counts("completeness_filter", rows_in=100, rows_out=80)
    log.close()
    content = (tmp_path / "screen.log").read_text(encoding="utf-8")
    assert "completeness_filter" in content
    assert "100" in content and "80" in content and "20" in content
