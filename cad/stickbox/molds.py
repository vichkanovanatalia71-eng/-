"""
STICKBOX 01 Monolith — оснащення для лиття декоративного бетону в силіконові форми.

Усі тіла будуються в координатах виробу (z — вгору в положенні використання),
масштабовані на SHRINK_COMP (компенсація усадки бетону + силікону) там, де це
формотворча геометрія. Друковані (жорсткі) деталі оснащення не масштабуються,
крім поверхонь, що формують виріб.

Система лиття корпусу («догори дном»):
  1. Майстер-модель зовнішньої форми (BM) — зовнішня поверхня корпусу без порожнини.
     Стоїть низом на базовій плиті; силікон (платиновий, Shore A 25–30) заливається зверху
     в жорстку гільзу. Після полімеризації блок перевертають — отвір форми = низ корпусу.
  2. Сердечник порожнини — силіконова «чашка» на знімному жорсткому хребті з мостом.
     Міст центрується штифтами в тих самих отворах гільзи, що й базова плита →
     єдиний ланцюг базування майстер → плита → гільза → міст → сердечник.
  3. Ребро жорсткості «пальця» кишені девайса — друкована вставка в силікон.
  4. Другий виступ сердечника (на тому ж мосту) формує полегшувальну порожнину правої колонки.
Кришка: майстер стоїть фланцем на плиті, пробкою вгору → форма «пробкою донизу».
Вставка девайса: жорстка друкована форма (чашка + сердечник + кришка-центратор).
"""
import math
import cadquery as cq
from cadquery import Vector

from . import params as p
from .params import v
from . import parts as P

d = p.derived()
K = v(p.SHRINK_COMP)
GA = v(p.GRIND_ALLOW)

SIL_WALL = 15.0      # товщина силікону зовнішньої форми корпусу (боки та дно)
SLEEVE_T = 5.0       # стінка друкованої гільзи
LUG = 14.0           # кутові вушка гільзи
PIN_D = 5.0          # штифти базування
PIN_HOLE = 5.3
BRIDGE_RAISE = 4.0   # міст піднятий над відкритою гранню (доступ для загладжування)
BRIDGE_T = 5.0
CORE_SKIN = 8.0      # товщина силіконової «чашки» сердечника
PRELOAD = 0.3        # (застаріле) натяг торцевих стиків
TAB_PRELOAD = 1.0    # натяг вкладки виїмки в стінку зовнішньої форми (податливий стик, аудит C3)
ROD_HOLE = 5.3       # наскрізні отвори під стяжні шпильки M5 (аудит C4)


def _rrp(c, w, h, r, z0, ext):
    cx, cy = c
    return P.prism_rrect(w, h, r, z0, z0 + ext, cx=cx, cy=cy)


def S(shape):
    """Масштаб формотворчої геометрії відносно початку координат (центр опорної площини)."""
    return shape.scale(K)


def box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, Vector(x0, y0, z0))


def cyl(r, z0, z1, x, y):
    return cq.Solid.makeCylinder(r, z1 - z0, Vector(x, y, z0))


# ==========================================================================
# 1. Майстер-модель зовнішньої форми корпусу
# ==========================================================================
MASTER_PINS = [(-40.0, -30.0), (-40.0, 30.0), (40.0, 25.0)]


def body_master():
    m = P.body(product=False, with_cavity=False, height_extra=GA, funnel_flare=False, pin_extra=P.SOCKET_DEPTH)
    # базувальні отвори в нижній (відкритій) грані — не впливають на форму
    for (x, y) in MASTER_PINS:
        m = m.cut(cyl(3.1, -GA - 1, -GA + 6, x, y))
    return S(m)


def _sleeve_dims():
    bb = body_master().BoundingBox()
    ix0, ix1 = bb.xmin - SIL_WALL, bb.xmax + SIL_WALL
    iy0, iy1 = bb.ymin - SIL_WALL, bb.ymax + SIL_WALL
    z0 = bb.zmin
    z1 = bb.zmax + SIL_WALL
    return ix0, ix1, iy0, iy1, z0, z1


