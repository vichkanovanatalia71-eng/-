"""Перевірка розбірного каркаса й силіконового блока форми (v3.7).

1. Товщина силіконового блока:
   * стінка «каркас ↔ майстер» — відстань від внутрішньої поверхні каркаса (з ключами) до майстра;
   * верх — відстань від верхньої грані силікону до майстра;
   * локальна товщина всього блока — промені всередину з точок його поверхні, з розбивкою за зонами
     (рельєф напису й знака NFC, шпилька отвору, перегородка прорізу, «палець» кишені — це навмисні деталі форми,
     а не стінки; решта має бути ≥ SIL_MIN).
2. Прогин стінок каркаса й зусилля на болтах роз'єму під гідростатичним тиском (заливка силікону і лиття бетону).
"""
import math

import numpy as np
import trimesh

from . import molds as M
from . import params as p
from . import parts as P
from .params import v
from .export import mesh_of

d = p.derived()
K = M.K

# Припущення (не вимірювання): густини рідин і модуль пружності друкованого PETG — типові значення, уточнити за даташитами
RHO_SILICONE_LIQ = 1.1e3    # кг/м³, рідкий силікон для форм
RHO_CONCRETE = 2.3e3        # кг/м³, свіжий бетон (консервативно — важчий за нашу суміш 1.7–2.0)
E_PETG = 2.0e3              # МПа, PETG (друк 100%, типове 1.9–2.1 ГПа)


def _contour_points(sp, z, step=1.0, inset=0.0):
    """Точки внутрішнього контуру каркаса (rounded rect) на висоті z, зміщені всередину на inset."""
    w, h, r = sp["w"] / 2 - inset, sp["h"] / 2 - inset, max(0.5, sp["r"] - inset)
    cx, cy = sp["cx"], sp["cy"]
    pts = []
    for (ax, ay, a0) in ((w - r, h - r, 0), (-(w - r), h - r, 90), (-(w - r), -(h - r), 180), (w - r, -(h - r), 270)):
        n = max(4, int(math.pi / 2 * r / step))
        for i in range(n):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + ax + r * math.cos(a), cy + ay + r * math.sin(a), z))
    for (x0, y0, x1, y1) in ((w - r, h, -(w - r), h), (-(w - r), -h, w - r, -h), (w, -(h - r), w, h - r), (-w, h - r, -w, -(h - r))):
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / step))
        pts += [(cx + x0 + (x1 - x0) * i / n, cy + y0 + (y1 - y0) * i / n, z) for i in range(n)]
    return pts


def _key_inset(sp, x, y, z):
    """Скільки ключ виступає всередину в точці контуру (0 — поза ключем)."""
    L = sp["w"] - 2 * sp["r"] - 4.0
    on_fb = abs(abs(y - sp["cy"]) - sp["h"] / 2) < 1e-6 and abs(x - sp["cx"]) <= L / 2
    if not on_fb:
        return 0.0
    for zk in sp["key_z"]:
        dz = abs(z - zk)
        if dz <= M.KEY_TOP / 2:
            return sp["key_h"]
        if dz <= M.KEY_B / 2:
            return sp["key_h"] * (M.KEY_B / 2 - dz) / ((M.KEY_B - M.KEY_TOP) / 2)
    return 0.0


def _dist(mesh, pts, chunk=1500):
    out = np.empty(len(pts))
    for a in range(0, len(pts), chunk):
        _, dd, _ = trimesh.proximity.closest_point(mesh, pts[a:a + chunk])
        out[a:a + chunk] = dd
    return out


def wall_thickness(kind="body"):
    sp = M.frame_spec(kind)
    master = M.body_master() if kind == "body" else M.lid_master()
    mm = mesh_of(master, 0.08, 0.15)
    # бічна стінка: внутрішня поверхня каркаса з ключами
    side = []
    zs = sorted(set([round(z, 2) for z in np.arange(sp["z0"] + 0.25, sp["z1"] - 0.25, 2.0)] +
                    [round(zk + dz, 2) for zk in sp["key_z"] for dz in (-1.0, 0.0, 1.0)]))
    for z in zs:
        for (x, y, _) in _contour_points(sp, z, step=2.0):
            ki = _key_inset(sp, x, y, z)
            nx, ny = x - sp["cx"], y - sp["cy"]
            # зсув усередину по нормалі прямої ділянки (на ключі — лише фронт/зад)
            if ki > 0:
                y = y - math.copysign(ki, ny)
            side.append((x, y, z))
    side = np.array(side)
    dist_side = _dist(mm, side)
    # верх: сітка точок на верхній грані силікону (поза фланцем ребра «пальця»)
    xs = np.arange(sp["cx"] - sp["w"] / 2 + 1, sp["cx"] + sp["w"] / 2 - 1, 3.0)
    ys = np.arange(sp["cy"] - sp["h"] / 2 + 1, sp["cy"] + sp["h"] / 2 - 1, 3.0)
    top = np.array([(x, y, sp["z1"]) for x in xs for y in ys])
    if kind == "body":
        sb = M.finger_stiffener().BoundingBox()
        top = top[~((top[:, 0] > sb.xmin - 1) & (top[:, 0] < sb.xmax + 1) & (top[:, 1] > sb.ymin - 1) & (top[:, 1] < sb.ymax + 1))]
    dist_top = _dist(mm, top)
    i_s, i_t = int(np.argmin(dist_side)), int(np.argmin(dist_top))
    return dict(side_min_mm=float(dist_side.min()), side_min_at=[round(c, 1) for c in side[i_s]],
                side_median_mm=float(np.median(dist_side)), side_p01_mm=float(np.percentile(dist_side, 1)),
                top_min_mm=float(dist_top.min()), top_min_at=[round(c, 1) for c in top[i_t]],
                n_side=int(len(side)), n_top=int(len(top)))


