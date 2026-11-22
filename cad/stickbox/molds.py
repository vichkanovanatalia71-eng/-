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
PRELOAD = 0.3        # натяг стиків силікон-силікон (без облою)


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
    m = P.body(product=False, with_cavity=False, height_extra=GA, funnel_flare=False)
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
    return bar.fuse(flange).clean()


# ==========================================================================
# 2. Сердечник порожнини
# ==========================================================================
def _recess_tab(z_from):
    """Вкладка, що формує пальцеву виїмку (від стінки форми до порожнини) + натяг."""
    w, r = v(p.RECESS_W), v(p.RECESS_R)
    top = d["recess_top"]
    y0 = -v(p.D) / 2 - PRELOAD
    y1 = d["cav_y0"] + v(p.R_CAV)
    prof = (cq.Workplane("XZ", origin=(0, y0, 0))
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
    core = core.fuse(P.flare_boss(PRELOAD))
    core = core.fuse(_recess_tab(z_open - neck))
    xc = d["cav_xc"]
    neck_s = P.prism_rrect(d["reb"], d["reb"], d["r_reb"], z_open - neck, z_open + 0.01, cx=xc)
    core = core.fuse(neck_s)
    return core.clean()


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
    # плита мосту: контур шийки + 4 мм та рукави до вушок
    neck_w = d["reb"] * K + 8
    plate = P.prism_rrect(neck_w, neck_w, d["r_reb"] * K + 4, zb0, zb1, cx=xc)
    for (x, y) in lug_positions():
        ang = math.atan2(y - 0, x - xc)
        L = math.hypot(x - xc, y)
        arm = (cq.Workplane("XY", origin=(xc, 0, zb0)).transformed(rotate=(0, 0, math.degrees(ang)))
               .center(L / 2, 0).rect(L, 14).extrude(BRIDGE_T).val())
        plate = plate.fuse(arm).fuse(cyl(9, zb0, zb1, x, y))
        plate = plate.fuse(cyl(6, zb1 - 0.01, z_open, x, y))            # ніжка до торця гільзи
        plate = plate.fuse(cyl(PIN_D / 2 - 0.1, z_open - 0.01, z_open + 8, x, y))  # штифт у вушко
    s = plate.fuse(spine)
    # заливні та вентиляційні отвори в зоні шийки (між хребтом і контуром шийки)
    r_mid = (side0 / 2 + d["reb"] * K / 2) / 2
    for (dx, dy, r) in ((-r_mid, 0, 5), (r_mid, 0, 5), (0, -r_mid, 2.5), (0, r_mid, 2.5)):
        s = s.cut(cyl(r, zb0 - 1, zb1 + 1, xc + dx, dy))
    # вентиляційний канал хребта (зрив вакууму при вийманні)
    s = s.cut(cyl(1.5, zb0 - 1, z_top + 1, xc, 0))
    # отвори під центрувальні штифти форми сердечника
    for sgn in (-1, 1):
        s = s.cut(cyl(2.15, zb0 - 1, zb1 + 1, xc + sgn * (neck_w / 2 - 3.5), 0))
    return s.clean()


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
    outer = P.prism_rrect(neck_w + 2 * 6, neck_w + 2 * 6, d["r_reb"] * K + 10, zb1, bb.zmax + wall, cx=xc)
    m = outer.cut(co)
    # штифти центрування мосту (вгору від обідка)
    for sgn in (-1, 1):
        m = m.fuse(cyl(2.0 - 0.1, zb1 - 5, zb1 + 0.01, xc + sgn * (neck_w / 2 - 3.5), 0))
    return m.clean()


# ==========================================================================
# 3. Кришка
# ==========================================================================
LID_SIL = 12.0
LID_PINS = [(-15.6 - 25, 0.0), (-15.6 + 25, 0.0)]


def lid_master():
    m = P.lid(product=False, grind_allow=GA)
    z0 = v(p.LID_RECESS) - GA
    for (x, y) in LID_PINS:
        m = m.cut(cyl(2.6, z0 - 1, z0 + 3.5, x, y))
    return S(m)


def _lid_sleeve_dims():
    bb = lid_master().BoundingBox()
    return (bb.xmin - LID_SIL, bb.xmax + LID_SIL, bb.ymin - LID_SIL, bb.ymax + LID_SIL, bb.zmin, bb.zmax + 10.0)


def lid_lugs():
    ix0, ix1, iy0, iy1, _, _ = _lid_sleeve_dims()
    o = 4 + 6
    return [(ix0 - o + 6, iy0 - o + 6), (ix1 + o - 6, iy0 - o + 6), (ix1 + o - 6, iy1 + o - 6), (ix0 - o + 6, iy1 + o - 6)]


def lid_sleeve():
    ix0, ix1, iy0, iy1, z0, z1 = _lid_sleeve_dims()
    t = 4.0
    cxy = ((ix0 + ix1) / 2, (iy0 + iy1) / 2)
    outer = _rrp(cxy, ix1 - ix0 + 2 * t, iy1 - iy0 + 2 * t, 8, z0, z1 - z0)
    inner = _rrp(cxy, ix1 - ix0, iy1 - iy0, 6, z0 - 1, z1 - z0 + 2)
    s = outer.cut(inner)
    for (x, y) in lid_lugs():
        s = s.fuse(cyl(6, z0, z1, x, y)).cut(inner)
        s = s.cut(cyl(PIN_HOLE / 2, z0 - 1, z1 + 1, x, y))
    return s.clean()


def lid_base_plate():
    ix0, ix1, iy0, iy1, z0, z1 = _lid_sleeve_dims()
    t = 5.0
    cxy = ((ix0 + ix1) / 2, (iy0 + iy1) / 2)
    plate = _rrp(cxy, ix1 - ix0 + 30, iy1 - iy0 + 30, 8, z0 - t, t)
    for (x, y) in lid_lugs():
        plate = plate.fuse(cyl(PIN_D / 2 - 0.1, z0, z0 + 6, x, y))
    for (x, y) in LID_PINS:
        plate = plate.fuse(cyl(2.5 * K - 0.15, z0, z0 + 3, x * K, y * K))
    return plate.clean()


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
    z_rim = bb.zmax + 2.0
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
        cup = cup.fuse(cyl(1.9, z_rim - 0.01, z_rim + 5, cx + sx * 22, cy))
    # сердечник = внутрішня порожнина вставки з канавками під ребра та ребрами-прорізами
    zi = d["pocket_floor"] + v(p.LINER_FLOOR)
    z_top_liner = v(p.H) - 0.3
    core = P.stadium_prism(d["liner_in_x"], d["liner_in_y"], cx, cy, zi, z_rim + 6)
    core = core.fillet(2.0, min(core.Faces(), key=lambda f: f.Center().z).Edges())
    core = core.cut(liner)  # канавки під мікроребра (ребра вставки віднімаються від сердечника)
    if v(p.SLOT_ON):
        w = v(p.SLOT_W)
        zb = v(p.H) - v(p.SLOT_DEPTH) + w / 2
        for sgn in (-1, 1):
            y_end = cy + sgn * (wy0 / 2 + 2)
            ya, yb = sorted((cy, y_end))
            fin = box(cx - w / 2 + 0.05, cx + w / 2 - 0.05, ya, yb, zb, z_rim + 6)
            fin = fin.fuse(cq.Solid.makeCylinder(w / 2 - 0.05, yb - ya, Vector(cx, ya, zb), Vector(0, 1, 0)))
            fin = fin.intersect(cav.fuse(box(cx - 20, cx + 20, cy - 40, cy + 40, z_rim, z_rim + 6)))
            core = core.fuse(fin)
    cap = P.stadium_prism(bb.xlen + 2 * wall + 8, bb.ylen + 2 * wall + 8, cx, cy, z_rim + 6, z_rim + 10)
    cap = cap.fuse(box(cx - 26, cx + 26, cy - 4, cy + 4, z_rim + 6, z_rim + 10))
    for sx in (-1, 1):
        cap = cap.cut(cyl(2.1, z_rim + 5, z_rim + 11, cx + sx * 22, cy))
    for sy in (-1, 1):
        cap = cap.cut(cyl(2.5, z_rim + 5, z_rim + 11, cx + 8.5, cy + sy * (wy0 / 2 - 1)))  # заливка/повітря
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
    cup, lcore = liner_mold()
    go, stick_g = gauges()
    return {
        "body_master": body_master(),
        "body_sleeve": body_sleeve(),
        "body_base_plate": body_base_plate(),
        "finger_stiffener": finger_stiffener(),
        "core_silicone": core_silicone(),
        "core_spine_bridge": core_spine_and_bridge(),
        "core_mold": core_mold(),
        "lid_master": lid_master(),
        "lid_sleeve": lid_sleeve(),
        "lid_base_plate": lid_base_plate(),
        "liner_mold_cup": cup,
        "liner_mold_core": lcore,
        "gauge_hole_go_7p90": go,
        "gauge_stick_heets": stick_g,
    }
