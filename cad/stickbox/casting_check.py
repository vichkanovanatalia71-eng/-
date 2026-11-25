"""
STICKBOX 01 — «віртуальне лиття»: що реально вийде з файлів оснащення, які отримує виробник форм.

Беремо STEP-файли оснащення (координати збірки, масштаб K) — силікон зовнішньої форми T15, силіконову чашку
сердечника T07, хребет із мостом T05, ребро «пальця» T04, каркаси T02a/T02b; для кришки — T16 і T09a/T09b.
Ставимо їх у положення лиття і заповнюємо бетоном увесь вільний простір до площини відкритої грані.
Отриманий виливок:
  1) порівнюємо з проєктною геометрією (у масштабі форми і після усадки 1/K та шліфування низу);
  2) міряємо на ньому резервуар, гніздо кришки, кишеню девайса, отвір, проріз, виїмку;
  3) перевіряємо посадку девайса, литої кришки і шнура;
  4) перевіряємо виймання з форм (кожну грань виливка — тим інструментом, що її формує);
  5) перевіряємо заповнення: зв'язність, найвужчі проміжки, «стелі», під якими лишається повітря;
  6) чутливість до зсуву сердечника в межах люфтів.

Усі числа — геометричні розрахунки з CAD; фізичних випробувань тут немає.
"""
import json
import math
import os
import time

import numpy as np
import cadquery as cq
from cadquery import Vector
import trimesh

from . import params as p
from . import parts as P
from . import molds as M
from .params import v
from .export import mesh_of

d = p.derived()
K = M.K
GA = M.GA
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STEP_DIR = os.path.join(ROOT, "tooling", "step")

G = 9.81
RHO_CONCRETE_MAX = 2.3e3   # кг/м³ — свіжий щільний мікробетон (верхня межа, як у mold_check)
_C = {}


# --------------------------------------------------------------------------
# завантаження оснащення
# --------------------------------------------------------------------------
TOOL_FILES = {
    "T15": "T15_ref_outer_silicone_mold_body", "T07": "T07_ref_cast_part_core_silicone",
    "T05": "T05_core_spine_bridge", "T04": "T04_finger_stiffener",
    "T02a": "T02a_body_frame_front", "T02b": "T02b_body_frame_back", "T01": "T01_body_master",
    "T16": "T16_ref_silicone_mold_lid", "T09a": "T09a_lid_frame_front", "T09b": "T09b_lid_frame_back",
    "T08": "T08_lid_master",
}


def tool(key):
    if key not in _C:
        sh = cq.importers.importStep(os.path.join(STEP_DIR, TOOL_FILES[key] + ".step"))
        vals = sh.vals()
        s = vals[0] if len(vals) == 1 else cq.Compound.makeCompound(vals)
        if isinstance(s, cq.Compound) and len(s.Solids()) == 1:
            s = s.Solids()[0]
        _C[key] = s
    return _C[key]


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, Vector(x0, y0, z0))


def _bb(s):
    b = s.BoundingBox()
    return [round(q, 2) for q in (b.xmin, b.xmax, b.ymin, b.ymax, b.zmin, b.zmax)]


def _vol(s):
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(s.wrapped, g, 1e-6)
    return g.Mass()


def _min_dist(a, b):
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    e = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    e.Perform()
    return e.Value() if e.IsDone() else float("nan")


def _common(a, b):
    try:
        r = a.intersect(b)
        return [s for s in r.Solids() if s.Volume() > 1e-4]
    except Exception:
        return None


# --------------------------------------------------------------------------
# де саме (людська назва зони за координатами виробу)
# --------------------------------------------------------------------------
def where(cx, cy, cz):
    H = v(p.H)
    if math.hypot(cx - d["cav_xc"], cy) < 7 and abs(cz - (d["z_ceil_c"] + v(p.FLARE_H))) < 4:
        return "стик шпильки отвору Ø8 з гніздом сердечника (розтруб)"
    if v(p.NFC_ON) and math.hypot(cx - v(p.NFC_X), cy - v(p.NFC_Y)) < 15 and cz > d["z_ceil_c"]:
        return "верхня плита: край кишені NFC-мітки ↔ воронка"
    if math.hypot(cx - d["cav_xc"], cy) < v(p.FUNNEL_D) / 2 + 1 and cz > d["z_ceil_c"]:
        return "воронка / отвір Ø8"
    if abs(cx - d["recess_x"]) < v(p.RECESS_W) / 2 + 3 and cy > v(p.D) / 2 - 9 and cz < d["recess_top"] + 3:
        return "виїмка язичка кришки (задня грань)"
    if abs(cx - d["pocket_cx"]) < d["pocket_x"] / 2 + 3 and abs(cy - d["pocket_cy"]) < d["pocket_y"] / 2 + 3 and cz > d["pocket_floor"] - 2:
        return "кишеня девайса"
    if cy < -v(p.D) / 2 + 3 and 20 < cz < 80:
        return "напис STICKBOX (фронт)"
    if cz > H - 3:
        return "верхня грань (знак NFC / кромки)"
    if cz < 1.0:
        return "низ (відкрита грань, шліфування)"
    if cz < d["z_sock"] + 3:
        return "гніздо кришки"
    return "резервуар / стінки"


