from __future__ import annotations

import datetime
from pathlib import Path

import duckdb
import polars as pl

_SCHEMA = """
CREATE TABLE IF NOT EXISTS stations (
    station_id      TEXT PRIMARY KEY,
    name            TEXT,
    river           TEXT,
    lat             DOUBLE,
    lon             DOUBLE,
    catchment_area  DOUBLE,
    downstream_id   TEXT,
    gauge_datum     DOUBLE,
    source          TEXT,
    river_km        DOUBLE,
    gkz             TEXT,
    license         TEXT
);
CREATE TABLE IF NOT EXISTS discharge_daily (
    station_id   TEXT,
    date         DATE,
    q            DOUBLE,
    quality_flag TEXT,
    PRIMARY KEY (station_id, date)
);
CREATE TABLE IF NOT EXISTS station_thresholds (
    station_id       TEXT PRIMARY KEY,
    q95              DOUBLE,
    mnq              DOUBLE,
    ref_period_start INTEGER,
    ref_period_end   INTEGER
);
CREATE TABLE IF NOT EXISTS station_year_metrics (
    station_id        TEXT,
    water_year        INTEGER,
    days_below        INTEGER,
    max_spell         INTEGER,
    deficit_volume_m3 DOUBLE,
    nm7q              DOUBLE,
    ssi               DOUBLE,
    data_completeness DOUBLE,
    PRIMARY KEY (station_id, water_year)
);
CREATE TABLE IF NOT EXISTS national_index (
    water_year        INTEGER PRIMARY KEY,
    index_days        DOUBLE,
    index_deficit     DOUBLE,
    index_ssi         DOUBLE,
    n_stations        INTEGER,
    coverage_area_km2 DOUBLE
);
"""


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(_SCHEMA)


def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    init_schema(con)
    return con


def write_stage_parquet(df: pl.DataFrame, interim_dir: Path, stage: str, name: str) -> Path:
    out_dir = interim_dir / stage
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.parquet"
    df.write_parquet(path)
    return path


class StageLog:
    def __init__(self, stage: str, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        self._stage = stage
        self._fh = (log_dir / f"{stage}.log").open("a", encoding="utf-8")
        self.info(f"=== Stage '{stage}' gestartet ===")

    def _write(self, line: str) -> None:
        stamp = datetime.datetime.now().isoformat(timespec="seconds")
        msg = f"{stamp} [{self._stage}] {line}"
        print(msg)
        self._fh.write(msg + "\n")
        self._fh.flush()

    def info(self, msg: str) -> None:
        self._write(msg)

    def counts(self, label: str, rows_in: int, rows_out: int) -> None:
        self._write(f"{label}: rein={rows_in} raus={rows_out} verworfen={rows_in - rows_out}")

    def close(self) -> None:
        self._write("=== Stage beendet ===")
        self._fh.close()