def lug_positions():
    ix0, ix1, iy0, iy1, _, _ = _sleeve_dims()
    o = SLEEVE_T + LUG / 2
    return [(ix0 - o + LUG / 2 - 1, iy0 - o + LUG / 2 - 1), (ix1 + o - LUG / 2 + 1, iy0 - o + LUG / 2 - 1),
            (ix1 + o - LUG / 2 + 1, iy1 + o - LUG / 2 + 1), (ix0 - o + LUG / 2 - 1, iy1 + o - LUG / 2 + 1)]


def body_sleeve():
    """Гільза (материнська форма): відкрита з обох торців, кутові вушка з наскрізними отворами Ø5.3."""
    ix0, ix1, iy0, iy1, z0, z1 = _sleeve_dims()
    t = SLEEVE_T
    outer = _rrp(((ix0 + ix1) / 2, (iy0 + iy1) / 2), ix1 - ix0 + 2 * t, iy1 - iy0 + 2 * t, 8, z0, z1 - z0)
    inner = _rrp(((ix0 + ix1) / 2, (iy0 + iy1) / 2), ix1 - ix0, iy1 - iy0, 6, z0 - 1, z1 - z0 + 2)
    s = outer.cut(inner)
    for (x, y) in lug_positions():
        lug = cyl(LUG / 2, z0, z1, x, y)
        web = box(min(x, (ix0 + ix1) / 2 + (x - (ix0 + ix1) / 2) * 0.9), max(x, (ix0 + ix1) / 2 + (x - (ix0 + ix1) / 2) * 0.9),
                  min(y, (iy0 + iy1) / 2 + (y - (iy0 + iy1) / 2) * 0.9), max(y, (iy0 + iy1) / 2 + (y - (iy0 + iy1) / 2) * 0.9), z0, z1)
        s = s.fuse(lug).fuse(web.cut(inner))
        s = s.cut(cyl(PIN_HOLE / 2, z0 - 1, z1 + 1, x, y))
    # вікна для полегшення та огляду не робимо — стінка тримає силікон від розпирання
    return s.clean()


def body_base_plate():
    """Базова плита заливки силікону: штифти у вушка гільзи + 3 штифти центрування майстра."""
    ix0, ix1, iy0, iy1, z0, z1 = _sleeve_dims()
    t = 6.0
    m = LUG + SLEEVE_T + 2
    plate = _rrp(((ix0 + ix1) / 2, (iy0 + iy1) / 2), ix1 - ix0 + 2 * m, iy1 - iy0 + 2 * m, 10, z0 - t, t)
    for (x, y) in lug_positions():
        plate = plate.fuse(cyl(PIN_D / 2 - 0.1, z0, z0 + 8, x, y))
    for (x, y) in MASTER_PINS:
        plate = plate.fuse(cyl(3.0 * K - 0.15, z0, z0 + 5, x * K, y * K))
    return plate.clean()


def finger_stiffener():
    """Жорстка вставка в силіконовий «палець» кишені (захист від прогину при вібрації).
    Покриття силіконом ≥4 мм; отвори Ø5 для механічного зчеплення; фланець врівень з дном форми."""
    cx, cy = d["pocket_cx"] * K, d["pocket_cy"] * K
    H = v(p.H) * K
    cover = 4.5
    wx = d["pocket_x"] * K - 2 * cover - 2 * d["pocket_inset_floor"]
    wy = d["pocket_y"] * K - 2 * cover - 2 * d["pocket_inset_floor"]
    z0 = d["pocket_floor"] * K + cover
    z_top = H + SIL_WALL
    bar = cq.Workplane("XY", origin=(cx, cy, z0)).slot2D(wy, wx, angle=90).extrude(z_top - z0).val()
    for z in range(int(z0 + 8), int(H - 5), 12):
        bar = bar.cut(cq.Solid.makeCylinder(2.5, wx + 4, Vector(cx - wx / 2 - 2, cy, z), Vector(1, 0, 0)))
    flange = box(cx - 9, cx + 9, cy - 24, cy + 24, z_top - 3, z_top)
    st = bar.fuse(flange)
    for dy in (-18, 18):  # отвори під штифти тримача T17 (аудит M7)
        st = st.cut(cyl(1.6, z_top - 4, z_top + 1, cx, cy + dy))
    return st.clean()