def _diff_list(a, b, scale=1.0, vmin=0.05):
    """Солідні шматки a − b (об'єм ≥ vmin мм³) з місцем. scale — множник координат до системи виробу."""
    try:
        r = a.cut(b)
    except Exception as ex:
        return dict(error=str(ex))
    out = []
    for s in r.Solids():
        vol = s.Volume()
        if vol < vmin:
            continue
        b_ = s.BoundingBox()
        c = b_.center
        out.append(dict(volume_mm3=round(vol, 3), where=where(c.x * scale, c.y * scale, c.z * scale),
                        bbox=_bb(s), size=[round(b_.xlen, 2), round(b_.ylen, 2), round(b_.zlen, 2)]))
    out.sort(key=lambda q: -q["volume_mm3"])
    return dict(total_mm3=round(sum(q["volume_mm3"] for q in out), 3), pieces=out)


# --------------------------------------------------------------------------
# 1. Збірка оснащення
# --------------------------------------------------------------------------
def assembly_check():
    T15, T07, T05, T04 = tool("T15"), tool("T07"), tool("T05"), tool("T04")
    frames = [tool("T02a"), tool("T02b")]
    R = {"valid": {k: tool(k).isValid() for k in TOOL_FILES}}
    # контакти сердечника з зовнішньою формою — лише задумані (вкладка виїмки з натягом, телескопічний стик шпильки)
    cs = _common(T07, T15) or []
    contacts = []
    for s in cs:
        b_ = s.BoundingBox()
        c = b_.center
        contacts.append(dict(volume_mm3=round(s.Volume(), 3), where=where(c.x / K, c.y / K, c.z / K), bbox=_bb(s)))
    expected = ("виїмка язичка кришки (задня грань)", "стик шпильки отвору Ø8 з гніздом сердечника (розтруб)")
    R["core_outer_contacts"] = contacts
    R["core_outer_unexpected"] = [c_ for c_ in contacts if c_["where"] not in expected]
    pairs = dict(spine_outer=(T05, T15), spine_stiffener=(T05, T04), stiffener_core=(T04, T07), spine_core=(T05, T07),
                 frames_outer=(cq.Compound.makeCompound(frames), T15), frames_spine=(cq.Compound.makeCompound(frames), T05))
    R["overlap_mm3"] = {}
    for k, (a, b) in pairs.items():
        cc = _common(a, b)
        R["overlap_mm3"][k] = round(sum(s.Volume() for s in cc), 4) if cc is not None else None
    # міст лежить ніжками на торцях вушок каркаса
    R["bridge_to_frame_gap_mm"] = round(min(_min_dist(T05, f) for f in frames), 4)
    # співвісність отворів під шпильки M5: міст ↔ вушка каркаса
    def hole_centers(sh, r):
        out = []
        for f in sh.Faces():
            if f.geomType() == "CYLINDER":
                try:
                    rad = f._geomAdaptor().Cylinder().Radius()
                except Exception:
                    continue
                if abs(rad - r) < 0.02:
                    loc = f._geomAdaptor().Cylinder().Location()
                    out.append((round(loc.X(), 3), round(loc.Y(), 3)))
        return sorted(set(out))
    hb = hole_centers(T05, M.ROD_HOLE / 2)
    hf = sorted(set(hole_centers(frames[0], 5.3 / 2) + hole_centers(frames[1], 5.3 / 2)))
    mis = [min(math.hypot(a[0] - b[0], a[1] - b[1]) for b in hf) for a in hb] if hb and hf else []
    R["rod_holes"] = dict(bridge=hb, frame=hf, max_misalignment_mm=round(max(mis), 4) if mis else None)
    # покриття ребра силіконом (ребро не повинно торкатися бетону)
    return R


# --------------------------------------------------------------------------
# 2. Віртуальне лиття корпусу
# --------------------------------------------------------------------------
def cast_body():
    """Бетон = простір усередині силіконової форми, не зайнятий сердечником/хребтом/ребром, від відкритої грані."""
    if "cast_body" in _C:
        return _C["cast_body"]
    T15, T07, T05, T04 = tool("T15"), tool("T07"), tool("T05"), tool("T04")
    b = T15.BoundingBox()
    z_open = (d["zb"] - GA) * K
    box = _box(b.xmin - 1, b.xmax + 1, b.ymin - 1, b.ymax + 1, z_open, b.zmax)
    rest = box.cut(T15).cut(T04).cut(T07).cut(T05)
    # зовні силіконового блока — те, що торкається бічних стінок обвідної коробки, і гнізда штифтів T17 над майстром
    # (критерій без жорстких меж bbox: після тесселяції OCC розширює bbox на прогин сітки)
    def _outer(q):
        return (q.xmin < b.xmin - 0.5 or q.xmax > b.xmax + 0.5 or q.ymin < b.ymin - 0.5 or q.ymax > b.ymax + 0.5
                or q.zmin > v(p.H) * K + 0.5)
    within = [s for s in rest.Solids() if not _outer(s.BoundingBox())]
    outside = [s for s in rest.Solids() if _outer(s.BoundingBox())]
    # бетон тече лише від площини заливки: заповнюється тільки те, що з нею з'єднане; решта — замкнені порожнини оснащення
    inside = [s for s in within if s.BoundingBox().zmin < z_open + 1e-3]
    sealed = [s for s in within if s not in inside]
    inside.sort(key=lambda s: -s.Volume())
    _C["cast_body"] = (inside, outside, z_open)
    _C["sealed_body"] = sealed
    return _C["cast_body"]


