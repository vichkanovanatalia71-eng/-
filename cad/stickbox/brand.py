"""
Фірмовий знак STICKBOX (без щита): бірюзова «хвиля» + сірий «стік-i» з відокремленою верхньою «крапкою».
Векторизовано з растрового логотипа замовника (data/brand_mark.json), спрощено під лиття:
  * v3.1: контур хвилі — плавні B-сплайни (штрафні найменші квадрати), у B-rep — одне гладке C2-ребро, не ламана;
  * між хвилею і стіком — бетонна перемичка MARK_WEB (кожен елемент — окрема кишеня під свою фарбу);
  * щілина «крапки» розширена до MARK_CAP_GAP (тонша перемичка в бетоні обламується);
  * гострі кінчики хвилі скруглені r = MARK_TIP_R (силіконовий виступ форми не рветься), гачок — r = MARK_HOOK_R.
"""
import json
import os
from functools import lru_cache
import numpy as np
import cadquery as cq
from shapely.geometry import Polygon, LineString
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from . import params as p
from .params import v

DATA = json.load(open(os.path.join(os.path.dirname(__file__), "data", "brand_mark.json")))


def _px_polys():
    sw = Polygon(DATA["swoosh_px"]).buffer(0)
    b = DATA["bar_px"]
    bar = Polygon([b["TL"], b["TR"], b["BR"], b["BL"]])
    return sw, bar


# --------------------------------------------------------------------------
# v3.1: плавні контури. Растрове трасування хвилі (320 точок, «сходинки» ±0.2–0.3 мм) замінено на плавні кубічні
# B-сплайни (штрафні найменші квадрати, Eilers–Marx), а в B-rep контур іде одним гладким ребром (C2), не ламаною.
# --------------------------------------------------------------------------
def _resample_open(P, step):
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    n = max(2, int(np.ceil(seg[-1] / step)) + 1)
    t = np.linspace(0, seg[-1], n)
    return np.c_[np.interp(t, seg, P[:, 0]), np.interp(t, seg, P[:, 1])]


def _turn_deg(R, m):
    v1 = R - np.roll(R, m, 0)
    v2 = np.roll(R, -m, 0) - R
    return np.degrees(np.arctan2(v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0], (v1 * v2).sum(1)))


def _fit_fair(P, n_ctrl, lam, iters=4, k=3):
    """Плавний кубічний B-сплайн через точки P (від кута до кута): кінці закріплені, решта — найменші квадрати
    зі штрафом lam·|Δ³c|² на контрольні точки (рівномірна зміна кривини). Параметри уточнюються проєкцією."""
    from scipy.interpolate import BSpline
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    u = d / d[-1]
    t = np.r_[[0.0] * k, np.linspace(0, 1, n_ctrl - k + 1), [1.0] * k]
    D = np.diff(np.eye(n_ctrl), 3, axis=0)
    c0, cn = P[0], P[-1]
    uu = np.linspace(0, 1, 4000)
    for _ in range(iters):
        A = BSpline.design_matrix(np.clip(u, 0, 1), t, k).toarray()
        rhs = P - np.outer(A[:, 0], c0) - np.outer(A[:, -1], cn)
        Ai, Di = A[:, 1:-1], D[:, 1:-1]
        drhs = -(np.outer(D[:, 0], c0) + np.outer(D[:, -1], cn))
        ci = np.linalg.solve(Ai.T @ Ai + lam * Di.T @ Di, Ai.T @ rhs + lam * Di.T @ drhs)
        spl = BSpline(t, np.vstack([c0, ci, cn]), k)
        Q = spl(uu)
        u = uu[np.argmin(((P[:, None, :] - Q[None, :, :]) ** 2).sum(-1), axis=1)]
        u[0], u[-1] = 0.0, 1.0
    return spl, float(np.sqrt(((P - spl(u)) ** 2).sum(1)).max())


