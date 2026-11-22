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


def _funnel_tool(with_flare=True, pin_extra=0.0):
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
            .moveTo(0, z_step - pin_extra)
            .lineTo(r_h, z_step - pin_extra)
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
            .lineTo(0, z_step).close())
    boss = prof.revolve(360, (0, 0, 0), (0, 1, 0)).val()
    # гніздо телескопічного стику: шпилька форми Ø8 заходить на SOCKET_DEPTH (аудит C3)
    rs = v(p.HOLE_D) / 2 - 0.05
    sock = (cq.Workplane("XZ").moveTo(0, z_step - SOCKET_DEPTH).lineTo(rs, z_step - SOCKET_DEPTH)
            .lineTo(rs, z_step - 0.6).lineTo(rs + 0.6, z_step + 0.01).lineTo(0, z_step + 0.01).close()
            .revolve(360, (0, 0, 0), (0, 1, 0)).val())
    return boss.cut(sock).translate(Vector(d["cav_xc"], 0, 0))


SOCKET_DEPTH = 3.0


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
    pk = pk.fillet(v(p.POCKET_FLOOR_R), bot.Edges())
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
    """Інструмент дебосингу напису STICKBOX (v2.6: з контурів гліфів Montserrat Bold, див. brand.py)."""
    from . import brand
    sols = [s for _, ss in brand.wordmark_solids() for s in ss]
    return cq.Compound.makeCompound(sols)


def body(product=True, with_slot=None, with_logo=None, with_cavity=True,
         with_recess=True, height_extra=0.0, funnel_flare=None, pin_extra=0.0):
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
                     v(p.POCKET_MOUTH_R))
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
    s = s.cut(_funnel_tool(with_flare=with_cavity if funnel_flare is None else funnel_flare, pin_extra=pin_extra))
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
        s = fillet_edges(s, outer, 0.3)     # внутрішній кут ребейту (не зменшує опору фланця)
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
            # кромка «стеля виїмки / стінка порожнини»: по ній проходить ущільнювач (аудит C2) → R1.5
            rt = d["recess_top"]
            def ceil_back(e, pts):
                return (all(abs(q.z - rt) < 0.02 for q in pts)
                        and all(abs(q.x) <= v(p.RECESS_W) / 2 + 0.05 for q in pts)
                        and all(q.y > -v(p.D) / 2 + 2.0 for q in pts))
            try:
                s = fillet_edges(s, edges_where(s, ceil_back), 1.5)
            except Exception as ex:  # pragma: no cover
                print("WARN recess ceiling fillet:", ex)

    if with_cavity and v(p.RELIEF_ON):
        s = s.cut(_relief_tool(height_extra))
        rt = d["rel_top"]
        top_e = edges_where(s, lambda e, pts: all(abs(q.z - rt) < 0.02 for q in pts)
                            and all(q.x > d["rel_x0"] - 0.5 and q.y > d["rel_y0"] - 0.5 for q in pts))
        try:
            s = fillet_edges(s, top_e, 4.0)
        except Exception as ex:  # pragma: no cover
            print("WARN relief fillet:", ex)
        if v(p.RL_ON):
            zr = d["rl_z_reb"]
            rcx, rcy, rw, rh = _relief_xy()
            near = lambda q: abs(q.x - rcx) < d["rl_reb_w"] / 2 + 0.3 and abs(q.y - rcy) < d["rl_reb_h"] / 2 + 0.3
            inner = edges_where(s, lambda e, pts: all(abs(q.z - zr) < 0.02 for q in pts) and all(near(q) for q in pts)
                                and all(abs(q.x - rcx) < rw / 2 + 1.2 and abs(q.y - rcy) < rh / 2 + 1.2 for q in pts))
            outer_e = edges_where(s, lambda e, pts: all(abs(q.z - zr) < 0.02 for q in pts) and all(near(q) for q in pts)
                                  and any(abs(q.x - rcx) > rw / 2 + 1.5 or abs(q.y - rcy) > rh / 2 + 1.5 for q in pts))
            for es, r in ((inner, 0.3), (outer_e, 0.3)):
                try:
                    s = fillet_edges(s, es, r)
                except Exception as ex:  # pragma: no cover
                    print("WARN relief rebate fillet:", ex)

    if with_logo:
        s = s.cut(_logo_tool())
        if v(p.MARK_ON):
            from . import brand
            s = s.cut(brand.mark_tool())
    return s.clean()


