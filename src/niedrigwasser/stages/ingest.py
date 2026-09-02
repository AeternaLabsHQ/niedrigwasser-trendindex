from __future__ import annotations

import argparse
import datetime
import json
import re
from pathlib import Path

import polars as pl

from niedrigwasser.build_topology import build_topology
from niedrigwasser.niwis import IngestError, NiwisClient
from niedrigwasser.store import StageLog, connect, write_stage_parquet

CAP = 15000
WINDOWS = [("1950-01-01", "1989-12-31"), ("1990-01-01", None)]  # None = heute

_STATION_SCHEMA = {
    "station_id": pl.Utf8, "name": pl.Utf8, "river": pl.Utf8,
    "lat": pl.Float64, "lon": pl.Float64, "catchment_area": pl.Float64,
    "downstream_id": pl.Utf8, "gauge_datum": pl.Float64, "source": pl.Utf8,
    "river_km": pl.Float64, "gkz": pl.Utf8, "license": pl.Utf8,
}


def _parse_river_km(raw) -> float | None:
    if raw is None:
        return None
    m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*", str(raw))
    return float(m.group(1).replace(",", ".")) if m else None


def _q_stations(messstellen: list[dict]) -> list[dict]:
    return [m for m in messstellen if "Abfluss" in (m.get("messgroesse") or [])]


def download_raw(
    client: NiwisClient, raw_dir: Path, refresh: bool = False, limit: int | None = None
) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    mess_path = raw_dir / "messstellen.json"
    if refresh or not mess_path.exists():
        mess_path.write_text(
            json.dumps(client.stations(), ensure_ascii=False), encoding="utf-8"
        )
    messstellen = json.loads(mess_path.read_text(encoding="utf-8"))

    today = datetime.date.today().isoformat()
    for st in _q_stations(messstellen)[:limit]:
        nr = st["messstelleNr"]
        sd_path = raw_dir / "stammdaten" / f"{nr}.json"
        if refresh or not sd_path.exists():
            sd_path.parent.mkdir(parents=True, exist_ok=True)
            sd_path.write_text(
                json.dumps(client.stammdaten(nr), ensure_ascii=False), encoding="utf-8"
            )
        for von, bis in WINDOWS:
            is_open_window = bis is None
            if is_open_window:
                # Offenes Zeitfenster endet "heute" -- ein Dateiname mit dem
                # Enddatum waere an jedem neuen Kalendertag anders und wuerde bei
                # jedem Lauf einen kompletten Neu-Download ausloesen. Stattdessen
                # stabiler Name; --refresh laedt trotzdem neu. Alte Dateien mit dem
                # frueheren datumsbehafteten Namensschema (vor diesem Fix) gelten
                # weiterhin als vorhanden, damit sie nicht erneut heruntergeladen
                # werden.
                q_path = raw_dir / "abfluss" / f"{nr}_{von}_current.json"
                legacy_exists = any((raw_dir / "abfluss").glob(f"{nr}_{von}_*.json"))
                if not refresh and (q_path.exists() or legacy_exists):
                    continue
            else:
                q_path = raw_dir / "abfluss" / f"{nr}_{von}_{bis}.json"
                if not refresh and q_path.exists():
                    continue
            rows = client.abfluss(nr, von, bis or today)
            if len(rows) >= CAP:
                raise IngestError(
                    f"Abfluss-Response fuer {nr} ({von}..{bis}) erreicht das "
                    f"15000er-Cap — Zeitfenster verkleinern"
                )
            q_path.parent.mkdir(parents=True, exist_ok=True)
            q_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def normalize_stations(messstellen: list[dict], stammdaten: dict[str, dict]) -> pl.DataFrame:
    rows = []
    for st in _q_stations(messstellen):
        nr = st["messstelleNr"]
        sd = stammdaten.get(nr, {})
        ezg = sd.get("ezgGroesse")
        gkz = sd.get("gkz")
        rows.append({
            "station_id": nr,
            "name": sd.get("name") or st.get("name"),
            "river": sd.get("gewaesser"),
            "lat": sd.get("breite"),
            "lon": sd.get("laenge"),
            "catchment_area": float(ezg) if ezg is not None else None,
            "downstream_id": None,
            "gauge_datum": sd.get("hoehePnp"),
            "source": sd.get("institution"),
            "river_km": _parse_river_km(sd.get("lageGewaesser")),
            "gkz": str(gkz) if gkz is not None else None,
            "license": sd.get("lizenz") or st.get("lizenz"),
        })
    return pl.DataFrame(rows, schema=_STATION_SCHEMA)