def _push_clear(Q, obstacle, clear, sigma=2.0, iters=4):
    """Плавно відсунути ділянку кривої Q від перешкоди до відстані ≥ clear (гаусова огинаюча зсуву, без зламів)."""
    from shapely.geometry import Point
    from shapely.ops import nearest_points
    Q = Q.copy()
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(Q, axis=0).T))]
    for _ in range(iters):
        dist = np.array([obstacle.distance(Point(*q)) for q in Q])
        deficit = np.maximum(0.0, clear - dist)
        if deficit.max() < 1e-4:
            break
        env = np.zeros(len(Q))
        for j in np.where(deficit > 0)[0]:
            env = np.maximum(env, deficit[j] * np.exp(-((s - s[j]) / sigma) ** 2))
        a, b = nearest_points(obstacle, Point(*Q[int(np.argmax(deficit))]))
        dv = np.array([b.x - a.x, b.y - a.y])
        Q = Q + env[:, None] * 1.15 * (dv / np.hypot(*dv))[None, :]
    return Q


FAIR_INFO = {}


def _bisect(fn, lo, hi, target, it=40):
    """Найменше x ∈ [lo, hi], для якого fn(x) ≥ target (fn зростає з x)."""
    for _ in range(it):
        mid = (lo + hi) / 2
        if fn(mid) >= target:
            hi = mid
        else:
            lo = mid
    return hi


MARK_CANON_H = 40.0   # висота знака, на якій будуються плавні криві (масштаб розробки, v2.6–v3.1)


@lru_cache(maxsize=1)
def _mark_canon():
    """Знак у канонічному масштабі (висота 40 мм, центр у (0, 0)): плавні сплайни хвилі, плавний відступ біля кута
    «крапки», зріз перемички вздовж стіка (MARK_WEB у цьому масштабі) — без скруглень (вони абсолютні, після масштабу).
    Повертає dict(swoosh, bar, split=(a, b), runs=[...])."""
    from shapely.geometry import Point
    sw, bar = _px_polys()
    allb = unary_union([sw, bar]).bounds
    s = MARK_CANON_H / (allb[3] - allb[1])
    cx, cy = (allb[0] + allb[2]) / 2, (allb[1] + allb[3]) / 2

    def tf(poly):
        return Polygon([((x - cx) * s, (cy - y) * s) for x, y in poly.exterior.coords])

    sw_mm, bar_mm = tf(sw), tf(bar)
    cs = DATA["cap_split_px"]
    x0, y0 = cs["p"]
    k = cs["slope_dy_dx"]
    a = ((x0 - 400 - cx) * s, (cy - (y0 + k * -400)) * s)
    b = ((x0 + 400 - cx) * s, (cy - (y0 + k * 400)) * s)
    web = v(p.MARK_WEB)
    step = 0.1
    rs = _resample_open(np.array(sw_mm.exterior.coords), step)[:-1]
    turn = _turn_deg(rs, int(1.0 / step))
    n = len(rs)
    corners = [i for i in range(n) if abs(turn[i]) > 35 and
               abs(turn[i]) == max(abs(turn[(i + j) % n]) for j in range(-15, 16))]
    pts, info = [], []
    for ia, ib in zip(corners, corners[1:] + [corners[0] + n]):
        P = rs[np.arange(ia, ib + 1) % n]
        L = float(np.hypot(*np.diff(P, axis=0).T).sum())
        nc = max(5, int(np.ceil(L / v(p.MARK_FAIR_PITCH))) + 3)
        spl, dev = _fit_fair(P, nc, v(p.MARK_FAIR_LAM))
        Q = spl(np.linspace(0, 1, max(60, int(L / 0.03))))
        near = np.array([bar_mm.distance(Point(*q)) < web + 0.05 for q in Q])
        # ділянка заходить у перемичку лише всередині (кут «крапки») → плавно відсунути й знову згладити тим самим
        # сплайном; якщо біля кінця ділянки (край і кінчик біля стіка) — їх формує прямий зріз перемички нижче
        local = bool(near.any() and not near[:20].any() and not near[-20:].any())
        if local:
            for _ in range(4):
                Qp = _push_clear(Q, bar_mm, web + 0.12, sigma=3.0)
                spl, _d = _fit_fair(_resample_open(Qp, step), nc, v(p.MARK_FAIR_LAM))
                Q = spl(np.linspace(0, 1, len(Q)))
                if min(bar_mm.distance(Point(*q)) for q in Q) >= web + 0.03:
                    break
            Q = _push_clear(Q, bar_mm, web + 0.03, sigma=3.0)
            dmin = np.sqrt(((P[:, None, :] - Q[None, ::5, :]) ** 2).sum(-1)).min(1)   # трасування → нова крива
            dev = max(dev, float(dmin.max()))
        info.append(dict(len_mm=round(L, 1), ctrl=nc, max_dev_from_trace_mm=round(dev, 3), pushed=local))
        pts.append(Q[:-1])
    fair = Polygon(np.vstack(pts)).buffer(0)
    swoosh = fair.difference(bar_mm.buffer(web, join_style=2))
    if swoosh.geom_type == "MultiPolygon":
        swoosh = max(swoosh.geoms, key=lambda g: g.area)
    return dict(swoosh=swoosh, bar=bar_mm, split=(a, b), runs=info)


