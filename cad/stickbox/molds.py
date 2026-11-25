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

# --- v3.7: розбірний каркас (материнська форма) для заливки силікону й лиття бетону ---
# Силікон — рівновіддалений від майстра (внутрішній контур каркаса = контур майстра + товщина), тож тонших місць немає;
# каркас — 2 половини (фронт / зад) з фланцями на болтах M4 і шпунтом; ключі всередині фіксують силіконовий блок
# по висоті (не витягується разом із виливком/сердечником); зовнішні обручі — жорсткість стінок при литті бетону.
SIL_SIDE = 15.0      # силікон з боків корпусу (номінал)
SIL_TOP = 15.0       # силікон над верхом майстра корпусу
LID_SIL_SIDE = 14.0  # силікон з боків кришки
LID_SIL_TOP = 12.0   # силікон над верхом майстра кришки
SIL_MIN = 12.0       # мінімум силікону між каркасом і майстром (у місцях ключів)
FRAME_T = 5.0        # стінка каркаса
KEY_H = 3.0          # висота ключа (виступ усередину) — корпус; кришка — 2.0
KEY_B, KEY_TOP = 9.0, 3.0   # основа / вершина трапецієподібного ключа (грані 45° — друк без підтримок)
HOOP_D, HOOP_T = 8.0, 4.0   # зовнішні обручі жорсткості: виліт / товщина
FL_W, FL_T = 12.0, 6.0      # фланці роз'єму: виліт від стінки / товщина кожної половини
BOLT_HOLE = 4.5             # отвори під болти M4
TONGUE_W, TONGUE_H = 2.0, 1.5   # шпунт на торці передньої половини
GROOVE_W, GROOVE_H = 2.5, 1.9   # паз на задній половині (зазор 0.25 на сторону)
RIM_H, RIM_W, RIM_GAP = 3.0, 3.0, 0.3   # бортик плити заливки навколо каркаса


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


_FRAME_CACHE = {}


def frame_spec(kind="body"):
    """Внутрішній контур каркаса = габарит майстра + товщина силікону; кути — R майстра + товщина (рівновіддалено)."""
    if kind in _FRAME_CACHE:
        return _FRAME_CACHE[kind]
    if kind == "body":
        bb = body_master().BoundingBox()
        ts, tt, key_h = SIL_SIDE, SIL_TOP, KEY_H
        r_m = v(p.R_V) * K
        n_key, hoops, bolts = 2, (0.0, 1 / 3, 2 / 3, 1.0), (1 / 6, 1 / 2, 5 / 6)
    else:
        bb = lid_master("main" if kind == "lid" else kind).BoundingBox()
        ts, tt, key_h = LID_SIL_SIDE, LID_SIL_TOP, 2.0
        r_m = (v(p.CAV_R_OUT) - v(p.PLUG_GAP)) * K if v(p.FULL_LID_ON) else v(p.R_CAV) * K
        n_key, hoops, bolts = 1, (0.0, 1.0), (0.5,)
    w, h = bb.xlen + 2 * ts, bb.ylen + 2 * ts
    sp = dict(kind=kind, cx=(bb.xmin + bb.xmax) / 2, cy=(bb.ymin + bb.ymax) / 2, w=w, h=h, r=r_m + ts, r_master=r_m,
              z0=bb.zmin, z1=bb.zmax + tt, t_side=ts, t_top=tt, key_h=key_h, n_key=n_key, hoops=hoops, bolts=bolts,
              master_bb=(bb.xmin, bb.xmax, bb.ymin, bb.ymax, bb.zmin, bb.zmax))
    sp["hf"] = sp["z1"] - sp["z0"]
    sp["key_z"] = [sp["z0"] + sp["hf"] * (i + 1) / (n_key + 1) for i in range(n_key)]
    _FRAME_CACHE[kind] = sp
    return sp


