"""
Фірмовий знак STICKBOX (без щита): бірюзова «хвиля» + сірий «стік-i» з відокремленою верхньою «крапкою».
Векторизовано з растрового логотипа замовника (data/brand_mark.json), спрощено під лиття:
  * між хвилею і стіком — бетонна перемичка MARK_WEB (кожен елемент — окрема кишеня під свою фарбу);
  * щілина «крапки» розширена до MARK_CAP_GAP (тонша перемичка в бетоні обламується);
  * гострі кінчики хвилі скруглені r = MARK_TIP_R (силіконовий виступ форми не рветься).
"""
import json
import os
import numpy as np
import cadquery as cq
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union

from . import params as p
from .params import v

DATA = json.load(open(os.path.join(os.path.dirname(__file__), "data", "brand_mark.json")))


def _px_polys():
    sw = Polygon(DATA["swoosh_px"]).buffer(0)
    b = DATA["bar_px"]
    bar = Polygon([b["TL"], b["TR"], b["BR"], b["BL"]])
    return sw, bar


def _smooth_poly(poly, sigma=0.9, step=0.15, protect_r=1.6):
    """Гаусове згладжування контуру вздовж довжини дуги. Точки з великою кривиною (кінчики хвилі,
    внутрішній «гачок») захищено: поблизу них вага згладжування плавно → 0."""
    ring = np.array(poly.exterior.coords)[:-1]
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(np.vstack([ring, ring[:1]]), axis=0).T))]
    L = seg[-1]
    s = np.arange(0, L, step)
    closed = np.vstack([ring, ring[:1]])
    xs, ys = np.interp(s, seg, closed[:, 0]), np.interp(s, seg, closed[:, 1])
    n = len(s)
    k = int(3 * sigma / step)
    w = np.exp(-0.5 * ((np.arange(-k, k + 1) * step) / sigma) ** 2)
    w /= w.sum()
    def circ(a):
        ext = np.r_[a[-k:], a, a[:k]]
        return np.convolve(ext, w, mode="valid")
    sx, sy = circ(xs), circ(ys)
    # кривина: кут повороту на базі ±0.6 мм
    m = max(1, int(0.6 / step))
    v1 = np.stack([xs - np.roll(xs, m), ys - np.roll(ys, m)], 1)
    v2 = np.stack([np.roll(xs, -m) - xs, np.roll(ys, -m) - ys], 1)
    ang = np.abs(np.arctan2(v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0], (v1 * v2).sum(1)))
    sharp = np.where(ang > np.radians(50))[0]
    prot = np.zeros(n)
    for i in sharp:
        d = np.minimum(np.abs(np.arange(n) - i), n - np.abs(np.arange(n) - i)) * step
        prot = np.maximum(prot, np.exp(-(d / protect_r) ** 2))
    fx, fy = prot * xs + (1 - prot) * sx, prot * ys + (1 - prot) * sy
    out = Polygon(np.c_[fx, fy]).buffer(0)
    return out.simplify(0.01)


def mark_polygons(height=None):
    """Повертає dict {swoosh, stem, cap} у мм (u — праворуч, v — вгору), центр знака в (0, 0)."""
    height = height or v(p.MARK_H)
    sw, bar = _px_polys()
    allb = unary_union([sw, bar]).bounds  # (minx, miny, maxx, maxy) у px
    s = height / (allb[3] - allb[1])
    cx, cy = (allb[0] + allb[2]) / 2, (allb[1] + allb[3]) / 2

    def tf(poly):
        pts = [((x - cx) * s, (cy - y) * s) for x, y in poly.exterior.coords]
        return Polygon(pts)

    sw_mm, bar_mm = tf(sw), tf(bar)
    # «крапка» стіка: поділ лінією, щілина MARK_CAP_GAP
    cs = DATA["cap_split_px"]
    x0, y0 = cs["p"]
    k = cs["slope_dy_dx"]
    a = ((x0 - 400 - cx) * s, (cy - (y0 + k * -400)) * s)
    bpt = ((x0 + 400 - cx) * s, (cy - (y0 + k * 400)) * s)
    line = LineString([a, bpt])
    gap = line.buffer(v(p.MARK_CAP_GAP) / 2, cap_style=2)
    parts = sorted(list(bar_mm.difference(gap).geoms), key=lambda g: -g.centroid.y)
    cap, stem = parts[0], parts[1]
    # хвиля: відділити від стіка перемичкою, скруглити кінчики
    r = v(p.MARK_TIP_R)
    # згладжування шуму растрового контуру (±0.3 мм «сходинки»), гострі елементи знака захищено
    sw_mm = _smooth_poly(sw_mm, sigma=0.9)
    swoosh = sw_mm.difference(bar_mm.buffer(v(p.MARK_WEB), join_style=2))
    swoosh = swoosh.buffer(-r).buffer(r)
    if swoosh.geom_type == "MultiPolygon":
        swoosh = max(swoosh.geoms, key=lambda g: g.area)
    swoosh = swoosh.simplify(0.02)
    cap = cap.buffer(-0.25, join_style=1).buffer(0.25, join_style=1)
    stem = stem.buffer(-0.25, join_style=1).buffer(0.25, join_style=1)
    return {"swoosh": swoosh, "stem": stem, "cap": cap}


