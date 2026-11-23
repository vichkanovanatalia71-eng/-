"""Комплект креслень STICKBOX 01 Monolith (SVG A3 + зведений PDF)."""
import os, sys, json, math
import numpy as np
import cadquery as cq
from cadquery import Vector
sys.path.insert(0, os.path.dirname(__file__))
from stickbox import parts as P, molds as M, params as p, drawing as DR, brand as BR0
from stickbox.params import v

OUT = os.path.join(os.path.dirname(__file__), "..", "drawings")
os.makedirs(OUT, exist_ok=True)
d = P.d
big = 600
NS = 7
REP = os.path.join(os.path.dirname(__file__), "..", "reports", "analysis.json")
AN = json.load(open(REP)) if os.path.exists(REP) else {}


def keep(shape, axis, val, side):
    """Залишити частину тіла з боку side (+1/-1) від площини axis=val."""
    lo, hi = (val, big) if side > 0 else (-big, val)
    b = {"x": M.box(lo, hi, -big, big, -big, big), "y": M.box(-big, big, lo, hi, -big, big),
         "z": M.box(-big, big, -big, big, lo, hi)}[axis]
    return shape.intersect(b)


GENERAL = [
    "Загальні допуски литих поверхонь: лінійні ±0.5 (до 120 мм), кутові ±0.5°; функціональні — див. позначення ⊕.",
    (f"⊕ Функціональні розміри (±0.25; отвір ±0.2): {'гніздо пробки' if P.rect_lid() else 'Г-резервуар'} біля низу ({P.d['Lx1'] - P.d['Lx0']:.0f} × {P.d['Ly1'] - P.d['Ly0']:.1f}), " +
     (f"пробка кришки {P.d['Lx1'] - P.d['Lx0'] - 2 * v(p.PLUG_GAP):.1f} × {P.d['Ly1'] - P.d['Ly0'] - 2 * v(p.PLUG_GAP):.1f}" if P.lid_hidden() else
      f"фланець кришки {P.d['flange_w']:.0f} × {P.d['flange_d']:.0f}") + ", кишеня девайса, отвір Ø8." if v(p.FULL_LID_ON) else
     f"⊕ Функціональні розміри (±0.25; отвір ±0.2): ребейт {P.d['reb']:.1f}, порожнина в зоні ущільнення {v(p.CAV):.1f}, кишеня девайса, отвір Ø8."),
    "Невказані радіуси литих ребер R0.5–1. Нижня (відкрита) грань — шліфування P120→P220, площинність 0.3, притуплення R≈1.",
]

body = P.body()
lid = P.lid()
oring = P.oring()
liner = P.felt_pad()   # v2.7: вставку прибрано у v2.5 — у збірці повстяна підкладка
_led, _btn = P.device_controls()
dev = P.device()
xc, cx, cy = d["cav_xc"], d["pocket_cx"], d["pocket_cy"]
H = v(p.H)
mass_body = AN.get("mass", {}).get("body", {}).get("mass_kg")
mass_lid = AN.get("mass", {}).get("lid", {}).get("mass_kg")

# ======================================================================
# Аркуш 1 — корпус: види
# ======================================================================
S = DR.Sheet("Корпус", "Деталь 01 — Корпус монолітний (загальні види)", "декоративний бетон / GFRC-премікс",
             "1:1", 1, NS, notes=GENERAL + ["Напис STICKBOX, літера I — фірмовий знак (стік-i + хвиля): дебосинг " + f"{v(p.LOGO_DEPTH)}" + " мм. Фарбування після виготовлення: STICK (з I) — RAL 7016 (темно-сірий), хвиля і BOX — бірюзовий (RAL 5018 / еталон бренду).", "Напис — Montserrat Bold, великі літери " + f"{v(p.LOGO_CAP_H)}" + " мм, центр на висоті " + f"{v(p.LOGO_Z):.0f}" + ", ширина " + f"{BR0.wordmark_layout()['info']['width_mm']:.1f}" + "; окремого знака немає (v3.2); перемички між елементами ≥1.2 мм. " + (f"Виїмка для пальця на задній грані {v(p.RECESS_W):.0f} × {v(p.HOOK_H):.0f} мм над фланцем кришки, кути R{P.recess_r():.1f}, кромки R≈1 (вручну)." if v(p.FULL_LID_ON) else "Виїмка 30 × " + f"{P.d['recess_top']:.1f}" + ", кути R7, кромки R1.5 (вручну).")], mass=(f"Маса ≈ {mass_body:.2f} кг (ρ 2000)" if mass_body else None))
V = S.view(body, "front", (100, 145), 1.0, label="ФРОНТАЛЬНИЙ ВИГЛЯД")
V.dim((-60, -45, 0), (60, -45, 0), "h", off=-16)
V.dim((-60, -45, 0), (-60, -45, H), "v", off=-10)
V.dim((-60, -45, H), (xc, -45, H), "h", off=9)
V.center_v((xc, -45, 88), 12)
V.dim((cx - 4, -45, H), (cx + 4, -45, H), "h", off=6)
V.dim((cx + 4, -45, H), (cx + 4, -45, H - v(p.SLOT_DEPTH)), "v", off=10)
V.leader((cx + 2, -45, v(p.H) - 6), 12, 14, "під кнопкою девайса", size=2.6)
# v2.7: вигляди ззаду та справа (1:2) — пальцеві виїмки основної кришки та кришечки полегшення
VB = S.view(body, "back", (226, 225.5), 0.5, hidden=False)
S.text((226, 174.5), "ВИГЛЯД ЗЗАДУ (1:2)", 3.6, weight="bold")
rx = d["recess_x"]
VB.dim((rx - v(p.RECESS_W) / 2, 45, 0), (rx + v(p.RECESS_W) / 2, 45, 0), "h", off=-5, txt=f"{v(p.RECESS_W):.0f}")
VB.leader((rx, 45, d["recess_top"]), 14, -16, (f"виїмка {v(p.RECESS_W):.0f}×{v(p.HOOK_H):.0f}, язичок кришки" if P.lid_hidden() else
                                                 f"виїмка для пальця {v(p.RECESS_W):.0f}×{v(p.HOOK_H):.0f} над фланцем" if v(p.FULL_LID_ON)
                                                 else f"виїмка кришки {v(p.RECESS_W):.0f}×{d['recess_top']:.1f}"))
rcy_ = (d["rel_y0"] + d["rel_y1"]) / 2
VR = S.view(body, "right", (322, 225.5), 0.5, hidden=False)
S.text((322, 174.5), "ВИГЛЯД СПРАВА (1:2)", 3.6, weight="bold")
if P.has_relief_lid():
    VR.dim((60, rcy_ - v(p.RL_RECESS_W) / 2, 0), (60, rcy_ + v(p.RL_RECESS_W) / 2, 0), "h", off=-5, txt=f"{v(p.RL_RECESS_W):.0f}")
    VR.leader((60, rcy_, d["rl_recess_top"]), 14, -16, f"виїмка кришечки {v(p.RL_RECESS_W):.0f}×{d['rl_recess_top']:.1f}")
VT = S.view(body, "top", (100, 222), 1.0, label="ВИД ЗВЕРХУ", label_dy=18)
VT.dim((60, -45, H), (60, 45, H), "v", off=16)
VT.dim((52, -45, H), (52, cy, H), "v", off=8, txt=f"{cy + 45:.1f}")
VT.dim((cx, 45, H), (60, 45, H), "h", off=8, txt=f"{60 - cx:.1f}")
VT.dim((-60, 45, H), (xc, 45, H), "h", off=8, txt=f"{xc + 60:.1f}")
VT.center_v((xc, 0, H), 16); VT.center_h((xc, 0, H), 16)
if v(p.NFC_ON):   # v3.3: знак NFC зверху, мітка Ø25 зсередини (у кишені стелі) — центр
    nx_, ny_ = v(p.NFC_X), v(p.NFC_Y)
    VT.center_v((nx_, ny_, H), 15); VT.center_h((nx_, ny_, H), 15)
    VT.dim((-60, -45, H), (nx_, -45, H), "h", off=-8, txt=f"{nx_ + 60:.0f}")
    VT.dim((-60, -45, H), (-60, ny_, H), "v", off=-8, txt=f"{ny_ + 45:.0f}")
    VT.leader((nx_ + 8.5, ny_ - 12, H), 30, 22, "знак NFC; мітка Ø25 — зсередини, аркуш 7", size=2.6)