def _mark_bounds_canon():
    """(низ стіка, верх «крапки») у канонічному масштабі — для вписування знака замість літери I."""
    bb = _mark_canon()["bar"].bounds
    return bb[1], bb[3]


@lru_cache(maxsize=8)
def _mark_geom(scale, dx=0.0, dy=0.0, web=None, cap_gap=None):
    """Знак у мм: канонічна форма × scale + зсув (dx, dy). Перемичка хвиля↔стік (web), щілина «крапки» (cap_gap) і радіуси —
    абсолютні (їх диктує лиття). Якщо після масштабування хвиля ближче до стіка, ніж web, вона зсувається як ціле
    (найкоротший зсув угору-ліворуч) — форма хвилі не обрізається. Повертає {name: (полігон, радіус скруглення або None)}."""
    from shapely import affinity
    C = _mark_canon()
    web = v(p.MARK_WEB) if web is None else web
    cap_gap = v(p.MARK_CAP_GAP) if cap_gap is None else cap_gap
    S = lambda g: affinity.scale(g, scale, scale, origin=(0, 0))
    bar_mm = S(C["bar"])
    a, b = [(x * scale, y * scale) for x, y in C["split"]]
    gap = LineString([a, b]).buffer(cap_gap / 2, cap_style=2)
    parts = sorted(list(bar_mm.difference(gap).geoms), key=lambda g: -g.centroid.y)
    cap, stem = parts[0], parts[1]
    bars = unary_union([cap, stem])
    swoosh = S(C["swoosh"])
    shift = (0.0, 0.0)
    if swoosh.distance(bars) < web - 1e-3:
        best = None
        for th in np.radians(np.arange(60, 241, 2)):
            u = (np.cos(th), np.sin(th))
            t = _bisect(lambda m: affinity.translate(swoosh, m * u[0], m * u[1]).distance(bars), 0.0, 6.0, web + 0.005, it=30)
            if best is None or t < best[0]:
                best = (t, u)
        shift = (best[0] * best[1][0], best[0] * best[1][1])
        swoosh = affinity.translate(swoosh, *shift)
    r = v(p.MARK_TIP_R)
    swoosh = swoosh.buffer(-r, quad_segs=64).buffer(r, quad_segs=64)            # опуклі кінчики R
    rh = v(p.MARK_HOOK_R)
    swoosh = swoosh.buffer(rh, quad_segs=64).buffer(-rh, quad_segs=64)          # увігнутий гачок R
    if swoosh.geom_type == "MultiPolygon":
        swoosh = max(swoosh.geoms, key=lambda g: g.area)
    T = lambda g: orient(affinity.translate(g, dx, dy), 1.0)
    FAIR_INFO.clear()
    FAIR_INFO.update(runs=C["runs"], web_min_mm=round(swoosh.distance(bars), 3), cap_gap_mm=round(stem.distance(cap), 3),
                     scale=round(scale, 4), swoosh_shift_mm=round(float(np.hypot(*shift)), 3),
                     trace_max_dev_mm=max(i["max_dev_from_trace_mm"] for i in C["runs"]))
    rb = v(p.MARK_BAR_R)
    return {"swoosh": (T(swoosh), None), "stem": (T(stem), rb), "cap": (T(cap), rb)}