def normalize_discharge(rows: list[dict]) -> pl.DataFrame:
    bad = [r for r in rows if r.get("einheit") != "m³/s"]
    if bad:
        raise IngestError(f"Unerwartete Einheit in Abflussdaten: {bad[0].get('einheit')!r}")
    df = pl.DataFrame(
        {
            "station_id": [r["messstelleNr"] for r in rows],
            "date": [r["datum"] for r in rows],
            "q": [r.get("messwert") for r in rows],
            "quality_flag": [r.get("flag") for r in rows],
        },
        schema={"station_id": pl.Utf8, "date": pl.Utf8, "q": pl.Float64,
                "quality_flag": pl.Utf8},
    )
    # NIWIS liefert negative Abfluesse nur als Sentinel/Fehlercodes (v. a. -777,
    # "Fehlwert"/"BfGAdded"/"BfGUnplausibel"), physikalisch ist Q < 0 an diesen Pegeln
    # nicht moeglich. Auf null setzen und den bestehenden flag-Wert verwerfen — der
    # Sentinel-Status ist die relevantere Information als ein ggf. vorhandener
    # Original-Flag (der bei -777-Werten ohnehin nur "unplausibel/fehlend" ausdrueckt).
    df = df.with_columns(
        pl.when(pl.col("q") < 0).then(None).otherwise(pl.col("q")).alias("q"),
        pl.when(pl.col("q") < 0).then(pl.lit("sentinel")).otherwise(pl.col("quality_flag"))
        .alias("quality_flag"),
    )
    return (
        df.with_columns(pl.col("date").str.to_date("%Y-%m-%d"))
        .unique(subset=["station_id", "date"], keep="first", maintain_order=True)
        .sort("station_id", "date")
    )


def run(args: argparse.Namespace) -> int:
    log = StageLog(stage="ingest", log_dir=Path(args.log_dir))
    raw_dir = Path(args.raw_dir)
    client = NiwisClient()
    try:
        download_raw(client, raw_dir, refresh=args.refresh, limit=args.limit)
        messstellen = json.loads((raw_dir / "messstellen.json").read_text(encoding="utf-8"))
        q_stations = _q_stations(messstellen)[: args.limit]
        stammdaten = {
            st["messstelleNr"]: json.loads(
                (raw_dir / "stammdaten" / f"{st['messstelleNr']}.json").read_text(encoding="utf-8")
            )
            for st in q_stations
        }
        stations_df = normalize_stations(messstellen, stammdaten)[: args.limit]
        log.counts("stations", rows_in=len(messstellen), rows_out=stations_df.height)

        overrides_path = Path(getattr(args, "topology_overrides", "config/topology_overrides.csv"))
        if args.limit is not None:
            log.info(
                "Smoke-Modus (--limit gesetzt) — Topologie wird nicht angewendet "
                "(Overrides sind auf den vollen 361er-Datensatz abgestimmt; auf einer "
                "Teilmenge wuerden sie irrefuehrende Teiltopologien erzeugen)"
            )
        elif overrides_path.exists():
            overrides_df = pl.read_csv(overrides_path)
            try:
                stations_df = build_topology(stations_df, overrides_df)
            except ValueError as exc:
                # TopologyError ist eine ValueError-Unterklasse; Spec 5.3 verlangt
                # hartes Scheitern (nicht nur Loggen+Weiterlaufen) bei Topologiefehlern.
                log.info(f"Topologie-Validierung fehlgeschlagen: {exc}")
                raise
            n_connected = stations_df.filter(pl.col("downstream_id").is_not_null()).height
            log.info(
                f"Topologie angewendet: {n_connected}/{stations_df.height} "
                f"Stationen mit downstream_id, {overrides_df.height} Overrides"
            )
        else:
            log.info(
                f"Overrides-Datei fehlt unter {overrides_path} — Topologie wird nicht "
                "angewendet, downstream_id bleibt unbefuellt"
            )

        frames = []
        for st in q_stations:
            nr = st["messstelleNr"]
            rows: list[dict] = []
            for f in sorted((raw_dir / "abfluss").glob(f"{nr}_*.json")):
                rows.extend(json.loads(f.read_text(encoding="utf-8")))
            if rows:
                frames.append(normalize_discharge(rows))
        discharge_df = (
            pl.concat(frames).unique(subset=["station_id", "date"], keep="first")
            .sort("station_id", "date")
            if frames
            else pl.DataFrame(schema={"station_id": pl.Utf8, "date": pl.Date,
                                      "q": pl.Float64, "quality_flag": pl.Utf8})
        )
        log.counts("discharge_daily", rows_in=discharge_df.height, rows_out=discharge_df.height)

        interim = Path(args.interim_dir)
        write_stage_parquet(stations_df, interim, "ingest", "stations")
        write_stage_parquet(discharge_df, interim, "ingest", "discharge_daily")

        if args.limit is not None:
            log.info(
                "Smoke-Modus (--limit gesetzt) — DuckDB-Load uebersprungen "
                "(Teilmenge wuerde stations/discharge_daily auf der Produktions-DB "
                "ueberschreiben); Ergebnis liegt nur als Parquet unter interim/ingest/"
            )
        else:
            con = connect(Path(args.db))
            con.execute("DELETE FROM stations")
            con.execute("INSERT INTO stations SELECT * FROM stations_df")
            con.execute("DELETE FROM discharge_daily")
            con.execute("INSERT INTO discharge_daily SELECT * FROM discharge_df")
            con.close()
        return 0
    finally:
        log.close()