VT.center_v((cx, cy, H), 24); VT.center_h((cx, cy, H), 16)
VT.leader((xc + 7.8, 7.8, H), 14, -26, "Ø22 воронка (S-профіль)")
VT.leader((xc - 2.8, -2.8, H), -26, -22, "Ø8 ⊕ наскрізний")
VT.leader((cx - 11.1, cy + 8, H), -20, -30, f"кишеня {d['pocket_x']:.1f}×{d['pocket_y']:.1f}, ухил {v(p.DRAFT_POCKET)}°")
VT.leader((-60 + 4.1, 45 - 4.1, H), -8, 10, f"R{v(p.R_V):.0f}")
VL = S.view(body, "left", (238, 145), 1.0, label="ВИГЛЯД ЗЛІВА")
VL.dim((-60, 45, 0), (-60, -45, 0), "h", off=-16)
VL.leader((-60, -45 + 1.8, H - 1.8), 10, -10, f"R{v(p.R_TOP):.0f} (верхній периметр)")
cutD = keep(body, "x", cx, +1)
VD = S.view(cutD, "left", (350, 145), 1.0, label="РОЗРІЗ D-D (вісь кишені)", section=(cutD, (cx, 0, 0), (1, 0, 0)))
VD.dim((cx, -45, H), (cx, -45 + v(p.T_FRONT_POCKET), H), "h", off=8, txt=f"{v(p.T_FRONT_POCKET):.0f}")
VD.dim((cx, cy + 6, H), (cx, cy + 6, d["pocket_floor"]), "v", off=-26, txt=f"{d['pocket_depth']:.1f}")
VD.dim((cx, 45, d["pocket_floor"]), (cx, 45, 0), "v", off=8, txt=f"{d['pocket_floor']:.1f}")
VD.dim((cx, -45, H), (cx, -45, H - v(p.SLOT_DEPTH)), "v", off=-8, txt=f"{v(p.SLOT_DEPTH):.0f}")
# позначення площини D-D на виді зверху
a, b = VT.P((cx, -52, H)), VT.P((cx, 52, H))
S.line(a, b, "c"); S.text((a[0] + 3, a[1] + 4), "D", 3.6, weight="bold"); S.text((b[0] + 3, b[1] - 1), "D", 3.6, weight="bold")
open(f"{OUT}/01_body_views.svg", "w").write(S.svg())
print("sheet 1")

# ======================================================================
# Аркуш 2 — корпус: розрізи та виносні елементи
# ======================================================================
if v(p.FULL_LID_ON):
    _notes2 = [f"Розріз A-A — по осі воронки (y = 0). Розріз C-C — по осі воронки (x = {xc:.1f}).",
               (f"Внизу — прямокутне гніздо пробки {d['Lx1'] - d['Lx0']:.0f} × {d['Ly1'] - d['Ly0']:.1f} R{v(p.CAV_R_OUT):.0f} від z = {d['zb']:.0f} до низу колонки тримача "
                f"z = {d.get('z_sock', 0):.0f} (фаска {v(p.COL_CHAMF):.0f}×45°); вище — Г-резервуар того самого контуру стінок до стелі; ухил {v(p.DRAFT_CAV)}° (вихід сердечника); "
                if P.rect_lid() else
                f"Г-резервуар: однаковий переріз від низу корпусу (z = {d['zb']:.0f}, верх фланця кришки) до стелі; ухил {v(p.DRAFT_CAV)}° (вихід сердечника); ") +
               f"купол стелі R{d['r_dome']:.0f} — стріла {v(p.DOME_SAG_FAR)} мм до найдальшого кута (відведення повітря).",
               f"Заходна фаска шнура {v(p.LEADIN_ANGLE):.0f}° × {v(p.LEADIN_LEN)} біля низу; кромку виїмки для пальця з боку резервуара притупити R≈1 (вручну).",
               ("v3.7: стінки моноліту стоять на площині опори; кришка схована в гнізді (низ урівень), язичок — у виїмці 15 × 5 на задній грані; розрізи через кишеню девайса — аркуш 4."
                if P.lid_hidden() else
                "Корпус стоїть на фланці кришки — кришка займає всю основу; розрізи через частину резервуара за кишенею девайса — аркуш 4.")]
else:
    _notes2 = None
S = DR.Sheet("Корпус", "Деталь 01 — Розрізи A-A, C-C; виносні елементи E (4:1), F (5:1)", "декоративний бетон / GFRC-премікс",
             "1:1; 4:1; 5:1", 2, NS, notes=_notes2 or [f"Розріз A-A — по осі воронки (y = 0). Розріз C-C — по осі воронки (x = {xc:.1f}).",
                                            f"Порожнина: ухил стінок {v(p.DRAFT_CAV)}° (вихід сердечника), купол стелі — стріла {v(p.DOME_SAG)} мм (відведення повітря).",
                                            f"Заходна фаска ущільнювача {v(p.LEADIN_ANGLE):.0f}° × {v(p.LEADIN_LEN)}; кромка стелі виїмки R1.5 (по ній проходить ущільнювач).",
                                            ("Г-резервуар: плече за кишенею девайса з'єднане з основною частиною над порогом z = " + f"{d['arm_sill_z']:.1f}" + " (стінка під ущільнювачем суцільна) — розрізи на аркуші 4. " if v(p.ARM_ON) else "") + "Полегшувальна порожнина правої колонки (відкрита знизу) — див. вид знизу на аркуші 5 і розріз D-D."])
cutA = keep(body, "y", 0, +1)
VA = S.view(cutA, "front", (95, 150), 1.0, label="РОЗРІЗ A-A", section=(cutA, (0, 0, 0), (0, 1, 0)))
FULL = bool(v(p.FULL_LID_ON))
if FULL:   # v3.5: Г-резервуар від низу корпусу; корпус стоїть на фланці кришки
    if P.rect_lid():   # v3.6: гніздо прямокутної пробки на всю ширину; колонка тримача — над ним
        VA.dim((d["Lx0"], 0, d["zb"] + 1), (d["Lx1"], 0, d["zb"] + 1), "h", off=-14, txt=f"{d['Lx1'] - d['Lx0']:.1f} ⊕ (гніздо)")
        VA.leader((d["Lxc"] + 6, 0, d["z_sock"]), -22, -26, f"низ колонки z = {d['z_sock']:.0f}, фаска {v(p.COL_CHAMF):.0f}×45°", size=2.6)
    else:
        VA.dim((d["Lx0"], 0, d["zb"] + 1), (d["Lxc"], 0, d["zb"] + 1), "h", off=-14, txt=f"{d['Lxc'] - d['Lx0']:.1f} ⊕ (низ)")
else:
    VA.dim((d["cav_x0"], 0, 5), (d["cav_x1"], 0, 5), "h", off=-24, txt=f"{v(p.CAV):.1f} ⊕ (низ)")
    VA.dim((xc - d["reb"] / 2, 0, 0), (xc + d["reb"] / 2, 0, 0), "h", off=-12, txt=f"{d['reb']:.1f} ⊕")
VA.dim((-60, 0, 0), (-60, 0, d["z_ceil_c"]), "v", off=-8, txt=f"{d['z_ceil_c']:.0f} (стеля, центр)")
VA.dim((xc + 14, 0, d["z_ceil_c"]), (xc + 14, 0, H), "v", off=6, txt=f"{v(p.T_TOP):.0f}")
if not P.lid_hidden():
    VA.dim((60, 0, 0), (60, 0, d["z_reb"]), "v", off=8, txt=(f"{d['zb']:.1f} (фланець кришки)" if FULL else f"{d['z_reb']:.1f} ⊕"))
if FULL:
    _tn = math.tan(math.radians(v(p.DRAFT_CAV)))
    VA.dim((-60, 0, 30), (d["Lx0"] + (30 - d["zb"]) * _tn, 0, 30), "h", off=6, txt=f"{v(p.WALL_T):.0f}")
elif v(p.WALL_ON):   # v3.4: зона ущільнення — 7.5; над порогом — тонкі стінки WALL_T (60° перехід)
    _tn = math.tan(math.radians(v(p.DRAFT_CAV)))
    VA.dim((-60, 0, 12), (d["cav_x0"] + (12 - d["z_reb"]) * _tn, 0, 12), "h", off=6, txt=f"{v(p.T_LEFT):.1f}")
    _zw = d["up_zt"] + 4
    VA.dim((-60, 0, _zw), (d["up_x0"] + (_zw - d["up_zt"]) * _tn, 0, _zw), "h", off=6, txt=f"{v(p.WALL_T):.0f}")
    VA.leader((d["up_x0"] + 1.2, 0, (d["up_z0"] + d["up_zt"]) / 2), 22, -26, f"перехід {v(p.WALL_STEP_DEG):.0f}°, z {d['up_z0']:.0f}–{d['up_zt']:.1f}", size=2.6)
else:
    VA.dim((-60, 0, 30), (d["cav_x0"], 0, 30), "h", off=6, txt=f"{v(p.T_LEFT):.0f}")
VA.leader(((d["Lxc"] if FULL else d["cav_x1"]) - 0.6, 0, 60), 12, -16, f"ухил {v(p.DRAFT_CAV)}°")
VA.leader((xc + 20, 0, d["z_ceil_c"] - 0.2), 18, -22, (f"купол R{d['r_dome']:.0f}, стріла {v(p.DOME_SAG_FAR)} до дальнього кута" if FULL
                                                    else f"купол R{d['r_dome']:.0f}, стріла {v(p.DOME_SAG)}"))
cutC = keep(body, "x", xc, +1)
VC = S.view(cutC, "left", (238, 150), 1.0, label="РОЗРІЗ C-C", section=(cutC, (xc, 0, 0), (1, 0, 0)))
if FULL:
    _zw, _tn = 40.0, math.tan(math.radians(v(p.DRAFT_CAV)))
    VC.dim((xc, -45, _zw), (xc, d["Ly0"] + (_zw - d["zb"]) * _tn, _zw), "h", off=0, txt=f"{v(p.WALL_FRONT_T)}")
    VC.dim((xc, 45, _zw), (xc, d["Ly1"] - (_zw - d["zb"]) * _tn, _zw), "h", off=0, txt=f"{45 - d['Ly1']:g}")
else:
    VC.dim((xc, -45, 0), (xc, d["cav_y0"], 0), "h", off=-8, txt=f"{d['t_front_back']:.1f}")