def cast_lid():
    if "cast_lid" in _C:
        return _C["cast_lid"]
    T16 = tool("T16")
    sp = M.frame_spec("lid")
    x0, x1, y0, y1, zmn, zmx = sp["master_bb"]
    b = T16.BoundingBox()
    z_open = (d["zb"] - GA) * K
    box = _box(b.xmin - 1, b.xmax + 1, b.ymin - 1, b.ymax + 1, z_open, b.zmax)
    rest = box.cut(T16)
    inside = [s for s in rest.Solids() if (lambda q: q.xmin > x0 - 0.05 and q.xmax < x1 + 0.05 and q.ymin > y0 - 0.05 and q.ymax < y1 + 0.05 and q.zmax < zmx + 0.05)(s.BoundingBox())]
    inside.sort(key=lambda s: -s.Volume())
    _C["cast_lid"] = (inside, z_open)
    return _C["cast_lid"]


def finish(cast, z_cut=0.0):
    """Усадка (1/K) і шліфування відкритої грані до z = 0 (низ виробу)."""
    s = cast.scale(1.0 / K)
    return s.intersect(_box(-200, 200, -200, 200, z_cut, 300)).Solids()[0]


def casting_vs_design():
    inside, outside, z_open = cast_body()
    C = inside[0]
    E = M.S(P.body(height_extra=GA))           # проєктний корпус + припуск на шліфування, у масштабі форми
    sealed = _C.get("sealed_body", [])
    R = dict(concrete_solids=len(inside), concrete_volumes_mm3=[round(s.Volume(), 2) for s in inside],
             sealed_voids=[dict(volume_mm3=round(s.Volume(), 3), where=where(*(np.array(_bb(s)).reshape(3, 2).mean(axis=1) / K)),
                                bbox=_bb(s), overlap_with_product_mm3=round(sum(q.Volume() for q in (_common(s, E) or [])), 4))
                           for s in sealed],
             non_concrete_voids=[dict(volume_mm3=round(s.Volume(), 2), bbox=_bb(s)) for s in outside if s.Volume() < 1000],
             cast_volume_mm3=round(_vol(C), 2), design_volume_mm3=round(_vol(E), 2))
    R["extra_concrete_vs_design"] = _diff_list(C, E, 1 / K)    # є у виливку, немає в проєкті
    R["missing_concrete_vs_design"] = _diff_list(E, C, 1 / K)  # є в проєкті, немає у виливку
    F = finish(C)
    B = P.body()
    _C["F"], _C["B"] = F, B
    R["finished"] = dict(volume_ml=round(_vol(F) / 1000, 3), design_volume_ml=round(_vol(B) / 1000, 3),
                         valid=F.isValid(), bbox=_bb(F), design_bbox=_bb(B))
    R["finished"]["extra"] = _diff_list(F, B)
    R["finished"]["missing"] = _diff_list(B, F)
    return R


def surface_deviation(a, b, n=30000, seed=3):
    """Відхилення поверхні a від поверхні b: відстань від точок на a до найближчої точки b (мм)."""
    ma, mb = mesh_of(a, 0.015, 0.06), mesh_of(b, 0.015, 0.06)
    pts, _ = trimesh.sample.sample_surface(ma, n, seed=seed)
    dist = np.empty(len(pts))
    pq = trimesh.proximity.ProximityQuery(mb)
    for i in range(0, len(pts), 2000):
        _, dd, _ = pq.on_surface(pts[i:i + 2000])
        dist[i:i + 2000] = dd
    big = dist > 0.05
    clusters = {}
    for q, dd in zip(pts[big], dist[big]):
        w = where(*q)
        c = clusters.setdefault(w, dict(points=0, max_mm=0.0))
        c["points"] += 1
        c["max_mm"] = round(max(c["max_mm"], float(dd)), 3)
    return dict(samples=n, max_mm=round(float(dist.max()), 4), p99_mm=round(float(np.percentile(dist, 99)), 4),
                p999_mm=round(float(np.percentile(dist, 99.9)), 4), share_over_0p05=round(float(big.mean()), 5),
                clusters_over_0p05=clusters)


def extents(shape):
    """Габарити за сіткою (BoundingBox OCC для B-сплайнових граней буває завищений на десяті частки мм)."""
    m = mesh_of(shape, 0.01, 0.05)
    return m.bounds


# --------------------------------------------------------------------------
# 3. Вимірювання на виливку (після усадки і шліфування) — променями по сітці
# --------------------------------------------------------------------------
class Probe:
    def __init__(self, shape):
        self.m = mesh_of(shape, 0.01, 0.05)

    def hit(self, o, dvec):
        o = np.array([o], float)
        dv = np.array([dvec], float) / np.linalg.norm(dvec)
        loc, ir, _ = self.m.ray.intersects_location(o, dv, multiple_hits=False)
        return float(np.linalg.norm(loc[0] - o[0])) if len(loc) else float("nan")

    def span(self, o, axis):
        e = np.zeros(3)
        e[axis] = 1
        return self.hit(o, e) + self.hit(o, -e), self.hit(o, -e), self.hit(o, e)


