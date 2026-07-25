"""Оптимизатор GeoJSON: уменьшает размер файла в разы без видимой потери качества.

Использование:
    python tools/optimize_geojson.py вход.geojson выход.geojson
    python tools/optimize_geojson.py вход.geojson выход.geojson --precision 5 --simplify 0.00005
    python tools/optimize_geojson.py вход.geojson выход.geojson --keep zone,zone_name,vri

Что делает:
- округляет координаты (--precision, по умолчанию 6 знаков = точность ~10 см);
- упрощает контуры алгоритмом Дугласа–Пекера (--simplify, в градусах;
  0.00003 ≈ 3 м — безопасно, 0.0001 ≈ 10 м — агрессивно);
- убирает подряд идущие одинаковые точки;
- --keep оставляет только нужные свойства (остальные часто весят больше геометрии!);
- пишет компактный JSON без пробелов.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def simplify_dp(points: list, tolerance: float) -> list:
    """Дуглас–Пекер без рекурсии (стек), безопасен для огромных контуров."""
    n = len(points)
    if n < 3 or tolerance <= 0:
        return points
    keep = [False] * n
    keep[0] = True
    keep[n - 1] = True
    stack = [(0, n - 1)]
    tol2 = tolerance * tolerance
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        ax, ay = points[first][0], points[first][1]
        bx, by = points[last][0], points[last][1]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        max_d2 = -1.0
        max_i = first
        for i in range(first + 1, last):
            px, py = points[i][0], points[i][1]
            if seg2 == 0:
                ddx, ddy = px - ax, py - ay
                d2 = ddx * ddx + ddy * ddy
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / seg2
                if t < 0:
                    t = 0.0
                elif t > 1:
                    t = 1.0
                cx, cy = ax + t * dx, ay + t * dy
                ddx, ddy = px - cx, py - cy
                d2 = ddx * ddx + ddy * ddy
            if d2 > max_d2:
                max_d2 = d2
                max_i = i
        if max_d2 > tol2:
            keep[max_i] = True
            stack.append((first, max_i))
            stack.append((max_i, last))
    return [points[i] for i in range(n) if keep[i] ]


def clean_ring(ring: list, precision: int, tolerance: float, closed: bool) -> list:
    pts = [ [round(c[0], precision), round(c[1], precision)] for c in ring ]
    out = []
    for p in pts:
        if not out or out[-1][0] != p[0] or out[-1][1] != p[1]:
            out.append(p)
    if tolerance > 0:
        out = simplify_dp(out, tolerance)
    if closed:
        if len(out) < 3:
            return []
        if out[0][0] != out[-1][0] or out[0][1] != out[-1][1]:
            out.append(list(out[0]))
        if len(out) < 4:
            return []
    return out


def clean_geometry(geom: dict, precision: int, tolerance: float):
    if not geom:
        return None
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Point":
        geom["coordinates"] = [round(coords[0], precision), round(coords[1], precision)]
        return geom
    if gtype == "MultiPoint":
        geom["coordinates"] = [ [round(c[0], precision), round(c[1], precision)] for c in coords ]
        return geom
    if gtype == "LineString":
        line = clean_ring(coords, precision, tolerance, closed=False)
        if len(line) < 2:
            return None
        geom["coordinates"] = line
        return geom
    if gtype == "MultiLineString":
        lines = []
        for part in coords:
            line = clean_ring(part, precision, tolerance, closed=False)
            if len(line) >= 2:
                lines.append(line)
        if not lines:
            return None
        geom["coordinates"] = lines
        return geom
    if gtype == "Polygon":
        rings = []
        for ring in coords:
            r = clean_ring(ring, precision, tolerance, closed=True)
            if r:
                rings.append(r)
        if not rings:
            return None
        geom["coordinates"] = rings
        return geom
    if gtype == "MultiPolygon":
        polys = []
        for poly in coords:
            rings = []
            for ring in poly:
                r = clean_ring(ring, precision, tolerance, closed=True)
                if r:
                    rings.append(r)
            if rings:
                polys.append(rings)
        if not polys:
            return None
        geom["coordinates"] = polys
        return geom
    if gtype == "GeometryCollection":
        geoms = []
        for g in geom.get("geometries", []):
            g2 = clean_geometry(g, precision, tolerance)
            if g2:
                geoms.append(g2)
        geom["geometries"] = geoms
        return geom if geoms else None
    return geom


def main() -> int:
    parser = argparse.ArgumentParser(description="Оптимизация GeoJSON для веб-карты")
    parser.add_argument("src", help="входной .geojson")
    parser.add_argument("dst", help="выходной .geojson")
    parser.add_argument("--precision", type=int, default=6, help="знаков после запятой (6 ≈ 10 см)")
    parser.add_argument("--simplify", type=float, default=0.0, help="допуск упрощения в градусах (0.00003 ≈ 3 м)")
    parser.add_argument("--keep", default="", help="список свойств через запятую, остальные удалить")
    args = parser.parse_args()

    with open(args.src, encoding="utf-8") as f:
        data = json.load(f)

    keep_props = [p.strip() for p in args.keep.split(",") if p.strip()]
    features_in = data.get("features", [])
    features_out = []
    for feat in features_in:
        geom = clean_geometry(feat.get("geometry"), args.precision, args.simplify)
        if geom is None:
            continue
        feat["geometry"] = geom
        if keep_props:
            props = feat.get("properties") or dict()
            feat["properties"] = dict((k, v) for k, v in props.items() if k in keep_props)
        feat.pop("bbox", None)
        features_out.append(feat)
    data["features"] = features_out
    data.pop("bbox", None)

    with open(args.dst, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    size_in = os.path.getsize(args.src)
    size_out = os.path.getsize(args.dst)
    pct = 100.0 * size_out / size_in if size_in else 0
    print(f"Объектов: {len(features_in)} -> {len(features_out)}")
    print(f"Размер: {size_in / 1048576:.2f} МБ -> {size_out / 1048576:.2f} МБ ({pct:.0f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