if v(p.WALL_ON) and not FULL:
    _zw = 60.0
    _tn = math.tan(math.radians(v(p.DRAFT_CAV)))
    VC.dim((xc, -45, _zw), (xc, d["up_y0"] + (_zw - d["up_zt"]) * _tn, _zw), "h", off=0, txt=f"{v(p.WALL_FRONT_T)}")
    VC.dim((xc, 45, _zw), (xc, d["up_y1"] - (_zw - d["up_zt"]) * _tn, _zw), "h", off=0, txt=f"{v(p.WALL_T):.0f}")
VC.dim((xc, 45, H), (xc, -45, H), "h", off=8, txt="90")
if not P.lid_hidden():   # v3.7: виїмка — на осі x = 0, поза розрізом C-C
    VC.dim((xc, 45, d["zb"] if v(p.FULL_LID_ON) else 0), (xc, 45, d["recess_top"]), "v", off=8,
           txt=(f"{v(p.HOOK_H):.0f} (виїмка)" if v(p.FULL_LID_ON) else f"{d['recess_top']:.1f} (виїмка)"))
# виносний елемент E — воронка, 4:1
ce, re = (330, 82), 42
DR.clip_begin(S, "cE", ce[0], ce[1], re)
k = 4.0
VE = DR.View(S, "front", None, k)
u0, v0 = VE.uv((xc, 0, d["z_ceil_c"] + 4.5))
VE.o = (ce[0] - k * u0, ce[1] + k * v0)
vis, hid = DR.hlr(cutA, "front", False)
for rings in DR.section_faces(cutA, (0, 0, 0), (0, 1, 0), "front"):
    dpath = "".join("M " + " L ".join(f"{VE.p(uu, vv)[0]:.3f},{VE.p(uu, vv)[1]:.3f}" for uu, vv in ring) + " Z " for ring in rings)
    S.el.append(f'<path class="hatch" d="{dpath}" fill-rule="evenodd"/>')
for pl in vis:
    S.poly([VE.p(uu, vv) for uu, vv in pl], "v")
DR.clip_end(S, ce[0], ce[1], re, "E (4:1) — воронка, отвір, розтруб")
VE.dim((xc - 11, 0, H), (xc + 11, 0, H), "h", off=6, txt="Ø22")
VE.dim((xc - 4, 0, d["z_ceil_c"] + v(p.FLARE_H) + 1), (xc + 4, 0, d["z_ceil_c"] + v(p.FLARE_H) + 1), "h", off=-2, txt="Ø8 ⊕")
VE.dim((xc - v(p.FLARE_D) / 2, 0, d["z_ceil_c"]), (xc + v(p.FLARE_D) / 2, 0, d["z_ceil_c"]), "h", off=-9, txt=f"Ø{v(p.FLARE_D)}")
VE.dim((xc + 6.5, 0, H), (xc + 6.5, 0, H - v(p.FUNNEL_DEPTH)), "v", off=14, txt=f"{v(p.FUNNEL_DEPTH):.0f}")
VE.dim((xc + 4, 0, H - v(p.FUNNEL_DEPTH)), (xc + 4, 0, d["z_ceil_c"] + v(p.FLARE_H)), "v", off=6, txt="2")
VE.dim((xc - 4.3, 0, d["z_ceil_c"] + v(p.FLARE_H)), (xc - 4.3, 0, d["z_ceil_c"]), "v", off=-8, txt=f"{v(p.FLARE_H):.0f}")
# виносний елемент F — ущільнення, 5:1
asm = cq.Compound.makeCompound([keep(s_, "y", 0, +1) for s_ in (body, lid, oring)])
cf, rf = (318, 186), 38
DR.clip_begin(S, "cF", cf[0], cf[1], rf)
k = 5.0
VF = DR.View(S, "front", None, k)
u0, v0 = VF.uv(((d["Lx0"] if FULL else d["cav_x0"]) - 1.5, 0, 8))
VF.o = (cf[0] - k * u0, cf[1] + k * v0)
vis, hid = DR.hlr(asm, "front", False)
for rings in DR.section_faces(asm, (0, 0, 0), (0, 1, 0), "front"):
    dpath = "".join("M " + " L ".join(f"{VF.p(uu, vv)[0]:.3f},{VF.p(uu, vv)[1]:.3f}" for uu, vv in ring) + " Z " for ring in rings)
    S.el.append(f'<path class="hatch" d="{dpath}" fill-rule="evenodd"/>')
for pl in vis:
    S.poly([VF.p(uu, vv) for uu, vv in pl], "v")
DR.clip_end(S, cf[0], cf[1], rf, "F (5:1) — кришка / ущільнення")
if FULL:   # v3.5: стінка 5 мм стоїть на фланці кришки; шнур — у канавці Г-пробки
    x0 = d["Lx0"]
    gz = (d["groove_z0"] + d["groove_z1"]) / 2
    VF.dim((-60, 0, gz), (x0 + (gz - d["zb"]) * math.tan(math.radians(v(p.DRAFT_CAV))), 0, gz), "h", off=7, txt=f"{v(p.WALL_T):.0f}")
    if P.lid_hidden():   # v3.7: кришка без фланця, низ урівень з корпусом
        VF.dim((x0 + v(p.PLUG_GAP) + 3.0, 0, 0), (x0 + v(p.PLUG_GAP) + 3.0, 0, d["groove_z0"]), "v", off=12, txt=f"{d['groove_z0']:.0f}")
        VF.leader((x0 + v(p.PLUG_GAP) + 4.0, 0, 0.0), 30, 22, "низ кришки урівень з корпусом")
    else:
        VF.dim((x0 - 2.0, 0, 0), (x0 - 2.0, 0, d["zb"]), "v", off=-6, txt=f"{v(p.FLANGE_T)}")
        VF.dim((-60 + v(p.LID_GAP), 0, 1.0), (-60, 0, 1.0), "h", off=-4, txt=f"{v(p.LID_GAP)}")
    VF.leader((x0 - 0.3, 0, d["zb"] + 1.0), 30, 8, f"фаска {v(p.LEADIN_ANGLE):.0f}°×{v(p.LEADIN_LEN)}")
    VF.leader((x0 + 1.4, 0, gz), 34, -24, f"шнур-губка Ø{v(p.ORING_CS):.0f}, стиснення {d['squeeze_pct']:.0f}%")
    VF.leader((x0 + 3.2, 0, d["groove_z0"] + 0.5), 34, 6, f"канавка {v(p.GROOVE_W)}×{d['groove_depth']:.1f}")
else:
    x0 = d["cav_x0"]
    VF.dim((x0 - v(p.SHOULDER), 0, d["z_reb"]), (x0, 0, d["z_reb"]), "h", off=4, txt=f"{v(p.SHOULDER)}")
    VF.dim((x0 - 2.0, 0, 0.5), (x0 - 2.0, 0, d["z_reb"]), "v", off=-6, txt=f"{v(p.FLANGE_T)}")
    VF.dim((x0 - 9, 0, 0), (x0 - 9, 0, 0.5), "v", off=-4, txt="0.5")
    VF.leader((x0 + 0.45, 0, 6.2), 30, 6, f"фаска {v(p.LEADIN_ANGLE):.0f}°×{v(p.LEADIN_LEN)}")
    VF.leader((x0 + 0.6 + 1.2, 0, v(p.LID_RECESS) + 11.0), 30, -16, f"шнур-губка Ø{v(p.ORING_CS):.0f}, стиснення {d['squeeze_pct']:.0f}%")
    VF.leader((x0 + 1.8, 0, v(p.LID_RECESS) + 9.0), 30, 18, f"канавка {v(p.GROOVE_W)}×{d['groove_depth']:.1f}")
open(f"{OUT}/02_body_sections.svg", "w").write(S.svg())
print("sheet 2")