def measure(F):
    pr = Probe(F)
    H = v(p.H)
    out = {}
    # гніздо кришки (прямокутне): ширина/глибина на кількох висотах
    sx, sy = -30.0, (d["Ly0"] + d["Ly1"]) / 2      # x = −30: поза виїмкою язичка (x = 0 ± 7.5)
    out["socket"] = []
    for z in (0.5, 5.5, 8.5, 13.5):
        w, _, _ = pr.span((sx, sy, z), 0)
        h, _, _ = pr.span((sx, sy, z), 1)
        out["socket"].append(dict(z=z, width_x=round(w, 3), depth_y=round(h, 3)))
    out["socket_roof_z"] = round(0.5 + pr.hit((d["Lx1"] - 15, d["Ly0"] + 15, 0.5), (0, 0, 1)), 3)   # під колонкою
    out["socket_design"] = dict(width_x=round(d["Lx1"] - d["Lx0"], 3), depth_y=round(d["Ly1"] - d["Ly0"], 3), roof_z=d["z_sock"])
    # резервуар: висота стелі, ширини на середині висоти
    out["reservoir"] = dict(
        ceiling_z_at_hole_axis_edge=round(20 + pr.hit((d["cav_xc"] + 10, 0, 20), (0, 0, 1)), 3),
        ceiling_z_main=round(20 + pr.hit((-40, 0, 20), (0, 0, 1)), 3),
        ceiling_z_arm=round(20 + pr.hit((d["Lxc"] + 12, d["Ly1"] - 15, 20), (0, 0, 1)), 3),
        width_x_main_z50=round(pr.span((-20, 0, 50), 0)[0], 3), depth_y_main_z50=round(pr.span((-20, 0, 50), 1)[0], 3),
        design_ceiling_c=d["z_ceil_c"], design_ceiling_edge=d["z_ceil_edge"])
    # кишеня девайса
    pcx, pcy = d["pocket_cx"], d["pocket_cy"]
    floor = H + 5 - pr.hit((pcx, pcy, H + 5), (0, 0, -1))
    out["pocket"] = dict(floor_z=round(floor, 3), depth=round(H - floor, 3), design_floor_z=d["pocket_floor"],
                         design_depth=round(H - d["pocket_floor"], 3), widths=[])
    for z in (floor + 3, (floor + H) / 2, H - 3):
        wx, _, _ = pr.span((pcx, pcy, z), 0)
        back = pr.hit((pcx, pcy, z), (0, 1, 0))
        # спереду по осі — проріз; міряємо поруч із ним (x + 5.5), де стінка кишені суцільна
        front = pr.hit((pcx + 5.5, pcy, z), (0, -1, 0))
        out["pocket"]["widths"].append(dict(z=round(z, 2), x=round(wx, 3), y_back_half=round(back, 3),
                                            y_front_half_at_x5p5=round(front, 3)))
    out["pocket"]["design"] = dict(x_top=round(d["pocket_x"], 3), y_top=round(d["pocket_y"], 3), floor_inset=round(d["pocket_inset_floor"], 3))
    # отвір Ø8: діаметри в 4 напрямках посередині прямої ділянки
    z_step = d["z_ceil_c"] + v(p.FLARE_H)
    z_t = H - v(p.FUNNEL_DEPTH)
    zh = (z_step + z_t) / 2
    o = (d["cav_xc"], 0, zh)
    dia = [pr.span(o, 0)[0], pr.span(o, 1)[0]]
    for a in (45, 135):
        e = np.array([math.cos(math.radians(a)), math.sin(math.radians(a)), 0])
        dia.append(pr.hit(o, e) + pr.hit(o, -e))
    out["hole"] = dict(z=round(zh, 2), diameters=[round(q, 3) for q in dia], design=v(p.HOLE_D),
                       straight_from_z=round(z_step, 2), straight_to_z=round(z_t, 2))
    # профіль низу отвору (стик зі сердечником): радіус отвору біля уступу
    out["hole_exit_profile"] = [dict(z=round(z, 3), radius=round(pr.hit((d["cav_xc"], 0, z), (1, 0, 0)), 3))
                                for z in (z_step + 0.3, z_step + 0.05, z_step - 0.05, z_step - 0.2, z_step - 0.4, z_step - 0.6, z_step - 0.9)]
    # проріз-вітрина
    zs = H - 10
    sw, _, _ = pr.span((pcx, -v(p.D) / 2 + 1.5, zs), 0)     # глибше за заокруглення R1 кромок на фронті
    out["slot"] = dict(z=zs, width=round(sw, 3), design=v(p.SLOT_W))
    # виїмка язичка (задня грань)
    rw, _, _ = pr.span((d["recess_x"], v(p.D) / 2 - 1.0, 2.0), 0)
    rt = 2.0 + pr.hit((d["recess_x"], v(p.D) / 2 - 1.0, 2.0), (0, 0, 1))
    out["notch"] = dict(width=round(rw, 3), top_z=round(rt, 3), design_width=v(p.RECESS_W), design_top=d["recess_top"])
    e = pr.m.bounds
    out["height"] = round(float(e[1][2] - e[0][2]), 3)
    out["footprint"] = [round(float(e[1][0] - e[0][0]), 3), round(float(e[1][1] - e[0][1]), 3)]
    return out


def reservoir_volume(F, LF):
    """Повітря над пробкою кришки (той самий метод, що analysis.run → cavity.net_volume_ml)."""
    env = P.prism_rrect(v(p.W) - 2, v(p.D) - 2, 12, d["z_plug_top"], d["z_ceil_c"] + 1)
    air = env.cut(F).cut(LF)
    sols = sorted(air.Solids(), key=lambda s: -s.Volume())
    return round(sols[0].Volume() / 1000, 3)


def water_volume(F, LF):
    """Об'єм води, якщо закритий виріб (кришка на місці) налити до краю горла воронки: внутрішня порожнина + отвір + воронка."""
    env = P.prism_rrect(v(p.W) - 0.2, v(p.D) - 0.2, 20, 0.05, v(p.H) - 0.01)
    air = env.cut(F).cut(LF)
    # частина, з'єднана з резервуаром (найбільша)
    sols = sorted(air.Solids(), key=lambda s: -s.Volume())
    return round(sols[0].Volume() / 1000, 3)