def _zones_body(pts):
    """Зони навмисних тонких деталей форми корпусу (у координатах майстра, масштаб K)."""
    from . import brand
    H = v(p.H) * K
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
    li = brand.wordmark_layout()["info"]
    (x0, x1), (y0, y1) = li["x_range"], li["y_range"]
    zl = v(p.LOGO_Z)
    logo = (y < (-v(p.D) / 2 + v(p.LOGO_DEPTH)) * K + 0.3) & (z > (zl + y0 - 1.5) * K) & (z < (zl + y1 + 1.5) * K) \
        & (x > (x0 - 1.5) * K) & (x < (x1 + 1.5) * K)
    nb = brand.nfc_symbol()["info"]["bounds"]
    nx, ny = v(p.NFC_X), v(p.NFC_Y)
    nfc = (z > H - v(p.LOGO_DEPTH) * K - 0.3) & (x > (nx + nb[0] - 1.5) * K) & (x < (nx + nb[2] + 1.5) * K) \
        & (y > (ny + nb[1] - 1.5) * K) & (y < (ny + nb[3] + 1.5) * K)
    pin = (np.hypot(x - d["cav_xc"] * K, y) < (v(p.HOLE_D) / 2 + 1.0) * K) & (z < (H - v(p.FUNNEL_DEPTH) * K + 0.5))
    slot = (np.abs(x - d["pocket_cx"] * K) < (v(p.SLOT_W) / 2 + 1.5) * K) & (y < (-v(p.D) / 2 + v(p.T_FRONT_POCKET) + 1.5) * K) \
        & (z > (v(p.H) - v(p.SLOT_DEPTH) - 1.5) * K)
    finger = (np.abs(x - d["pocket_cx"] * K) < (d["pocket_x"] / 2 + 1.5) * K) & (np.abs(y - d["pocket_cy"] * K) < (d["pocket_y"] / 2 + 1.5) * K) \
        & (z < H + 0.5)
    return {"рельєф напису (1.0 мм)": logo, "рельєф знака NFC (1.0 мм)": nfc, "шпилька отвору Ø8": pin,
            "перегородка прорізу 8 × 34": slot & ~finger, "«палець» кишені (шкіра на ребрі T04)": finger}


def _zones_lid(pts):
    gz0, gz1 = d["groove_z0"] * K, d["groove_z1"] * K
    z = pts[:, 2]
    bead = (z > gz0 - 0.5) & (z < gz1 + 0.5)
    return {"валик канавки шнура (5 × 2.0)": bead}


def local_thickness(kind="body", n=24000, seed=3):
    """Локальна товщина силіконового блока: промені всередину з точок поверхні."""
    sil = M.mold_silicone(kind)
    m = mesh_of(sil, 0.05, 0.1)
    m.merge_vertices()
    pts, fidx = trimesh.sample.sample_surface_even(m, n, seed=seed)
    nrm = m.face_normals[fidx]
    org = pts - nrm * 0.02
    th = np.full(len(pts), np.inf)
    for a in range(0, len(pts), 3000):                   # частинами — менше пам'яті
        sl = slice(a, a + 3000)
        loc, iray, _ = m.ray.intersects_location(org[sl], -nrm[sl], multiple_hits=False)
        th[a + iray] = np.linalg.norm(loc - org[sl][iray], axis=1)
    # промені вздовж стінки каркаса (точка на верхній/нижній грані впритул до стінки, нормаль вертикальна) — не товщина
    sp = M.frame_spec(kind)
    qx = np.maximum(np.abs(pts[:, 0] - sp["cx"]) - (sp["w"] / 2 - sp["r"]), 0)
    qy = np.maximum(np.abs(pts[:, 1] - sp["cy"]) - (sp["h"] / 2 - sp["r"]), 0)
    d_wall = sp["r"] - np.hypot(qx, qy) - np.maximum(np.minimum(np.maximum(np.abs(pts[:, 0] - sp["cx"]) - (sp["w"] / 2 - sp["r"]),
                                                                          np.abs(pts[:, 1] - sp["cy"]) - (sp["h"] / 2 - sp["r"])), 0), 0)
    graze = (d_wall < sp["key_h"] + 0.6) & (np.abs(nrm[:, 2]) > 0.9)
    ok = np.isfinite(th) & ~graze
    pts, th = pts[ok], th[ok]
    zones = _zones_body(pts) if kind == "body" else _zones_lid(pts)
    rest = np.ones(len(pts), bool)
    out = {}
    for name, msk in zones.items():
        rest &= ~msk
        if msk.any():
            out[name] = dict(min_mm=float(th[msk].min()), p05_mm=float(np.percentile(th[msk], 5)), n=int(msk.sum()))
    # «решта»: тонкі місця, якщо є, — з координатами (для пошуку)
    th_r, pts_r = th[rest], pts[rest]
    order = np.argsort(th_r)[:8]
    out["решта блока"] = dict(min_mm=float(th_r.min()), p01_mm=float(np.percentile(th_r, 1)), p05_mm=float(np.percentile(th_r, 5)),
                             median_mm=float(np.median(th_r)), n=int(len(th_r)),
                             thinnest=[dict(t=round(float(th_r[i]), 2), at=[round(c, 1) for c in pts_r[i]]) for i in order])
    return out