def _relief_xy():
    w = d["rel_x1"] - d["rel_x0"]
    h = d["rel_y1"] - d["rel_y0"]
    return (d["rel_x0"] + d["rel_x1"]) / 2, (d["rel_y0"] + d["rel_y1"]) / 2, w, h


def _relief_tool(height_extra=0.0, rebate=True):
    """Полегшувальна порожнина правої колонки: відкрита знизу, ухил DRAFT_CAV (вихід сердечника).
    v2.5: знизу — ребейт під кришечку з ущільнювачем та заходна фаска 30°."""
    cx, cy, w, h = _relief_xy()
    z0 = -height_extra - 1.0
    below = prism_rrect(w, h, v(p.RELIEF_R), z0, 0.01, cx=cx, cy=cy)
    up = prism_rrect(w, h, v(p.RELIEF_R), 0.0, d["rel_top"], cx=cx, cy=cy, taper=v(p.DRAFT_CAV))
    t = below.fuse(up)
    if rebate and v(p.RL_ON):
        zr = d["rl_z_reb"]
        reb = prism_rrect(d["rl_reb_w"], d["rl_reb_h"], d["rl_r_reb"], z0, zr, cx=cx, cy=cy)
        L = 1.6
        rad = L * math.tan(math.radians(30))
        lead = prism_rrect(w + 2 * rad, h + 2 * rad, v(p.RELIEF_R) + rad, zr - 0.01, zr + L, cx=cx, cy=cy, taper=30.0)
        t = t.fuse(reb).fuse(lead)
    return t.clean()


# --------------------------------------------------------------------------
# Кришка (координати збірки: низ кришки на z = LID_RECESS)
# --------------------------------------------------------------------------
def lid(product=True, grind_allow=0.0):
    xc = d["cav_xc"]
    ft = v(p.FLANGE_T)
    z0 = v(p.LID_RECESS)
    fl = prism_rrect(d["flange"], d["flange"], d["r_flange"], z0 - grind_allow, z0 + ft, cx=xc)
    zt = z0 + d["lid_t"]
    zc = zt - v(p.PLUG_CHAMF_H)
    plug = prism_rrect(d["plug"], d["plug"], d["r_plug"], z0 + ft - EPS, zc + EPS, cx=xc,
                       taper=v(p.DRAFT_CAV))
    # верх борту — фаска R×H (≈30°): прибирає кут, що впирається в стінку при перекосі (аудит C1)
    inset = (zc - (z0 + ft)) * TAN_C
    ang = math.degrees(math.atan2(v(p.PLUG_CHAMF_R), v(p.PLUG_CHAMF_H)))
    cap = prism_rrect(d["plug"] - 2 * inset, d["plug"] - 2 * inset, d["r_plug"] - inset, zc, zt, cx=xc, taper=ang)
    s = fl.fuse(plug).fuse(cap).clean()
    # заокруглення внутрішнього кута фланець/пробка та зовнішньої верхньої кромки фланця
    zf = z0 + ft
    corner = edges_where(s, lambda e, pts: all(abs(q.z - zf) < 0.02 for q in pts)
                         and all(max(abs(q.x - xc), abs(q.y)) < d["plug"] / 2 + 0.05 for q in pts))
    s = fillet_edges(s, corner, 0.5)
    fl_top = edges_where(s, lambda e, pts: all(abs(q.z - zf) < 0.02 for q in pts)
                         and all(max(abs(q.x - xc), abs(q.y)) > d["flange"] / 2 - 2.0 for q in pts))
    s = fillet_edges(s, fl_top, 0.3)
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
    if v(p.LID_TRAY):
        zf = z0 + v(p.LID_FLOOR)
        ztop = z0 + d["lid_t"]
        tray = prism_rrect(d["tray"], d["tray"], d["r_tray"], zf, ztop + 1.0, cx=xc, taper=-v(p.TRAY_DRAFT))
        tray = tray.fillet(3.0, min(tray.Faces(), key=lambda f: f.Center().z).Edges())
        s = s.cut(tray)
        rim = edges_where(s, lambda e, pts: all(abs(q.z - ztop) < 0.02 for q in pts)
                          and all(max(abs(q.x - xc), abs(q.y)) < d["tray"] / 2 + 1.5 for q in pts))
        try:
            s = fillet_edges(s, rim, 1.0)
        except Exception as ex:  # pragma: no cover
            print("WARN tray rim fillet:", ex)
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
    a_ax = cs / 2 * 0.98   # губка стискається об'ємно: осьовий розмір ≈ вільному
    half_c = d["groove_bottom_half"] + a_rad
    r_c = d["r_groove_bottom"] + a_rad
    wire = _rrect_wire(half_c, r_c, z, xc)
    # профіль у площині, перпендикулярній до шляху в середині передньої сторони (дотична = X)
    prof = cq.Workplane("YZ", origin=(xc, -half_c, z)).ellipse(a_rad, a_ax)
    return prof.sweep(cq.Workplane("XY").add(wire), transition="right").val()


