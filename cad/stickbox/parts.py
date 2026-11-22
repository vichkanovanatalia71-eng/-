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
    tool = cav.fuse(reb).fuse(lead).clean()
    if v(p.WALL_ON):
        tool = _with_thin_walls(tool, sph)
    if v(p.ARM_ON):
        tool = _with_arm(tool)
    if v(p.NFC_ON):
        tool = tool.fuse(_nfc_pocket_tool()).clean()
    return tool


def _rr_sketch(x0, x1, y0, y1, r, r_right=None):
    """Прямокутник із заокругленими кутами; r_right — окремий радіус двох правих кутів (+X)."""
    sk = cq.Sketch().rect(x1 - x0, y1 - y0)
    if r_right is None or abs(r_right - r) < 1e-9:
        return sk.vertices().fillet(r)
    return sk.vertices("<X").fillet(r).reset().vertices(">X").fillet(r_right)


def _rr_wire(x0, x1, y0, y1, r, z, r_right=None):
    f = _rr_sketch(x0, x1, y0, y1, r, r_right)._faces.Faces()[0]
    return f.outerWire().translate(Vector((x0 + x1) / 2, (y0 + y1) / 2, z))


def _with_thin_walls(tool, sph):
    """v3.4: над зоною ущільнення резервуар ширшає до стінок WALL_T (фронт WALL_FRONT_T): шийка (стінка під шнуром,
    бортик ребейту) — без змін до порогу up_z0; далі похила смуга WALL_STEP_DEG до up_zt; вище — тонкостінна частина
    з тим самим ухилом, куполом стелі й R_CEIL. Права стінка (перегородка до кишені девайса) — без змін.
    Сердечник проходить шийку, підтискаючись усередину на up_step (після виймання хребта)."""
    zr, xc = d["z_reb"], d["cav_xc"]
    tn = math.tan(math.radians(v(p.DRAFT_CAV)))
    z0, zt = d["up_z0"], d["up_zt"]
    h = v(p.CAV) / 2
    def neck(z):
        e = (z - zr) * tn
        return (xc - h + e, xc + h - e, -h + e, h - e, v(p.R_CAV) - e)
    nx0, nx1, ny0, ny1, nr = neck(z0)
    ux1, nr_t = neck(zt)[1], neck(zt)[4]                  # права стінка і праві кути — продовження шийки
    up = (d["up_x0"], ux1, d["up_y0"], d["up_y1"], d["up_r"])
    trans = cq.Solid.makeLoft([_rr_wire(nx0, nx1, ny0, ny1, nr, z0), _rr_wire(*up, zt, r_right=nr_t)], True)
    top_extra = 3.0
    U = (cq.Workplane("XY", origin=((up[0] + up[1]) / 2, (up[2] + up[3]) / 2, zt - 0.01))
         .placeSketch(_rr_sketch(*up, r_right=nr_t)).extrude(d["z_ceil_c"] + top_extra - zt + 0.01, taper=v(p.DRAFT_CAV)).val())
    U = U.intersect(sph)
    top_face = max(U.Faces(), key=lambda f: f.Center().z)
    U = U.fillet(v(p.R_CEIL), top_face.Edges())
    # спільні грані (права стінка, купол) → звичайне об'єднання OCC мовчки повертає один операнд; нечітке (1 мкм) — коректне
    out = tool.fuse(trans, tol=1e-3).fuse(U, tol=1e-3).clean()
    assert out.isInside(Vector(d["up_x0"] + 0.5, 0, (zt + d["z_ceil_edge"]) / 2)), "thin-wall cavity fuse failed"
    return out