def _rounded(pg, fr):
    return pg if fr is None else pg.buffer(-fr, join_style=1, quad_segs=32).buffer(fr, join_style=1, quad_segs=32)


def mark_polygons(height=None):
    """Окремий знак (до v3.2): dict {swoosh, stem, cap} у мм, центр знака в (0, 0) — уже скруглені."""
    g = _mark_geom(float(height or v(p.MARK_H)) / MARK_CANON_H)
    return {k: _rounded(pg, fr) for k, (pg, fr) in g.items()}


# ---------------- полігон → грань OCC з гладкими ребрами ----------------
def _ring_runs(ring, corner_deg):
    R = np.asarray(ring, float)
    keep = [0]
    for i in range(1, len(R)):
        if np.hypot(*(R[i] - R[keep[-1]])) > 1e-6:
            keep.append(i)
    R = R[keep]
    if np.hypot(*(R[0] - R[-1])) < 1e-6:
        R = R[:-1]
    turn = _turn_deg(R, 1)
    cs = [i for i in range(len(R)) if abs(turn[i]) > corner_deg]
    if not cs:
        return [R], []
    n = len(R)
    return [R[np.arange(a, b + 1) % n] for a, b in zip(cs, cs[1:] + [cs[0] + n])], [turn[i] for i in cs]


def _interp_edge(Q, to3d, periodic):
    from OCP.TColgp import TColgp_HArray1OfPnt
    from OCP.gp import gp_Pnt
    from OCP.GeomAPI import GeomAPI_Interpolate
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    arr = TColgp_HArray1OfPnt(1, len(Q))
    for i, q in enumerate(Q):
        arr.SetValue(i + 1, gp_Pnt(*to3d(q)))
    api = GeomAPI_Interpolate(arr, periodic, 1e-7)
    api.Perform()
    return cq.Edge(BRepBuilderAPI_MakeEdge(api.Curve()).Edge())


def _edge_run(P, to3d, step):
    a, b = P[0], P[-1]
    ch = b - a
    L = np.hypot(*ch)
    if len(P) == 2 or np.max(np.abs((P[:, 0] - a[0]) * ch[1] - (P[:, 1] - a[1]) * ch[0])) / L < 1e-3:
        return cq.Edge.makeLine(cq.Vector(*to3d(a)), cq.Vector(*to3d(b)))
    Q = _resample_open(P, min(step, L / 6))
    return _interp_edge(Q, to3d, False)


def _wire(ring, to3d, corner_deg, step):
    runs, turns = _ring_runs(ring, corner_deg)
    if not turns:   # замкнений контур без кутів (хвиля, О) — одне періодичне C2-ребро
        R = runs[0]
        Q = _resample_open(np.vstack([R, R[:1]]), step)[:-1]
        return cq.Wire.assembleEdges([_interp_edge(Q, to3d, True)])
    return cq.Wire.assembleEdges([_edge_run(r, to3d, step) for r in runs])


def smooth_face(poly, to3d, corner_deg=20.0, step=0.15, fillet_r=None):
    """Полігон shapely (щільно дискретизовані криві) → плоска грань OCC: прямі — відрізки, криві — інтерполяційні
    C2 B-сплайни між справжніми кутами (злам > corner_deg). fillet_r — точне 2D-скруглення кутів (лише прямі)."""
    poly = orient(poly, 1.0)
    ow = _wire(np.array(poly.exterior.coords), to3d, corner_deg, step)
    iws = [_wire(np.array(h.coords), to3d, corner_deg, step) for h in poly.interiors]
    F = cq.Face.makeFromWires(ow, iws)
    if fillet_r:
        F = F.fillet2D(fillet_r, F.Vertices())
    return F


