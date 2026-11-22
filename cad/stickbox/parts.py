"""
STICKBOX 01 Monolith — параметрична CAD-модель деталей (CadQuery / OpenCASCADE B-Rep).

Деталі:
  body()        — монолітний корпус (декоративний бетон)
  lid()         — нижня кришка з пробкою та канавкою під О-кільце (декоративний бетон)
  oring()       — О-кільце VMQ у встановленому (стиснутому) стані — для збірки
  oring_free()  — О-кільце у вільному стані (специфікація закупівлі)
  liner()       — знімна силіконова вставка кишені девайса
  device()      — габаритний макет IQOS ILUMA ONE (для перевірок і рендерів)
  stick()       — макет стіка TEREA
"""
import math
import cadquery as cq
from cadquery import Vector
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse

from . import params as p
from .params import v

d = p.derived()
TAN_C = math.tan(math.radians(v(p.DRAFT_CAV)))
TAN_P = math.tan(math.radians(v(p.DRAFT_POCKET)))
EPS = 1e-3


# --------------------------------------------------------------------------
# Допоміжні функції
# --------------------------------------------------------------------------
def rrect(w, h, r, z=0.0, cx=0.0, cy=0.0):
    """Ескіз прямокутника із заокругленими кутами на висоті z."""
    return (cq.Workplane("XY", origin=(cx, cy, z)).sketch()
            .rect(w, h).vertices().fillet(r).finalize())


def prism_rrect(w, h, r, z0, z1, cx=0.0, cy=0.0, taper=0.0):
    """Призма з заокругленого прямокутника z0→z1; taper>0 — звуження вгору."""
    return rrect(w, h, r, z0, cx, cy).extrude(z1 - z0, taper=taper).val()


def fillet_edges(solid, edges, r):
    if not edges:
        return solid
    return solid.fillet(r, edges)