# ======================================================================
# Аркуш 3 — кришка
# ======================================================================
if v(p.FULL_LID_ON):   # v3.5: кришка на всю основу з Г-пробкою
    L = lid
    LT = d["lid_t"]
    HID = P.lid_hidden()
    pw_, pd_ = d["Lx1"] - d["Lx0"] - 2 * v(p.PLUG_GAP), d["Ly1"] - d["Ly0"] - 2 * v(p.PLUG_GAP)
    fw, fd = (pw_, pd_) if HID else (d["flange_w"], d["flange_d"])
    r_fw = (v(p.CAV_R_OUT) - v(p.PLUG_GAP)) if HID else d["r_flange"]
    ft_ = 0.0 if HID else v(p.FLANGE_T)
    tn = math.tan(math.radians(v(p.DRAFT_CAV)))
    RECT = P.rect_lid()
    _pn = "прямокутна пробка" if RECT else "Г-пробка"
    S = DR.Sheet("Кришка", f"Деталь 02 — Кришка: {_pn}, канавка шнура, лоток", "декоративний бетон / GFRC-премікс",
                 "1:1; 4:1", 3, NS, mass=(f"Маса ≈ {mass_lid:.3f} кг (ρ 2000)" if mass_lid else None),
                 notes=([f"v3.7: кришка схована в дні — без фланця; нижня грань (відкрита грань лиття, P120→P220, площинність 0.2) урівень з низом корпусу.",
                         f"Язичок {v(p.RECESS_W) - 2 * v(p.LID_TAB_GAP):.0f} мм завширшки: {v(p.LID_TAB_TIP_T)} біля торця → {v(p.LID_TAB_ROOT_T)} біля кореня (скіс 45°), "
                         f"торець на {v(p.LID_TAB_INSET)} усередині габариту; входить у виїмку {v(p.RECESS_W):.0f} × {v(p.HOOK_H):.0f} задньої грані — кришка стає лише язичком до виїмки."]
                        if HID else
                        ["Видима (нижня) грань — відкрита грань лиття: шліфування P120→P220 з припуском 0.5; площинність 0.2. На ній стоїть увесь виріб.",
                         f"Фланець — уся основа {fw:.0f} × {fd:.0f}, R{d['r_flange']:.1f}: на {v(p.LID_GAP)} мм менший за корпус з кожного боку "
                         "(тіньова лінія); корпус стоїть на ньому торцями стінок."]) + [
                        (f"Пробка — прямокутник {d['Lx1'] - d['Lx0'] - 2 * v(p.PLUG_GAP):.1f} × {d['Ly1'] - d['Ly0'] - 2 * v(p.PLUG_GAP):.1f} R{v(p.CAV_R_OUT) - v(p.PLUG_GAP):.1f} "
                         f"(гніздо корпусу мінус {v(p.PLUG_GAP)} на сторону), ухил {v(p.DRAFT_CAV)}°, висота {d['plug_h']:.0f}; " if RECT else
                         f"Г-пробка — профіль резервуара мінус {v(p.PLUG_GAP)} мм на сторону, ухил {v(p.DRAFT_CAV)}°, висота {d['plug_h']:.0f}; ") +
                        f"верх борту — фаска {v(p.PLUG_CHAMF_R)} × {v(p.PLUG_CHAMF_H)}; кромки канавки R0.4.",
                        f"Шнур Ø{v(p.ORING_CS):.0f} (закритопориста силіконова губка), відріз {d['seal_cut_len']:.0f} мм, стиснення ≈{d['squeeze_pct']:.0f}%; " +
                        ("прямокутна петля з 4 кутами R≈11. " if RECT else "огинає кут колонки тримача. ") +
                        f"Лоток пробки: дно {v(p.LID_FLOOR)}, ухил {v(p.TRAY_DRAFT):.0f}°" +
                        (f"; над лотком під колонкою тримача — зазор {v(p.SOCK_TOP_GAP)} до низу колонки." if RECT else ".")])
    VLt = S.view(L, "top", (88, 140), 1.0, label="ВИД ЗВЕРХУ (внутрішня сторона)")
    VLt.dim((-fw / 2, fd / 2, LT), (fw / 2, fd / 2, LT), "h", off=8, txt=f"{fw:.1f}")
    VLt.dim((fw / 2, -fd / 2, LT), (fw / 2, fd / 2, LT), "v", off=8, txt=f"{fd:.1f}")
    VLt.leader((-fw / 2 + 4.0, -fd / 2 + 4.0, 0), 16, 14, f"R{r_fw:.1f}")
    if HID:
        _t = P.lid_tab_dims()
        VLt.leader((_t["x"] + _t["w"] / 2 - 1.0, _t["y_tip"] - 1.0, 0), 22, -14, f"язичок {_t['w']:.0f} мм (у виїмку 15 × 5)")
        ys = 0.0
    elif RECT:
        _c = (v(p.CAV_R_OUT) - v(p.PLUG_GAP)) * (1 - 1 / math.sqrt(2))
        VLt.leader((d["Lx1"] - v(p.PLUG_GAP) - _c, d["Ly0"] + v(p.PLUG_GAP) + _c, LT), 16, 22,
                   f"пробка {d['Lx1'] - d['Lx0'] - 2 * v(p.PLUG_GAP):.1f} × {d['Ly1'] - d['Ly0'] - 2 * v(p.PLUG_GAP):.1f}, R{v(p.CAV_R_OUT) - v(p.PLUG_GAP):.1f}")
        ys = 0.0
    else:
        VLt.leader((d["Lxc"] - v(p.PLUG_GAP) - 2.0, d["Lyc"] + v(p.PLUG_GAP) + 2.0, LT), 22, 34,
                   f"Г-пробка, зазор {v(p.PLUG_GAP)}; кут колонки R{v(p.CAV_R_COL) + v(p.PLUG_GAP):.1f}")
        ys = (d["Lyc"] + d["Ly1"]) / 2
    Ls = keep(L, "y", ys, +1)
    VLs = S.view(Ls, "front", (290, 92), 1.0, label=f"РОЗРІЗ (y = {ys:.1f})", section=(Ls, (0, ys, 0), (0, 1, 0)))
    xp0, xp1 = d["Lx0"] + v(p.PLUG_GAP), d["Lx1"] - v(p.PLUG_GAP)
    VLs.dim((xp0, ys, d["zb"]), (xp1, ys, d["zb"]), "h", off=-22, txt=f"{xp1 - xp0:.1f} ⊕ (основа пробки)")
    if not HID:
        VLs.dim((-fw / 2, ys, 0), (fw / 2, ys, 0), "h", off=-12, txt=f"{fw:.1f}")
        VLs.dim((fw / 2, ys, 0), (fw / 2, ys, v(p.FLANGE_T)), "v", off=4, txt=f"{v(p.FLANGE_T)}")
    VLs.dim((fw / 2, ys, 0), (fw / 2, ys, LT), "v", off=10, txt=f"{LT:.1f}")
    g0, g1 = d["groove_z0"], d["groove_z1"]
    gz = (g0 + g1) / 2
    gb = d["Lx0"] + (gz - d["zb"]) * tn + v(p.PLUG_GAP) + d["groove_depth"]     # дно канавки (ліва сторона)
    pr = d["Lx0"] + v(p.PLUG_GAP) + (g1 - d["zb"]) * tn                         # грань пробки над канавкою
    cg, rg = (330, 165), 36
    DR.clip_begin(S, "cG", cg[0], cg[1], rg)
    k = 4.0
    VG = DR.View(S, "front", None, k)
    u0, v0 = VG.uv((pr + 1.0, ys, 12.0))
    VG.o = (cg[0] - k * u0, cg[1] + k * v0)
    vis, hid = DR.hlr(Ls, "front", False)
    for rings in DR.section_faces(Ls, (0, ys, 0), (0, 1, 0), "front"):
        dpath = "".join("M " + " L ".join(f"{VG.p(uu, vv)[0]:.3f},{VG.p(uu, vv)[1]:.3f}" for uu, vv in ring) + " Z " for ring in rings)
        S.el.append(f'<path class="hatch" d="{dpath}" fill-rule="evenodd"/>')
    for pl in vis:
        S.poly([VG.p(uu, vv) for uu, vv in pl], "v")
    DR.clip_end(S, cg[0], cg[1], rg, "G (4:1) — канавка шнура (ліва сторона)")
    VG.dim((gb, ys, g0), (gb, ys, g1), "v", off=8, txt=f"{v(p.GROOVE_W)}")
    VG.dim((pr, ys, g1), (gb, ys, g1), "h", off=5, txt=f"{d['groove_depth']:.1f}")
    VG.dim((pr - 1.5, ys, ft_), (pr - 1.5, ys, g0), "v", off=-10, txt=f"{g0 - ft_:.1f}")
    VG.leader((pr + 1.0, ys, LT - 1.7), -8, -8, f"фаска {v(p.PLUG_CHAMF_R)}×{v(p.PLUG_CHAMF_H)}")
    if HID:   # v3.7: виносний елемент H — розріз по осі язичка (x = 0): язичок у виїмці задньої грані
        _t = P.lid_tab_dims()
        asmH = cq.Compound.makeCompound([keep(s_, "x", _t["x"], +1) for s_ in (body, lid, oring)])
        ch, rh = (86, 242), 30
        DR.clip_begin(S, "cH", ch[0], ch[1], rh)
        kH = 4.0
        VHt = DR.View(S, "right", None, kH)
        u0, v0 = VHt.uv((_t["x"], d["Ly1"] + 1.0, 6.0))
        VHt.o = (ch[0] - kH * u0, ch[1] + kH * v0)
        vis, hid = DR.hlr(asmH, "right", False)
        for rings in DR.section_faces(asmH, (_t["x"], 0, 0), (1, 0, 0), "right"):
            dpath = "".join("M " + " L ".join(f"{VHt.p(uu, vv)[0]:.3f},{VHt.p(uu, vv)[1]:.3f}" for uu, vv in ring) + " Z " for ring in rings)
            S.el.append(f'<path class="hatch" d="{dpath}" fill-rule="evenodd"/>')
        for pl in vis:
            S.poly([VHt.p(uu, vv) for uu, vv in pl], "v")
        DR.clip_end(S, ch[0], ch[1], rh, f"H (4:1) — язичок у виїмці {v(p.RECESS_W):.0f} × {v(p.HOOK_H):.0f}")
        VHt.dim((_t["x"], _t["y_tip"] - 0.6, 0), (_t["x"], _t["y_tip"] - 0.6, _t["t_tip"]), "v", off=6, txt=f"{_t['t_tip']}")
        VHt.dim((_t["x"], _t["y_ramp0"] - 0.8, 0), (_t["x"], _t["y_ramp0"] - 0.8, _t["t_root"]), "v", off=-8, txt=f"{_t['t_root']}")
        VHt.dim((_t["x"], v(p.D) / 2, 0), (_t["x"], v(p.D) / 2, d["recess_top"]), "v", off=12, txt=f"{v(p.HOOK_H):.0f}")