def stiffener_holder():
    """T17: тримач ребра «пальця» під час заливки силікону — лежить на верхньому торці гільзи,
    штифти Ø4.9 у вушка гільзи, 2 штифти Ø3 у фланець ребра (XY та висота задані однозначно)."""
    _, _, _, _, z0, z1 = _sleeve_dims()
    cx, cy = d["pocket_cx"] * K, d["pocket_cy"] * K
    lugs = lug_positions()
    (xa, ya), (xb, yb) = lugs[1], lugs[2]
    t = 4.0
    bar = box(xa - 7, xa + 7, ya, yb, z1, z1 + t)
    arm = box(cx - 9, xa, cy - 9, cy + 9, z1, z1 + t)
    pad = box(cx - 11, cx + 11, cy - 26, cy + 26, z1, z1 + t)
    h = bar.fuse(arm).fuse(pad)
    for (x, y) in ((xa, ya), (xb, yb)):
        h = h.fuse(cyl(PIN_D / 2 - 0.1, z1 - 8, z1 + 0.01, x, y))
    for dy in (-18, 18):
        h = h.fuse(cyl(1.5, z1 - 3, z1 + 0.01, cx, cy + dy))
    return h.clean()


# ==========================================================================
# 2. Сердечник порожнини
# ==========================================================================
def _recess_tab(z_from):
    """Вкладка, що формує пальцеву виїмку (від стінки форми до порожнини) + натяг.
    v2.7: виїмка на задній грані, по осі кришки."""
    w, r = v(p.RECESS_W), v(p.RECESS_R)
    top = d["recess_top"]
    s_ = 1 if v(p.RECESS_SIDE) > 0 else -1
    y0 = s_ * (v(p.D) / 2 + TAB_PRELOAD)
    y1 = (d["cav_y1"] - v(p.R_CAV)) if s_ > 0 else (d["cav_y0"] + v(p.R_CAV))
    prof = (cq.Workplane("XZ", origin=(d["recess_x"], y0, 0))
            .moveTo(-w / 2, z_from).lineTo(w / 2, z_from).lineTo(w / 2, top - r)
            .radiusArc((w / 2 - r, top), -r)
            .lineTo(-w / 2 + r, top)
            .radiusArc((-w / 2, top - r), -r)
            .close())
    return prof.extrude(-(y1 - y0)).val()


def core_outer(neck=BRIDGE_RAISE):
    """Повна формотворча поверхня сердечника (до масштабування)."""
    z_open = -GA
    cav = P._cavity_tool()
    cut = box(-200, 200, -200, 200, z_open, 200)
    core = cav.intersect(cut)
    core = core.fuse(P.flare_boss())
    core = core.fuse(_recess_tab(z_open - neck))
    xc = d["cav_xc"]
    neck_s = P.prism_rrect(d["reb"], d["reb"], d["r_reb"], z_open - neck, z_open + 0.01, cx=xc)
    core = core.fuse(neck_s)
    if v(p.RELIEF_ON):
        core = core.fuse(relief_core_outer(neck))
    return core.clean()


def _relief_xywh():
    w = d["rel_x1"] - d["rel_x0"]
    h = d["rel_y1"] - d["rel_y0"]
    return (d["rel_x0"] + d["rel_x1"]) / 2, (d["rel_y0"] + d["rel_y1"]) / 2, w, h