def base_void_dims():
    """v3.4: порожнина полегшення знизу під рампою плеча: план (x0, x1, y0, y1), стеля — площина рампи мінус WALL_T."""
    xc = d["cav_xc"]
    x0 = xc + d["reb"] / 2 + v(p.WALL_T)                      # 5 мм до ребейту кришки
    x1 = v(p.W) / 2 - v(p.WALL_T)
    y0 = d["pocket_cy"] + d["pocket_y"] / 2 + v(p.WALL_T)       # 5 мм до заднього торця кишені девайса
    y1 = v(p.D) / 2 - v(p.WALL_T)
    sill = d["arm_sill_z"]
    xs = d["cav_x1"] - (sill - d["z_reb"]) * math.tan(math.radians(v(p.DRAFT_CAV)))
    t = math.radians(v(p.ARM_RAMP_DEG))
    zv = lambda x: sill + (x - xs) * math.tan(t) - v(p.WALL_T) / math.cos(t)
    return dict(x0=x0, x1=x1, y0=y0, y1=y1, zv=zv, z_at_x0=zv(x0), z_at_x1=zv(x1))


def base_void_tool(z_bottom=-3.0):
    """Тіло порожнини полегшення (віднімається з корпусу; та сама форма — друкована вставка на мості сердечника)."""
    b = base_void_dims()
    x0, x1, y0, y1 = b["x0"], b["x1"], b["y0"], b["y1"]
    ztop = b["z_at_x1"] + 1.0
    V = prism_rrect(x1 - x0, y1 - y0, v(p.BASE_VOID_R), z_bottom, ztop, cx=(x0 + x1) / 2, cy=(y0 + y1) / 2,
                    taper=v(p.BASE_VOID_DRAFT))
    xa, xb = x0 - 5, x1 + 5
    pts = [(xa, z_bottom - 1), (xb, z_bottom - 1), (xb, b["zv"](xb)), (xa, b["zv"](xa))]
    keep = cq.Workplane("XZ", origin=(0, 60, 0)).polyline(pts).close().extrude(120).val()
    V = V.intersect(keep)
    try:   # внутрішній кут стеля→стінки порожнини R2 (без концентратора напружень)
        top = [f for f in V.Faces() if f.normalAt().z > 0.3 and f.Center().z > b["z_at_x0"] - 1]
        V = V.fillet(2.0, [e for f in top for e in f.Edges()])
    except Exception as ex:  # pragma: no cover
        print("WARN base void fillet:", ex)
    return V


def _nfc_pocket_tool():
    """v3.3: кишеня під NFC-мітку в стелі порожнини (зсередини): Ø NFC_POCKET_D біля стелі, звуження NFC_POCKET_TAPER
    догори; дно кишені (верх) — на NFC_COVER нижче верхньої грані. Сердечник отримує відповідний виступ."""
    x, y = v(p.NFC_X), v(p.NFC_Y)
    z_top = v(p.H) - v(p.NFC_COVER)
    z0 = d["z_ceil_edge"] - 1.0                      # нижче купола — початок усередині порожнини
    h = z_top - z0
    r0 = v(p.NFC_POCKET_D) / 2
    r1 = r0 - (z_top - d["z_ceil_c"]) * math.tan(math.radians(v(p.NFC_POCKET_TAPER)))
    r_base = r1 + h * math.tan(math.radians(v(p.NFC_POCKET_TAPER)))
    return cq.Solid.makeCone(r_base, r1, h, Vector(x, y, z0), Vector(0, 0, 1))


def nfc_pocket_dims():
    """(z дна кишені, z стелі в центрі мітки, глибина від стелі, Ø біля стелі, Ø угорі)."""
    x, y = v(p.NFC_X), v(p.NFC_Y)
    R = d["r_dome"]
    rr = math.hypot(x - d["cav_xc"], y)
    z_c = d["z_ceil_c"] - (R - math.sqrt(R * R - rr * rr))
    z_top = v(p.H) - v(p.NFC_COVER)
    t = math.tan(math.radians(v(p.NFC_POCKET_TAPER)))
    r1 = v(p.NFC_POCKET_D) / 2 - (z_top - d["z_ceil_c"]) * t
    return dict(z_top=z_top, z_ceil=z_c, depth=z_top - z_c, d_ceil=2 * (r1 + (z_top - z_c) * t), d_top=2 * r1,
                slab=v(p.H) - z_c)