def _prism(poly, x0, z_center, depth, fillet_r=None):
    """Призма з полігона на фронтальній грані (площина XZ), вглиб корпусу (+Y)."""
    y_face = -v(p.D) / 2 - 0.01
    F = smooth_face(poly, lambda q: (x0 + q[0], y_face, z_center + q[1]), fillet_r=fillet_r)
    return cq.Solid.extrudeLinear(F, cq.Vector(0, depth + 0.01, 0))


def mark_solids(depth=None):
    depth = depth or v(p.LOGO_DEPTH)
    zc = v(p.MARK_Z)
    return {k: _prism(pg, v(p.MARK_X), zc, depth, fr) for k, (pg, fr) in _mark_geom(float(v(p.MARK_H)) / MARK_CANON_H).items()}


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

    def quad(p0, p1, p2):
        # v3.1: щільна дискретизація (≈0.04 мм) — далі криві перетворюються на гладкі B-сплайни (smooth_face)
        L = (np.hypot(p1[0] - p0[0], p1[1] - p0[1]) + np.hypot(p2[0] - p1[0], p2[1] - p1[1])) * k
        n = max(8, int(np.ceil(L / 0.04)))
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
                Lc = (np.hypot(c1[0] - p0[0], c1[1] - p0[1]) + np.hypot(c2[0] - c1[0], c2[1] - c1[1]) +
                      np.hypot(e[0] - c2[0], e[1] - c2[1])) * k
                nc = max(10, int(np.ceil(Lc / 0.04)))
                for t in [i / nc for i in range(1, nc + 1)]:
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


@lru_cache(maxsize=2)
def wordmark_layout():
    """Напис STICKBOX у мм; центр по X = 0, центр по висоті великих літер = 0.
    v3.2 (LOGO_I_MARK): літера I — фірмовий знак: стік + «крапка» займають висоту великих літер (від базової лінії до
    верху), хвиля піднімається над рядком. Відстані знак↔T і знак↔C — як у шрифті між T|I та I|C (не менше перемички).
    Повертає dict(letters=[(ch, geom)], mark={name: (полігон, радіус)} або None, swoosh=полігон або None, info)."""
    from shapely import affinity
    Ch = v(p.LOGO_CAP_H)
    letters, k = _glyph_polys(p.LOGO_TEXT, p.LOGO_FONT, Ch, v(p.LOGO_TRACK))
    info = {}
    mark = None
    if v(p.LOGO_I_MARK) and "I" in p.LOGO_TEXT:
        iI = p.LOGO_TEXT.index("I")
        gT, gI, gC = letters[iI - 1][1], letters[iI][1], letters[iI + 1][1]
        web = v(p.LOGO_I_WEB)
        gap_l = max(gT.distance(gI), web)
        gap_r = max(gI.distance(gC), web)
        yb, yt = _mark_bounds_canon()
        f = Ch / (yt - yb)
        M0 = _mark_geom(f, 0.0, -yb * f, v(p.LOGO_I_WEB), v(p.LOGO_I_CAP_GAP))   # низ стіка — на базовій лінії, верх «крапки» — на Ch
        U0 = unary_union([_rounded(pg, fr) for pg, fr in M0.values()])
        # знак праворуч від T: найменший зсув, за якого відстань до T = gap_l
        lo, hi = gT.bounds[0] - U0.bounds[0], gT.bounds[2] - U0.bounds[0] + gap_l + 1
        dxm = _bisect(lambda x: affinity.translate(U0, x, 0).distance(gT), lo, hi, gap_l)
        U = affinity.translate(U0, dxm, 0)
        # хвіст напису (C K B O X) — найменший зсув, за якого відстань до знака = gap_r
        tail = unary_union([g for _, g in letters[iI + 1:]])
        lo, hi = U.bounds[0] - tail.bounds[0], U.bounds[2] - tail.bounds[0] + gap_r + 1
        dxt = _bisect(lambda x: affinity.translate(tail, x, 0).distance(U), lo, hi, gap_r)
        mark = {kk: (affinity.translate(pg, dxm, 0), fr) for kk, (pg, fr) in M0.items()}
        letters = (letters[:iI] + [("I", unary_union([_rounded(*mark["stem"]), _rounded(*mark["cap"])]))]
                   + [(ch, affinity.translate(g, dxt, 0)) for ch, g in letters[iI + 1:]])
        info = dict(mark_scale=round(f, 4), mark_height_mm=round(MARK_CANON_H * f, 2), gap_T_mark=round(gap_l, 2),
                    gap_mark_C=round(gap_r, 2), swoosh_above_caps_mm=round(_rounded(*mark["swoosh"]).bounds[3] - Ch, 2),
                    **{kk: vv for kk, vv in FAIR_INFO.items() if kk != "runs"}, runs=FAIR_INFO.get("runs"))
    geoms = [g for _, g in letters] + ([_rounded(*mark["swoosh"])] if mark else [])
    allb = unary_union(geoms).bounds
    dx = -(allb[0] + allb[2]) / 2
    dy = -Ch / 2
    letters = [(ch, affinity.translate(g, dx, dy)) for ch, g in letters]
    if mark:
        mark = {kk: (affinity.translate(pg, dx, dy), fr) for kk, (pg, fr) in mark.items()}
    info.update(width_mm=round(allb[2] - allb[0], 2), x_range=(round(allb[0] + dx, 2), round(allb[2] + dx, 2)),
                y_range=(round(allb[1] + dy, 2), round(allb[3] + dy, 2)),
                min_letter_gap_mm=round(min(a.distance(b) for (_, a), (_, b) in zip(letters, letters[1:])), 2))
    return dict(letters=letters, mark=mark, swoosh=_rounded(*mark["swoosh"]) if mark else None, info=info)