else:
    L = lid.translate(Vector(-xc, 0, -v(p.LID_RECESS)))
    LT = d["lid_t"]
    S = DR.Sheet("Кришка", "Деталь 02 — Нижня кришка з пробкою-лотком і канавкою ущільнювача", "декоративний бетон / GFRC-премікс",
                 "1:1; 2:1; 6:1", 3, NS, mass=(f"Маса ≈ {mass_lid:.3f} кг (ρ 2000)" if mass_lid else None),
                 notes=["Видима (нижня) грань — відкрита грань лиття: шліфування P120→P220 з припуском 0.5; площинність 0.2.",
                        f"Пробка: ухил {v(p.DRAFT_CAV)}° (вужча вгору). Канавка ущільнювача формується валиком силіконової форми; кромки R0.4. Верх борту — фаска 2 × 3.5 (антизаклинювання).",
                        f"Ущільнювач: шнур Ø{v(p.ORING_CS):.0f} із закритопористої силіконової губки, відріз {d['seal_cut_len']:.0f} мм, стиснення ≈{d['squeeze_pct']:.0f}%. Лоток пробки: ухил {v(p.TRAY_DRAFT)}°, дно {v(p.LID_FLOOR)}."])
    VLt = S.view(L, "top", (90, 130), 1.0, label="ВИД ЗВЕРХУ (внутрішня сторона)")
    VLt.dim((-d["flange"] / 2, d["flange"] / 2, LT), (d["flange"] / 2, d["flange"] / 2, LT), "h", off=8, txt=f"{d['flange']:.1f}")
    VLt.dim((d["flange"] / 2, -d["flange"] / 2, LT), (d["flange"] / 2, d["flange"] / 2, LT), "v", off=8, txt=f"{d['flange']:.1f}")
    VLt.leader((-d["flange"] / 2 + 5.4, -d["flange"] / 2 + 5.4, 0), -12, 14, f"R{d['r_flange']:.1f}")
    VLt.leader((-d["plug"] / 2 + 4.5, d["plug"] / 2 - 4.5, LT), -12, -18, f"пробка {d['plug']:.1f}, R{d['r_plug']:.1f}; лоток {d['tray']:.1f}")
    Ls = keep(L, "y", 0, +1)
    VLs = S.view(Ls, "front", (245, 105), 2.0, label="РОЗРІЗ (2:1)", section=(Ls, (0, 0, 0), (0, 1, 0)))
    VLs.dim((-d["plug"] / 2, 0, 4.6), (d["plug"] / 2, 0, 4.6), "h", off=-30, txt=f"{d['plug']:.1f} ⊕ (основа пробки)")
    VLs.dim((-d["flange"] / 2, 0, 0), (d["flange"] / 2, 0, 0), "h", off=-8, txt=f"{d['flange']:.1f}")
    VLs.dim((d["flange"] / 2, 0, 0), (d["flange"] / 2, 0, LT), "v", off=10, txt=f"{LT:.1f}")
    VLs.dim((d["flange"] / 2, 0, 0), (d["flange"] / 2, 0, v(p.FLANGE_T)), "v", off=4, txt=f"{v(p.FLANGE_T)}")
    cg, rg = (330, 190), 38
    DR.clip_begin(S, "cG", cg[0], cg[1], rg)
    k = 6.0
    VG = DR.View(S, "front", None, k)
    u0, v0 = VG.uv((d["plug"] / 2 - 1, 0, d["groove_z0"] + 1))
    VG.o = (cg[0] - k * u0, cg[1] + k * v0)
    vis, hid = DR.hlr(Ls, "front", False)
    for rings in DR.section_faces(Ls, (0, 0, 0), (0, 1, 0), "front"):
        dpath = "".join("M " + " L ".join(f"{VG.p(uu, vv)[0]:.3f},{VG.p(uu, vv)[1]:.3f}" for uu, vv in ring) + " Z " for ring in rings)
        S.el.append(f'<path class="hatch" d="{dpath}" fill-rule="evenodd"/>')
    for pl in vis:
        S.poly([VG.p(uu, vv) for uu, vv in pl], "v")
    gb = d["groove_bottom_half"]
    pr = d["plug"] / 2 - ((d["groove_z0"] + d["groove_z1"]) / 2 - 4.5) * np.tan(np.radians(1))
    DR.clip_end(S, cg[0], cg[1], rg, "G (6:1) — канавка ущільнювача")
    VG.dim((gb, 0, d["groove_z0"]), (gb, 0, d["groove_z1"]), "v", off=-8, txt=f"{v(p.GROOVE_W)}")
    VG.dim((gb, 0, d["groove_z1"]), (pr, 0, d["groove_z1"]), "h", off=5, txt=f"{d['groove_depth']:.1f}")
    VG.dim((pr + 1.5, 0, v(p.FLANGE_T)), (pr + 1.5, 0, d["groove_z0"]), "v", off=10, txt=f"{d['groove_z0'] - v(p.FLANGE_T):.1f}")
    VG.leader((pr - 1.0, 0, d["lid_t"] - 1.7), 8, -8, f"фаска {v(p.PLUG_CHAMF_R)}×{v(p.PLUG_CHAMF_H)}")
open(f"{OUT}/03_lid.svg", "w").write(S.svg())
print("sheet 3")