def oring_free():
    """Відріз губчастого шнура у вільному стані, згорнутий у кільце (довжина по центру = seal_cut_len)."""
    cs = v(p.ORING_CS)
    r_c = d["seal_cut_len"] / (2 * math.pi)
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
def felt_pad():
    """v2.5: м'яка повстяна підкладка на дні кишені (самоклеюча), стадіон по пласкій частині дна."""
    inset = d["pocket_inset_floor"]
    fx = d["pocket_x"] - 2 * inset - 2 * v(p.POCKET_FLOOR_R) - 2 * v(p.FELT_INSET)
    fy = d["pocket_y"] - 2 * inset - 2 * v(p.POCKET_FLOOR_R) - 2 * v(p.FELT_INSET)
    z0 = d["pocket_floor"]
    pad = stadium_prism(fx, fy, d["pocket_cx"], d["pocket_cy"], z0, z0 + v(p.LINER_FLOOR))
    top = max(pad.Faces(), key=lambda f: f.Center().z)
    return pad.fillet(0.6, top.Edges())


def felt_pad_dims():
    inset = d["pocket_inset_floor"]
    fx = d["pocket_x"] - 2 * inset - 2 * v(p.POCKET_FLOOR_R) - 2 * v(p.FELT_INSET)
    fy = d["pocket_y"] - 2 * inset - 2 * v(p.POCKET_FLOOR_R) - 2 * v(p.FELT_INSET)
    return fx, fy