def _frame_lugs(sp):
    """Вушка під шпильки M5 — на діагоналях кутів, впритул до заокругленої стінки."""
    ax, ay = sp["w"] / 2 - sp["r"], sp["h"] / 2 - sp["r"]
    dd = (sp["r"] + FRAME_T + LUG / 2 - 1.5) / math.sqrt(2)
    return [(sp["cx"] + sx * (ax + dd), sp["cy"] + sy * (ay + dd)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def _sleeve_dims():
    """Сумісність: прямокутник внутрішнього контуру каркаса корпусу (ix0, ix1, iy0, iy1, z0, z1)."""
    sp = frame_spec("body")
    return (sp["cx"] - sp["w"] / 2, sp["cx"] + sp["w"] / 2, sp["cy"] - sp["h"] / 2, sp["cy"] + sp["h"] / 2, sp["z0"], sp["z1"])


def lug_positions():
    return _frame_lugs(frame_spec("body"))


def frame_inner(sp, extra=0.0):
    """Порожнина каркаса (без ключів)."""
    return P.prism_rrect(sp["w"], sp["h"], sp["r"], sp["z0"] - extra, sp["z1"] + extra, cx=sp["cx"], cy=sp["cy"])


def frame_keys(sp):
    """Ключі: трапецієподібні виступи всередину на фронтальній і задній прямих ділянках (по X)."""
    kh = sp["key_h"]
    L = sp["w"] - 2 * sp["r"] - 4.0                       # лише пряма ділянка (кути — без ключів: вільне розкриття)
    keys = []
    for zk in sp["key_z"]:
        for sy in (-1, 1):
            y_wall = sp["cy"] + sy * sp["h"] / 2
            prof = (cq.Workplane("YZ", origin=(sp["cx"] - L / 2, 0, 0))
                    .polyline([(y_wall + sy * 0.5, zk - KEY_B / 2), (y_wall - sy * kh, zk - KEY_TOP / 2),
                               (y_wall - sy * kh, zk + KEY_TOP / 2), (y_wall + sy * 0.5, zk + KEY_B / 2)]).close()
                    .extrude(L).val())
            # торці ключа — скіс 45° у плані (плавний вихід канавки в силіконі, без різкого уступу)
            plan = (cq.Workplane("XY", origin=(0, 0, zk - KEY_B / 2 - 1))
                    .polyline([(sp["cx"] - L / 2, y_wall + sy * 0.6), (sp["cx"] - L / 2 + kh + 0.6, y_wall - sy * (kh + 0.01)),
                               (sp["cx"] + L / 2 - kh - 0.6, y_wall - sy * (kh + 0.01)), (sp["cx"] + L / 2, y_wall + sy * 0.6)]).close()
                    .extrude(KEY_B + 2).val())
            keys.append(prof.intersect(plan))
    out = keys[0]
    for k_ in keys[1:]:
        out = out.fuse(k_)
    return out


def _rr_wire(sp, off, z):
    w, h, r = sp["w"] / 2 + off, sp["h"] / 2 + off, sp["r"] + off
    return P._rr_wire(sp["cx"] - w, sp["cx"] + w, sp["cy"] - h, sp["cy"] + h, r, z)


def _hoop(sp, f):
    """Обруч: плоска смуга HOOP_T × HOOP_D; знизу (крім обруча на столі принтера, z0) — скіс 45°, друк без підтримок."""
    t, z0, z1 = FRAME_T, sp["z0"], sp["z1"]
    if f <= 0.0:
        return _rrp((sp["cx"], sp["cy"]), sp["w"] + 2 * (t + HOOP_D), sp["h"] + 2 * (t + HOOP_D), sp["r"] + t + HOOP_D, z0, HOOP_T)
    zt = min(z0 + f * sp["hf"] + HOOP_T / 2, z1)
    zb = zt - HOOP_T
    flat = _rrp((sp["cx"], sp["cy"]), sp["w"] + 2 * (t + HOOP_D), sp["h"] + 2 * (t + HOOP_D), sp["r"] + t + HOOP_D, zb, HOOP_T)
    cham = cq.Solid.makeLoft([_rr_wire(sp, t - 0.5, zb - HOOP_D - 0.5), _rr_wire(sp, t + HOOP_D, zb)], True)
    return flat.fuse(cham)


def _frame_whole(sp):
    """Каркас цілим (до розрізання на половини)."""
    t = FRAME_T
    cxy = (sp["cx"], sp["cy"])
    z0, z1 = sp["z0"], sp["z1"]
    outer = _rrp(cxy, sp["w"] + 2 * t, sp["h"] + 2 * t, sp["r"] + t, z0, sp["hf"])
    s = outer
    for f in sp["hoops"]:                                   # обручі жорсткості (на торцях — широкі опорні поверхні)
        s = s.fuse(_hoop(sp, f))
    xo = sp["w"] / 2 + t
    for sx in (-1, 1):                                       # фланці роз'єму (площина y = cy)
        xa, xb = sorted((sp["cx"] + sx * (xo - 1.0), sp["cx"] + sx * (xo + FL_W)))
        s = s.fuse(box(xa, xb, sp["cy"] - FL_T, sp["cy"] + FL_T, z0, z1))
    for (x, y) in _frame_lugs(sp):                          # вушка під шпильки M5
        s = s.fuse(cyl(LUG / 2, z0, z1, x, y))
        ang = math.atan2(y - sp["cy"], x - sp["cx"])
        web = (cq.Workplane("XY", origin=(x, y, z0)).transformed(rotate=(0, 0, math.degrees(ang)))
               .center(-LUG / 2, 0).rect(LUG, LUG * 0.8).extrude(sp["hf"]).val())
        s = s.fuse(web)
    s = s.cut(frame_inner(sp, extra=1.0))
    s = s.fuse(frame_keys(sp))
    for (x, y) in _frame_lugs(sp):
        s = s.cut(cyl(PIN_HOLE / 2, z0 - 1, z1 + 1, x, y))
    for f in sp["bolts"]:
        zc = z0 + f * sp["hf"]
        for sx in (-1, 1):
            xb_ = sp["cx"] + sx * (xo + FL_W / 2)
            s = s.cut(cq.Solid.makeCylinder(BOLT_HOLE / 2, 2 * FL_T + 2, Vector(xb_, sp["cy"] - FL_T - 1, zc), Vector(0, 1, 0)))
    return s.clean()


_HALVES_CACHE = {}


def frame_halves(kind="body"):
    """Передня (y < cy) і задня (y > cy) половини; шпунт на передній, паз на задній (по товщині стінки, на всю висоту)."""
    if kind not in _HALVES_CACHE:
        _HALVES_CACHE[kind] = _frame_halves(kind)
    return _HALVES_CACHE[kind]


def _frame_halves(kind):
    sp = frame_spec(kind)
    whole = _frame_whole(sp)
    big = 600
    front = whole.intersect(box(-big, big, -big, sp["cy"], -big, big))
    back = whole.intersect(box(-big, big, sp["cy"], big, -big, big))
    xm = sp["w"] / 2 + FRAME_T / 2
    for sx in (-1, 1):
        x = sp["cx"] + sx * xm
        front = front.fuse(box(x - TONGUE_W / 2, x + TONGUE_W / 2, sp["cy"] - 0.01, sp["cy"] + TONGUE_H, sp["z0"], sp["z1"]))
        back = back.cut(box(x - GROOVE_W / 2, x + GROOVE_W / 2, sp["cy"] - 1, sp["cy"] + GROOVE_H, sp["z0"] - 1, sp["z1"] + 1))
    return front.clean(), back.clean()


def mold_silicone(kind="body"):
    """Силіконовий блок форми: порожнина каркаса − ключі − майстер (− ребро «пальця» для корпусу)."""
    sp = frame_spec(kind)
    sil = frame_inner(sp).cut(frame_keys(sp))
    if kind == "body":
        st = finger_stiffener()
        sil = sil.cut(body_master()).cut(st)
        # гнізда Ø3.2 у фланці ребра займають штифти тримача T17 — силікону там немає
        cx, cy = d["pocket_cx"] * K, d["pocket_cy"] * K
        zt = st.BoundingBox().zmax
        for dy in (-18, 18):
            sil = sil.cut(cyl(1.6, zt - 3.0, zt + 0.5, cx, cy + dy))   # лише в товщі фланця (3 мм)
    else:
        sil = sil.cut(lid_master("main" if kind == "lid" else kind))
    # дрібні замкнені об'єми — гнізда штифтів у низі майстра (їх займають штифти плити), не силікон
    sols = sorted(sil.clean().Solids(), key=lambda q: -q.Volume())
    return sols[0]


def body_sleeve():
    """Каркас корпусу (обидві половини разом) — для візуалізації; друкуються окремо: T02a, T02b."""
    f, b = frame_halves("body")
    return cq.Compound.makeCompound([f, b])


def _plate(sp, lugs, master_pins, pin_r, t=6.0):
    """Плита заливки силікону: штифти у вушка каркаса, штифти майстра, бортик навколо каркаса (герметичність стику)."""
    m = 3.0                                   # поле за бортиком (вушка й штифти — всередині контуру обручів)
    cxy = (sp["cx"], sp["cy"])
    z0 = sp["z0"]
    ow, oh, orr = sp["w"] + 2 * (FRAME_T + HOOP_D), sp["h"] + 2 * (FRAME_T + HOOP_D), sp["r"] + FRAME_T + HOOP_D
    plate = _rrp(cxy, ow + 2 * (m + RIM_W), oh + 2 * (m + RIM_W), orr + 6, z0 - t, t)
    rim = (_rrp(cxy, ow + 2 * (RIM_GAP + RIM_W), oh + 2 * (RIM_GAP + RIM_W), orr + RIM_GAP + RIM_W, z0, RIM_H)
           .cut(_rrp(cxy, ow + 2 * RIM_GAP, oh + 2 * RIM_GAP, orr + RIM_GAP, z0 - 1, RIM_H + 2)))
    xo = sp["w"] / 2 + FRAME_T
    for sx in (-1, 1):                         # проріз бортика під фланці роз'єму
        xa, xb = sorted((sp["cx"] + sx * (xo - 1), sp["cx"] + sx * (xo + FL_W + 1)))
        rim = rim.cut(box(xa, xb, sp["cy"] - FL_T - 1, sp["cy"] + FL_T + 1, z0 - 1, z0 + RIM_H + 1))
    for (x, y) in lugs:                        # і під вушка
        rim = rim.cut(cyl(LUG / 2 + 1.0, z0 - 1, z0 + RIM_H + 1, x, y))
    plate = plate.fuse(rim)
    for (x, y) in lugs:
        plate = plate.fuse(cyl(PIN_D / 2 - 0.1, z0, z0 + 8, x, y))
    for (x, y) in master_pins:
        plate = plate.fuse(cyl(pin_r, z0, z0 + 5, x, y))
    return plate.clean()


def body_base_plate():
    """Базова плита заливки силікону: штифти у вушка каркаса + 3 штифти центрування майстра + бортик."""
    return _plate(frame_spec("body"), lug_positions(), [(x * K, y * K) for x, y in MASTER_PINS], 3.0 * K - 0.15)


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
    w, r = v(p.RECESS_W), P.recess_r()
    top = d["recess_top"]
    s_ = 1 if v(p.RECESS_SIDE) > 0 else -1
    y0 = s_ * (v(p.D) / 2 + TAB_PRELOAD)
    y1 = (d["cav_y1"] - v(p.R_CAV)) if s_ > 0 else (d["cav_y0"] + v(p.R_CAV))
    if v(p.FULL_LID_ON):   # v3.5: виїмка крізь задню стінку 5 мм — вкладка заходить у сердечник на 3 мм
        y1 = (d["Ly1"] - 3.0) if s_ > 0 else (d["Ly0"] + 3.0)
    prof = (cq.Workplane("XZ", origin=(d["recess_x"], y0, 0))
            .moveTo(-w / 2, z_from).lineTo(w / 2, z_from).lineTo(w / 2, top - r)
            .radiusArc((w / 2 - r, top), -r)
            .lineTo(-w / 2 + r, top)
            .radiusArc((-w / 2, top - r), -r)
            .close())
    return prof.extrude(-(y1 - y0)).val()


def core_outer(neck=BRIDGE_RAISE):
    """Повна формотворча поверхня сердечника (до масштабування)."""
    z_open = (d["zb"] if v(p.FULL_LID_ON) else 0.0) - GA
    cav = P._cavity_tool()
    cut = box(-200, 200, -200, 200, z_open, 200)
    core = cav.intersect(cut)
    core = core.fuse(P.flare_boss())
    core = core.fuse(_recess_tab(z_open - neck))
    xc = d["cav_xc"]
    if v(p.FULL_LID_ON):   # v3.5: шийка сердечника — Г-профіль гирла резервуара (разом із заходною фаскою)
        rad = v(p.LEADIN_LEN) * math.tan(math.radians(v(p.LEADIN_ANGLE)))
        neck_s = P.S_loft(-rad - 0.2, z_open - neck, -rad - 0.2, z_open + 0.01)   # v3.6: прямокутна
    else:
        neck_s = P.prism_rrect(d["reb"], d["reb"], d["r_reb"], z_open - neck, z_open + 0.01, cx=xc)
    core = core.fuse(neck_s)
    if v(p.RELIEF_ON):
        core = core.fuse(relief_core_outer(neck))
    # v3.7.1: гніздо телескопічного стику — останнім кроком (купол резервуара не повинен його заповнювати)
    core = core.cut(P.socket_tool())
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
    """Жорсткий хребет (знімний, ухил 2°) + міст із ніжками та штифтами у вушка гільзи.
    v3.4: на мосту — вставка порожнини полегшення основи (BASE_VOID_ON), виходить униз разом із хребтом."""
    xc = d["cav_xc"] * K
    FULL = bool(v(p.FULL_LID_ON))
    z_open = ((d["zb"] if FULL else 0.0) - GA) * K
    zb1 = z_open - BRIDGE_RAISE          # низ мосту
    zb0 = zb1 - BRIDGE_T
    inset = CORE_SKIN
    side0 = v(p.CAV) * K - 2 * inset
    z_top = (d["z_ceil_edge"] - CORE_SKIN) * K
    if FULL:   # v3.5: Г-хребет (Г-профіль мінус шкіра сердечника, ухил 2°) і Г-плита мосту
        t2 = math.tan(math.radians(2.0))
        za, zt_ = zb1 / K - 0.01, z_top / K
        spine = S(P.L_loft(CORE_SKIN, za, CORE_SKIN + (zt_ - za) * t2, zt_))
        rad = v(p.LEADIN_LEN) * math.tan(math.radians(v(p.LEADIN_ANGLE)))
        plate = S(P.S_loft(-rad + 0.8, zb0 / K, -rad + 0.8, zb1 / K))   # v3.6: прямокутна плита (під гніздом пробки)
        neck_w = 0.0
    else:
        spine = (cq.Workplane("XY", origin=(xc, 0, zb1 - 0.01)).sketch().rect(side0, side0).vertices().fillet(8)
                 .finalize().extrude(z_top - zb1, taper=2.0).val())
        # плита мосту: лише над шийкою сердечника (−1 мм на сторону) — бортик лишається відкритим (аудит M2)
        neck_w = d["reb"] * K - 2
        plate = P.prism_rrect(neck_w, neck_w, d["r_reb"] * K - 1, zb0, zb1, cx=xc)
    for (px_, py_) in core_pins():   # вушка під центрувальні штифти форми сердечника (поза шийкою)
        plate = plate.fuse(cyl(6.0, zb0, zb1, px_, py_))
        if v(p.FULL_LID_ON):        # перемичка вушка до плити
            plate = plate.fuse(box(min(px_, xc), max(px_, xc), py_ - 4, py_ + 4, zb0, zb1).intersect(cyl(abs(px_ - xc) + 1, zb0 - 1, zb1 + 1, px_, py_)))
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
    if v(p.BASE_VOID_ON):
        # v3.4: вставка порожнини полегшення основи — на мості (виходить униз разом із хребтом), майданчик + перемичка до плити
        bvd = P.base_void_dims()
        ins = S(P.base_void_tool(z_bottom=zb1 / K - 0.2))
        bx0, bx1, by0, by1 = bvd["x0"] * K, bvd["x1"] * K, bvd["y0"] * K, bvd["y1"] * K
        pad = P.prism_rrect(bx1 - bx0 - 2, by1 - by0 - 2, v(p.BASE_VOID_R) - 1, zb0, zb1, cx=(bx0 + bx1) / 2, cy=(by0 + by1) / 2)
        link = box(xc + neck_w / 2 - 3, bx0 + 3, (by0 + by1) / 2 - 8, (by0 + by1) / 2 + 8, zb0, zb1)
        plate = plate.fuse(ins).fuse(pad).fuse(link)
    s = plate.fuse(spine)
    # заливні та вентиляційні отвори в зоні шийки (між хребтом і контуром шийки)
    if FULL:   # v3.5: смуга між Г-хребтом і краєм плити ≈8.5 мм → отвори Ø6 / Ø4
        om = (CORE_SKIN + (-v(p.LEADIN_LEN) * math.tan(math.radians(v(p.LEADIN_ANGLE))) + 0.8)) / 2
        holes = [(d["Lx0"] + om, 0.0, 3.0), (d["Lx1"] - om, (d["Lyc"] + d["Ly1"]) / 2, 3.0),
                 ((d["Lx0"] + d["Lxc"]) / 2, d["Ly0"] + om, 2.0), (d["cav_xc"], d["Ly1"] - om, 2.0)]
        if P.rect_lid():   # v3.6: під колонкою тримача — суцільний силікон гнізда; заливний отвір по центру зони колонки
            holes.append(((d["Lxc"] + d["Lx1"]) / 2, (d["Ly0"] + d["Lyc"]) / 2, 3.0))
        for (hx, hy, r) in holes:
            s = s.cut(cyl(r, zb0 - 1, zb1 + 1, hx * K, hy * K))
    else:
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
        pass
    for (px_, py_) in core_pins():
        s = s.cut(cyl(2.15, zb0 - 1, zb1 + 1, px_, py_))
    # наскрізні отвори під стяжні шпильки M5 (міст притискається до гільзи — сердечник не спливає)
    for (x, y) in lug_positions():
        s = s.cut(cyl(ROD_HOLE / 2, zb0 - 1, z_open + 1, x, y))
    return s.clean()


CORE_PIN_X = d["reb"] * K / 2 + 5.0


def core_pins():
    """Центрувальні штифти мосту у формі сердечника (масштабовані координати), поза контуром сердечника.
    v3.5: правий штифт — у зоні колонки тримача (поза Г-сердечником), лівий — за лівою стінкою.
    v3.6: шийка прямокутна (гніздо пробки) — обидва штифти за лівою і правою стінками."""
    xc = d["cav_xc"] * K
    if P.rect_lid():   # v3.6: шийка — повний прямокутник; обидва штифти за лівою і правою стінками
        rad = v(p.LEADIN_LEN) * math.tan(math.radians(v(p.LEADIN_ANGLE)))
        return [((d["Lx0"] - rad - 0.2) * K - 7.0, 0.0), ((d["Lx1"] + rad + 0.2) * K + 7.0, 0.0)]
    if v(p.FULL_LID_ON):
        return [(xc - CORE_PIN_X, 0.0), (d["pocket_cx"] * K, d["pocket_cy"] * K)]
    return [(xc - CORE_PIN_X, 0.0), (xc + CORE_PIN_X, 0.0)]


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
    z_open = ((d["zb"] if v(p.FULL_LID_ON) else 0.0) - GA) * K
    zb1 = z_open - BRIDGE_RAISE
    neck_w = d["reb"] * K + 8
    pins_x = [q[0] for q in core_pins()]
    x0 = min(xc - CORE_PIN_X - 5, bb.xmin - wall, min(pins_x) - 6)
    x1 = max(xc + CORE_PIN_X + 5, bb.xmax + wall, max(pins_x) + 6)
    y0 = min(-neck_w / 2 - 6, bb.ymin - wall)
    y1 = max(neck_w / 2 + 6, bb.ymax + wall)
    outer = P.prism_rrect(x1 - x0, y1 - y0, 10, zb1, bb.zmax + wall, cx=(x0 + x1) / 2, cy=(y0 + y1) / 2)
    m = outer.cut(co)
    # штифти центрування мосту (вгору від обідка)
    for sgn in (-1, 1):
        pass
    for (px_, py_) in core_pins():
        m = m.fuse(cyl(2.0 - 0.1, zb1 - 5, zb1 + 0.01, px_, py_))
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


def _lid_kind(kind):
    return "lid" if kind == "main" else kind


def _lid_sleeve_dims(kind="main"):
    sp = frame_spec(_lid_kind(kind))
    return (sp["cx"] - sp["w"] / 2, sp["cx"] + sp["w"] / 2, sp["cy"] - sp["h"] / 2, sp["cy"] + sp["h"] / 2, sp["z0"], sp["z1"])


def lid_lugs(kind="main"):
    return _frame_lugs(frame_spec(_lid_kind(kind)))


def lid_sleeve(kind="main"):
    f, b = frame_halves(_lid_kind(kind))
    return cq.Compound.makeCompound([f, b])


def lid_base_plate(kind="main"):
    sp = frame_spec(_lid_kind(kind))
    if kind == "main":
        return _plate(sp, lid_lugs(kind), [(x * K, y * K) for x, y in LID_PINS], 2.5 * K - 0.15, t=5.0)
    return _plate(sp, lid_lugs(kind), [(x * K, y * K) for x, y in rl_pins()], 2.5 * K - 0.15, t=5.0)


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
        "body_frame_front": frame_halves("body")[0],
        "body_frame_back": frame_halves("body")[1],
        "body_base_plate": body_base_plate(),
        "finger_stiffener": finger_stiffener(),
        "stiffener_holder": stiffener_holder(),
        "core_silicone": core_silicone(),
        "core_spine_bridge": core_spine_and_bridge(),
        "core_mold": core_mold(),
        "lid_master": lid_master(),
        "lid_frame_front": frame_halves("lid")[0],
        "lid_frame_back": frame_halves("lid")[1],
        "lid_base_plate": lid_base_plate(),
        "gauge_hole_go_7p90": go,
        "gauge_stick_heets": stick_g,
    } | ({"rlid_master": lid_master("relief"), "rlid_sleeve": lid_sleeve("relief"),
          "rlid_base_plate": lid_base_plate("relief")} if P.has_relief_lid() else {})