# ======================================================================
# Аркуш 4 — повстяна підкладка + Г-подібний резервуар (v3.0) / кришечка полегшення (до v3.0)
# ======================================================================
FP = P.felt_pad().translate(Vector(-cx, -cy, -d["pocket_floor"]))
fx, fy = P.felt_pad_dims()
if not P.has_relief_lid():
    zH = 50.0
    FULL = bool(v(p.FULL_LID_ON))
    RECT = P.rect_lid()
    ya = (d["pocket_cy"] if RECT else (d["Lyc"] + d["Ly1"]) / 2) if FULL else ((d["arm_y0"] + d["arm_y1"]) / 2)
    _n4 = [f"04: підкладка (овал) {fx:.1f} × {fy:.1f} × {v(p.LINER_FLOOR):.1f} мм, вирубка; клеїти на чисте загерметизоване дно кишені.",
           "Г-резервуар: однаковий переріз до стелі — частина за кишенею девайса з'єднана з основною по всій висоті; "
           "порогу, рампи й порожнини полегшення немає.",
           *([(f"v3.7: кришка схована в дні (без фланця, низ урівень з корпусом, висота {d['plug_h']:.0f}); пробка й шнур Ø{v(p.ORING_CS):.0f} — прямокутник R{v(p.CAV_R_OUT):.0f}; "
                f"язичок у виїмці {v(p.RECESS_W):.0f} × {v(p.HOOK_H):.0f} на задній грані, шнур — над виїмкою (z {d['groove_z0']:.0f}–{d['groove_z1']:.0f})."
                if P.lid_hidden() else
                f"v3.6: кришка — уся основа; пробка й шнур Ø{v(p.ORING_CS):.0f} — прямокутник R{v(p.CAV_R_OUT):.0f} по стінках {v(p.WALL_T):.0f} (ліва, права) / {v(p.WALL_FRONT_T)} (фронт, зад) мм — кришку можна ставити будь-яким боком."),
              f"Низ колонки тримача піднято до z = {d.get('z_sock', 0):.0f} (над пробкою, зазор {v(p.SOCK_TOP_GAP)}), фаска {v(p.COL_CHAMF):.0f}×45°; "
              f"дно кишені z = {d['pocket_floor']:.1f} (бетон {d.get('col_slab', 0):.1f}); девайс виступає на {v(p.DEV_PROTRUDE):.0f} мм."]
             if RECT else
             [f"Кришка — уся основа: шнур Ø{v(p.ORING_CS):.0f} на Г-пробці огинає кут колонки тримача (R{v(p.CAV_R_COL):.0f}); стінка під шнуром суцільна, "
              "виїмка для пальця — нижче канавки."]),
           ("Сердечник — прямокутна основа (гніздо пробки) + Г-призма з ухилом 0.75° на Г-хребті: виходить прямо вниз, без підтиску." if RECT else
            "Сердечник — Г-призма з ухилом 0.75° на Г-хребті: виходить прямо вниз, без підтиску.")] if FULL else None
    S = DR.Sheet("Підкладка, Г-резервуар", "Деталь 04 — підкладка; корпус 01 — Г-резервуар",
                 "04: повсть на клейовій основі; 01: бетон", "2:1; 1:1", 4, NS,
                 notes=_n4 or [f"04: підкладка (овал) {fx:.1f} × {fy:.1f} × {v(p.LINER_FLOOR):.1f} мм, вирубка; клеїти на чисте загерметизоване дно кишені.",
                        f"Г-резервуар: плече за кишенею з'єднане з основною частиною над порогом z = {d['arm_sill_z']:.1f} — на {v(p.ARM_SILL_MARGIN)} мм вище "
                        f"канавки ущільнювача, тож стінка під шнуром суцільна по всьому периметру квадратної кришки.",
                        f"Дно плеча — рампа {v(p.ARM_RAMP_DEG):.0f}° до порогу (стіки зісковзують до отвору); кромка порогу — фаска 1.5; кут колонки тримача R{v(p.ARM_CORNER_R):.0f}; "
                        f"дуга R16 порогу в задньому правому куті — притупити вручну.",
                        "Сердечник: плече — суцільний силікон; виймання: хребет → основна чашка → плече вздовж рампи → по порогу → униз."])
    VFt = S.view(FP, "top", (52, 125), 2.0, label="04 — ВИД ЗВЕРХУ (2:1)", label_dy=16)
    VFt.dim((-fx / 2, 0, 2), (fx / 2, 0, 2), "h", off=-34, txt=f"{fx:.1f}")
    VFt.dim((0, -fy / 2, 2), (0, fy / 2, 2), "v", off=-22, txt=f"{fy:.1f}")
    cutH = keep(body, "z", zH, -1)
    VH = S.view(cutH, "top", (190, 125), 1.0, hidden=False, label=f"РОЗРІЗ H-H (z = {zH:.0f}) — Г-РЕЗЕРВУАР", label_dy=14,
                section=(cutH, (0, 0, zH), (0, 0, 1)))
    if FULL:
        _tz = (zH - d["zb"]) * math.tan(math.radians(v(p.DRAFT_CAV)))
        VH.dim((d["Lxc"] + _tz, 30, zH), (d["Lx1"] - _tz, 30, zH), "h", off=-24, txt="частина за колонкою")
        VH.dim((d["Lx1"] - _tz, 20, zH), (60, 20, zH), "h", off=22, txt=f"{60 - d['Lx1'] + _tz:.1f}")
        VH.dim((45, d["Ly1"] - _tz, zH), (45, 45, zH), "v", off=8, txt=f"{45 - d['Ly1'] + _tz:.1f}")
        _c = v(p.CAV_R_COL) * (1 - 1 / math.sqrt(2))
        VH.leader((d["Lxc"] + _tz + _c, d["Lyc"] + _tz - _c, zH), -26, 20, f"кут колонки R{v(p.CAV_R_COL):.0f}")
    else:
        xa_ = d["cav_x1"] - (zH - d["z_reb"]) * math.tan(math.radians(v(p.DRAFT_CAV)))
        VH.dim((xa_, 30, zH), (d["arm_x1"] - (zH - d["z_reb"]) * math.tan(math.radians(v(p.DRAFT_CAV))), 30, zH), "h", off=-24, txt="плече")
        VH.dim((d["arm_x1"], 20, zH), (60, 20, zH), "h", off=22, txt=f"{60 - d['arm_x1']:.0f}")
        VH.dim((45, d["arm_y1"], zH), (45, 45, zH), "v", off=8, txt=f"{45 - d['arm_y1']:.1f}")
        VH.leader((d["cav_x1"] + 1.5, d["arm_y0"] - 1.5, zH), -26, 20, f"кут колонки R{v(p.ARM_CORNER_R):.0f}")
    VH.leader((cx, cy, zH), -34, 30, "кишеня девайса (колонка)")
    asmA = cq.Compound.makeCompound([keep(s_, "y", ya, +1) for s_ in (body, lid, oring)])
    VAa = S.view(asmA, "front", (330, 172), 1.0, hidden=False,
                 label=(f"РОЗРІЗ A-A (y = {ya:.1f}, через кишеню девайса)" if (FULL and RECT) else f"РОЗРІЗ A-A (y = {ya:.1f}, через частину за колонкою)"), label_dy=14,
                 section=(asmA, (0, ya, 0), (0, 1, 0)))
    if FULL:
        _gz = (d["groove_z0"] + d["groove_z1"]) / 2
        if RECT:
            VAa.leader((d["Lx0"] + 0.6, ya, _gz), 22, -44, f"шнур Ø{v(p.ORING_CS):.0f} — суцільна стінка {v(p.WALL_T):.0f} мм", size=2.6)
            VAa.leader((d["Lxc"] + 10, ya, d["z_sock"]), -22, -16, f"низ колонки z = {d['z_sock']:.0f}", size=2.6)
            VAa.leader((cx, ya, d["pocket_floor"]), -40, -20, f"дно кишені z = {d['pocket_floor']:.1f}", size=2.6)
        else:
            VAa.leader((d["Lx1"] - 0.6, ya, _gz), 20, 26, f"шнур Ø{v(p.ORING_CS):.0f} — суцільна стінка {v(p.WALL_T):.0f} мм")
            VAa.leader((10, ya, 2.0), -30, 22, "кришка — уся основа")
        VAa.dim((60, ya, 0), (60, ya, d["z_ceil_edge"]), "v", off=12, txt=f"{d['z_ceil_edge']:.1f}")
    else:
        VAa.leader((d["cav_x1"] - 0.3, ya, d["arm_sill_z"]), 6, -46, f"поріг z = {d['arm_sill_z']:.1f}")
        VAa.leader((d["cav_x1"] + 12, ya, d["arm_sill_z"] + 12 * math.tan(math.radians(v(p.ARM_RAMP_DEG)))), -6, -22, f"рампа {v(p.ARM_RAMP_DEG):.0f}°")
        VAa.leader((d["cav_x1"] - 0.6, ya, v(p.LID_RECESS) + (d["groove_z0"] + d["groove_z1"]) / 2), -34, 22, "шнур Ø4 — суцільна стінка")
        VAa.dim((d["arm_x1"], ya, 0), (d["arm_x1"], ya, d["z_ceil_edge"]), "v", off=12, txt=f"{d['z_ceil_edge']:.1f}")
    if v(p.BASE_VOID_ON):   # v3.4: порожнина полегшення знизу під рампою
        bv = P.base_void_dims()
        VAa.leader(((bv["x0"] + bv["x1"]) / 2, ya, 8), -26, -62, f"порожнина полегшення знизу, стінки {v(p.WALL_T):.0f}", size=2.6)
    # позначення площин розрізу на виді H-H
    a_, b_ = VH.P((-64, ya, zH)), VH.P((64, ya, zH))
    S.line(a_, b_, "c"); S.text((a_[0] - 3, a_[1] + 1), "A", 3.6, weight="bold"); S.text((b_[0] + 3, b_[1] + 1), "A", 3.6, weight="bold")
    open(f"{OUT}/04_felt_pad_L_reservoir.svg", "w").write(S.svg())
    for _f in (f"{OUT}/04_felt_pad_relief_lid.svg",):
        if os.path.exists(_f):
            os.remove(_f)
else:
    rcx, rcy, rw, rh = P._relief_xy()
    RL = P.relief_lid().translate(Vector(-rcx, -rcy, -v(p.LID_RECESS)))
    S = DR.Sheet("Підкладка, кришечка", "Деталі 04 (підкладка кишені) і 05 (кришечка полегшення)",
                 "04: повсть на клейовій основі; 05: бетон", "2:1", 4, NS,
                 notes=[f"04: підкладка {fx:.1f} × {fy:.1f} × {v(p.LINER_FLOOR):.1f} мм, вирубка; клеїти на чисте загерметизоване дно кишені.",
                        f"05: кришечка знімається пальцем за язичок через виїмку на правій грані; ущільнювач — шнур-губка Ø{v(p.RL_CS):.0f}, відріз {d['rl_seal_cut_len']:.0f} мм."])
    VFt = S.view(FP, "top", (70, 110), 2.0, label="04 — ВИД ЗВЕРХУ (2:1)", label_dy=16)
    VRt = S.view(RL, "top", (185, 110), 2.0, label="05 — ВИД ЗВЕРХУ (2:1)", label_dy=12)
    RLs = keep(RL, "y", 0, +1)
    VRs = S.view(RLs, "front", (320, 110), 2.0, label="05 — РОЗРІЗ (2:1)", section=(RLs, (0, 0, 0), (0, 1, 0)), label_dy=14)
    open(f"{OUT}/04_felt_pad_relief_lid.svg", "w").write(S.svg())
import glob as _g
for _f in _g.glob(f"{OUT}/04_liner.svg"):
    os.remove(_f)
print("sheet 4")

# ======================================================================
# Аркуш 5 — складальне креслення + специфікація
# ======================================================================
S = DR.Sheet("Збірка", "Складальне креслення, специфікація (BOM)", "див. специфікацію", "1:1", 5, NS,
             notes=["Девайс IQOS ILUMA ONE (121.6×30.6×16.4, 68.5 г) — не входить до комплекту, показано довідково.",
                    "Кришка ставиться язичком до виїмки на задній грані (язичок — фіксатор положення); знімається пальцем за язичок." + ("" if not P.has_relief_lid() else " Кришечка — язичком до виїмки справа."),
                    f"Девайс — USB-C донизу, кнопкою до фронту: світлова смужка (z {d['btn_z1']:.0f}–{d['led_z1']:.0f}) і кнопка (z {d['btn_z0']:.0f}–{d['btn_z1']:.0f}) — над корпусом; під кнопкою — проріз-вітрина."])
asm_full = cq.Compound.makeCompound([body, lid, oring, liner, dev, _led, _btn])
VA5 = S.view(asm_full, "front", (88, 176), 1.0, hidden=False, label="ЗБІРКА — ФРОНТАЛЬНИЙ ВИГЛЯД", label_dy=12)
VA5.dim((cx + 8.2, -45, H), (cx + 8.2, -45, H + v(p.DEV_PROTRUDE)), "v", off=14, txt=f"{v(p.DEV_PROTRUDE):.0f} (виступ девайса)")
VA5.dim((-60, -45, 0), (-60, -45, H + v(p.DEV_PROTRUDE)), "v", off=-10, txt=f"{H + v(p.DEV_PROTRUDE):.0f}")
VBot = S.view(body, "bottom", (88, 250), 0.5, hidden=False, label="ВИД ЗНИЗУ (1:2) — кришку знято", label_dy=10)
asmB = cq.Compound.makeCompound([keep(s_, "y", cy, +1) for s_ in (body, lid, oring, liner, dev)])
VB5 = S.view(asmB, "front", (218, 176), 1.0, hidden=False, label="РОЗРІЗ B-B (вісь кишені)", label_dy=12,
             section=(asmB, (0, cy, 0), (0, 1, 0)))