def relief_core_outer(neck=BRIDGE_RAISE):
    """Другий виступ сердечника — формує полегшувальну порожнину правої колонки."""
    z_open = -GA
    rel = P._relief_tool(GA).intersect(box(-200, 200, -200, 200, z_open, 200))
    top = max(rel.Faces(), key=lambda f: f.Center().z)
    rel = rel.fillet(4.0, top.Edges())
    cx, cy, w, h = _relief_xywh()
    if v(p.RL_ON):   # v2.5: шийка по контуру ребейту кришечки
        neck_s = P.prism_rrect(d["rl_reb_w"], d["rl_reb_h"], d["rl_r_reb"], z_open - neck, z_open + 0.01, cx=cx, cy=cy)
    else:
        neck_s = P.prism_rrect(w, h, v(p.RELIEF_R), z_open - neck, z_open + 0.01, cx=cx, cy=cy)
    rel = rel.fuse(neck_s)
    if v(p.RL_ON) and v(p.RL_RECESS_ON):   # v2.7: вкладка виїмки кришечки на правій грані + натяг у стінку форми
        wr, rr, top = v(p.RL_RECESS_W), v(p.RL_RECESS_R), d["rl_recess_top"]
        x0 = v(p.W) / 2 + TAB_PRELOAD
        x1 = d["rel_x1"] - 2.0
        z_from = z_open - neck
        tab = (cq.Workplane("YZ", origin=(x0, cy, 0))
               .moveTo(-wr / 2, z_from).lineTo(wr / 2, z_from).lineTo(wr / 2, top - rr)
               .radiusArc((wr / 2 - rr, top), -rr)
               .lineTo(-wr / 2 + rr, top)
               .radiusArc((-wr / 2, top - rr), -rr)
               .close().extrude(-(x0 - x1)).val())
        rel = rel.fuse(tab)
    return rel.clean()


def core_spine_and_bridge():
    """Жорсткий хребет (знімний, ухил 2°) + міст із ніжками та штифтами у вушка гільзи."""
    xc = d["cav_xc"] * K
    z_open = -GA * K
    zb1 = z_open - BRIDGE_RAISE          # низ мосту
    zb0 = zb1 - BRIDGE_T
    inset = CORE_SKIN
    side0 = v(p.CAV) * K - 2 * inset
    z_top = (d["z_ceil_edge"] - CORE_SKIN) * K
    spine = (cq.Workplane("XY", origin=(xc, 0, zb1 - 0.01)).sketch().rect(side0, side0).vertices().fillet(8)
             .finalize().extrude(z_top - zb1, taper=2.0).val())
    # плита мосту: лише над шийкою сердечника (−1 мм на сторону) — бортик лишається відкритим (аудит M2)
    neck_w = d["reb"] * K - 2
    plate = P.prism_rrect(neck_w, neck_w, d["r_reb"] * K - 1, zb0, zb1, cx=xc)
    for sgn in (-1, 1):   # вушка під центрувальні штифти форми сердечника (поза шийкою)
        plate = plate.fuse(cyl(6.0, zb0, zb1, xc + sgn * CORE_PIN_X, 0))
    for (x, y) in lug_positions():
        ang = math.atan2(y - 0, x - xc)
        L = math.hypot(x - xc, y)
        arm = (cq.Workplane("XY", origin=(xc, 0, zb0)).transformed(rotate=(0, 0, math.degrees(ang)))
               .center(L / 2, 0).rect(L, 14).extrude(BRIDGE_T).val())
        plate = plate.fuse(arm).fuse(cyl(9, zb0, zb1, x, y))
        plate = plate.fuse(cyl(6, zb1 - 0.01, z_open, x, y))            # ніжка до торця гільзи
    if v(p.RELIEF_ON):
        rcx, rcy, rw, rh = _relief_xywh()
        rcx, rcy, rw, rh = rcx * K, rcy * K, rw * K, rh * K
        pad = P.prism_rrect(d["rl_reb_w"] * K - 2, d["rl_reb_h"] * K - 2, d["rl_r_reb"] * K - 1, zb0, zb1, cx=rcx, cy=rcy)
        link = box(min(xc, rcx), max(xc, rcx), rcy - 7, rcy + 7, zb0, zb1)
        rskin = 6.0
        rz_top = (d["rel_top"] - rskin) * K
        rspine = P.prism_rrect(rw - 2 * rskin, rh - 2 * rskin, 3.0, zb1 - 0.01, rz_top, cx=rcx, cy=rcy, taper=2.0)
        plate = plate.fuse(pad).fuse(link).fuse(rspine)
    s = plate.fuse(spine)
    # заливні та вентиляційні отвори в зоні шийки (між хребтом і контуром шийки)
    r_mid = (side0 / 2 + d["reb"] * K / 2) / 2
    for (dx, dy, r) in ((-r_mid, 0, 5), (r_mid, 0, 5), (0, -r_mid, 2.5), (0, r_mid, 2.5)):
        s = s.cut(cyl(r, zb0 - 1, zb1 + 1, xc + dx, dy))
    # вентиляційний канал хребта (зрив вакууму при вийманні)
    s = s.cut(cyl(1.5, zb0 - 1, z_top + 1, xc, 0))
    if v(p.RELIEF_ON):
        rcx, rcy, rw, rh = _relief_xywh()
        s = s.cut(cyl(1.5, zb0 - 1, (d["rel_top"] - 6) * K + 1, rcx * K, rcy * K))       # вент хребта полегшення
        for dy in (-1, 1):                                                                # заливка/повітря чашки полегшення
            s = s.cut(cyl(2.0, zb0 - 1, zb1 + 1, rcx * K, rcy * K + dy * (rh * K / 2 - 3.0)))
    # отвори під центрувальні штифти форми сердечника
    for sgn in (-1, 1):
        s = s.cut(cyl(2.15, zb0 - 1, zb1 + 1, xc + sgn * CORE_PIN_X, 0))
    # наскрізні отвори під стяжні шпильки M5 (міст притискається до гільзи — сердечник не спливає)
    for (x, y) in lug_positions():
        s = s.cut(cyl(ROD_HOLE / 2, zb0 - 1, z_open + 1, x, y))
    return s.clean()