# --------------------------------------------------------------------------
# 4. Посадка: девайс, кришка, шнур
# --------------------------------------------------------------------------
def fits(F, LF):
    dev = P.device()
    felt = P.felt_pad()
    oring = P.oring()
    R = {}
    R["device"] = dict(interference_mm3=round(sum(s.Volume() for s in (_common(F, dev) or [])), 4),
                       min_clearance_mm=round(_min_dist(F, dev), 3),
                       protrusion_mm=round(float(extents(dev)[1][2] - extents(F)[1][2]), 3),
                       design_protrusion_mm=v(p.DEV_PROTRUDE),
                       felt_interference_mm3=round(sum(s.Volume() for s in (_common(F, felt) or [])), 4),
                       device_on_felt_gap_mm=round(_min_dist(felt, dev), 3))
    for r in (7.0, 7.5):
        dv = P.device(corner_r=r)
        R["device"][f"corner_R{r}"] = dict(interference_mm3=round(sum(s.Volume() for s in (_common(F, dv) or [])), 4),
                                           min_clearance_mm=round(_min_dist(F, dv), 3))
    R["lid"] = dict(interference_mm3=round(sum(s.Volume() for s in (_common(F, LF) or [])), 4),
                    min_clearance_mm=round(_min_dist(F, LF), 3),
                    lid_bottom_z=round(float(extents(LF)[0][2]), 3), body_bottom_z=round(float(extents(F)[0][2]), 3),
                    lid_top_z=round(float(extents(LF)[1][2]), 3))
    # зазор язичка у виїмці (по боках і зверху) — променями з язичка
    prL = Probe(LF)
    prF = Probe(F)
    t = P.lid_tab_dims()
    zt = d["zb"] + t["t_tip"] / 2
    y_mid = (t["y_ramp1"] + t["y_tip"]) / 2
    R["tab"] = dict(side_gap_left=round(prF.hit((t["x"] - t["w"] / 2 + 0.01, y_mid, zt), (-1, 0, 0)), 3),
                    side_gap_right=round(prF.hit((t["x"] + t["w"] / 2 - 0.01, y_mid, zt), (1, 0, 0)), 3),
                    top_gap_tip=round(prF.hit((t["x"], y_mid, d["zb"] + t["t_tip"] + 0.01), (0, 0, 1)), 3),
                    tip_inset_from_back_face=round(v(p.D) / 2 - (y_mid + prL.hit((t["x"], y_mid, zt), (0, 1, 0))), 3))
    # шнур: глибина залозу = відстань від дна канавки литої кришки до стінки гнізда литого корпусу (на висоті середини канавки)
    gz = (d["groove_z0"] + d["groove_z1"]) / 2
    tn = math.tan(math.radians(v(p.DRAFT_CAV)))
    ob = (gz - d["zb"]) * tn + v(p.PLUG_GAP) + d["groove_depth"]
    poly = P.S_polygon(ob, gz)
    pts = [poly.exterior.interpolate(t_, normalized=True) for t_ in np.linspace(0, 1, 200, endpoint=False)]
    cx_, cy_ = poly.centroid.x, poly.centroid.y
    # на прямих ділянках прямокутника — промінь по нормалі до стінки (кути R12 пропускаємо)
    gl_n = []
    for q in pts:
        x, y = q.x, q.y
        # нормаль: для прямих ділянок прямокутника — вісь; для кутів — радіально від центру кута
        hx = (d["Lx1"] - d["Lx0"]) / 2
        hy = (d["Ly1"] - d["Ly0"]) / 2
        if abs(x - cx_) < hx - 15:
            nvec = (0, 1 if y > cy_ else -1, 0)
        elif abs(y - cy_) < hy - 15:
            nvec = (1 if x > cx_ else -1, 0, 0)
        else:
            continue
        o_ = (x - nvec[0] * 0.3, y - nvec[1] * 0.3, gz)
        a_ = prL.hit(o_, nvec)
        b_ = prF.hit(o_, nvec)
        if not (math.isnan(a_) or math.isnan(b_)):
            gl_n.append(b_ - a_)
    gl_n = np.array(gl_n)
    cs = v(p.ORING_CS)
    R["seal"] = dict(gland_depth_min=round(float(gl_n.min()), 3), gland_depth_max=round(float(gl_n.max()), 3),
                     squeeze_pct_min=round((cs - gl_n.max()) / cs * 100, 1), squeeze_pct_max=round((cs - gl_n.min()) / cs * 100, 1),
                     design_gland=d["gland_depth"], design_squeeze_pct=round(d["squeeze_pct"], 1), samples=int(len(gl_n)),
                     oring_vs_body_overlap_mm3=round(sum(s.Volume() for s in (_common(F, oring) or [])), 3),
                     oring_vs_lid_overlap_mm3=round(sum(s.Volume() for s in (_common(LF, oring) or [])), 3))
    return R


# --------------------------------------------------------------------------
# 5. Виймання з форм: кожна грань виливка — тим інструментом, що її формує
# --------------------------------------------------------------------------
def _sample_tree(shape, n):
    from scipy.spatial import cKDTree
    m = mesh_of(shape, 0.02, 0.1)
    pts, _ = trimesh.sample.sample_surface(m, n, seed=5)
    return cKDTree(np.vstack([pts, m.vertices]))


