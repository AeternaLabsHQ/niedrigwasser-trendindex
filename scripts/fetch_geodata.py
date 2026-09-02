"""Erzeugt site/geo.json — Deutschland-Basemap fuer die Stationskarte.

Quelle: Natural Earth 10m (public domain, https://www.naturalearthdata.com/),
GeoJSON-Ableitung aus dem offiziellen Spiegel-Repo
https://github.com/nvkelso/natural-earth-vector (Ordner ``geojson/``).
Lizenz: Natural Earth ist gemeinfrei ("All versions of Natural Earth raster +
vector map data found on this website are in the public domain.").

Layer:
- ``land``    — Landesumriss Deutschland (ne_10m_admin_0_countries, ADM0_A3=DEU)
- ``laender`` — Bundeslandgrenzen (ne_10m_admin_1_states_provinces_lines, DEU)
- ``rivers``  — grosse Fluesse (ne_10m_rivers_lake_centerlines +
                ne_10m_rivers_europe), auf die Karten-BBox geclippt

Verarbeitung (pure Python, keine neuen Dependencies):
- Douglas-Peucker-Vereinfachung (Toleranz in Grad, pro Layer)
- Koordinaten auf 3 Dezimalstellen gerundet
- Ziel: site/geo.json < 80 KB, wird als statisches Asset committet

Aufruf (einmalig / bei NE-Updates):  uv run python scripts/fetch_geodata.py
"""

from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
FILES = {
    "admin0": "ne_10m_admin_0_countries.geojson",
    "admin1": "ne_10m_admin_1_states_provinces_lines.geojson",
    "rivers": "ne_10m_rivers_lake_centerlines.geojson",
    "rivers_eu": "ne_10m_rivers_europe.geojson",
}

# Karten-BBox — identisch zur Projektion in site/template.html (renderMap).
LON0, LON1 = 5.5, 15.5
LAT0, LAT1 = 47.0, 55.5

# Fluesse: nur die grossen Namen (Orientierung, nicht Vollstaendigkeit).
RIVER_NAMES = {
    "rhine", "rhein", "elbe", "danube", "donau", "weser", "main", "mosel",
    "moselle", "neckar", "oder", "havel", "spree", "ems", "saale", "inn",
    "isar", "lech", "aller", "ruhr", "lahn", "fulda", "werra", "leine",
    "salzach", "naab", "regen", "altmuehl", "altmühl", "saar",
}


def fetch(name: str, cache_dir: Path) -> dict:
    """Laedt eine NE-GeoJSON-Datei (mit lokalem Cache)."""
    path = cache_dir / FILES[name]
    if not path.exists():
        url = BASE + FILES[name]
        print(f"lade {url} ...")
        with urllib.request.urlopen(url) as resp:  # noqa: S310 - feste https-URL
            path.write_bytes(resp.read())
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- Geometrie

