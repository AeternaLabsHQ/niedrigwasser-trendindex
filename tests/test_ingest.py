import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import httpx
import polars as pl
import pytest

from niedrigwasser.niwis import IngestError, NiwisClient
from niedrigwasser.stages.ingest import download_raw, normalize_discharge, normalize_stations, run

MESSSTELLEN = [
    {"messstelleNr": "S1", "name": "Alpha", "landcode": "DEBY",
     "lizenz": "cc-by/4.0", "messgroesse": ["Abfluss", "Wasserstand"]},
    {"messstelleNr": "S2", "name": "Beta", "landcode": "DEBW",
     "lizenz": "dl-zero-de/2.0", "messgroesse": ["Wasserstand"]},  # kein Abfluss
]
STAMM_S1 = {
    "messstelleNr": "S1", "name": "Alpha", "institution": "LfU BY",
    "lizenz": "cc-by/4.0", "laenge": 12.23, "breite": 48.06,
    "gewaesser": "Inn", "gkz": 18, "lageGewaesser": "158.665",
    "ezgGroesse": 11960, "hoehePnp": 420.41,
}
ABFLUSS_S1 = [
    {"messstelleNr": "S1", "datum": "1992-01-02", "messwert": 10.0, "einheit": "m³/s", "flag": None},
    {"messstelleNr": "S1", "datum": "1992-01-01", "messwert": 12.5, "einheit": "m³/s", "flag": "p"},
    {"messstelleNr": "S1", "datum": "1992-01-01", "messwert": 99.0, "einheit": "m³/s", "flag": None},
]


def test_normalize_stations_keeps_only_q_and_maps_fields():
    df = normalize_stations(MESSSTELLEN, {"S1": STAMM_S1})
    assert df["station_id"].to_list() == ["S1"]
    row = df.row(0, named=True)
    assert row["river"] == "Inn"
    assert row["catchment_area"] == 11960.0
    assert row["river_km"] == 158.665
    assert row["gkz"] == "18"
    assert row["license"] == "cc-by/4.0"
    assert row["source"] == "LfU BY"
    assert row["downstream_id"] is None


def test_normalize_stations_defensive_river_km():
    stamm = dict(STAMM_S1, lageGewaesser="ca. 158,7?")
    df = normalize_stations(MESSSTELLEN, {"S1": stamm})
    assert df.row(0, named=True)["river_km"] is None


def test_normalize_discharge_sorts_dedupes_parses():
    df = normalize_discharge(ABFLUSS_S1)
    assert df["date"].to_list() == [date(1992, 1, 1), date(1992, 1, 2)]
    # Duplikat 1992-01-01: erster Wert der Eingabe gewinnt (12.5)
    assert df.filter(pl.col("date") == date(1992, 1, 1))["q"][0] == 12.5
    assert df["quality_flag"].to_list() == ["p", None]


def test_normalize_discharge_rejects_wrong_unit():
    rows = [dict(ABFLUSS_S1[0], einheit="cm")]
    with pytest.raises(IngestError):
        normalize_discharge(rows)


def test_normalize_discharge_filters_negative_sentinel_values():
    rows = [
        {"messstelleNr": "S1", "datum": "1992-01-03", "messwert": -777.0,
         "einheit": "m³/s", "flag": "BfGAdded"},
        {"messstelleNr": "S1", "datum": "1992-01-04", "messwert": -0.001,
         "einheit": "m³/s", "flag": None},
        {"messstelleNr": "S1", "datum": "1992-01-05", "messwert": 5.0,
         "einheit": "m³/s", "flag": "p"},
    ]
    df = normalize_discharge(rows)
    sentinel_day = df.filter(pl.col("date") == date(1992, 1, 3))
    assert sentinel_day["q"][0] is None
    assert sentinel_day["quality_flag"][0] == "sentinel"
    other_negative_day = df.filter(pl.col("date") == date(1992, 1, 4))
    assert other_negative_day["q"][0] is None
    assert other_negative_day["quality_flag"][0] == "sentinel"
    ok_day = df.filter(pl.col("date") == date(1992, 1, 5))
    assert ok_day["q"][0] == 5.0
    assert ok_day["quality_flag"][0] == "p"


def _mock_client() -> NiwisClient:
    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p.endswith("/messstelle"):
            return httpx.Response(200, json=MESSSTELLEN)
        if p.endswith("/stammdaten"):
            return httpx.Response(200, json=STAMM_S1)
        if p.endswith("/abfluss"):
            return httpx.Response(200, json=ABFLUSS_S1)
        return httpx.Response(404)

    return NiwisClient(transport=httpx.MockTransport(handler), delay_s=0)


def test_download_raw_writes_files_and_is_idempotent(tmp_path: Path):
    download_raw(_mock_client(), tmp_path)
    assert (tmp_path / "messstellen.json").exists()
    assert (tmp_path / "stammdaten" / "S1.json").exists()
    abfluss_files = sorted((tmp_path / "abfluss").glob("S1_*.json"))
    assert len(abfluss_files) == 2  # zwei Zeitfenster
    # kein Stammdaten/Abfluss-File fuer die W-only-Station
    assert not (tmp_path / "stammdaten" / "S2.json").exists()

    # Idempotenz: zweiter Lauf laesst mtime unveraendert (Dateien werden uebersprungen)
    before = (tmp_path / "messstellen.json").stat().st_mtime_ns
    download_raw(_mock_client(), tmp_path)
    assert (tmp_path / "messstellen.json").stat().st_mtime_ns == before