def nfc_tag():
    """Довідкова модель NFC-мітки (наліпка Ø NFC_TAG_D), приклеєна до дна кишені (обличчям у порожнину)."""
    x, y = v(p.NFC_X), v(p.NFC_Y)
    z_top = v(p.H) - v(p.NFC_COVER)
    return cq.Solid.makeCylinder(v(p.NFC_TAG_D) / 2, v(p.NFC_TAG_T), Vector(x, y, z_top - v(p.NFC_TAG_T)))


def has_relief_lid():
    return bool(v(p.RELIEF_ON) and v(p.RL_ON))


def _arm_tool():
    """v3.0: плече Г-подібного резервуара за кишенею девайса.
    Знизу — поріг (стінка під ущільнювачем суцільна) і рампа ARM_RAMP_DEG до порогу.
    Стеля пласка на висоті краю купола, заокруглення R_CEIL робиться на простій призмі (стабільна геометрія OCC)."""
    R = d["arm_r"] if v(p.WALL_ON) else v(p.ARM_R)
    x0 = d["cav_x1"] - v(p.R_CAV) - R - 2.0          # заходить у пряму ділянку задньої стінки основної порожнини
    x1, y0, y1 = d["arm_x1"], d["arm_y0"], d["arm_y1"]
    A = prism_rrect(x1 - x0, y1 - y0, R, d["z_reb"], d["z_ceil_edge"], cx=(x0 + x1) / 2, cy=(y0 + y1) / 2,
                    taper=v(p.DRAFT_CAV))
    top = max(A.Faces(), key=lambda f: f.Center().z)
    try:
        A = A.fillet(v(p.R_CEIL), top.Edges())
    except Exception as ex:  # pragma: no cover
        print("WARN arm ceiling fillet:", ex)
    return A.intersect(_arm_keep(x0 - 5, x1 + 5, top=d["z_ceil_edge"] + 5.0))


def _arm_keep(xa, xb, top=None):
    """Призма «над рампою/порогом і під стелею плеча» (переріз XZ, витягнута по Y).
    Рампа починається точно на верхній кромці стінки основної порожнини з ухилом (без пласкої смужки)."""
    sill = d["arm_sill_z"]
    xs = d["cav_x1"] - (sill - d["z_reb"]) * math.tan(math.radians(v(p.DRAFT_CAV)))
    ce = d["z_ceil_edge"] if top is None else top
    t = math.tan(math.radians(v(p.ARM_RAMP_DEG)))
    f = math.tan(math.radians(v(p.ARM_CEIL_SLOPE))) if top is None else 0.0
    pts = [(xa, sill), (xs, sill), (xb, sill + (xb - xs) * t), (xb, ce - (xb - xs) * f), (xs, ce), (xa, ce)]
    return cq.Workplane("XZ", origin=(0, 60, 0)).polyline(pts).close().extrude(120).val()