def wordmark_polygons():
    """[(літера, полігон)] у мм (центр напису в 0); при LOGO_I_MARK літера I = стік + «крапка» знака."""
    return wordmark_layout()["letters"]


def wordmark_swoosh():
    """Хвиля знака-I (полігон, мм) або None."""
    return wordmark_layout()["swoosh"]


def _solid_from_geom(geom, x0, z_center, depth):
    """Призми з shapely Polygon/MultiPolygon з дірками (O, B) — гладкі ребра (smooth_face)."""
    polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    return [_prism(pg, x0, z_center, depth) for pg in polys]


def wordmark_solids(depth=None):
    """[(літера, [solids])] — для різання і для масок фарби STICK/BOX. Літера I при LOGO_I_MARK — стік і «крапка» знака
    (точні 2D-скруглення кутів). Хвиля — окремо: wordmark_swoosh_solid()."""
    depth = depth or v(p.LOGO_DEPTH)
    L = wordmark_layout()
    out = []
    for ch, g in L["letters"]:
        if ch == "I" and L["mark"]:
            out.append((ch, [_prism(L["mark"][kk][0], 0.0, v(p.LOGO_Z), depth, L["mark"][kk][1]) for kk in ("stem", "cap")]))
        else:
            out.append((ch, _solid_from_geom(g, 0.0, v(p.LOGO_Z), depth)))
    return out


def wordmark_swoosh_solid(depth=None):
    L = wordmark_layout()
    if not L["mark"]:
        return None
    return _prism(L["mark"]["swoosh"][0], 0.0, v(p.LOGO_Z), depth or v(p.LOGO_DEPTH))