def _perp_dist(pt: tuple, a: tuple, b: tuple) -> float:
    ax, ay = a
    bx, by = b
    px, py = pt
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def douglas_peucker(points: list, tol: float) -> list:
    """Iterative Douglas-Peucker-Vereinfachung (Toleranz in Grad)."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i0, i1 = stack.pop()
        dmax, imax = 0.0, -1
        for i in range(i0 + 1, i1):
            d = _perp_dist(points[i], points[i0], points[i1])
            if d > dmax:
                dmax, imax = d, i
        if dmax > tol and imax > 0:
            keep[imax] = True
            stack.append((i0, imax))
            stack.append((imax, i1))
    return [p for p, k in zip(points, keep) if k]


def in_bbox(p: tuple, pad: float = 0.0) -> bool:
    return (LON0 - pad) <= p[0] <= (LON1 + pad) and (LAT0 - pad) <= p[1] <= (LAT1 + pad)


def clip_line(points: list, pad: float = 0.2) -> list:
    """Zerteilt eine Linie in Segmente, die (mit Rand) in der BBox liegen."""
    segs, cur = [], []
    for i, p in enumerate(points):
        inside = in_bbox(p, pad)
        prev_inside = i > 0 and in_bbox(points[i - 1], pad)
        if inside:
            if not prev_inside and i > 0:
                cur.append(points[i - 1])  # Einstiegspunkt mitnehmen
            cur.append(p)
        else:
            if prev_inside:
                cur.append(p)  # Ausstiegspunkt mitnehmen
            if len(cur) >= 2:
                segs.append(cur)
            cur = []
    if len(cur) >= 2:
        segs.append(cur)
    return segs


def rnd(points: list) -> list:
    out, last = [], None
    for lon, lat in points:
        q = [round(lon, 3), round(lat, 3)]
        if q != last:
            out.append(q)
            last = q
    return out


def iter_lines(geom: dict):
    if geom["type"] == "LineString":
        yield geom["coordinates"]
    elif geom["type"] == "MultiLineString":
        yield from geom["coordinates"]


def iter_rings(geom: dict):
    if geom["type"] == "Polygon":
        yield from geom["coordinates"]
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield from poly


# ---------------------------------------------------------------- Layer

def build_land(admin0: dict, tol: float) -> list:
    rings = []
    for feat in admin0["features"]:
        props = feat.get("properties", {})
        if props.get("ADM0_A3") not in ("DEU",) and props.get("ISO_A3") != "DEU":
            continue
        for ring in iter_rings(feat["geometry"]):
            pts = [(p[0], p[1]) for p in ring]
            simp = douglas_peucker(pts, tol)
            if len(simp) >= 4:
                rings.append(rnd(simp))
    if not rings:
        raise SystemExit("BLOCKED: Deutschland (DEU) nicht in admin0 gefunden")
    return rings


def stitch(lines: list) -> list:
    """Verkettet Segmente mit gemeinsamen Endpunkten zu laengeren Linien."""
    lines = [list(li) for li in lines]
    changed = True
    while changed:
        changed = False
        lines = [li for li in lines if li]
        by_start: dict = {}
        for i, li in enumerate(lines):
            by_start.setdefault(tuple(li[0]), []).append(i)
        for i, li in enumerate(lines):
            if not li:
                continue
            end = tuple(li[-1])
            for j in by_start.get(end, []):
                if j != i and lines[j] and lines[i]:
                    lines[i] = lines[i] + lines[j][1:]
                    lines[j] = []
                    changed = True
                    break
            if changed:
                break
    return [li for li in lines if len(li) >= 2]


def build_laender(admin1: dict, tol: float) -> list:
    lines = []
    for feat in admin1["features"]:
        props = feat.get("properties", {})
        if props.get("ADM0_A3") != "DEU" and props.get("adm0_a3") != "DEU":
            continue
        for line in iter_lines(feat["geometry"]):
            pts = [(p[0], p[1]) for p in line]
            simp = rnd(douglas_peucker(pts, tol))
            if len(simp) >= 2:
                lines.append(simp)
    return stitch(lines)


def build_rivers(sources: list, tol: float) -> list:
    lines, seen = [], set()
    for fc in sources:
        for feat in fc["features"]:
            props = feat.get("properties", {})
            name = (props.get("name") or props.get("name_en") or "").lower()
            if name not in RIVER_NAMES:
                continue
            for line in iter_lines(feat["geometry"]):
                pts = [(p[0], p[1]) for p in line]
                for seg in clip_line(pts):
                    simp = rnd(douglas_peucker(seg, tol))
                    if len(simp) < 2:
                        continue
                    key = (simp[0][0], simp[0][1], simp[-1][0], simp[-1][1], len(simp))
                    if key in seen:  # Duplikate rivers vs. rivers_europe
                        continue
                    seen.add(key)
                    lines.append(simp)
    return lines


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    cache = root / "data" / "raw" / "naturalearth"
    cache.mkdir(parents=True, exist_ok=True)

    admin0 = fetch("admin0", cache)
    admin1 = fetch("admin1", cache)
    rivers = fetch("rivers", cache)
    rivers_eu = fetch("rivers_eu", cache)

    geo = {
        "meta": {
            "source": "Natural Earth 10m (public domain)",
            "url": "https://www.naturalearthdata.com/",
            "bbox": [LON0, LAT0, LON1, LAT1],
        },
        "land": build_land(admin0, tol=0.012),
        "laender": build_laender(admin1, tol=0.01),
        "rivers": build_rivers([rivers, rivers_eu], tol=0.008),
    }

    out = root / "site" / "geo.json"
    out.write_text(
        json.dumps(geo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    size = out.stat().st_size
    print(
        f"site/geo.json geschrieben: {size / 1024:.1f} KiB — "
        f"land={len(geo['land'])} Ringe, laender={len(geo['laender'])} Linien, "
        f"rivers={len(geo['rivers'])} Segmente"
    )
    if size > 80 * 1024:
        raise SystemExit(f"geo.json zu gross ({size} bytes > 80 KB) — Toleranzen erhoehen")


if __name__ == "__main__":
    main()