def frame_deflection(kind="body"):
    """Прогин найдовшої прямої стінки каркаса під гідростатичним тиском — балка між кутами (консервативно:
    рівномірний максимальний тиск, шарнірні опори; жорсткість силікону не враховано)."""
    sp = M.frame_spec(kind)
    t, Hf = M.FRAME_T, sp["hf"]
    L = sp["w"] - 2 * sp["r"] + 2 * (sp["r"] + t) * (1 - 1 / math.sqrt(2))   # пряма ділянка + частина дуг до 45°
    n_hoop = len(sp["hoops"])
    # переріз: стінка Hf × t + n обручів HOOP_T × HOOP_D назовні
    A_w, y_w = Hf * t, t / 2
    A_h, y_h = M.HOOP_T * M.HOOP_D, t + M.HOOP_D / 2
    A = A_w + n_hoop * A_h
    yc = (A_w * y_w + n_hoop * A_h * y_h) / A
    I = Hf * t ** 3 / 12 + A_w * (y_w - yc) ** 2 + n_hoop * (M.HOOP_T * M.HOOP_D ** 3 / 12 + A_h * (y_h - yc) ** 2)
    I0 = Hf * t ** 3 / 12
    g = 9.81
    depth_sil = Hf                                   # рівень рідкого силікону = верх каркаса
    depth_con = (sp["master_bb"][5] - sp["master_bb"][4])   # глибина виливка ≈ висота майстра
    out = dict(span_mm=L, I_with_hoops_mm4=I, I_wall_only_mm4=I0, E_MPa=E_PETG)
    for name, rho, h in (("заливка силікону", RHO_SILICONE_LIQ, depth_sil), ("лиття бетону", RHO_CONCRETE, depth_con)):
        p_max_kpa = rho * g * (h / 1000) / 1000
        q = p_max_kpa * 1e-3 * Hf                        # Н/мм (рівномірно, консервативно)
        w_ss = 5 * q * L ** 4 / (384 * E_PETG * I)
        w_ss0 = 5 * q * L ** 4 / (384 * E_PETG * I0)
        # розпірна сила на роз'єм: тиск × проекція (ширина × глибина рідини), середній гідростатичний
        F = p_max_kpa * 1e-3 / 2 * sp["w"] * min(h, Hf)
        out[name] = dict(p_max_kPa=p_max_kpa, deflection_mm=w_ss, deflection_without_hoops_mm=w_ss0,
                         split_force_N=F, per_bolt_N=F / (2 * len(sp["bolts"])))
    return out


def run():
    res = {}
    for kind in ("body", "lid"):
        sp = M.frame_spec(kind)
        sil = M.mold_silicone(kind)
        f, b = M.frame_halves(kind)
        res[kind] = dict(
            frame=dict(inner_w=sp["w"], inner_h=sp["h"], inner_r=sp["r"], height=sp["hf"], t_side=sp["t_side"], t_top=sp["t_top"],
                       key_h=sp["key_h"], key_z=sp["key_z"], n_bolts=2 * len(sp["bolts"]), wall=M.FRAME_T,
                       outer_bbox=[round(x, 1) for x in (f.fuse(b).BoundingBox().xlen, f.fuse(b).BoundingBox().ylen, f.fuse(b).BoundingBox().zlen)],
                       front_ml=f.Volume() / 1000, back_ml=b.Volume() / 1000, valid=bool(f.isValid() and b.isValid())),
            silicone_ml=sil.Volume() / 1000,
            interference_mm3=dict(front_silicone=f.intersect(sil).Volume(), back_silicone=b.intersect(sil).Volume(),
                                  front_back=f.intersect(b).Volume()),
            walls=wall_thickness(kind), local=local_thickness(kind), deflection=frame_deflection(kind))
    return res
