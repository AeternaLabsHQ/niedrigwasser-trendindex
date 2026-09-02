import argparse
from pathlib import Path

import polars as pl

from niedrigwasser.stages.trend import run
from niedrigwasser.store import connect


def _seed(
    db: Path, interim: Path,
    null_ssi_year: int | None = None,
    nan_deficit_year: int | None = None,
    sparse_nm7q_station: bool = False,
) -> None:
    """Seed-Daten fuer die trend-Stage.

    ``null_ssi_year`` / ``nan_deficit_year`` setzen in
    ``national_index_primary.parquet`` (nur dort) den Wert des jeweiligen
    Wasserjahres auf null bzw. NaN — fuer die Luecken-Guards in
    ``_national_trends`` / ``_gev_deficit``.

    ``sparse_nm7q_station`` haengt eine zweite Station "C" an, die genug
    Jahre fuer den Stations-Filter hat, deren nm7q-Reihe aber bis auf 5
    Werte leer ist — dort liefert mk_trend "insufficient" mit p_value=None
    (Testfall fuer die BH-Adjustierung mit Luecken).
    """
    con = connect(db)
    station_ids = ["A", "C"] if sparse_nm7q_station else ["A"]
    n_st = len(station_ids)
    stations_df = pl.DataFrame({
        "station_id": station_ids,
        "name": station_ids, "river": ["r"] * n_st, "lat": [1.0] * n_st, "lon": [1.0] * n_st,
        "catchment_area": [100.0] * n_st, "downstream_id": [None] * n_st,
        "gauge_datum": [None] * n_st, "source": ["x"] * n_st, "river_km": [None] * n_st,
        "gkz": [None] * n_st, "license": [None] * n_st,
    })
    con.execute("INSERT INTO stations SELECT * FROM stations_df")
    con.close()

    years = list(range(1992, 2026))  # 34 Jahre, Fenster 1992-2025 -> >=25
    n = len(years)
    noise = [0.3, -0.2, 0.1, -0.4, 0.2] * ((n // 5) + 1)
    days_below = [max(0.0, 5 + i + noise[i]) for i in range(n)]  # steigender Trend
    deficit_vol = [d * 1000.0 for d in days_below]
    nm7q = [max(0.5, 10.0 - 0.2 * i + noise[i]) for i in range(n)]  # fallender Trend

    metrics = pl.DataFrame({
        "station_id": ["A"] * n,
        "water_year": years,
        "days_below": days_below,
        "max_spell": [d for d in days_below],
        "deficit_volume_m3": deficit_vol,
        "nm7q": nm7q,
        "ssi": [0.0] * n,
        "data_completeness": [1.0] * n,
    })
    if sparse_nm7q_station:
        metrics = pl.concat([metrics, pl.DataFrame({
            "station_id": ["C"] * n,
            "water_year": years,
            "days_below": days_below,
            "max_spell": [d for d in days_below],
            "deficit_volume_m3": deficit_vol,
            # nur die ersten 5 Jahre besetzt -> n < MIN_MK_N -> p_value None
            "nm7q": [nm7q[i] if i < 5 else None for i in range(n)],
            "ssi": [0.0] * n,
            "data_completeness": [1.0] * n,
        })])
    (interim / "metrics").mkdir(parents=True)
    metrics.write_parquet(interim / "metrics" / "station_year_metrics.parquet")

    agg_dir = interim / "aggregate"
    agg_dir.mkdir(parents=True)
    for variant in ["primary", "natural", "allsinks", "allsinks_natural"]:
        idx = pl.DataFrame({
            "water_year": years,
            "index_days": [float(d) for d in days_below],
            "index_deficit": [float(d) * 0.1 + (i * 0.05) for i, d in enumerate(days_below)],
            "index_ssi": [0.0] * n,
            "n_stations": [1] * n,
            "coverage_area_km2": [100.0] * n,
        })
        # WY 1991 (ausserhalb des Trend-Fensters 1992-2025) mit krassem
        # Ausreisser vorne anhaengen - reproduziert F1 (Fenster-Leck):
        # ohne WINDOW-Filter in _national_trends/_gev_deficit wuerde dieser
        # Wert den Trend/Fit verzerren.
        outlier = pl.DataFrame({
            "water_year": [1991],
            "index_days": [999.0],
            "index_deficit": [999.0],
            "index_ssi": [999.0],
            "n_stations": [1],
            "coverage_area_km2": [100.0],
        })
        idx = pl.concat([outlier, idx])
        if variant == "primary":
            if null_ssi_year is not None:
                idx = idx.with_columns(
                    pl.when(pl.col("water_year") == null_ssi_year)
                    .then(pl.lit(None, dtype=pl.Float64))
                    .otherwise(pl.col("index_ssi")).alias("index_ssi")
                )
            if nan_deficit_year is not None:
                idx = idx.with_columns(
                    pl.when(pl.col("water_year") == nan_deficit_year)
                    .then(pl.lit(float("nan"), dtype=pl.Float64))
                    .otherwise(pl.col("index_deficit")).alias("index_deficit")
                )
        idx.write_parquet(agg_dir / f"national_index_{variant}.parquet")

    # zusaetzlicher Sensitivitaets-Aggregat-Ordner (identische Daten) fuer
    # den agg-suffix-Isolations-Test.
    agg_dir_sens = interim / "aggregate-sens1"
    agg_dir_sens.mkdir(parents=True)
    for f in agg_dir.glob("*.parquet"):
        pl.read_parquet(f).write_parquet(agg_dir_sens / f.name)


def test_trend_stage_end_to_end(tmp_path: Path):
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    out_dir = tmp_path / "out"
    _seed(db, interim)

    rc = run(argparse.Namespace(
        db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
        agg_suffix="", metrics_suffix="", out_dir=str(out_dir),
    ))
    assert rc == 0

    station_csv = out_dir / "station_trends.csv"
    assert station_csv.exists()
    st = pl.read_csv(station_csv)
    assert st.height == 1
    row = st.row(0, named=True)
    assert row["station_id"] == "A"
    assert row["n_years"] == 34
    assert row["days_below_trend"] == "increasing"
    assert row["nm7q_trend"] == "decreasing"
    assert row["min_year"] == 2025
    # BH-FDR-Zusatzspalten: adjustierte p-Werte nie kleiner als die Roh-p-Werte
    assert "days_below_p_fdr" in st.columns
    assert "nm7q_p_fdr" in st.columns
    assert row["days_below_p_fdr"] >= row["days_below_p"]
    assert row["nm7q_p_fdr"] >= row["nm7q_p"]

    national = pl.read_parquet(interim / "trend" / "national_trends.parquet")
    assert national.height == 4 * 3  # 4 Varianten x 3 Metriken
    row_days_primary = national.filter(
        (pl.col("variant") == "primary") & (pl.col("metric") == "index_days")
    ).row(0, named=True)
    assert row_days_primary["trend"] == "increasing"
    # F1: 1991-Ausreisser darf nicht in die Fit-Basis rutschen (n=34, nicht 35).
    assert row_days_primary["n"] == 34

    decades = pl.read_parquet(interim / "trend" / "decade_stats.parquet")
    assert set(decades["metric"].unique().to_list()) == {"days_below", "deficit_mm", "nm7q"}
    assert set(decades["decade"].unique().to_list()) == {
        "1992-2001", "2002-2013", "2014-2025",
    }

    gev = pl.read_parquet(interim / "trend" / "gev_deficit.parquet")
    assert gev.height == 1
    gev_row = gev.row(0, named=True)
    assert gev_row["target_year"] == 2018
    assert gev_row["value"] is not None
    assert gev_row["n_years"] == 34
    assert gev_row["value"] < 900  # nicht der 1991-Ausreisserwert
    assert "xi_free" in gev.columns
    assert "rp_empirical" in gev.columns
    assert gev_row["rp_empirical"] is not None


def test_trend_stage_bh_fdr_spalten(tmp_path: Path):
    """Die BH-Zusatzspalten stehen je Kennzahl getrennt in station_trends.csv:
    adjustierte p-Werte >= Roh-p, und None bleibt None, wo kein Test lief."""
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    out_dir = tmp_path / "out"
    _seed(db, interim, sparse_nm7q_station=True)

    rc = run(argparse.Namespace(
        db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
        agg_suffix="", metrics_suffix="", out_dir=str(out_dir),
    ))
    assert rc == 0

    st = pl.read_csv(out_dir / "station_trends.csv")
    assert st.height == 2
    assert "days_below_p_fdr" in st.columns
    assert "nm7q_p_fdr" in st.columns

    for row in st.iter_rows(named=True):
        for raw, adj in [("days_below_p", "days_below_p_fdr"), ("nm7q_p", "nm7q_p_fdr")]:
            if row[raw] is None:
                assert row[adj] is None
            else:
                assert row[adj] is not None
                assert row[adj] >= row[raw] - 1e-12

    # Station C hat zu wenige nm7q-Werte -> kein Test, also auch kein FDR-Wert.
    c_row = st.filter(pl.col("station_id") == "C").row(0, named=True)
    assert c_row["nm7q_trend"] == "insufficient"
    assert c_row["nm7q_p"] is None
    assert c_row["nm7q_p_fdr"] is None
    # days_below wurde bei C sehr wohl getestet - die Familien sind getrennt.
    assert c_row["days_below_p"] is not None
    assert c_row["days_below_p_fdr"] is not None


def test_trend_stage_agg_suffix_isolates_output(tmp_path: Path):
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    out_dir = tmp_path / "out"
    _seed(db, interim)

    # Sensitivitaetslauf liest interim/aggregate/ (Default-Variantenordner
    # existiert bereits aus _seed) und schreibt unter eigenem Suffix.
    rc = run(argparse.Namespace(
        db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
        agg_suffix="sens1", metrics_suffix="", out_dir=str(out_dir),
    ))
    assert rc == 0

    assert (interim / "trend-sens1" / "national_trends.parquet").exists()
    assert (interim / "trend-sens1" / "decade_stats.parquet").exists()
    assert (interim / "trend-sens1" / "gev_deficit.parquet").exists()
    assert not (interim / "trend" / "national_trends.parquet").exists()
    assert not (out_dir / "station_trends.csv").exists()


def test_trend_stage_metrics_suffix_reads_suffix_metrics(tmp_path: Path):
    """--metrics-suffix muss interim/metrics-<suffix>/ lesen, nicht das feste
    interim/metrics/ (Bugfix: decade_stats/station_trends wurden bei
    Sensitivitaetslaeufen bisher immer aus dem Hauptlauf-Ordner gespeist,
    unabhaengig von --agg-suffix)."""
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    out_dir = tmp_path / "out"
    _seed(db, interim)

    # Eigener metrics-<suffix>-Ordner mit klar unterscheidbaren Werten
    # (Station "B", konstant 42.0 statt Station "A"s steigender Reihe).
    years = list(range(1992, 2026))
    n = len(years)
    metrics_suffix_df = pl.DataFrame({
        "station_id": ["B"] * n,
        "water_year": years,
        "days_below": [42.0] * n,
        "max_spell": [42.0] * n,
        "deficit_volume_m3": [42000.0] * n,
        "nm7q": [42.0] * n,
        "ssi": [0.0] * n,
        "data_completeness": [1.0] * n,
    })
    metrics_suffix_dir = interim / "metrics-sens1"
    metrics_suffix_dir.mkdir(parents=True)
    metrics_suffix_df.write_parquet(metrics_suffix_dir / "station_year_metrics.parquet")

    # zweite Station "B" auch in der DB, sonst joint decade_stats mangels
    # catchment_area zu Nullwerten statt zu skippen.
    con = connect(db)
    stations_df = pl.DataFrame({
        "station_id": ["B"],
        "name": ["B"], "river": ["r"], "lat": [1.0], "lon": [1.0],
        "catchment_area": [100.0], "downstream_id": [None],
        "gauge_datum": [None], "source": ["x"], "river_km": [None],
        "gkz": [None], "license": [None],
    })
    con.execute("INSERT INTO stations SELECT * FROM stations_df")
    con.close()

    rc = run(argparse.Namespace(
        db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
        agg_suffix="sens1", metrics_suffix="sens1", out_dir=str(out_dir),
    ))
    assert rc == 0

    decades = pl.read_parquet(interim / "trend-sens1" / "decade_stats.parquet")
    days_below_decades = decades.filter(pl.col("metric") == "days_below")
    # Station "B" liefert konstant 42.0 - waere hier stattdessen Station "A"s
    # steigende Reihe (aus dem falschen interim/metrics/) zu sehen, waeren
    # mean/median nicht konstant 42.0 ueber alle Dekaden.
    assert all(v == 42.0 for v in days_below_decades["mean"].to_list())
    assert all(v == 42.0 for v in days_below_decades["median"].to_list())


def test_trend_stage_national_trend_ueberspringt_null_jahr(tmp_path: Path):
    """Ein null-Jahr im nationalen Index darf den Trend nicht sprengen: die
    Reihe wird auf den verbleibenden Jahren gerechnet (n um 1 kleiner), statt
    mit TypeError zu sterben oder NaN durchzureichen."""
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    _seed(db, interim, null_ssi_year=2000)

    rc = run(argparse.Namespace(
        db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
        agg_suffix="", metrics_suffix="", out_dir=str(tmp_path / "out"),
    ))
    assert rc == 0

    national = pl.read_parquet(interim / "trend" / "national_trends.parquet")
    primary_ssi = national.filter(
        (pl.col("variant") == "primary") & (pl.col("metric") == "index_ssi")
    ).row(0, named=True)
    assert primary_ssi["n"] == 33          # 34 Fensterjahre minus das null-Jahr
    assert primary_ssi["trend"] == "no trend"

    # Nur primary hat die Luecke - die anderen Varianten bleiben bei 34.
    natural_ssi = national.filter(
        (pl.col("variant") == "natural") & (pl.col("metric") == "index_ssi")
    ).row(0, named=True)
    assert natural_ssi["n"] == 34
    # Andere Metriken derselben Variante ebenfalls unberuehrt.
    primary_days = national.filter(
        (pl.col("variant") == "primary") & (pl.col("metric") == "index_days")
    ).row(0, named=True)
    assert primary_days["n"] == 34


def test_trend_stage_gev_ueberspringt_nan_zieljahr(tmp_path: Path):
    """NaN im index_deficit: aus der Fit-Basis fliegt der Wert raus, und ein
    NaN im GEV-Zieljahr 2018 fuehrt zu value=None statt zu NaN-Kennzahlen."""
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    _seed(db, interim, nan_deficit_year=2018)

    rc = run(argparse.Namespace(
        db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
        agg_suffix="", metrics_suffix="", out_dir=str(tmp_path / "out"),
    ))
    assert rc == 0

    gev_row = pl.read_parquet(interim / "trend" / "gev_deficit.parquet").row(0, named=True)
    assert gev_row["n_years"] == 33        # NaN-Jahr nicht in der Fit-Basis
    assert gev_row["value"] is None
    assert gev_row["rp_empirical"] is None
    assert gev_row["rp_start"] is None
    assert gev_row["rp_end"] is None

    national = pl.read_parquet(interim / "trend" / "national_trends.parquet")
    primary_deficit = national.filter(
        (pl.col("variant") == "primary") & (pl.col("metric") == "index_deficit")
    ).row(0, named=True)
    assert primary_deficit["n"] == 33
    assert primary_deficit["p_value"] == primary_deficit["p_value"]  # kein NaN