CORE_PIN_X = d["reb"] * K / 2 + 5.0


def core_silicone():
    core = S(core_outer())
    return core.cut(core_spine_and_bridge()).clean()


def core_mold():
    """Жорстка друкована форма для відливання силіконової «чашки» сердечника (стінка 4 мм).
    Розкрита догори (у координатах виробу — донизу); центрування мосту 2 штифтами Ø4."""
    xc = d["cav_xc"] * K
    co = S(core_outer())
    bb = co.BoundingBox()
    wall = 4.0
    z_open = -GA * K
    zb1 = z_open - BRIDGE_RAISE
    neck_w = d["reb"] * K + 8
    x0 = min(xc - CORE_PIN_X - 5, bb.xmin - wall)
    x1 = max(xc + CORE_PIN_X + 5, bb.xmax + wall)
    y0 = min(-neck_w / 2 - 6, bb.ymin - wall)
    y1 = max(neck_w / 2 + 6, bb.ymax + wall)
    outer = P.prism_rrect(x1 - x0, y1 - y0, 10, zb1, bb.zmax + wall, cx=(x0 + x1) / 2, cy=(y0 + y1) / 2)
    m = outer.cut(co)
    # штифти центрування мосту (вгору від обідка)
    for sgn in (-1, 1):
        m = m.fuse(cyl(2.0 - 0.1, zb1 - 5, zb1 + 0.01, xc + sgn * CORE_PIN_X, 0))
    return m.clean()


# ==========================================================================
# 3. Кришка
# ==========================================================================
LID_SIL = 12.0
LID_PINS = [(-15.6 - 25, 0.0), (-15.6 + 25, 0.0)]


def lid_master(kind="main"):
    if kind == "relief":
        mm = P.relief_lid(product=False, grind_allow=GA)
        z0 = v(p.LID_RECESS) - GA
        for (x, y) in rl_pins():
            mm = mm.cut(cyl(2.6, z0 - 1, z0 + 3.0, x, y))
        return S(mm)
    m = P.lid(product=False, grind_allow=GA)
    z0 = v(p.LID_RECESS) - GA
    for (x, y) in LID_PINS:
        m = m.cut(cyl(2.6, z0 - 1, z0 + 3.5, x, y))
    return S(m)