def forming_map(C, tools, z_open, n_tool=600000):
    """Для кожної грані сітки виливка — інструмент, до поверхні якого вона найближча (той, що її формує)."""
    m = mesh_of(C, 0.02, 0.08)
    c, nrm, area = m.triangles_center, m.face_normals, m.area_faces
    names = list(tools)
    dist = np.full((len(c), len(names)), np.inf)
    for j, k in enumerate(names):
        tr = _sample_tree(tools[k], n_tool)
        dist[:, j], _ = tr.query(c, k=1)
    lab = np.array(names, dtype=object)[np.argmin(dist, axis=1)]
    lab[np.abs(c[:, 2] - z_open) < 0.02] = "open"
    return m, c, nrm, area, lab, dist.min(axis=1)


def demold(fm, pull):
    m, c, nrm, area, lab, _ = fm
    R = {}
    for k, dvec in pull.items():
        msk = np.where(lab == k)[0]
        if not len(msk):
            continue
        orig = c[msk] + nrm[msk] * 0.03
        hit = np.zeros(len(msk), bool)
        for i in range(0, len(msk), 20000):
            sl = slice(i, i + 20000)
            hit[sl] = m.ray.intersects_any(orig[sl], np.tile(dvec, (len(orig[sl]), 1)))
        zones = {}
        for q, a_ in zip(c[msk][hit], area[msk][hit]):
            w = where(*(q / K))
            zones[w] = round(zones.get(w, 0.0) + float(a_) / K ** 2, 2)
        R[k] = dict(faces=int(len(msk)), area_mm2=round(float(area[msk].sum()) / K ** 2, 1), blocked_faces=int(hit.sum()),
                    blocked_area_mm2=round(float(area[msk][hit].sum()) / K ** 2, 3), blocked_by_zone=zones)
    return R


def trap_where(q):
    """Назва «стелі» за положенням кластера граней (координати виробу)."""
    z0, z1 = q[:, 2].min(), q[:, 2].max()
    x0, x1, y0, y1 = q[:, 0].min(), q[:, 0].max(), q[:, 1].min(), q[:, 1].max()
    if v(p.NFC_ON) and abs(q[:, 0].mean() - v(p.NFC_X)) < 4 and abs(q[:, 1].mean() - v(p.NFC_Y)) < 4 and z0 > d["z_ceil_c"] + 1:
        return "торець кишені NFC-мітки (стеля над міткою)"
    if abs(z1 - d["z_sock"]) < 0.05 and abs(z0 - d["z_sock"]) < 0.05:
        return "низ колонки тримача (стеля гнізда кришки, z 14.5)"
    if z1 <= d["recess_top"] + 0.05 and y0 > v(p.D) / 2 - 10:
        return "стеля виїмки язичка (z 5)"
    if z0 > d["z_ceil_edge"] - 1.0 and z1 <= d["z_ceil_c"] + 0.05:
        return "купол резервуара" if (x1 - x0) > 30 and (y1 - y0) > 30 else "кромка купола біля стінки (R стелі)"
    if y1 < -v(p.D) / 2 + 3:
        return "напис STICKBOX (уступи літер)"
    return where(*q.mean(axis=0))


def air_traps(fm, cos_lim=0.966):
    """«Стелі» в положенні лиття: грані бетону, звернені вниз у координатах виробу (n_z < −cos 15°), окрім відкритої грані.
    Форма стоїть догори дном → такі грані дивляться вгору в бетоні; бульбашки, що спливають, збираються під ними."""
    m, c, nrm, area, lab, _ = fm
    sel = np.where((nrm[:, 2] < -cos_lim) & (lab != "open"))[0]
    if not len(sel):
        return []
    adj = m.face_adjacency
    s_set = np.zeros(len(c), bool)
    s_set[sel] = True
    e = adj[s_set[adj[:, 0]] & s_set[adj[:, 1]]]
    comps = trimesh.graph.connected_components(e, nodes=sel, min_len=1)
    out = []
    for comp in comps:
        a_ = float(area[comp].sum()) / K ** 2
        if a_ < 3.0:
            continue
        q = c[comp] / K
        slope = np.degrees(np.arccos(np.clip(-nrm[comp, 2], -1, 1)))
        tools_ = {}
        for t_ in lab[comp]:
            tools_[t_] = tools_.get(t_, 0) + 1
        out.append(dict(area_mm2=round(a_, 1), where=trap_where(q), z_product=[round(float(q[:, 2].min()), 2), round(float(q[:, 2].max()), 2)],
                        x=[round(float(q[:, 0].min()), 1), round(float(q[:, 0].max()), 1)],
                        y=[round(float(q[:, 1].min()), 1), round(float(q[:, 1].max()), 1)],
                        slope_deg_min=round(float(slope.min()), 2), slope_deg_mean=round(float(np.average(slope, weights=area[comp])), 2),
                        formed_by=max(tools_, key=tools_.get)))
    out.sort(key=lambda r: -r["area_mm2"])
    return out


