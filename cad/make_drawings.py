"""Комплект креслень STICKBOX 01 Monolith (SVG A3 + зведений PDF)."""
import os, sys, json
import numpy as np
import cadquery as cq
from cadquery import Vector
sys.path.insert(0, os.path.dirname(__file__))
from stickbox import parts as P, molds as M, params as p, drawing as DR
from stickbox.params import v

OUT = os.path.join(os.path.dirname(__file__), "..", "drawings")
os.makedirs(OUT, exist_ok=True)
d = P.d
big = 600
NS = 6
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
    f"⊕ Функціональні розміри (±0.25; отвір ±0.2): ребейт {P.d['reb']:.1f}, порожнина в зоні ущільнення {v(p.CAV):.1f}, кишеня девайса, отвір Ø8.",
    "Невказані радіуси литих ребер R0.5–1. Нижня (відкрита) грань — шліфування P120→P220, площинність 0.3, притуплення R≈1.",
]

body = P.body()
lid = P.lid()
oring = P.oring()
liner = P.liner()
dev = P.device()
xc, cx, cy = d["cav_xc"], d["pocket_cx"], d["pocket_cy"]
H = v(p.H)
mass_body = AN.get("mass", {}).get("body", {}).get("mass_kg")
mass_lid = AN.get("mass", {}).get("lid", {}).get("mass_kg")

# ======================================================================
# Аркуш 1 — корпус: види
# ======================================================================
S = DR.Sheet("Корпус", "Деталь 01 — Корпус монолітний (загальні види)", "декоративний бетон / GFRC-премікс",
             "1:1", 1, NS, notes=GENERAL + ["Логотип STICKBOX — дебосинг 0.6 (Inter Medium, великі літери ≈7.6 мм, центр на висоті 24). Пальцева виїмка 30 × " + f"{P.d['recess_top']:.1f}" + ", кути R7, кромки R1.5 (вручну)."], mass=(f"Маса ≈ {mass_body:.2f} кг (ρ 2000)" if mass_body else None))
V = S.view(body, "front", (100, 145), 1.0, label="ФРОНТАЛЬНИЙ ВИГЛЯД")
V.dim((-60, -45, 0), (60, -45, 0), "h", off=-16)
V.dim((-60, -45, 0), (-60, -45, H), "v", off=-10)
V.dim((-60, -45, H), (xc, -45, H), "h", off=9)
V.center_v((xc, -45, 88), 12)
V.dim((cx - 4, -45, H), (cx + 4, -45, H), "h", off=6)
V.dim((cx + 4, -45, H), (cx + 4, -45, H - v(p.SLOT_DEPTH)), "v", off=10)
V.dim((-15, -45, 0), (15, -45, 0), "h", off=-7)
V.dim((15, -45, 0), (15, -45, d["recess_top"]), "v", off=24, txt=f"{d['recess_top']:.1f}")
VT = S.view(body, "top", (100, 222), 1.0, label="ВИД ЗВЕРХУ", label_dy=18)
VT.dim((60, -45, H), (60, 45, H), "v", off=16)
VT.dim((52, -45, H), (52, cy, H), "v", off=8, txt=f"{cy + 45:.1f}")
VT.dim((cx, 45, H), (60, 45, H), "h", off=8, txt=f"{60 - cx:.1f}")
VT.dim((-60, 45, H), (xc, 45, H), "h", off=8, txt=f"{xc + 60:.1f}")
VT.center_v((xc, 0, H), 16); VT.center_h((xc, 0, H), 16)
VT.center_v((cx, cy, H), 24); VT.center_h((cx, cy, H), 16)
VT.leader((xc + 7.8, 7.8, H), 14, -26, "Ø22 воронка (S-профіль)")
VT.leader((xc - 2.8, -2.8, H), -26, -22, "Ø8 ⊕ наскрізний")
VT.leader((cx - 11.1, cy + 8, H), -30, 12, f"кишеня {d['pocket_x']:.1f}×{d['pocket_y']:.1f}, ухил {v(p.DRAFT_POCKET)}°")
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
S = DR.Sheet("Корпус", "Деталь 01 — Розрізи A-A, C-C; виносні елементи E (4:1), F (5:1)", "декоративний бетон / GFRC-премікс",
             "1:1; 4:1; 5:1", 2, NS, notes=[f"Розріз A-A — по осі воронки (y = 0). Розріз C-C — по осі воронки (x = {xc:.1f}).",
                                            f"Порожнина: ухил стінок {v(p.DRAFT_CAV)}° (вихід сердечника), купол стелі — стріла {v(p.DOME_SAG)} мм (відведення повітря).",
                                            f"Заходна фаска ущільнювача {v(p.LEADIN_ANGLE):.0f}° × {v(p.LEADIN_LEN)}; кромка стелі виїмки R1.5 (по ній проходить ущільнювач).",
                                            "Полегшувальна порожнина правої колонки (відкрита знизу) — див. вид знизу на аркуші 5 і розріз D-D."])
