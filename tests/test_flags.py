from pathlib import Path

import polars as pl
import pytest

from niedrigwasser.flags import apply_flags, load_station_flags


def _write_csv(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "flags.csv"
    p.write_text(content, encoding="utf-8")
    return p


def test_load_valid_flags(tmp_path):
    p = _write_csv(tmp_path, "station_id,flag,note\nS1,reservoir,Talsperre Oberlauf\nS2,mining,Spree Flutung\n")
    df = load_station_flags(p)
    assert df.height == 2
    assert set(df.columns) == {"station_id", "flag", "note"}


def test_load_unknown_flag_raises(tmp_path):
    p = _write_csv(tmp_path, "station_id,flag,note\nS1,volcano,quatsch\n")
    with pytest.raises(ValueError):
        load_station_flags(p)


def test_apply_flags_near_natural(tmp_path):
    p = _write_csv(
        tmp_path,
        "station_id,flag,note\nS1,reservoir,x\nS1,erosion,y\nS2,erosion,z\n",
    )
    stations = pl.DataFrame({"station_id": ["S1", "S2", "S3"]})
    out = apply_flags(stations, load_station_flags(p)).sort("station_id")
    assert out["is_near_natural"].to_list() == [False, True, True]
    assert out.filter(pl.col("station_id") == "S1")["flags"][0].to_list() == ["reservoir", "erosion"]


def test_apply_flags_custom_excluding(tmp_path):
    p = _write_csv(
        tmp_path,
        "station_id,flag,note\nS1,reservoir,x\nS1,erosion,y\nS2,erosion,z\n",
    )
    flags = load_station_flags(p)
    stations = pl.DataFrame({"station_id": ["S1", "S2", "S3"]})

    # Default-Aufruf bleibt unveraendert: 'erosion' schliesst nicht aus.
    default_out = apply_flags(stations, flags).sort("station_id")
    assert default_out["is_near_natural"].to_list() == [False, True, True]

    # Strengere Ausschlussmenge: S2 (nur 'erosion') ist jetzt nicht mehr naturnah.
    strict_out = apply_flags(
        stations, flags, excluding={"reservoir", "transfer", "mining", "erosion"}
    ).sort("station_id")
    assert strict_out["is_near_natural"].to_list() == [False, False, True]
    # Spaltenschema identisch zum Default-Aufruf.
    assert strict_out.columns == default_out.columns


def test_apply_flags_unknown_excluding_raises(tmp_path):
    p = _write_csv(tmp_path, "station_id,flag,note\nS1,reservoir,x\n")
    stations = pl.DataFrame({"station_id": ["S1"]})
    with pytest.raises(ValueError):
        apply_flags(stations, load_station_flags(p), excluding={"reservoir", "volcano"})