def _solid_from_poly(poly, z_center, depth):
    """Призма з полігона на фронтальній грані (площина XZ), вглиб корпусу (+Y)."""
    y_face = -v(p.D) / 2 - 0.01
    pts = [(x, y + z_center) for x, y in list(poly.exterior.coords)[:-1]]
    wp = cq.Workplane("XZ", origin=(v(p.MARK_X), y_face, 0)).polyline(pts).close()
    return wp.extrude(-(depth + 0.01)).val()


def mark_solids(depth=None):
    depth = depth or v(p.LOGO_DEPTH)
    polys = mark_polygons()
    zc = v(p.MARK_Z)
    return {k: _solid_from_poly(pl, zc, depth) for k, pl in polys.items()}


def mark_tool():
    s = mark_solids()
    return s["swoosh"].fuse(s["stem"]).fuse(s["cap"]).clean()


# --------------------------------------------------------------------------
# Напис STICKBOX з контурів гліфів (fontTools → shapely → призми).
# Причина: OCCT-тріангуляція TTF-кривих Montserrat дає невалідні тіла окремих літер.
# --------------------------------------------------------------------------
def _glyph_polys(text, font_path, cap_h, track=0.0):
    from fontTools.ttLib import TTFont
    from fontTools.pens.recordingPen import RecordingPen
    from shapely.geometry import Polygon as SP

    f = TTFont(font_path)
    gs = f.getGlyphSet()
    cmap = f.getBestCmap()
    cap = f["OS/2"].sCapHeight or f["head"].unitsPerEm * 0.7
    k = cap_h / cap
    hmtx = f["hmtx"]
    x = 0.0
    letters = []

    def quad(p0, p1, p2, n=8):
        return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                 (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
                for t in [i / n for i in range(1, n + 1)]]

    for ch in text:
        gname = cmap[ord(ch)]
        pen = RecordingPen()
        gs[gname].draw(pen)
        rings, cur = [], []
        for op, args in pen.value:
            if op == "moveTo":
                cur = [args[0]]
            elif op == "lineTo":
                cur.append(args[0])
            elif op == "qCurveTo":
                pts = list(args)
                start = cur[-1]
                # TrueType: послідовні off-curve точки — неявні on-curve посередині
                offs, end = pts[:-1], pts[-1]
                if end is None:  # замкнений контур лише з off-curve точок
                    end = ((offs[-1][0] + offs[0][0]) / 2, (offs[-1][1] + offs[0][1]) / 2)
                for i, c in enumerate(offs):
                    e = end if i == len(offs) - 1 else ((c[0] + offs[i + 1][0]) / 2, (c[1] + offs[i + 1][1]) / 2)
                    cur.extend(quad(start, c, e))
                    start = e
            elif op == "curveTo":
                p0 = cur[-1]
                c1, c2, e = args
                for t in [i / 10 for i in range(1, 11)]:
                    mt = 1 - t
                    cur.append((mt ** 3 * p0[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * e[0],
                                mt ** 3 * p0[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * e[1]))
            elif op in ("closePath", "endPath"):
                if len(cur) >= 3:
                    rings.append([((px + x) * k, py * k) for px, py in cur])
                cur = []
        # TrueType — правило non-zero: контури одного напрямку (за годинниковою) об'єднуються (K з 3 контурів,
        # що перекриваються), контури протилежного напрямку — дірки (B, O). Even-odd тут дає «дірку» в перекритті.
        def sarea(r):
            return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]))
        outer = [SP(r).buffer(0) for r in rings if sarea(r) < 0]
        holes = [SP(r).buffer(0) for r in rings if sarea(r) >= 0]
        from shapely.ops import unary_union as _u
        geom = _u(outer)
        if holes:
            geom = geom.difference(_u(holes))
        letters.append((ch, geom))
        x += hmtx[gname][0] + track / k
    return letters, k


def wordmark_polygons():
    """Літери STICKBOX у мм; центр напису по X = 0, базова лінія + cap/2 = 0 (центр по висоті великих літер)."""
    letters, k = _glyph_polys(p.LOGO_TEXT, p.LOGO_FONT, v(p.LOGO_CAP_H), v(p.LOGO_TRACK))
    from shapely.ops import unary_union as uu
    allb = uu([g for _, g in letters]).bounds
    dx = -(allb[0] + allb[2]) / 2
    dy = -v(p.LOGO_CAP_H) / 2
    from shapely import affinity
    out = []
    for ch, g in letters:
        g = affinity.translate(g, dx, dy).simplify(0.01)
        out.append((ch, g))
    return out


def _solid_from_geom(geom, x0, z_center, depth):
    """Призма з shapely Polygon/MultiPolygon з дірками (літери O, B)."""
    y_face = -v(p.D) / 2 - 0.01
    polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    solids = []
    for pg in polys:
        wp = cq.Workplane("XZ", origin=(x0, y_face, 0))
        outer = [(x, y + z_center) for x, y in list(pg.exterior.coords)[:-1]]
        sol = wp.polyline(outer).close().extrude(-(depth + 0.01)).val()
        for hole in pg.interiors:
            hp = [(x, y + z_center) for x, y in list(hole.coords)[:-1]]
            hs = cq.Workplane("XZ", origin=(x0, y_face, 0)).polyline(hp).close() \
                .extrude(-(depth + 0.01)).val()
            sol = sol.cut(hs)
        solids.append(sol)
    return solids


def wordmark_solids(depth=None):
    """[(літера, [solids])] — для різання і для масок фарби STICK/BOX."""
    depth = depth or v(p.LOGO_DEPTH)
    return [(ch, _solid_from_geom(g, 0.0, v(p.LOGO_Z), depth)) for ch, g in wordmark_polygons()]