def _with_arm(tool):
    arm = _arm_tool()
    u = tool.fuse(arm).clean()
    xs, y0, sill = d["cav_x1"], d["arm_y0"], d["arm_sill_z"]
    # кут колонки тримача, що виступає в резервуар → R ARM_CORNER_R (лофт чверть-кола вздовж ребра з ухилами обох стінок;
    # починається над рампою, щоб не підрізати її)
    R = v(p.ARM_CORNER_R)
    tn = math.tan(math.radians(v(p.DRAFT_CAV)))
    zr = d["z_reb"]
    za = sill - 0.5
    zb = d["z_ceil_edge"] - v(p.R_CEIL) - 1.0   # нижче зони заокруглення стелі (без дотичних граней)
    def prof(z):
        cx, cy = xs - (z - zr) * tn, y0 + (z - zr) * tn
        m = (cx + R - R / math.sqrt(2), cy - R + R / math.sqrt(2))
        return (cq.Workplane("XY", origin=(0, 0, z)).moveTo(cx - 0.3, cy + 0.3).lineTo(cx + R, cy + 0.3).lineTo(cx + R, cy)
                .threePointArc(m, (cx, cy - R)).lineTo(cx - 0.3, cy - R).close().wires().val())
    try:
        cutter = cq.Solid.makeLoft([prof(za), prof(zb)], True)
        cutter = cutter.intersect(_arm_keep(xs - 10, xs + 3 * R, top=zb + 1))   # низ різця — площина рампи (без уступу)
        u = u.fuse(cutter).clean()
    except Exception as ex:  # pragma: no cover
        print("WARN arm column corner:", ex)
    # кромка порогу (стінка основної порожнини → рампа / пласка ділянка в куті R16) → R ARM_SILL_R
    tn_ = math.tan(math.radians(v(p.DRAFT_CAV)))
    xw = xs - (sill - d["z_reb"]) * tn_
    rc = v(p.R_CAV) - (sill - d["z_reb"]) * tn_
    ccx, ccy = xs - v(p.R_CAV), d["cav_y1"] - v(p.R_CAV)
    def on_line(e, pts):
        return all(abs(q.z - sill) < 0.05 and abs(q.x - xw) < 0.3 and y0 - v(p.ARM_CORNER_R) - 1 < q.y <= ccy + 0.3 for q in pts)
    def on_arc(e, pts):
        return all(abs(q.z - sill) < 0.05 and q.y > ccy - 0.3 and abs(math.hypot(q.x - ccx, q.y - ccy) - rc) < 0.3 for q in pts)
    # кромка порогу — фаски (пряма ділянка 1.5, дуга R16 1.2): аналітичні грані; заокруглення OCC на ланцюжку лінія→дуга
    # будує B-сплайн, що заходить у смугу ущільнювача (перевірено) — тому фаски
    # фаска прямої ділянки порогу (стінка → рампа) — явна трикутна призма вздовж кромки (площини, стабільний допуск)
    c = v(p.ARM_SILL_R) * 0.75
    th = math.radians(v(p.ARM_RAMP_DEG))
    tri = [(xw - 0.05, sill - c), (xw - 0.05, sill + 0.05), (xw + c * math.cos(th), sill + c * math.sin(th) + 0.05)]
    ya, yb = y0 - v(p.ARM_CORNER_R) - 0.5, ccy
    try:
        wedge = cq.Workplane("XZ", origin=(0, yb, 0)).polyline(tri).close().extrude(yb - ya).val()
        u = u.fuse(wedge).clean()
        d["arm_sill_r_applied"] = c
    except Exception as ex:  # pragma: no cover
        print("WARN arm sill chamfer:", ex)
    # дуга R16 (стінка → пласкі «серпик», 90°): фаску OCC будує з допуском вершин ≈5.7 мм (неприйнятно для STEP/друку
    # майстрів) — кромку не моделюємо, притупити вручну шліфувальною губкою (доступна через отвір кришки)
    return u


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
    # v2.9: овал (стадіон) під овальний девайс; якщо POCKET_R менший за півширину — заокруглений прямокутник
    if v(p.POCKET_R) >= d["pocket_x"] / 2 - 1e-6:
        pk = stadium_prism(wx0, wy0, d["pocket_cx"], d["pocket_cy"], zf, H + extra, taper=-v(p.DRAFT_POCKET))
    else:
        pk = prism_rrect(wx0, wy0, v(p.POCKET_R) - inset, zf, H + extra, cx=d["pocket_cx"], cy=d["pocket_cy"],
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
    """Пальцева виїмка основної кришки у нерухомому корпусі (v2.7: задня грань, на осі кришки)."""
    w, r = v(p.RECESS_W), v(p.RECESS_R)
    top = d["recess_top"]
    s_ = 1 if v(p.RECESS_SIDE) > 0 else -1
    y0 = s_ * (v(p.D) / 2 + 2)
    # наскрізь до лицьової поверхні пробки, включно із зоною кутового радіуса порожнини
    y1 = (d["cav_y1"] - v(p.R_CAV)) if s_ > 0 else (d["cav_y0"] + v(p.R_CAV))
    prof = (cq.Workplane("XZ", origin=(d["recess_x"], y0, 0))
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
    sw = brand.wordmark_swoosh_solid()          # v3.2: хвиля знака-I
    if sw is not None:
        sols.append(sw)
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
            s_ = 1 if v(p.RECESS_SIDE) > 0 else -1
            rx = d["recess_x"]
            def on_recess(e, pts):
                return (all(abs(q.x - rx) <= v(p.RECESS_W) / 2 + 0.05 for q in pts)
                        and all(abs(q.y - s_ * v(p.D) / 2) < 0.02 for q in pts)
                        and all(-height_extra + 0.05 < q.z < 10 for q in pts))
            try:
                s = fillet_edges(s, edges_where(s, on_recess), 1.5)
            except Exception as ex:  # pragma: no cover
                print("WARN recess fillet:", ex)
            # кромка «стеля виїмки / стінка порожнини»: по ній проходить ущільнювач (аудит C2) → R1.5
            rt = d["recess_top"]
            def ceil_back(e, pts):
                return (all(abs(q.z - rt) < 0.02 for q in pts)
                        and all(abs(q.x - rx) <= v(p.RECESS_W) / 2 + 0.05 for q in pts)
                        and all(s_ * q.y < v(p.D) / 2 - 2.0 for q in pts))
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
            if with_recess and v(p.RL_RECESS_ON):
                s = s.cut(_rl_recess_tool())
                xr, wr, rtop = v(p.W) / 2, v(p.RL_RECESS_W), d["rl_recess_top"]
                on_face = lambda e, pts: (all(abs(q.x - xr) < 0.02 for q in pts)
                                          and all(abs(q.y - rcy) <= wr / 2 + 0.05 for q in pts)
                                          and all(-height_extra + 0.05 < q.z < rtop + 0.1 for q in pts))
                ceil_in = lambda e, pts: (all(abs(q.z - rtop) < 0.02 for q in pts)
                                          and all(abs(q.y - rcy) <= wr / 2 + 0.05 for q in pts)
                                          and all(q.x < xr - 2.0 for q in pts))
                for sel, r in ((on_face, 1.5), (ceil_in, 1.5)):
                    try:
                        s = fillet_edges(s, edges_where(s, sel), r)
                    except Exception as ex:  # pragma: no cover
                        print("WARN rl recess fillet:", ex)

    if with_cavity and v(p.BASE_VOID_ON):            # v3.4: порожнина полегшення знизу (формує вставка, не зовнішня форма)
        s = s.cut(base_void_tool(z_bottom=-height_extra - 2.0))
    if with_logo:
        s = s.cut(_logo_tool())
        if v(p.MARK_ON):
            from . import brand
            s = s.cut(brand.mark_tool())
        if v(p.NFC_ON):                                  # v3.3: знак NFC на верхній грані
            from . import brand
            ns = brand.nfc_symbol_solids()
            s = s.cut(cq.Compound.makeCompound(ns["waves"] + ns["text"]))
    return s.clean()


def _rl_recess_tool():
    """v2.7: пальцева виїмка кришечки полегшення — права грань, по центру кришечки; наскрізь у порожнину."""
    cx, cy, rw, rh = _relief_xy()
    w, r, top = v(p.RL_RECESS_W), v(p.RL_RECESS_R), d["rl_recess_top"]
    x0 = v(p.W) / 2 + 2
    x1 = d["rel_x1"] - 2.0
    prof = (cq.Workplane("YZ", origin=(x0, cy, 0))
            .moveTo(-w / 2, -1).lineTo(w / 2, -1).lineTo(w / 2, top - r)
            .radiusArc((w / 2 - r, top), -r)
            .lineTo(-w / 2 + r, top)
            .radiusArc((-w / 2, top - r), -r)
            .close())
    return prof.extrude(-(x0 - x1)).val()


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
def _lid_tab(c_along, edge, sgn, axis, notch_w, z0, grind_allow, ref_c=None):
    """Язичок кришки: від кромки фланця (edge) назовні до грані корпусу − LID_TAB_INSET, у межах ширини виїмки.
    axis — вісь, уздовж якої язичок виходить назовні ("y" — задня грань, "x" — права грань)."""
    w = notch_w - 2 * v(p.LID_TAB_GAP)
    face = (v(p.D) if axis == "y" else v(p.W)) / 2
    out = sgn * (face - v(p.LID_TAB_INSET))
    inn = edge - sgn * 3.0                     # заходить у фланець на 3 мм (злиття)
    L = abs(out - inn)
    mid = (out + inn) / 2
    zb, zt = z0 - grind_allow, z0 + v(p.LID_TAB_T)
    if axis == "y":
        t = prism_rrect(w, L, v(p.LID_TAB_R), zb, zt, cx=c_along, cy=mid)
        top = lambda e, pts: all(abs(q.z - zt) < 0.02 for q in pts) and all(sgn * q.y > sgn * edge + 0.3 for q in pts)
    else:
        t = prism_rrect(L, w, v(p.LID_TAB_R), zb, zt, cx=mid, cy=c_along)
        top = lambda e, pts: all(abs(q.z - zt) < 0.02 for q in pts) and all(sgn * q.x > sgn * edge + 0.3 for q in pts)
    try:
        t = fillet_edges(t, edges_where(t, top), 0.8)
    except Exception as ex:  # pragma: no cover
        print("WARN tab fillet:", ex)
    return t


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
    if v(p.LID_TAB_ON):   # v2.9: язичок у виїмці корпусу
        s_ = 1 if v(p.RECESS_SIDE) > 0 else -1
        s = s.fuse(_lid_tab(d["recess_x"], s_ * (d["flange"] / 2), s_, "y", v(p.RECESS_W), z0, grind_allow, ref_c=0.0)).clean()
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
    if v(p.POCKET_R) >= d["pocket_x"] / 2 - 1e-6:
        pad = stadium_prism(fx, fy, d["pocket_cx"], d["pocket_cy"], z0, z0 + v(p.LINER_FLOOR))
    else:
        rf = max(1.0, v(p.POCKET_R) - inset - v(p.POCKET_FLOOR_R) - v(p.FELT_INSET))
        pad = prism_rrect(fx, fy, rf, z0, z0 + v(p.LINER_FLOOR), cx=d["pocket_cx"], cy=d["pocket_cy"])
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
    zc = zt - v(p.RL_CHAMF_H)
    plug = prism_rrect(d["rl_plug_w"], d["rl_plug_h"], d["rl_r_plug"], z0 + ft - EPS, zc + EPS, cx=cx, cy=cy, taper=v(p.DRAFT_CAV))
    # v2.7: верх пробки — фаска R×H (антизаклинювання при знятті за правий край через виїмку)
    inset = (zc - (z0 + ft)) * TAN_C
    ang = math.degrees(math.atan2(v(p.RL_CHAMF_R), v(p.RL_CHAMF_H)))
    lr = v(p.RL_LIP_RELIEF)
    cap = prism_rrect(d["rl_plug_w"] - 2 * inset - 2 * lr, d["rl_plug_h"] - 2 * inset - 2 * lr, d["rl_r_plug"] - inset - lr,
                      zc, zt, cx=cx, cy=cy, taper=ang)
    zf = z0 + ft
    # бортик над канавкою — уступ RL_LIP_RELIEF всередину (від верху канавки до фаски)
    g1_ = zf + v(p.RL_LAND) + v(p.RL_GROOVE_W)
    ins_g = (g1_ - zf) * TAN_C
    lip_out = prism_rrect(d["rl_plug_w"] + 6, d["rl_plug_h"] + 6, d["rl_r_plug"] + 3, g1_, zc + 1, cx=cx, cy=cy)
    lip_in = prism_rrect(d["rl_plug_w"] - 2 * ins_g - 2 * lr, d["rl_plug_h"] - 2 * ins_g - 2 * lr, d["rl_r_plug"] - ins_g - lr,
                         g1_ - 0.01, zc + 1.01, cx=cx, cy=cy, taper=v(p.DRAFT_CAV))
    plug = plug.cut(lip_out.cut(lip_in))
    s = fl.fuse(plug).fuse(cap).clean()
    corner = edges_where(s, lambda e, pts: all(abs(q.z - zf) < 0.02 for q in pts)
                         and all(abs(q.x - cx) < d["rl_plug_w"] / 2 + 0.05 and abs(q.y - cy) < d["rl_plug_h"] / 2 + 0.05 for q in pts))
    s = fillet_edges(s, corner, 0.4)
    if v(p.LID_TAB_ON) and v(p.RL_RECESS_ON):   # v2.9: язичок у виїмці правої грані
        s = s.fuse(_lid_tab(cy, cx + d["rl_flange_w"] / 2, 1, "x", v(p.RL_RECESS_W), z0, grind_allow)).clean()
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
    """Об'єм дебосингу окремих частин логотипа (під фарбу): STICK (з v3.2 I = стік і «крапка» знака) — RAL 7016;
    BOX + хвиля знака — бірюзовий. which: STICK | BOX | MARK_SWOOSH | MARK_BAR | GREY | TEAL."""
    if which.startswith("MARK") or which in ("GREY", "TEAL"):
        from . import brand
        if v(p.MARK_ON):   # окремий знак над написом (до v3.2)
            ms = brand.mark_solids()
            bar, sw = [ms["stem"], ms["cap"]], [ms["swoosh"]]
        else:              # v3.2: знак — літера I напису; стік і «крапка» вже в групі STICK
            bar, sw = [], [s for s in [brand.wordmark_swoosh_solid()] if s is not None]
        if which == "MARK_SWOOSH":
            return cq.Compound.makeCompound(sw)
        if which == "MARK_BAR":
            if not bar:
                return cq.Compound.makeCompound([s for ch, ss in brand.wordmark_solids() if ch == "I" for s in ss])
            return cq.Compound.makeCompound(bar)
        txt = logo_fill("STICK" if which == "GREY" else "BOX")
        extra = bar if which == "GREY" else sw
        if v(p.NFC_ON):   # v3.3: знак NFC — слово NFC темно-сіре, дуги бірюзові
            ns = brand.nfc_symbol_solids()
            extra = extra + (ns["text"] if which == "GREY" else ns["waves"])
        return cq.Compound.makeCompound(list(txt.Solids()) + extra)
    from . import brand
    n = len("STICK")
    letters = brand.wordmark_solids()
    group = letters[:n] if which == "STICK" else letters[n:]
    return cq.Compound.makeCompound([s for _, ss in group for s in ss])


def device(corner_r=None):
    """Габаритна модель ILUMA ONE: заокруглений прямокутник 16.4 × 30.6, кутовий радіус DEV_R (припущення)."""
    cx, cy = d["pocket_cx"], d["pocket_cy"]
    z0 = d["dev_z0"]
    r = v(p.DEV_R) if corner_r is None else corner_r
    if r >= v(p.DEV_T) / 2 - 1e-6:
        s = stadium_prism(v(p.DEV_T), v(p.DEV_W), cx, cy, z0, z0 + v(p.DEV_L))
    else:
        s = prism_rrect(v(p.DEV_T), v(p.DEV_W), r, z0, z0 + v(p.DEV_L), cx=cx, cy=cy)
    ends = [f for f in s.Faces() if abs(f.Center().z - z0) < 0.01 or abs(f.Center().z - (z0 + v(p.DEV_L))) < 0.01]
    for fr in (5.0, 4.0, 3.0):
        try:
            return s.fillet(fr, [e for f in ends for e in f.Edges()])
        except Exception:
            continue
    return s


def device_controls():
    """Світлова смужка та кнопка на вузькій грані девайса, зверненій до фронту (довідково, за фото замовника)."""
    cx = d["pocket_cx"]
    yf = d["pocket_cy"] - v(p.DEV_W) / 2
    w = v(p.DEV_CTRL_W)
    def pad(z0, z1, width):
        L = z1 - z0
        slab = (cq.Workplane("XZ", origin=(cx, yf - 0.15, 0)).center(0, (z0 + z1) / 2)
                .slot2D(L, width, angle=90).extrude(-1.5).val())
        shell = stadium_prism(v(p.DEV_T) + 0.3, v(p.DEV_W) + 0.3, cx, d["pocket_cy"], z0 - 1, z1 + 1)
        return slab.intersect(shell)   # накладка повторює овальну грань девайса
    led = pad(d["btn_z1"] + 0.8, d["led_z1"], w)      # v2.8: смужка ближче до торця зі стіком
    btn = pad(d["btn_z0"], d["btn_z1"], w - 0.3)
    return led, btn


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