def test_download_raw_skips_legacy_named_open_window_file(tmp_path: Path):
    # Regression: das offene Zeitfenster (bis=None) endete frueher im Dateinamen
    # auf "heute" -- an einem neuen Kalendertag wurde die Datei "von gestern" nicht
    # gefunden und komplett neu heruntergeladen. Simuliert hier eine Alt-Datei mit
    # dem frueheren, datumsbehafteten Namensschema (Enddatum = "gestern") und prueft,
    # dass kein Abfluss-Request mehr ausgeloest wird.
    abfluss_calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p.endswith("/messstelle"):
            return httpx.Response(200, json=MESSSTELLEN)
        if p.endswith("/stammdaten"):
            return httpx.Response(200, json=STAMM_S1)
        if p.endswith("/abfluss"):
            abfluss_calls.append(request.url)
            return httpx.Response(200, json=ABFLUSS_S1)
        return httpx.Response(404)

    c = NiwisClient(transport=httpx.MockTransport(handler), delay_s=0)

    (tmp_path / "abfluss").mkdir(parents=True)
    (tmp_path / "stammdaten").mkdir(parents=True)
    (tmp_path / "messstellen.json").write_text(json.dumps(MESSSTELLEN), encoding="utf-8")
    (tmp_path / "stammdaten" / "S1.json").write_text(json.dumps(STAMM_S1), encoding="utf-8")
    # geschlossenes Fenster bereits vorhanden
    (tmp_path / "abfluss" / "S1_1950-01-01_1989-12-31.json").write_text(
        json.dumps(ABFLUSS_S1), encoding="utf-8"
    )
    # offenes Fenster: Alt-Datei mit "gestrigem" Enddatum statt stabilem Namen
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    (tmp_path / "abfluss" / f"S1_1990-01-01_{yesterday}.json").write_text(
        json.dumps(ABFLUSS_S1), encoding="utf-8"
    )

    download_raw(c, tmp_path)

    assert abfluss_calls == []


def test_download_raw_fails_on_cap(tmp_path: Path):
    big = [dict(ABFLUSS_S1[0], datum=f"1992-01-01")] * 15000

    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p.endswith("/messstelle"):
            return httpx.Response(200, json=MESSSTELLEN)
        if p.endswith("/stammdaten"):
            return httpx.Response(200, json=STAMM_S1)
        return httpx.Response(200, json=big)

    c = NiwisClient(transport=httpx.MockTransport(handler), delay_s=0)
    with pytest.raises(IngestError):
        download_raw(c, tmp_path)


def test_run_with_limit_skips_topology(tmp_path: Path, monkeypatch):
    # F5-Regression: --limit muss durchlaufen, ohne dass apply_overrides an den
    # (auf den vollen 361er-Datensatz abgestimmten) Overrides scheitert.
    monkeypatch.setattr("niedrigwasser.stages.ingest.NiwisClient", lambda *a, **k: _mock_client())
    args = argparse.Namespace(
        raw_dir=str(tmp_path / "raw"), interim_dir=str(tmp_path / "interim"),
        db=str(tmp_path / "test.duckdb"), log_dir=str(tmp_path / "logs"),
        refresh=False, limit=1, topology_overrides="config/topology_overrides.csv",
    )
    rc = run(args)
    assert rc == 0
    log_text = (tmp_path / "logs" / "ingest.log").read_text(encoding="utf-8")
    assert "Smoke-Modus" in log_text


def test_run_with_limit_does_not_wipe_existing_db(tmp_path: Path, monkeypatch):
    # F1-Regression: --limit darf die (ggf. volle Produktions-)DB nicht mit der
    # Teilmenge ueberschreiben. DuckDB-Load muss im Smoke-Modus komplett entfallen.
    from niedrigwasser.store import connect

    monkeypatch.setattr("niedrigwasser.stages.ingest.NiwisClient", lambda *a, **k: _mock_client())
    db_path = tmp_path / "test.duckdb"

    con = connect(db_path)
    con.execute(
        "INSERT INTO stations (station_id, name) VALUES ('X1', 'Seed'), ('X2', 'Seed2')"
    )
    con.execute(
        "INSERT INTO discharge_daily (station_id, date, q) VALUES "
        "('X1', '2000-01-01', 1.0), ('X1', '2000-01-02', 2.0)"
    )
    con.close()

    args = argparse.Namespace(
        raw_dir=str(tmp_path / "raw"), interim_dir=str(tmp_path / "interim"),
        db=str(db_path), log_dir=str(tmp_path / "logs"),
        refresh=False, limit=1, topology_overrides="config/topology_overrides.csv",
    )
    rc = run(args)
    assert rc == 0

    con = connect(db_path)
    assert con.execute("SELECT count(*) FROM stations").fetchone()[0] == 2
    assert con.execute("SELECT count(*) FROM discharge_daily").fetchone()[0] == 2
    con.close()


@pytest.mark.live
def test_live_smoke_two_stations(tmp_path: Path):
    c = NiwisClient()
    download_raw(c, tmp_path, limit=2)
    mess = json.loads((tmp_path / "messstellen.json").read_text(encoding="utf-8"))
    assert len(mess) > 600
    files = list((tmp_path / "abfluss").glob("*.json"))
    assert len(files) == 4