# --------------------------------------------------------------------------
# v3.3: знак NFC на верхній грані (над міткою, що клеїться зсередини). Оригінальний простий знак — «крапка» і три дуги
# (безконтактний зв'язок) + слово NFC; офіційний N-Mark NFC Forum — товарний знак з власними правилами, тут не відтворюється.
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def nfc_symbol():
    """Знак NFC у мм: u — праворуч (+X), v — до задньої грані (+Y); центр хвиль = центр мітки (0, 0).
    Повертає dict(waves=полігони бірюзові (MultiPolygon), text=[(літера, полігон)] темно-сірі, info)."""
    from shapely.geometry import Point, MultiPolygon
    from shapely import affinity
    w, g = v(p.NFC_STROKE), v(p.NFC_GAP)
    rd = 1.4                                       # «крапка»
    radii = [rd + g + w / 2]
    for _ in range(2):
        radii.append(radii[-1] + w + g)
    span = np.radians(45.0)
    parts = [Point(0, 0).buffer(rd, quad_segs=64)]
    for r in radii:
        t = np.linspace(-span, span, max(60, int(2 * span * r / 0.04)))
        arc = LineString(np.c_[r * np.cos(t), r * np.sin(t)])
        parts.append(arc.buffer(w / 2, quad_segs=32, cap_style=1))
    waves = MultiPolygon([pg for pg in parts])
    b = waves.bounds
    waves = affinity.translate(waves, -(b[0] + b[2]) / 2, -(b[1] + b[3]) / 2)
    wb = waves.bounds
    if not v(p.NFC_TEXT_ON):   # v3.7: лише хвилі, без слова «NFC»
        info = dict(waves_w=round(wb[2] - wb[0], 2), waves_h=round(wb[3] - wb[1], 2), radii=[round(r, 2) for r in radii],
                    text_track=None, text_gap_min=None, text_w=0.0, bounds=[round(x, 2) for x in wb])
        return dict(waves=waves, text=[], info=info)
    # слово NFC: трекінг підбирається так, щоб перемички між літерами були ≥ NFC_GAP
    cap = v(p.NFC_TEXT_CAP)
    track = 0.0
    for _ in range(30):
        letters, k = _glyph_polys("NFC", p.LOGO_FONT, cap, track)
        gmin = min(a.distance(b_) for (_, a), (_, b_) in zip(letters, letters[1:]))
        if gmin >= g:
            break
        track += (g - gmin) + 0.02
    tb = unary_union([q for _, q in letters]).bounds
    wb = waves.bounds
    dy = wb[1] - 2 * g - cap                       # під хвилями, проміжок 2 перемички
    letters = [(ch, affinity.translate(q, -(tb[0] + tb[2]) / 2, dy)) for ch, q in letters]
    allb = unary_union([waves] + [q for _, q in letters]).bounds
    info = dict(waves_w=round(wb[2] - wb[0], 2), waves_h=round(wb[3] - wb[1], 2), radii=[round(r, 2) for r in radii],
                text_track=round(track, 2), text_gap_min=round(gmin, 2), text_w=round(tb[2] - tb[0], 2),
                bounds=[round(x, 2) for x in allb])
    return dict(waves=waves, text=letters, info=info)


def _prism_top(poly, x0, y0, depth):
    """Призма з полігона на верхній грані (z = H), вглиб корпусу (−Z)."""
    zt = v(p.H) + 0.01
    F = smooth_face(poly, lambda q: (x0 + q[0], y0 + q[1], zt))
    return cq.Solid.extrudeLinear(F, cq.Vector(0, 0, -(depth + 0.01)))


def nfc_symbol_solids(depth=None):
    """{'waves': [тіла], 'text': [тіла]} у координатах корпусу (центр — NFC_X, NFC_Y)."""
    depth = depth or v(p.LOGO_DEPTH)
    S_ = nfc_symbol()
    x0, y0 = v(p.NFC_X), v(p.NFC_Y)
    waves = [_prism_top(pg, x0, y0, depth) for pg in S_["waves"].geoms]
    text = [_prism_top(pg, x0, y0, depth) for _, q in S_["text"] for pg in (q.geoms if q.geom_type == "MultiPolygon" else [q])]
    return {"waves": waves, "text": text}
