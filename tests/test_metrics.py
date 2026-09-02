from datetime import date, timedelta

import polars as pl

from niedrigwasser.metrics import station_year_metrics

THRESH = pl.DataFrame({"station_id": ["A"], "q95": [10.0], "mnq": [5.0],
                       "ref_period_start": [1992], "ref_period_end": [2011]})


def _daily(station: str, wy: int, values):
    start = date(wy - 1, 11, 1)
    days = [start + timedelta(days=i) for i in range(len(values))]
    return pl.DataFrame({"station_id": [station] * len(values), "date": days,
                         "q": values}).with_columns(pl.col("date").cast(pl.Date))


def test_days_below_and_deficit():
    # 3 Tage unter Schwelle (8, 9, 6), Rest 20
    vals = [20.0] * 100 + [8.0, 9.0, 6.0] + [20.0] * 262
    out = station_year_metrics(_daily("A", 2001, vals), THRESH)
    row = out.row(0, named=True)
    assert row["water_year"] == 2001
    assert row["days_below"] == 3
    assert row["deficit_volume_m3"] == (2 + 1 + 4) * 86400.0
    assert row["max_spell"] == 3


def test_max_spell_uses_pooling():
    # Run 3 Tage, 4 Tage drueber, Run 2 Tage -> gepoolt 9 Tage Spannweite
    vals = [20.0] * 50 + [5.0] * 3 + [20.0] * 4 + [5.0] * 2 + [20.0] * 306
    out = station_year_metrics(_daily("A", 2001, vals), THRESH, inter_event=5)
    row = out.row(0, named=True)
    assert row["days_below"] == 5
    assert row["max_spell"] == 9
    out3 = station_year_metrics(_daily("A", 2001, vals), THRESH, inter_event=3)
    assert out3.row(0, named=True)["max_spell"] == 3


def test_nm7q_complete_windows_only():
    # konstant 20, ein 7-Tage-Block mit 6 -> nm7q = 8.0 nur wenn Fenster komplett
    vals = [20.0] * 100 + [6.0] * 7 + [20.0] * 258
    out = station_year_metrics(_daily("A", 2001, vals), THRESH)
    assert out.row(0, named=True)["nm7q"] == 6.0


def test_nm7q_null_when_gaps_break_all_windows():
    # jeder 4. Tag fehlt -> kein vollstaendiges 7-Tage-Fenster
    vals = [20.0 if i % 4 else None for i in range(365)]
    out = station_year_metrics(_daily("A", 2001, vals), THRESH)
    assert out.row(0, named=True)["nm7q"] is None


def test_missing_days_not_below():
    # Kalenderluecke: nur 100 Tage geliefert, alle ueber Schwelle
    vals = [20.0] * 100
    out = station_year_metrics(_daily("A", 2001, vals), THRESH)
    row = out.row(0, named=True)
    assert row["days_below"] == 0 and row["max_spell"] == 0
    assert row["deficit_volume_m3"] == 0.0


def test_station_without_threshold_dropped():
    out = station_year_metrics(_daily("X", 2001, [1.0] * 50), THRESH)
    assert out.height == 0


THRESH_AB = pl.DataFrame({"station_id": ["A", "B"], "q95": [10.0, 10.0],
                          "mnq": [5.0, 5.0], "ref_period_start": [1992, 1992],
                          "ref_period_end": [2011, 2011]})


def test_nm7q_isolated_across_stations_and_years():
    # Station A: WY2001, konstant hoch (365 Tage, deckt Wasserjahr voll ab)
    a_wy2001 = _daily("A", 2001, [20.0] * 365)

    # Station B: WY2001, beginnt mit 6 niedrigen Tagen, dann konstant hoch.
    # In sortierter Reihenfolge (station_id, water_year, date) folgt B direkt
    # auf A -> ohne .over()-Isolation koennte das erste 7-Tage-Fenster von B
    # faelschlich A-Werte (20.0) aus dem Zeilenende von A mitmitteln.
    b_vals = [1.0] * 6 + [20.0] * 359
    b_wy2001 = _daily("B", 2001, b_vals)

    daily = pl.concat([a_wy2001, b_wy2001])
    out = station_year_metrics(daily, THRESH_AB)

    row_b = out.filter((pl.col("station_id") == "B") & (pl.col("water_year") == 2001)).row(
        0, named=True
    )
    # Erste 6 Tage sind niedrig, kein vollstaendiges Fenster kann sie referenzieren,
    # ohne auch Station-A-Werte einzuschliessen -> waere Isolation kaputt, entstuende
    # ein Mischwert < 20.0 und > reinem Niedrig-Mittel. Mit Isolation ist das erste
    # vollstaendige Fenster [Tag1..Tag7] = 6x1.0 + 1x20.0 -> Mittel ~3.71.
    expected_first_window = (6 * 1.0 + 20.0) / 7
    assert row_b["nm7q"] == expected_first_window

    # Station A (WY2001) darf durch B's niedrige Werte nicht beeinflusst werden.
    row_a = out.filter((pl.col("station_id") == "A") & (pl.col("water_year") == 2001)).row(
        0, named=True
    )
    assert row_a["nm7q"] == 20.0


def test_nm7q_isolated_across_water_years():
    # Ende WY2001 (Oktober) niedrig, WY2002 durchgehend hoch. Ein Fenster,
    # das ueber den Wasserjahreswechsel hinweg mischen wuerde, haette einen
    # nm7q < 20.0 fuer WY2002 -> mit Isolation muss WY2002 exakt 20.0 sein.
    wy2001_vals = [20.0] * 358 + [1.0] * 7  # letzte 7 Tage (Ende Okt) niedrig
    wy2002_vals = [20.0] * 365

    daily = pl.concat([
        _daily("A", 2001, wy2001_vals),
        _daily("A", 2002, wy2002_vals),
    ])
    out = station_year_metrics(daily, THRESH)

    row_2001 = out.filter(pl.col("water_year") == 2001).row(0, named=True)
    assert row_2001["nm7q"] == 1.0

    row_2002 = out.filter(pl.col("water_year") == 2002).row(0, named=True)
    assert row_2002["nm7q"] == 20.0