def edges_where(solid, pred):
    out = []
    for e in solid.Edges():
        pts = [e.positionAt(t) for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
        if pred(e, pts):
            out.append(e)
    return out


def at_z(z, tol=0.02):
    return lambda e, pts: all(abs(q.z - z) < tol for q in pts)


def stadium_prism(wx, wy, cx, cy, z0, z1, taper=0.0):
    """Стадіон (обабіч півкола) з довгою віссю вздовж Y."""
    wp = cq.Workplane("XY", origin=(cx, cy, z0)).slot2D(wy, wx, angle=90)
    return wp.extrude(z1 - z0, taper=taper).val()


# --------------------------------------------------------------------------
# Корпус
# --------------------------------------------------------------------------
def _outer_block(H, bottom_arris=True):
    W, D = v(p.W), v(p.D)
    s = cq.Workplane("XY").box(W, D, H, centered=(True, True, False))
    s = s.edges("|Z").fillet(v(p.R_V))
    s = s.faces(">Z").edges().fillet(v(p.R_TOP))
    if bottom_arris:
        s = s.faces("<Z").edges().fillet(v(p.R_BOT))
    return s.val()


def _cavity_tool():
    """Порожнина + ребейт кришки (інструмент віднімання), з куполом і заокругленнями."""
    zr = d["z_reb"]
    xc = d["cav_xc"]
    top_extra = 3.0
    cav = prism_rrect(v(p.CAV), v(p.CAV), v(p.R_CAV), zr, d["z_ceil_c"] + top_extra,
                      cx=xc, taper=v(p.DRAFT_CAV))
    R = d["r_dome"]
    sph = cq.Solid.makeSphere(R, Vector(xc, 0, d["z_ceil_c"] - R), angleDegrees1=-90, angleDegrees2=90)
    cav = cav.intersect(sph)
    # заокруглення стеля→стінки
    top_face = max(cav.Faces(), key=lambda f: f.Center().z)
    cav = cav.fillet(v(p.R_CEIL), top_face.Edges())
    reb = prism_rrect(d["reb"], d["reb"], d["r_reb"], -1.0, zr, cx=xc)
    # заходна фаска для О-кільця: 20° × 2.5 мм (радіально ≈0.91)
    L = v(p.LEADIN_LEN)
    rad = L * math.tan(math.radians(v(p.LEADIN_ANGLE)))
    lead = prism_rrect(v(p.CAV) + 2 * rad, v(p.CAV) + 2 * rad, v(p.R_CAV) + rad, zr - 0.01, zr + L, cx=xc,
                       taper=v(p.LEADIN_ANGLE))
    return cav.fuse(reb).fuse(lead).clean()


def _funnel_tool(with_flare=True):
    """Воронка (S-крива, дотична до верху та до отвору) + отвір Ø8 + розтруб на виході."""
    H = v(p.H)
    r_h = v(p.HOOK_H) * 0 + v(p.HOLE_D) / 2
    r_f = v(p.FUNNEL_D) / 2
    fd = v(p.FUNNEL_DEPTH)
    z_t = H - fd                    # горло воронки
    z_c = d["z_ceil_c"]
    z_step = z_c + v(p.FLARE_H)     # стик «шпилька форми / конус сердечника»
    r_step = v(p.FLARE_STEP_D) / 2
    r_fl = v(p.FLARE_D) / 2
    k1, k2 = 0.55 * (r_f - r_h), 0.45 * fd
    a = math.radians(30.0)  # вхід у горло під 30° до вертикалі
    prof = (cq.Workplane("XZ")
            .moveTo(0, z_step)
            .lineTo(r_h, z_step)
            .lineTo(r_h, z_t)
            .bezier([(r_h, z_t), (r_h + k2 * math.sin(a), z_t + k2 * math.cos(a)), (r_f - k1, H), (r_f, H)],
                    includeCurrent=False)
            .lineTo(r_f, H + 2)
            .lineTo(0, H + 2)
            .close())
    funnel = prof.revolve(360, (0, 0, 0), (0, 1, 0)).val()
    # розтруб (конус) — продовжений нижче стелі
    slope = (r_fl - r_step) / v(p.FLARE_H)
    z_low = z_c - 2.0
    r_low = r_fl + slope * 2.0
    fl = (cq.Workplane("XZ").moveTo(0, z_low).lineTo(r_low, z_low).lineTo(r_step, z_step)
          .lineTo(0, z_step).close().revolve(360, (0, 0, 0), (0, 1, 0)).val())
    tool = funnel.fuse(fl).clean() if with_flare else funnel
    return tool.translate(Vector(d["cav_xc"], 0, 0))


def flare_boss(preload=0.3):
    """Конус розтруба як частина сердечника (від стелі до стику зі шпилькою форми + натяг)."""
    z_c = d["z_ceil_c"]
    z_step = z_c + v(p.FLARE_H)
    r_step = v(p.FLARE_STEP_D) / 2
    r_fl = v(p.FLARE_D) / 2
    slope = (r_fl - r_step) / v(p.FLARE_H)
    z_low = z_c - 2.0
    r_low = r_fl + slope * 2.0
    prof = (cq.Workplane("XZ").moveTo(0, z_low).lineTo(r_low, z_low).lineTo(r_step, z_step)
            .lineTo(r_step, z_step + preload).lineTo(0, z_step + preload).close())
    return prof.revolve(360, (0, 0, 0), (0, 1, 0)).val().translate(Vector(d["cav_xc"], 0, 0))


def _pocket_tool():
    H = v(p.H)
    inset = d["pocket_inset_floor"]
    wx0 = d["pocket_x"] - 2 * inset
    wy0 = d["pocket_y"] - 2 * inset
    zf = d["pocket_floor"]
    extra = 2.0
    pk = stadium_prism(wx0, wy0, d["pocket_cx"], d["pocket_cy"], zf, H + extra,
                       taper=-v(p.DRAFT_POCKET))
    bot = min(pk.Faces(), key=lambda f: f.Center().z)
    pk = pk.fillet(3.0, bot.Edges())
    return pk


def _slot_tool():
    H = v(p.H)
    w = v(p.SLOT_W)
    cx = d["pocket_cx"]
    zb = H - v(p.SLOT_DEPTH) + w / 2
    y0, y1 = -v(p.D) / 2 - 2, d["pocket_cy"]
    box = cq.Workplane("XY").box(w, y1 - y0, H + 2 - zb, centered=(True, False, False)) \
        .translate((cx, y0, zb)).val()
    cyl = cq.Solid.makeCylinder(w / 2, y1 - y0, Vector(cx, y0, zb), Vector(0, 1, 0))
    return box.fuse(cyl).clean()


def _recess_tool():
    """Пальцева виїмка у нерухомому корпусі (фронт, по центру, біля краю кришки)."""
    w, r = v(p.RECESS_W), v(p.RECESS_R)
    top = d["recess_top"]
    y0 = -v(p.D) / 2 - 2
    # наскрізь до лицьової поверхні пробки, включно із зоною кутового радіуса порожнини
    y1 = d["cav_y0"] + v(p.R_CAV)
    prof = (cq.Workplane("XZ", origin=(0, y0, 0))
            .moveTo(-w / 2, -1).lineTo(w / 2, -1).lineTo(w / 2, top - r)
            .radiusArc((w / 2 - r, top), -r)
            .lineTo(-w / 2 + r, top)
            .radiusArc((-w / 2, top - r), -r)
            .close())
    return prof.extrude(-(y1 - y0)).val()


def _logo_tool(depth_sign=-1):
    txt = (cq.Workplane("XZ", origin=(0, -v(p.D) / 2 - 0.01, v(p.LOGO_Z)))
           .text(p.LOGO_TEXT, v(p.LOGO_SIZE), depth_sign * (v(p.LOGO_DEPTH) + 0.01),
                 fontPath=p.LOGO_FONT, halign="center", valign="center"))
    return txt.val()


def body(product=True, with_slot=None, with_logo=None, with_cavity=True,
         with_recess=True, height_extra=0.0, funnel_flare=None):
    """
    product=True  — геометрія готового виробу (з притупленнями після шліфування).
    product=False — геометрія для майстер-моделі (без притуплень відкритої грані).
    with_cavity=False — лише зовнішня оболонка (майстер для зовнішньої силіконової форми).
    height_extra — припуск на шліфування відкритої грані (додається знизу).
    """
    with_slot = bool(v(p.SLOT_ON)) if with_slot is None else with_slot
    with_logo = bool(v(p.LOGO_ON)) if with_logo is None else with_logo
    H = v(p.H)
    # Нижні кромки (зовнішня R≈1 і внутрішня кромка ребейту R≈0.5) — ручне притуплення після
    # шліфування відкритої грані; у CAD не моделюються (відкрита грань формується не силіконом).
    s = _outer_block(H + height_extra, bottom_arris=False).translate(Vector(0, 0, -height_extra))

    # кишеня девайса
    s = s.cut(_pocket_tool())
    # фаска/заокруглення кромки кишені (контакт з девайсом/вставкою)
    s = fillet_edges(s, edges_where(s, lambda e, pts: all(abs(q.z - H) < 0.02 for q in pts)
                                    and all(q.x > d["pocket_cx"] - d["pocket_x"] / 2 - 0.5 for q in pts)
                                    and all(abs(q.y - d["pocket_cy"]) < d["pocket_y"] / 2 + 0.5 for q in pts)),
                     1.0)
    if with_slot:
        s = s.cut(_slot_tool())
        # заокруглення кромок прорізу на фронті та зверху
        cx, w = d["pocket_cx"], v(p.SLOT_W)
        def on_slot(e, pts):
            near_x = all(cx - w / 2 - 0.05 <= q.x <= cx + w / 2 + 0.05 for q in pts)
            front = all(q.y < -v(p.D) / 2 + v(p.T_FRONT_POCKET) - 0.3 for q in pts)
            outer = any(q.y < -v(p.D) / 2 + 0.3 for q in pts) or any(q.z > H - 0.3 for q in pts)
            return near_x and front and outer
        try:
            s = fillet_edges(s, edges_where(s, on_slot), 1.0)
        except Exception as ex:  # pragma: no cover
            print("WARN slot fillet:", ex)

    # верхня воронка + отвір + розтруб
    s = s.cut(_funnel_tool(with_flare=with_cavity if funnel_flare is None else funnel_flare))
    z_t = H - v(p.FUNNEL_DEPTH)
    throat = edges_where(s, lambda e, pts: all(abs(q.z - z_t) < 0.02 for q in pts)
                         and all(math.hypot(q.x - d["cav_xc"], q.y) < v(p.HOLE_D) / 2 + 0.05 for q in pts))
    s = fillet_edges(s, throat, v(p.THROAT_R))

    if with_cavity:
        s = s.cut(_cavity_tool())
        zr = d["z_reb"]
        xc = d["cav_xc"]
        half_cav = v(p.CAV) / 2
        rad_li = v(p.LEADIN_LEN) * math.tan(math.radians(v(p.LEADIN_ANGLE)))
        inner = edges_where(s, lambda e, pts: all(abs(q.z - zr) < 0.02 for q in pts)
                            and all(max(abs(q.x - xc), abs(q.y)) < half_cav + rad_li + 0.3 for q in pts))
        s = fillet_edges(s, inner, 0.4)     # притуплення кромки фаски (не ріже О-кільце)
        outer = edges_where(s, lambda e, pts: all(abs(q.z - zr) < 0.02 for q in pts)
                            and all(max(abs(q.x - xc), abs(q.y)) > half_cav + 1.0 for q in pts))
        s = fillet_edges(s, outer, 0.5)     # внутрішній кут ребейту
        if with_recess:
            s = s.cut(_recess_tool())
            def on_recess(e, pts):
                return (all(abs(q.x) <= v(p.RECESS_W) / 2 + 0.05 for q in pts)
                        and all(abs(q.y + v(p.D) / 2) < 0.02 for q in pts)
                        and all(-height_extra + 0.05 < q.z < 10 for q in pts))
            try:
                s = fillet_edges(s, edges_where(s, on_recess), 1.5)
            except Exception as ex:  # pragma: no cover
                print("WARN recess fillet:", ex)

    if with_logo:
        s = s.cut(_logo_tool())
    return s.clean()


# --------------------------------------------------------------------------
# Кришка (координати збірки: низ кришки на z = LID_RECESS)
# --------------------------------------------------------------------------
def lid(product=True, grind_allow=0.0):
    xc = d["cav_xc"]
    ft = v(p.FLANGE_T)
    z0 = v(p.LID_RECESS)
    fl = prism_rrect(d["flange"], d["flange"], d["r_flange"], z0 - grind_allow, z0 + ft, cx=xc)
    plug = prism_rrect(d["plug"], d["plug"], d["r_plug"], z0 + ft - EPS, z0 + d["lid_t"], cx=xc,
                       taper=v(p.DRAFT_CAV))
    s = fl.fuse(plug).clean()
    # фаска верхньої кромки пробки (заведення)
    top = max(s.Faces(), key=lambda f: f.Center().z)
    s = s.chamfer(1.0, None, top.Edges())
    # заокруглення внутрішнього кута фланець/пробка та зовнішньої верхньої кромки фланця
    zf = z0 + ft
    corner = edges_where(s, lambda e, pts: all(abs(q.z - zf) < 0.02 for q in pts)
                         and all(max(abs(q.x - xc), abs(q.y)) < d["plug"] / 2 + 0.05 for q in pts))
    s = fillet_edges(s, corner, 0.5)
    fl_top = edges_where(s, lambda e, pts: all(abs(q.z - zf) < 0.02 for q in pts)
                         and all(max(abs(q.x - xc), abs(q.y)) > d["flange"] / 2 - 2.0 for q in pts))
    s = fillet_edges(s, fl_top, 0.6)
    if product:
        bot = min(s.Faces(), key=lambda f: f.Center().z)
        s = s.fillet(0.8, bot.Edges())
    # канавка О-кільця
    g0, g1 = z0 + d["groove_z0"], z0 + d["groove_z1"]
    gb = 2 * d["groove_bottom_half"]
    ring_out = prism_rrect(d["plug"] + 6, d["plug"] + 6, d["r_plug"] + 3, g0, g1, cx=xc)
    ring_in = prism_rrect(gb, gb, d["r_groove_bottom"], g0 - 1, g1 + 1, cx=xc)
    s = s.cut(ring_out.cut(ring_in))
    half_gb = d["groove_bottom_half"]
    def groove_inner(e, pts):
        return (all(abs(q.z - g0) < 0.02 or abs(q.z - g1) < 0.02 for q in pts)
                and all(max(abs(q.x - xc), abs(q.y)) < half_gb + 0.05 for q in pts))
    def groove_outer(e, pts):
        return (all(abs(q.z - g0) < 0.02 or abs(q.z - g1) < 0.02 for q in pts)
                and all(max(abs(q.x - xc), abs(q.y)) > half_gb + 0.5 for q in pts))
    s = fillet_edges(s, edges_where(s, groove_inner), 0.4)
    s = fillet_edges(s, edges_where(s, groove_outer), 0.4)
    return s.clean()


# --------------------------------------------------------------------------
# О-кільце
# --------------------------------------------------------------------------
def _rrect_wire(half, r, z, xc):
    pts = [Vector(xc - half, -half, z), Vector(xc + half, -half, z),
           Vector(xc + half, half, z), Vector(xc - half, half, z)]
    w = cq.Wire.makePolygon(pts, close=True)
    return w.fillet2D(r, w.Vertices())


def oring(installed=True):
    """Встановлене кільце: еліптичний перетин (радіально = глибина залозу 2.4,
    аксіально ≈3.75), площа перетину = площі круга Ø3.0 (силікон нестисливий)."""
    xc = d["cav_xc"]
    z = v(p.LID_RECESS) + (d["groove_z0"] + d["groove_z1"]) / 2
    cs = v(p.ORING_CS)
    a_rad = d["gland_depth"] / 2
    a_ax = (cs / 2) ** 2 / a_rad
    half_c = d["groove_bottom_half"] + a_rad
    r_c = d["r_groove_bottom"] + a_rad
    wire = _rrect_wire(half_c, r_c, z, xc)
    # профіль у площині, перпендикулярній до шляху в середині передньої сторони (дотична = X)
    prof = cq.Workplane("YZ", origin=(xc, -half_c, z)).ellipse(a_rad, a_ax)
    return prof.sweep(cq.Workplane("XY").add(wire), transition="right").val()


def oring_free():
    cs = v(p.ORING_CS)
    r_c = v(p.ORING_ID) / 2 + cs / 2
    return cq.Solid.makeTorus(r_c, cs / 2)


# --------------------------------------------------------------------------
# Силіконова вставка тримача девайса
# --------------------------------------------------------------------------
def liner(with_slot=None):
    with_slot = bool(v(p.SLOT_ON)) if with_slot is None else with_slot
    H = v(p.H)
    cx, cy = d["pocket_cx"], d["pocket_cy"]
    fit = v(p.LINER_FIT)
    inset = d["pocket_inset_floor"]
    z0 = d["pocket_floor"]
    z1 = H - 0.3                              # верх вставки на 0.3 нижче площини верху
    wx0 = d["pocket_x"] - 2 * inset + 2 * fit
    wy0 = d["pocket_y"] - 2 * inset + 2 * fit
    outer = stadium_prism(wx0, wy0, cx, cy, z0, z1, taper=-v(p.DRAFT_POCKET))
    bot = min(outer.Faces(), key=lambda f: f.Center().z)
    outer = outer.fillet(3.0, bot.Edges())
    zi = z0 + v(p.LINER_FLOOR)
    inner = stadium_prism(d["liner_in_x"], d["liner_in_y"], cx, cy, zi, z1 + 2)
    ib = min(inner.Faces(), key=lambda f: f.Center().z)
    inner = inner.fillet(2.0, ib.Edges())
    s = outer.cut(inner)
    # мікроребра (4 шт., на широких гранях) — центрування, мінімальний контакт
    rib_r, rib_h = 0.6, 0.35
    for sx in (-1, 1):
        for dy in (-7.0, 7.0):
            x = cx + sx * (d["liner_in_x"] / 2 + (rib_r - rib_h))
            rib = cq.Solid.makeCylinder(rib_r, (z1 - 4) - (zi + 1.5), Vector(x, cy + dy, zi + 1.5))
            s = s.fuse(rib)
    if with_slot:
        w = v(p.SLOT_W)
        zb = H - v(p.SLOT_DEPTH) + w / 2
        for sgn in (-1, 1):  # симетрично — вставку неможливо встановити неправильно
            y_end = cy + sgn * (d["pocket_y"] / 2 + 1)
            y_a, y_b = sorted((cy, y_end))
            box = cq.Workplane("XY").box(w, y_b - y_a, H + 2 - zb, centered=(True, False, False)) \
                .translate((cx, y_a, zb)).val()
            cyl = cq.Solid.makeCylinder(w / 2, y_b - y_a, Vector(cx, y_a, zb), Vector(0, 1, 0))
            s = s.cut(box.fuse(cyl))
    top = edges_where(s, lambda e, pts: all(abs(q.z - z1) < 0.02 for q in pts))
    try:
        s = fillet_edges(s, top, 0.6)
    except Exception as ex:  # pragma: no cover
        print("WARN liner top fillet:", ex)
    return s.clean()


# --------------------------------------------------------------------------
# Макети
# --------------------------------------------------------------------------
def device():
    cx, cy = d["pocket_cx"], d["pocket_cy"]
    z0 = d["dev_z0"]
    s = stadium_prism(v(p.DEV_T), v(p.DEV_W), cx, cy, z0, z0 + v(p.DEV_L))
    ends = [f for f in s.Faces() if abs(f.Center().z - z0) < 0.01 or abs(f.Center().z - (z0 + v(p.DEV_L))) < 0.01]
    s = s.fillet(6.0, [e for f in ends for e in f.Edges()])
    return s


def stick():
    return cq.Solid.makeCylinder(v(p.STICK_D) / 2, v(p.STICK_L))


def assembly_parts():
    return {
        "body": body(),
        "lid": lid(),
        "oring": oring(),
        "liner": liner(),
        "device": device(),
    }