def _lid_sleeve_dims(kind="main"):
    bb = lid_master(kind).BoundingBox()
    return (bb.xmin - LID_SIL, bb.xmax + LID_SIL, bb.ymin - LID_SIL, bb.ymax + LID_SIL, bb.zmin, bb.zmax + 10.0)


def lid_lugs(kind="main"):
    ix0, ix1, iy0, iy1, _, _ = _lid_sleeve_dims(kind)
    o = 4 + 6
    return [(ix0 - o + 6, iy0 - o + 6), (ix1 + o - 6, iy0 - o + 6), (ix1 + o - 6, iy1 + o - 6), (ix0 - o + 6, iy1 + o - 6)]


def lid_sleeve(kind="main"):
    ix0, ix1, iy0, iy1, z0, z1 = _lid_sleeve_dims(kind)
    t = 4.0
    cxy = ((ix0 + ix1) / 2, (iy0 + iy1) / 2)
    outer = _rrp(cxy, ix1 - ix0 + 2 * t, iy1 - iy0 + 2 * t, 8, z0, z1 - z0)
    inner = _rrp(cxy, ix1 - ix0, iy1 - iy0, 6, z0 - 1, z1 - z0 + 2)
    s = outer.cut(inner)
    for (x, y) in lid_lugs(kind):
        s = s.fuse(cyl(6, z0, z1, x, y)).cut(inner)
        s = s.cut(cyl(PIN_HOLE / 2, z0 - 1, z1 + 1, x, y))
    return s.clean()


def lid_base_plate(kind="main"):
    ix0, ix1, iy0, iy1, z0, z1 = _lid_sleeve_dims(kind)
    t = 5.0
    cxy = ((ix0 + ix1) / 2, (iy0 + iy1) / 2)
    plate = _rrp(cxy, ix1 - ix0 + 30, iy1 - iy0 + 30, 8, z0 - t, t)
    for (x, y) in lid_lugs(kind):
        plate = plate.fuse(cyl(PIN_D / 2 - 0.1, z0, z0 + 6, x, y))
    if kind == "main":
        for (x, y) in LID_PINS:
            plate = plate.fuse(cyl(2.5 * K - 0.15, z0, z0 + 3, x * K, y * K))
    else:
        for (x, y) in rl_pins():
            plate = plate.fuse(cyl(2.5 * K - 0.15, z0, z0 + 2.5, x * K, y * K))
    return plate.clean()


def rl_pins():
    cx, cy, w, h = P._relief_xy()
    return [(cx, cy - h / 4), (cx, cy + h / 4)]