cutA = keep(body, "y", 0, +1)
VA = S.view(cutA, "front", (95, 150), 1.0, label="РОЗРІЗ A-A", section=(cutA, (0, 0, 0), (0, 1, 0)))
VA.dim((d["cav_x0"], 0, 5), (d["cav_x1"], 0, 5), "h", off=-24, txt=f"{v(p.CAV):.1f} ⊕ (низ)")
VA.dim((xc - d["reb"] / 2, 0, 0), (xc + d["reb"] / 2, 0, 0), "h", off=-12, txt=f"{d['reb']:.1f} ⊕")
VA.dim((-60, 0, 0), (-60, 0, d["z_ceil_c"]), "v", off=-8, txt=f"{d['z_ceil_c']:.0f} (стеля, центр)")
VA.dim((xc + 14, 0, d["z_ceil_c"]), (xc + 14, 0, H), "v", off=6, txt=f"{v(p.T_TOP):.0f}")
VA.dim((60, 0, 0), (60, 0, d["z_reb"]), "v", off=8, txt=f"{d['z_reb']:.1f} ⊕")
VA.dim((-60, 0, 30), (d["cav_x0"], 0, 30), "h", off=6, txt=f"{v(p.T_LEFT):.0f}")
VA.leader((d["cav_x1"] - 0.6, 0, 60), 12, -16, f"ухил {v(p.DRAFT_CAV)}°")
VA.leader((xc + 20, 0, d["z_ceil_edge"] + 0.5), 18, -22, f"купол R{d['r_dome']:.0f}, стріла {v(p.DOME_SAG)}")
cutC = keep(body, "x", xc, +1)
VC = S.view(cutC, "left", (238, 150), 1.0, label="РОЗРІЗ C-C", section=(cutC, (xc, 0, 0), (1, 0, 0)))
VC.dim((xc, -45, 0), (xc, d["cav_y0"], 0), "h", off=-8, txt=f"{d['t_front_back']:.1f}")
VC.dim((xc, 45, 0), (xc, -45, 0), "h", off=-16, txt="90")
VC.dim((xc, 45, 0), (xc, 45, d["recess_top"]), "v", off=8, txt=f"{d['recess_top']:.1f} (виїмка)")
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
u0, v0 = VF.uv((d["cav_x0"] - 1.5, 0, 8))
VF.o = (cf[0] - k * u0, cf[1] + k * v0)
vis, hid = DR.hlr(asm, "front", False)
for rings in DR.section_faces(asm, (0, 0, 0), (0, 1, 0), "front"):
    dpath = "".join("M " + " L ".join(f"{VF.p(uu, vv)[0]:.3f},{VF.p(uu, vv)[1]:.3f}" for uu, vv in ring) + " Z " for ring in rings)
    S.el.append(f'<path class="hatch" d="{dpath}" fill-rule="evenodd"/>')
for pl in vis:
    S.poly([VF.p(uu, vv) for uu, vv in pl], "v")
DR.clip_end(S, cf[0], cf[1], rf, "F (5:1) — кришка / ущільнення")
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
# Аркуш 4 — силіконова вставка
# ======================================================================
Ln = liner.translate(Vector(-cx, -cy, -d["pocket_floor"]))
S = DR.Sheet("Вставка", "Деталь 04 — Знімна силіконова вставка тримача девайса", "платиновий силікон Shore A 40–50, графіт",
             "1:1; 2:1", 4, NS,
             notes=["Вставка симетрична: прорізи з обох торців — встановлення в будь-якому з 2 положень (захист від помилки).",
                    "Посадка в бетонній кишені з натягом 0.15 на сторону; верх на 0.3 нижче площини корпусу.",
                    "4 мікроребра (R0.6, висота 0.35) центрують девайс: зазор 0.05 по ребрах, 0.4 по стінках."])