# --------------------------------------------------------------------------
# 6. Заповнення: найвужчі проміжки між інструментами, спливання сердечника, чутливість до зсуву
# --------------------------------------------------------------------------
def gaps_core_outer(shift=(0.0, 0.0, 0.0), n=400000):
    """Найвужчий проміжок, який заповнює бетон між сердечником (T07) і зовнішньою формою (T15) / ребром (T04),
    без зон задуманого контакту (вкладка виїмки, стик шпильки). shift — зсув сердечника, мм (масштаб форми)."""
    key = ("gtrees", n)
    if key not in _C:
        from scipy.spatial import cKDTree
        mo = mesh_of(cq.Compound.makeCompound([tool("T15"), tool("T04")]), 0.02, 0.1)
        po, _ = trimesh.sample.sample_surface(mo, n, seed=7)
        mc = mesh_of(tool("T07"), 0.02, 0.1)
        pc, fc = trimesh.sample.sample_surface(mc, n // 2, seed=8)
        ncore = mc.face_normals[fc]          # назовні сердечника = у бетон
        inside, _, _ = cast_body()
        mC = mesh_of(inside[0], 0.02, 0.1)
        ps, fi = trimesh.sample.sample_surface(mC, 800000, seed=9)
        _C[key] = (cKDTree(po), po, (pc, ncore), (cKDTree(ps), mC.face_normals[fi]))
    tr, po, (pc, ncore), (trC, nC) = _C[key]
    q = pc + np.array(shift)
    dd, ii = tr.query(q, k=1)
    pp = q / K
    excl = np.array([where(*r) in ("виїмка язичка кришки (задня грань)", "стик шпильки отвору Ø8 з гніздом сердечника (розтруб)")
                     for r in pp])
    excl |= pp[:, 2] < d["zb"] + 0.3      # шийка сердечника біля відкритої грані (вище — бетону немає)
    dd = np.where(excl, np.inf, dd)
    # лише проміжки, що проходять крізь бетон: середина відрізка «сердечник → форма» — у виливку
    cand = np.where(dd < 8.0 * K)[0]
    mid = (q[cand] + po[ii[cand]]) / 2 - np.array(shift) / 2
    # «усередині бетону»: середина лежить з внутрішнього боку найближчої точки поверхні виливка (до неї ≥ 1 мм — вибірка 0.2 мм)
    _, jj = trC.query(mid, k=1)
    sp_ = trC.data[jj]
    inc = np.einsum("ij,ij->i", mid - sp_, nC[jj]) < 0
    # товщина «поперек стінки»: відрізок до протилежної поверхні майже по нормалі сердечника (≤ 35°); кути й уступи —
    # не стінки (відстань від купола до кромки шпильки біля отвору — це кут суцільної верхньої плити, а не вузький канал)
    seg = po[ii[cand]] - q[cand]
    seg /= np.linalg.norm(seg, axis=1)[:, None] + 1e-12
    along = np.einsum("ij,ij->i", seg, ncore[cand]) > math.cos(math.radians(35))
    ok = np.full(len(dd), False)
    ok[cand[inc & along]] = True
    dd = np.where(ok, dd, np.inf)
    i = int(np.argmin(dd))
    z_ = pp[i][2]
    zl = v(p.LEADIN_LEN) + 0.5            # заходна фаска шнура біля площини заливки
    dd2 = np.where(pp[:, 2] > zl, dd, np.inf)
    j = int(np.argmin(dd2))
    return dict(min_gap_mm=round(float(dd[i]) / K, 3), at=[round(float(r), 1) for r in pp[i]], where=where(*pp[i]),
                lead_in_zone=bool(z_ < zl),
                min_gap_above_lead_in_mm=round(float(dd2[j]) / K, 3), at_above=[round(float(r), 1) for r in pp[j]],
                where_above=where(*pp[j]))


def core_uplift():
    """Виштовхувальна сила бетону на сердечник (без ваги сердечника — із запасом) і на «палець» форми."""
    inside, outside, z_open = cast_body()
    T07, T05 = tool("T07"), tool("T05")
    cut = _box(-200, 200, -200, 200, z_open, 300)
    v_core = sum(s.Volume() for s in T07.fuse(T05).intersect(cut).Solids())
    F_core = RHO_CONCRETE_MAX * G * v_core * 1e-9
    pk_vol = P._pocket_tool().intersect(_box(-200, 200, -200, 200, 0, v(p.H))).Volume() * K ** 3
    F_f = RHO_CONCRETE_MAX * G * pk_vol * 1e-9
    return dict(core_displaced_ml=round(v_core / 1000, 1), core_uplift_N=round(F_core, 1), per_rod_N=round(F_core / 4, 1),
                rods="4 × M5 (переріз за різьбою 14.2 мм², клас 4.6: Rm 400 МПа → ≈5.7 кН на шпильку)",
                finger_uplift_N=round(F_f, 2), rho_kg_m3=RHO_CONCRETE_MAX)


def shift_sensitivity(delta=0.3):
    """Сердечник центрується мостом на 4 шпильках M5 у отворах Ø5.3 (мосту і вушок): люфт до 0.15 + 0.15 мм."""
    out = [dict(shift=[0, 0, 0], **gaps_core_outer())]
    for a in range(0, 360, 45):
        s = (delta * math.cos(math.radians(a)), delta * math.sin(math.radians(a)), 0.0)
        r = gaps_core_outer(s)
        out.append(dict(shift=[round(q, 3) for q in s], **r))
    # натяг вкладки виїмки при зсуві від задньої стінки
    return dict(cases=out, worst_min_gap_mm=min(c["min_gap_mm"] for c in out),
                worst_above_lead_in_mm=min(c["min_gap_above_lead_in_mm"] for c in out),
                tab_preload_at_worst_mm=round(M.TAB_PRELOAD - delta, 2))


# --------------------------------------------------------------------------
# 7. Кришка: лиття з T16, порівняння і виймання
# --------------------------------------------------------------------------
def lid_casting():
    inside, z_open = cast_lid()
    LC = inside[0]
    E = M.S(P.lid(product=False, grind_allow=GA))
    R = dict(concrete_solids=len(inside), cast_volume_mm3=round(_vol(LC), 2), design_volume_mm3=round(_vol(E), 2))
    R["extra_vs_design"] = _diff_list(LC, E, 1 / K)
    R["missing_vs_design"] = _diff_list(E, LC, 1 / K)
    LF = finish(LC)
    LB = P.lid()
    _C["LF"] = LF
    R["finished"] = dict(volume_ml=round(_vol(LF) / 1000, 3), design_volume_ml=round(_vol(LB) / 1000, 3), valid=LF.isValid())
    R["finished"]["extra"] = _diff_list(LF, LB)
    R["finished"]["missing"] = _diff_list(LB, LF)
    fm = forming_map(LC, {"T16": tool("T16")}, z_open, n_tool=400000)
    dm = demold(fm, {"T16": np.array([0, 0, 1.0])})
    # заблоковане — валик канавки шнура (задумане податливе піднутрення 2 мм) чи інше
    m, c, nrm, area, lab, _ = fm
    msk = np.where(lab == "T16")[0]
    orig = c[msk] + nrm[msk] * 0.03
    hit = m.ray.intersects_any(orig, np.tile([0, 0, 1.0], (len(orig), 1)))
    q = c[msk][hit] / K
    g0, g1 = d["groove_z0"], d["groove_z1"]
    in_groove = (q[:, 2] > g0 - 0.6) & (q[:, 2] < g1 + 0.6)
    dm["T16"]["blocked_in_cord_groove_mm2"] = round(float(area[msk][hit][in_groove].sum()) / K ** 2, 2)
    dm["T16"]["blocked_elsewhere_mm2"] = round(float(area[msk][hit][~in_groove].sum()) / K ** 2, 3)
    R["demold"] = dm
    R["air_traps"] = air_traps(fm)
    return R


# --------------------------------------------------------------------------
def run(write_to=None, verbose=True):
    t0 = time.time()
    log = (lambda *a: print(f"[{time.time() - t0:6.1f}s]", *a, flush=True)) if verbose else (lambda *a: None)
    R = {}
    R["assembly"] = assembly_check(); log("assembly", R["assembly"]["core_outer_unexpected"], R["assembly"]["overlap_mm3"])
    R["body_casting"] = casting_vs_design(); log("body cast", R["body_casting"]["concrete_solids"], R["body_casting"]["finished"]["extra"]["total_mm3"], R["body_casting"]["finished"]["missing"]["total_mm3"])
    F, B = _C["F"], _C["B"]
    R["lid_casting"] = lid_casting(); LF = _C["LF"]; log("lid cast", R["lid_casting"]["finished"]["extra"]["total_mm3"], R["lid_casting"]["finished"]["missing"]["total_mm3"])
    R["deviation_body"] = dict(cast_to_design=surface_deviation(F, B), design_to_cast=surface_deviation(B, F)); log("deviation body")
    R["deviation_lid"] = dict(cast_to_design=surface_deviation(LF, P.lid()), design_to_cast=surface_deviation(P.lid(), LF)); log("deviation lid")
    R["measure"] = measure(F); log("measure")
    R["reservoir_ml"] = dict(cast=reservoir_volume(F, LF), design=reservoir_volume(B, P.lid()))
    R["water_fill_ml"] = dict(cast=water_volume(F, LF), design=water_volume(B, P.lid())); log("volumes", R["reservoir_ml"], R["water_fill_ml"])
    R["fit"] = fits(F, LF); log("fit")
    inside, outside, z_open = cast_body()
    fm = forming_map(inside[0], {"T15": tool("T15"), "T07": tool("T07"), "T05": tool("T05"), "T04": tool("T04")}, z_open)
    lab = fm[4]
    R["forming"] = {k: round(float(fm[3][lab == k].sum()) / K ** 2, 1) for k in ("T15", "T07", "T05", "T04", "open")}
    R["forming_T04_min_dist_mm"] = round(_min_dist(inside[0], tool("T04")) / K, 3)
    R["demold_body"] = demold(fm, {"T15": np.array([0, 0, 1.0]), "T07": np.array([0, 0, -1.0]), "T05": np.array([0, 0, -1.0])}); log("demold")
    # напис на вертикальній фронтальній стінці: після розкриття каркаса силікон відгортають від фронту (−y)
    m_, c_, n_, a_, lab_, _ = fm
    lg = np.where((lab_ == "T15") & (c_[:, 1] / K < -v(p.D) / 2 + 3) & (c_[:, 2] / K > 20) & (c_[:, 2] / K < 80))[0]
    hit = m_.ray.intersects_any(c_[lg] + n_[lg] * 0.03, np.tile([0, -1.0, 0], (len(lg), 1)))
    R["demold_body"]["T15_front_peel"] = dict(faces=int(len(lg)), area_mm2=round(float(a_[lg].sum()) / K ** 2, 1),
                                              blocked_area_mm2=round(float(a_[lg][hit].sum()) / K ** 2, 3))
    R["air_traps_body"] = air_traps(fm); log("air traps", len(R["air_traps_body"]))
    del fm, m_, c_, n_, a_, lab_
    import gc
    gc.collect()
    R["uplift"] = core_uplift()
    R["shift"] = shift_sensitivity(); log("shift")
    if write_to:
        with open(write_to, "w") as f:
            json.dump(R, f, indent=1, ensure_ascii=False, default=float)
    return R


if __name__ == "__main__":
    import sys
    r = run(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps(r, indent=1, ensure_ascii=False, default=float)[:20000])