# ==========================================================================
# 4. Форма силіконової вставки девайса (жорстка, друкована)
# ==========================================================================
def liner_mold():
    """Повертає (чашка, сердечник). Вставка відливається отвором догори, як у виробі."""
    liner = P.liner()
    bb = liner.BoundingBox()
    cx, cy = d["pocket_cx"], d["pocket_cy"]
    wall = 3.0
    z_bot = bb.zmin - wall
    z_rim = bb.zmax          # обідок чашки = верх вставки (аудит M8)
    # чашка: стадіон-оболонка навколо зовнішньої поверхні вставки
    outer = P.stadium_prism(bb.xlen + 2 * wall + 8, bb.ylen + 2 * wall + 8, cx, cy, z_bot, z_rim)
    outer = outer.fuse(box(cx - 26, cx + 26, cy - 4, cy + 4, z_rim - 4, z_rim))  # вушка під центратор
    # порожнина = зовнішня поверхня вставки (без ребер/прорізів) + продовження вгору
    inset = d["pocket_inset_floor"]
    fit = v(p.LINER_FIT)
    wx0 = d["pocket_x"] - 2 * inset + 2 * fit
    wy0 = d["pocket_y"] - 2 * inset + 2 * fit
    cav = P.stadium_prism(wx0, wy0, cx, cy, d["pocket_floor"], z_rim + 1, taper=-v(p.DRAFT_POCKET))
    cav = cav.fillet(3.0, min(cav.Faces(), key=lambda f: f.Center().z).Edges())
    cup = outer.cut(cav)
    for sx in (-1, 1):
        cup = cup.fuse(cyl(1.9, z_rim - 0.01, z_rim + 3.5, cx + sx * 22, cy))   # штифти в кришку на 3.5 (аудит M7)
    # сердечник = внутрішня порожнина вставки з канавками під ребра та ребрами-прорізами
    zi = d["pocket_floor"] + v(p.LINER_FLOOR)
    z_top_liner = v(p.H) - 0.3
    core = P.stadium_prism(d["liner_in_x"], d["liner_in_y"], cx, cy, zi, z_rim + 4)
    core = core.fillet(2.0, min(core.Faces(), key=lambda f: f.Center().z).Edges())
    core = core.cut(liner)  # канавки під мікроребра (ребра вставки віднімаються від сердечника)
    if v(p.SLOT_ON):
        w = v(p.SLOT_W)
        zb = v(p.H) - v(p.SLOT_DEPTH) + w / 2
        for sgn in (-1, 1):
            y_end = cy + sgn * (wy0 / 2 + 2)
            ya, yb = sorted((cy, y_end))
            fin = box(cx - w / 2 + 0.05, cx + w / 2 - 0.05, ya, yb, zb, z_rim + 4)
            fin = fin.fuse(cq.Solid.makeCylinder(w / 2 - 0.05, yb - ya, Vector(cx, ya, zb), Vector(0, 1, 0)))
            fin = fin.intersect(cav.fuse(box(cx - 20, cx + 20, cy - 40, cy + 40, z_rim, z_rim + 4)))
            core = core.fuse(fin)
    # кришка-центратор лежить на обідку: її нижня площина формує верхній торець вставки
    cap = P.stadium_prism(bb.xlen + 2 * wall + 8, bb.ylen + 2 * wall + 8, cx, cy, z_rim, z_rim + 4)
    cap = cap.fuse(box(cx - 26, cx + 26, cy - 4, cy + 4, z_rim, z_rim + 4))
    for sx in (-1, 1):
        cap = cap.cut(cyl(2.1, z_rim - 1, z_rim + 5, cx + sx * 22, cy))
    for sy in (-1, 1):
        cap = cap.cut(cyl(1.8, z_rim - 1, z_rim + 5, cx + 9.4, cy + sy * (wy0 / 2 - 4)))  # вихід надлишку/повітря
    core = core.fuse(cap)
    # проміжок між сердечником і чашкою над вставкою: силікон доходить до верху вставки
    return cup.clean(), core.clean()


# ==========================================================================
# 5. Калібри контролю якості
# ==========================================================================
def gauges():
    """Калібр отвору «ПРОХІД» Ø7.90 (має пройти отвір повністю) та імітатор стіка HEETS Ø7.42×45."""
    go = cq.Workplane("XY").circle(7.90 / 2).extrude(14).faces(">Z").workplane() \
        .circle(6).extrude(20).edges(">Z").fillet(2).val()
    stick = cq.Workplane("XY").circle(v(p.HEETS_D) / 2).extrude(v(p.STICK_L)).edges().fillet(0.6).val()
    return go, stick


def all_tooling():
    go, stick_g = gauges()
    return {
        "body_master": body_master(),
        "body_sleeve": body_sleeve(),
        "body_base_plate": body_base_plate(),
        "finger_stiffener": finger_stiffener(),
        "stiffener_holder": stiffener_holder(),
        "core_silicone": core_silicone(),
        "core_spine_bridge": core_spine_and_bridge(),
        "core_mold": core_mold(),
        "lid_master": lid_master(),
        "lid_sleeve": lid_sleeve(),
        "lid_base_plate": lid_base_plate(),
        "rlid_master": lid_master("relief"),
        "rlid_sleeve": lid_sleeve("relief"),
        "rlid_base_plate": lid_base_plate("relief"),
        "gauge_hole_go_7p90": go,
        "gauge_stick_heets": stick_g,
    }
