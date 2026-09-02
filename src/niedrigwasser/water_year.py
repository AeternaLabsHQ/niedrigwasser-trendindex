from datetime import date

import polars as pl


def water_year(d: date) -> int:
    """Deutsches Wasserjahr: 1. Nov bis 31. Okt, benannt nach dem Endjahr."""
    return d.year + 1 if d.month >= 11 else d.year


def water_year_start(wy: int) -> date:
    return date(wy - 1, 11, 1)


def water_year_end(wy: int) -> date:
    return date(wy, 10, 31)


def day_of_water_year(d: date) -> int:
    return (d - water_year_start(water_year(d))).days + 1


def water_year_expr(col: str = "date") -> pl.Expr:
    c = pl.col(col)
    return pl.when(c.dt.month() >= 11).then(c.dt.year() + 1).otherwise(c.dt.year())