VNt = S.view(Ln, "top", (85, 95), 2.0, label="ВИД ЗВЕРХУ (2:1)")
VNt.dim((-d["liner_in_x"] / 2, 0, 86.3), (d["liner_in_x"] / 2, 0, 86.3), "h", off=-24, txt="17.2")
VNt.dim((0, -d["liner_in_y"] / 2, 86.3), (0, d["liner_in_y"] / 2, 86.3), "v", off=-30, txt="31.4")
VNt.dim((-11.25, 0, 86.3), (11.25, 0, 86.3), "h", off=-34, txt="22.5 (верх)")
VNt.leader((d["liner_in_x"] / 2 - 0.3, 7, 86.3), 16, -12, "мікроребро R0.6 ×4")
Lx = keep(Ln, "x", 0, +1)
VNs = S.view(Lx, "left", (230, 140), 1.0, label="РОЗРІЗ уздовж (1:1)", section=(Lx, (0, 0, 0), (1, 0, 0)))
VNs.dim((0, 18.4, 0), (0, 18.4, 86.3), "v", off=10, txt="86.3")
VNs.dim((0, 0, 0), (0, 0, 3), "v", off=-32, txt="3 (дно)")
VNs.dim((0, -18.4, 86.3), (0, -18.4, 86.3 - 34 + 0.3), "v", off=-10, txt="33.7 (проріз)")
Ly = keep(Ln, "y", 0, +1)
VNf = S.view(Ly, "front", (330, 140), 1.0, label="РОЗРІЗ поперек (1:1)", section=(Ly, (0, 0, 0), (0, 1, 0)))
VNf.leader((-11.25, 0, 70), -14, -10, "ухил 0.75°")
open(f"{OUT}/04_liner.svg", "w").write(S.svg())
print("sheet 4")

# ======================================================================
# Аркуш 5 — складальне креслення + специфікація
# ======================================================================
S = DR.Sheet("Збірка", "Складальне креслення, специфікація (BOM)", "див. специфікацію", "1:1", 5, NS,
             notes=["Девайс IQOS ILUMA ONE (121.6×30.6×16.4, 68.5 г) — не входить до комплекту, показано довідково.",
                    "Кришка ставиться в будь-якому з 4 положень (квадратна пробка). Знімається пальцем через виїмку."])
asm_full = cq.Compound.makeCompound([body, lid, oring, liner, dev])
VA5 = S.view(asm_full, "front", (88, 150), 1.0, hidden=False, label="ЗБІРКА — ФРОНТАЛЬНИЙ ВИГЛЯД")
VA5.dim((cx + 8.2, -45, H), (cx + 8.2, -45, H + v(p.DEV_PROTRUDE)), "v", off=14, txt=f"{v(p.DEV_PROTRUDE):.0f} (виступ девайса)")
VA5.dim((-60, -45, 0), (-60, -45, H + v(p.DEV_PROTRUDE)), "v", off=-10, txt=f"{H + v(p.DEV_PROTRUDE):.0f}")
VBot = S.view(body, "bottom", (88, 238), 0.5, hidden=False, label="ВИД ЗНИЗУ (1:2) — кришку знято", label_dy=10)
asmB = cq.Compound.makeCompound([keep(s_, "y", cy, +1) for s_ in (body, lid, oring, liner, dev)])
VB5 = S.view(asmB, "front", (218, 150), 1.0, hidden=False, label="РОЗРІЗ B-B (вісь кишені)",
             section=(asmB, (0, cy, 0), (0, 1, 0)))
rows = [("1", "01", "Корпус монолітний", "декор. бетон / GFRC", "1", f"{mass_body:.2f} кг" if mass_body else ""),
        ("2", "02", "Кришка нижня з пробкою", "декор. бетон / GFRC", "1", f"{mass_lid:.3f} кг" if mass_lid else ""),
        ("3", "03", f"Ущільнювач: шнур Ø4 × {d['seal_cut_len']:.0f}", "силіконова губка", "1", "покупне"),
        ("4", "04", "Вставка тримача девайса", "платин. силікон 40–50 ShA", "1", "≈18 г"),
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
rows2 = [("Габарити (Ш×Г×В)", "120 × 90 × 95 мм"), ("Чистий об'єм порожнини", f"{kc.get('net_volume_ml', 302):.0f} мл"),
         ("Місткість (симуляція, див. звіт)", CAPTXT),
         ("Маса комплекту без девайса", f"{AN.get('assembly', {}).get('mass_kg', 0):.2f} кг (ρ 2000); 0.87 кг (ρ 1800)"),
         ("Кут статичного перекидання", f"{st.get('tip_angle_deg', 0):.0f}°"),
         ("Отвір / воронка", "Ø8 ⊕ / Ø22, пряма ділянка 2 мм")]
DR.table(S, 282, 85, ["Характеристика", "Значення"], rows2, [52, 77], size=2.6)
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
                    "Отвір Ø8 — телескопічний стик: шпилька форми заходить у гніздо сердечника на 3 мм. Вкладка виїмки — натяг 1.0 мм у стінку форми.",
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
         ("T11–T12", "Форма вставки девайса (чашка+сердечник)", "друк смола"),
         ("T13–T14", "Калібр отвору Ø7.90, імітатор HEETS Ø7.42", "друк смола"),
         ("T17", "Тримач ребра «пальця» (заливка силікону)", "друк PETG")]
DR.table(S, 235, 40, ["Поз.", "Найменування", "Матеріал / процес"], rows3, [16, 70, 62], size=2.6)
open(f"{OUT}/06_tooling_casting_scheme.svg", "w").write(S.svg())
print("sheet 6")