rows = [("1", "01", "Корпус монолітний", "декор. бетон / GFRC", "1", f"{mass_body:.2f} кг" if mass_body else ""),
        ("1a", "07/08", "Фарба логотипа STICK/BOX", "RAL 7016 / бірюзов.", "—", "після лиття"),
        ("2", "02", "Кришка нижня з пробкою", "декор. бетон / GFRC", "1", f"{mass_lid:.3f} кг" if mass_lid else ""),
        ("3", "03", f"Ущільнювач: шнур Ø4 × {d['seal_cut_len']:.0f}", "силіконова губка", "1", "покупне"),
        ("4", "04", "Підкладка кишені", f"повсть {fx:.0f}×{fy:.0f}×{v(p.LINER_FLOOR):.0f}", "1", "вирубка"),
        *([("5a", "05", "Кришечка полегшення", "декор. бетон / GFRC", "1", f"{AN.get('mass', {}).get('relief_lid', {}).get('mass_kg', 0):.3f} кг"),
           ("5b", "06", f"Шнур Ø3 × {d['rl_seal_cut_len']:.0f} (кришечка)", "силіконова губка", "1", "покупне")] if P.has_relief_lid() else []),
        ("5", "—", "Опори самоклеючі Ø8×1", "PU / повсть (опція)", "4", "покупне"),
        ("—", "90", "IQOS ILUMA ONE (довідково)", "—", "—", "68.5 г")]
DR.table(S, 282, 40, ["Поз.", "Позн.", "Найменування", "Матеріал", "К-сть", "Прим."], rows,
         [9, 10, 42, 40, 10, 18], size=2.6)
kc = AN.get("cavity", {})
_cp = os.path.join(os.path.dirname(__file__), "..", "reports", "capacity_sim.json")
if os.path.exists(_cp):
    _c = json.load(open(_cp))
    CAPTXT = f"≈{_c['no_shake_mean']:.0f} без струшування / ≈{_c['with_shake_mean']:.0f} зі струшуванням"
else:
    CAPTXT = "див. reports/capacity_sim.json"
st = AN.get("stability", {})
rows2 = [("Габарити (Ш×Г×В)", "120 × 90 × 95 мм"), ("Чистий об'єм порожнини", f"{kc.get('net_volume_ml', 302):.0f} мл" + (f" (Г-резервуар: {kc['main_ml']:.0f} + плече {kc['arm_ml']:.0f})" if kc.get('arm_ml') else "")),
         ("Місткість (симуляція, див. звіт)", CAPTXT),
         ("Маса комплекту без девайса", (lambda vc_: f"{vc_ * 2.0e-3:.2f} кг (ρ 2000); {vc_ * 1.8e-3:.2f} (ρ 1800); {vc_ * 1.75e-3:.2f} (ρ 1750)")(
             sum(AN.get('mass', {}).get(k_, {}).get('volume_ml', 0) for k_ in ('body', 'lid', 'relief_lid')))),
         ("Кут статичного перекидання", f"{st.get('tip_angle_deg', 0):.0f}°"),
         ("Отвір / воронка", "Ø8 ⊕ / Ø22, пряма ділянка 2 мм")]
DR.table(S, 282, 102, ["Характеристика", "Значення"], rows2, [52, 77], size=2.6)
open(f"{OUT}/05_assembly_bom.svg", "w").write(S.svg())
print("sheet 5")

# ======================================================================
# Аркуш 6 — оснащення: схема лиття корпусу
# ======================================================================
T = M.all_tooling()
ix0, ix1, iy0, iy1, z0, z1 = M._sleeve_dims()
sleeve_in = M._rrp(((ix0 + ix1) / 2, (iy0 + iy1) / 2), ix1 - ix0, iy1 - iy0, 6, z0, z1 - z0)
sil = sleeve_in.cut(T["body_master"]).cut(T["finger_stiffener"])
casting = M.S(P.body(product=False, height_extra=M.GA))
flip = lambda s: s.rotate(Vector(0, 0, 0), Vector(1, 0, 0), 180)
tool_asm = cq.Compound.makeCompound([flip(keep(s, "y", 0, -1)) for s in
                                     (T["body_sleeve"], sil, T["core_silicone"], T["core_spine_bridge"], T["finger_stiffener"], casting)])
S = DR.Sheet("Оснащення", "Схема лиття корпусу «догори дном» — розріз по осі воронки", "див. перелік оснащення", "1:1", 6, NS,
             notes=["Базування: майстер T01 → плита T03 (штифти) → гільза T02 → міст T05; міст стягується 4 шпильками M5 крізь вушка гільзи (сердечник не спливає).",
                    "Отвір Ø8 — телескопічний стик: шпилька форми заходить у гніздо сердечника на 3 мм. Вкладка виїмки (задня грань) — натяг 1.0 мм у стінку форми; плече сердечника (Г-резервуар) — суцільний силікон, виймається вздовж рампи.",
                    "Масштаб формотворчої геометрії ×1.002 (усадка); калібрувати за пробними виливками."])
VT6 = S.view(tool_asm, "front", (122, 72), 1.0, hidden=False, label="РОЗРІЗ ОСНАЩЕННЯ (положення лиття, 1:1)",
             section=(tool_asm, (0, 0, 0), (0, 1, 0)), label_dy=14)
F6 = lambda q: (q[0], -q[1], -q[2])  # перевернуте положення лиття
VT6.leader(F6((-80, -1, 50)), -10, -14, "T02 гільза")
VT6.leader(F6((-66, -1, 40)), -6, 20, "силікон форми")
VT6.leader(F6((-50, -1, 40)), 8, 34, "бетон (виливок)")
VT6.leader(F6((-30, -1, 40)), 20, 46, "T07 сердечник")
VT6.leader(F6((-15, -1, 30)), 46, 52, "T05 хребет+міст")
VT6.leader(F6((40, -1, 60)), 20, 40, "T04 ребро «пальця»")
rows3 = [("T01", "Майстер-модель зовн. форми", "друк смола/FDM + шліфування"),
         ("T02", "Гільза (материнська форма)", "друк PETG/ABS"),
         ("T03", "Базова плита заливки силікону", "друк PETG"),
         ("T04", "Ребро жорсткості «пальця»", "друк PETG"),
         ("T05", "Хребет + міст сердечника", "друк PETG"),
         ("T06", "Форма для силіконової чашки", "друк PETG / смола"),
         ("T07", "Сердечник (силікон)", "платин. силікон ShA 25–30"),
         ("T08–T10", "Майстер, гільза, плита форми кришки", "друк"),
         *([("T18–T20", "Майстер, гільза, плита форми кришечки полегшення", "друк смола / FDM")] if P.has_relief_lid() else []),
         ("T13–T14", "Калібр отвору Ø7.90, імітатор HEETS Ø7.42", "друк смола"),
         ("T17", "Тримач ребра «пальця» (заливка силікону)", "друк PETG")]
DR.table(S, 235, 40, ["Поз.", "Найменування", "Матеріал / процес"], rows3, [16, 70, 62], size=2.6)
open(f"{OUT}/06_tooling_casting_scheme.svg", "w").write(S.svg())
print("sheet 6")

# ======================================================================
# Аркуш 7 — напис STICKBOX зі знаком-I: артворк дебосингу та схема фарбування (v3.2)
# ======================================================================
BR = BR0
from shapely import affinity as _aff
from shapely.ops import unary_union as _uu, nearest_points as _np
LW = BR.wordmark_layout()
wm = LW["letters"]
swo = LW["swoosh"]
mk = LW["mark"]
S = DR.Sheet("Логотип", "Напис STICKBOX зі знаком-I, знак NFC: артворк дебосингу, схема фарбування", "дебосинг у корпусі 01; фарба для бетону",
             "2:1 (1:1)", 7, NS, notes=[
                 f"1. Напис врізаний у фронтальну грань на {v(p.LOGO_DEPTH)} мм, стінки кишень 90° до грані (знімаються еластичною формою). "
                 "Окремого знака над написом немає (v3.2).",
                 f"2. Літера I — фірмовий знак: стік і «крапка» на висоту великих літер ({v(p.LOGO_CAP_H)} мм), хвиля над рядком.",
                 f"3. Перемички бетону: хвиля / стік ≥{v(p.LOGO_I_WEB)}, стік / «крапка» {v(p.LOGO_I_CAP_GAP)}, між літерами ≥{LW['info']['min_letter_gap_mm']} мм. "
                 f"Кінчики хвилі R{v(p.MARK_TIP_R)}, гачок R{v(p.MARK_HOOK_R)}, кути стіка R{v(p.MARK_BAR_R)}.",
                 "4. Montserrat Bold (OFL). Знак — з растрового логотипа замовника, плавні B-сплайни; оригінальний вектор бренду — замінити.",
                 "5. Фарбування — після першого шару просочення; надлишки знімати врівень з гранню (техкарта 05, §6). Фарба — не металік.",
                 *([f"6. Знак NFC на верхній грані (той самий дебосинг {v(p.LOGO_DEPTH)} мм); під ним зсередини — мітка Ø{v(p.NFC_TAG_D):.0f} у кишені стелі, бетону над міткою {v(p.NFC_COVER):.0f} мм."] if v(p.NFC_ON) else [])])