def relief_lid(product=True, grind_allow=0.0):
    """v2.5: кришечка полегшувальної порожнини (фланець урівень + пробка з канавкою під шнур Ø3)."""
    cx, cy, rw, rh = _relief_xy()
    z0 = v(p.LID_RECESS)
    ft = v(p.RL_FLANGE_T)
    fl = prism_rrect(d["rl_flange_w"], d["rl_flange_h"], d["rl_r_reb"] - v(p.RL_GAP), z0 - grind_allow, z0 + ft, cx=cx, cy=cy)
    zt = z0 + d["rl_t"]
    plug = prism_rrect(d["rl_plug_w"], d["rl_plug_h"], d["rl_r_plug"], z0 + ft - EPS, zt, cx=cx, cy=cy, taper=v(p.DRAFT_CAV))
    s = fl.fuse(plug).clean()
    top = max(s.Faces(), key=lambda f: f.Center().z)
    s = s.chamfer(0.8, None, top.Edges())
    zf = z0 + ft
    corner = edges_where(s, lambda e, pts: all(abs(q.z - zf) < 0.02 for q in pts)
                         and all(abs(q.x - cx) < d["rl_plug_w"] / 2 + 0.05 and abs(q.y - cy) < d["rl_plug_h"] / 2 + 0.05 for q in pts))
    s = fillet_edges(s, corner, 0.4)
    if product:
        bot = min(s.Faces(), key=lambda f: f.Center().z)
        s = s.fillet(0.6, bot.Edges())
    g0 = zf + v(p.RL_LAND)
    g1 = g0 + v(p.RL_GROOVE_W)
    gd = d["rl_groove_depth"]
    zm = (g0 + g1) / 2
    shrink = (zm - zf) * TAN_C
    gw, gh = d["rl_plug_w"] - 2 * shrink - 2 * gd, d["rl_plug_h"] - 2 * shrink - 2 * gd
    ring_out = prism_rrect(d["rl_plug_w"] + 6, d["rl_plug_h"] + 6, d["rl_r_plug"] + 3, g0, g1, cx=cx, cy=cy)
    ring_in = prism_rrect(gw, gh, max(1.0, d["rl_r_plug"] - shrink - gd), g0 - 1, g1 + 1, cx=cx, cy=cy)
    s = s.cut(ring_out.cut(ring_in))
    gedges = edges_where(s, lambda e, pts: all(abs(q.z - g0) < 0.02 or abs(q.z - g1) < 0.02 for q in pts))
    try:
        s = fillet_edges(s, gedges, 0.3)
    except Exception as ex:  # pragma: no cover
        print("WARN rl groove fillet:", ex)
    return s.clean()


def relief_seal():
    """Губчастий шнур Ø3 кришечки у встановленому стані (радіально — глибина залозу)."""
    cx, cy, rw, rh = _relief_xy()
    z0 = v(p.LID_RECESS) + v(p.RL_FLANGE_T)
    g0 = z0 + v(p.RL_LAND)
    zm = g0 + v(p.RL_GROOVE_W) / 2
    gd = d["rl_groove_depth"]
    shrink = (zm - z0) * TAN_C
    # фактичний залоз з урахуванням ухилів стінки порожнини (від z=0) і пробки (від основи пробки)
    gland = gd + v(p.RL_PLUG_GAP) - zm * TAN_C + (zm - z0) * TAN_C
    a_rad = gland / 2
    hw = (d["rl_plug_w"] - 2 * shrink) / 2 - gd + a_rad
    hh = (d["rl_plug_h"] - 2 * shrink) / 2 - gd + a_rad
    r_c = max(1.0, d["rl_r_plug"] - shrink - gd) + a_rad
    pts = [Vector(cx - hw, cy - hh, zm), Vector(cx + hw, cy - hh, zm), Vector(cx + hw, cy + hh, zm), Vector(cx - hw, cy + hh, zm)]
    w0 = cq.Wire.makePolygon(pts, close=True)
    w = w0.fillet2D(r_c, w0.Vertices())
    prof = cq.Workplane("YZ", origin=(cx, cy - hh, zm)).ellipse(a_rad, v(p.RL_CS) / 2 * 0.98)
    return prof.sweep(cq.Workplane("XY").add(w), transition="right").val()


def logo_fill(which="STICK"):
    """Об'єм дебосингу окремих частин логотипа (під фарбу): STICK + стік знака — RAL 7016;
    BOX + хвиля знака — бірюзовий. which: STICK | BOX | MARK_SWOOSH | MARK_BAR | GREY | TEAL."""
    if which.startswith("MARK") or which in ("GREY", "TEAL"):
        from . import brand
        ms = brand.mark_solids()
        if which == "MARK_SWOOSH":
            return ms["swoosh"]
        if which == "MARK_BAR":
            return cq.Compound.makeCompound([ms["stem"], ms["cap"]])
        txt = logo_fill("STICK" if which == "GREY" else "BOX")
        extra = [ms["stem"], ms["cap"]] if which == "GREY" else [ms["swoosh"]]
        return cq.Compound.makeCompound(list(txt.Solids()) + extra)
    from . import brand
    n = len("STICK")
    letters = brand.wordmark_solids()
    group = letters[:n] if which == "STICK" else letters[n:]
    return cq.Compound.makeCompound([s for _, ss in group for s in ss])


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