V = DR.View(S, "front", (135, 200), 2.0)
Y0 = -v(p.D) / 2
GREY, TEAL = "#383E42", "#058B8C"


def _fill(geom, color, dx=0.0, dz=0.0):
    for pg in (geom.geoms if geom.geom_type == "MultiPolygon" else [geom]):
        dpath = ""
        pg = pg.simplify(0.003)   # v3.1: контури щільні (гладкі сплайни) — для SVG досить 3 мкм
        for ring in [pg.exterior] + list(pg.interiors):
            pts = [V.P((x + dx, Y0, z + dz)) for x, z in ring.coords]
            dpath += "M " + " L ".join(f"{a:.3f},{b:.3f}" for a, b in pts) + " Z "
        S.el.append(f'<path d="{dpath}" fill="{color}" fill-rule="evenodd" stroke="#111" stroke-width="0.25"/>')


zl = v(p.LOGO_Z)
for i, (ch, g) in enumerate(wm):
    _fill(g, GREY if i < 5 else TEAL, 0, zl)
if swo is not None:
    _fill(swo, TEAL, 0, zl)
# контекст: низ грані, межі пласкої частини фронту (далі — R вертикальних ребер)
xf = v(p.W) / 2 - v(p.R_V)
S.line(V.P((-xf, Y0, 0)), V.P((xf, Y0, 0)), "v")
V.center_v((0, Y0, zl), 14); V.center_h((0, Y0, zl), 44)
allg = _uu([g for _, g in wm] + ([swo] if swo is not None else []))
ab = allg.bounds
Ch = v(p.LOGO_CAP_H)
V.dim((ab[0], Y0, zl + ab[1]), (ab[2], Y0, zl + ab[1]), "h", off=-12, txt=f"{ab[2] - ab[0]:.1f}")
V.dim((ab[2], Y0, zl - Ch / 2), (ab[2], Y0, zl + Ch / 2), "v", off=6, txt=f"{Ch:.1f}")
V.dim((ab[0], Y0, 0), (ab[0], Y0, zl), "v", off=-12, txt=f"{zl:.0f}")
gaps = [ga.distance(gb) for (_, ga), (_, gb) in zip(wm, wm[1:])]
if mk:
    st, cp = mk["stem"][0], mk["cap"][0]
    bars = _uu([st, cp])
    mb = _uu([bars, swo]).bounds
    V.dim((ab[2], Y0, zl - Ch / 2), (ab[2], Y0, zl + mb[3]), "v", off=16, txt=f"{mb[3] + Ch / 2:.1f}")   # до верху хвилі
    a_, b_ = _np(swo, st); mid = ((a_.x + b_.x) / 2, (a_.y + b_.y) / 2)
    V.leader((mid[0], Y0, zl + mid[1]), -10, -46, f"перемичка хвиля / стік {swo.distance(bars):.1f}")
    a_, b_ = _np(st, cp); mid = ((a_.x + b_.x) / 2, (a_.y + b_.y) / 2)
    V.leader((mid[0], Y0, zl + mid[1]), 10, -58, f"щілина стік / «крапка» {st.distance(cp):.1f}")
    tip = max(swo.exterior.coords, key=lambda q: q[0] + q[1])
    V.leader((tip[0], Y0, zl + tip[1]), 40, -34, f"кінчики хвилі R{v(p.MARK_TIP_R)}")
kb = wm[4][1].distance(wm[5][1])
kx = (wm[4][1].bounds[2] + wm[5][1].bounds[0]) / 2
V.leader((kx, Y0, zl - Ch / 2 + 1.0), 24, 30, f"межа кольорів K|B: {kb:.1f} (мін. між літерами {min(gaps):.1f})")
# 1:1 вид цілої грані
VF = S.view(body, "front", (330, 152), 1.0, hidden=False, label="ФРОНТ 1:1 (розташування)", label_dy=10)
# v3.3: знак NFC (верхня грань) і розріз кишені мітки
nfc_w = nfc_t = 0.0
if v(p.NFC_ON):
    NS_ = BR.nfc_symbol()
    nx_, ny_ = v(p.NFC_X), v(p.NFC_Y)
    VN = DR.View(S, "top", (78, 236), 2.0)

    def _fill_top(geom, color):
        for pg in (geom.geoms if geom.geom_type == "MultiPolygon" else [geom]):
            pg = pg.simplify(0.003)
            dpath = ""
            for ring in [pg.exterior] + list(pg.interiors):
                pts = [VN.P((x, y_, H)) for x, y_ in ring.coords]
                dpath += "M " + " L ".join(f"{a:.3f},{b:.3f}" for a, b in pts) + " Z "
            S.el.append(f'<path d="{dpath}" fill="{color}" fill-rule="evenodd" stroke="#111" stroke-width="0.25"/>')
    _fill_top(NS_["waves"], TEAL)
    for _, q in NS_["text"]:
        _fill_top(q, GREY)
    S.el.append(f'<circle cx="{VN.P((0, 0, H))[0]:.2f}" cy="{VN.P((0, 0, H))[1]:.2f}" r="{v(p.NFC_TAG_D):.2f}" fill="none" stroke="#555" stroke-width="0.25" stroke-dasharray="2 1.2"/>')
    VN.center_v((0, 0, H), 15); VN.center_h((0, 0, H), 15)
    nb = NS_["info"]["bounds"]
    VN.dim((nb[0], nb[1], H), (nb[2], nb[1], H), "h", off=-5, txt=f"{nb[2] - nb[0]:.1f}")
    VN.dim((nb[2], nb[1], H), (nb[2], nb[3], H), "v", off=5, txt=f"{nb[3] - nb[1]:.1f}")
    S.text((78, 274), "ЗНАК NFC (2:1), зверху", 3.0, weight="bold")
    S.text((78, 279), f"пунктир — мітка Ø{v(p.NFC_TAG_D):.0f} під ним", 2.4)
    nfc_w = NS_["waves"].area
    nfc_t = sum(q.area for _, q in NS_["text"])
    # виносний елемент G — розріз по центру мітки (y = NFC_Y), 2:1
    from stickbox import analysis as _an  # noqa: F401
    ND = P.nfc_pocket_dims()
    cutG = cq.Compound.makeCompound([keep(body, "y", ny_, +1), keep(P.nfc_tag(), "y", ny_, +1)])
    cg, rg = (176, 240), 28
    DR.clip_begin(S, "cG", cg[0], cg[1], rg)
    k = 2.0
    VG = DR.View(S, "front", None, k)
    u0, v0 = VG.uv((nx_, ny_, ND["z_top"]))
    VG.o = (cg[0] - k * u0, cg[1] + k * v0)
    vis, hid = DR.hlr(cutG, "front", False)
    for rings in DR.section_faces(cutG, (0, ny_, 0), (0, 1, 0), "front"):
        dpath = "".join("M " + " L ".join(f"{VG.p(uu, vv)[0]:.3f},{VG.p(uu, vv)[1]:.3f}" for uu, vv in ring) + " Z " for ring in rings)
        S.el.append(f'<path class="hatch" d="{dpath}" fill-rule="evenodd"/>')
    for pl in vis:
        S.poly([VG.p(uu, vv) for uu, vv in pl], "v")
    DR.clip_end(S, cg[0], cg[1], rg, "G (2:1) — кишеня NFC-мітки (розріз по центру)")
    VG.dim((nx_ - ND["d_ceil"] / 2, ny_, ND["z_ceil"] - 0.3), (nx_ + ND["d_ceil"] / 2, ny_, ND["z_ceil"] - 0.3), "h", off=-5, txt=f"Ø{v(p.NFC_POCKET_D)}")
    VG.dim((nx_ + 6, ny_, ND["z_top"]), (nx_ + 6, ny_, H), "v", off=0, txt=f"{v(p.NFC_COVER):.0f}")
    VG.dim((nx_ - 6, ny_, ND["z_ceil"]), (nx_ - 6, ny_, ND["z_top"]), "v", off=0, txt=f"{ND['depth']:.1f}")
    VG.leader((nx_ + 3, ny_, ND["z_top"] - v(p.NFC_TAG_T) / 2), 20, 14, f"мітка Ø{v(p.NFC_TAG_D):.0f} (клей)", size=2.4)
# таблиця фарб
ag = sum(g.area for _, g in wm[:5]) + nfc_t
at = sum(g.area for _, g in wm[5:]) + (swo.area if swo is not None else 0.0) + nfc_w
dep = v(p.LOGO_DEPTH)
rows7 = [("RAL 7016 темно-сірий", "S T + стік-I + C K" + (" + «NFC»" if (v(p.NFC_ON) and v(p.NFC_TEXT_ON)) else ""), f"{ag:.0f}", f"{ag * dep / 1000:.2f}"),
         ("Бірюзовий RAL 5018 / еталон", "хвиля + B O X" + (" + дуги NFC" if v(p.NFC_ON) else ""), f"{at:.0f}", f"{at * dep / 1000:.2f}"),
         ("Разом", "маски 07 / 08 у exports/", f"{ag + at:.0f}", f"{(ag + at) * dep / 1000:.2f}")]
DR.table(S, 236, 186, ["Колір", "Елементи", "Площа, мм²", "Об'єм, мл"], rows7, [44, 56, 22, 22], size=2.6)
open(f"{OUT}/07_logo_artwork_paint.svg", "w").write(S.svg())
print("sheet 7", round(ag, 1), round(at, 1))
