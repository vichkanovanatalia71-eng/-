"""Додаткові GLB для рендерів: оснащення в розрізі (положення лиття), купа стіків із симуляції."""
import json, math, os, sys
import numpy as np
import cadquery as cq
from cadquery import Vector
sys.path.insert(0, os.path.dirname(__file__))
from stickbox import parts as P, molds as M, export as X, params as p
from stickbox.params import v

OUT = os.path.join(os.path.dirname(__file__), "render", "glb")
os.makedirs(OUT, exist_ok=True)
big = 500
half = M.box(-big, big, 0, big, -big, big)   # прибрати задню половину (y>0)

def flip(s):
    return s.rotate(Vector(0, 0, 0), Vector(1, 0, 0), 180)

T = M.all_tooling()
sil = M.mold_silicone("body")
casting = M.S(P.body(product=False, height_extra=M.GA))
items = [("t_sleeve", M.body_sleeve(), "print"), ("t_silicone", sil, "silicone"),
         ("t_core", T["core_silicone"], "silicone"), ("t_bridge", T["core_spine_bridge"], "print"),
         ("t_stiff", T["finger_stiffener"], "print"), ("t_concrete", casting, "body")]
# положення лиття: догори дном; переріз по y=0
sec = [(n, flip(s.cut(half)), mk) for n, s, mk in items]
X.export_glb(sec, f"{OUT}/tooling_body_section.glb", tol=0.05, ang=0.15)
# вибухова схема оснащення (повні тіла, положення лиття)
X.export_glb([(n, flip(s), mk) for n, s, mk in items if n != "t_concrete"] + [("t_master", flip(T["body_master"]), "master")],
             f"{OUT}/tooling_body_full.glb", tol=0.05, ang=0.15)
# v3.7: розбірний каркас — заливка силікону (майстер на плиті) і переріз по x = 0 (рівновіддалений силікон, ключі)
fr_f, fr_b = M.frame_halves("body")
X.export_glb([("frame_front", fr_f, "print"), ("frame_back", fr_b, "print"), ("silicone", sil, "silicone"),
              ("master", T["body_master"], "master"), ("plate", T["body_base_plate"], "mold"),
              ("stiff", T["finger_stiffener"], "print")], f"{OUT}/mold_frame.glb", tol=0.05, ang=0.15)
cut_x0 = M.box(-big, 0, -big, big, -big, big)   # прибрати x < 0 — видно переріз
X.export_glb([(n, s_.cut(cut_x0), mk) for n, s_, mk in [("frame_front", fr_f, "print"), ("frame_back", fr_b, "print"),
              ("silicone", sil, "silicone"), ("master", T["body_master"], "master"), ("plate", T["body_base_plate"], "mold"),
              ("stiff", T["finger_stiffener"], "print")]], f"{OUT}/mold_frame_section.glb", tol=0.05, ang=0.15)
# форма кришки в розрізі (пробкою донизу)
sil_lid = M.mold_silicone("lid")
lid_cast = M.S(P.lid(product=False, grind_allow=M.GA))
X.export_glb([(n, flip(s.cut(half)), mk) for n, s, mk in [("t_lid_sleeve", M.lid_sleeve(), "print"), ("t_lid_sil", sil_lid, "silicone"),
              ("t_lid_concrete", lid_cast, "lid")]], f"{OUT}/tooling_lid_section.glb", tol=0.04, ang=0.12)
# форма малої кришечки в розрізі (пробкою донизу) — лише якщо кришечка є (до v3.0)
if P.has_relief_lid():
    rx0, rx1, ry0, ry1, rz0, rz1 = M._lid_sleeve_dims("relief")
    rl_in = M._rrp(((rx0 + rx1) / 2, (ry0 + ry1) / 2), rx1 - rx0, ry1 - ry0, 6, rz0, rz1 - rz0)
    sil_rl = rl_in.cut(T["rlid_master"])
    rl_cast = M.S(P.relief_lid(product=False, grind_allow=M.GA))
    cyr = P._relief_xy()[1] * M.K
    cut_r = M.box(-big, big, cyr, big, -big, big)
    X.export_glb([(n, flip(s.cut(cut_r)), mk) for n, s, mk in [("t_rl_sleeve", T["rlid_sleeve"], "print"), ("t_rl_sil", sil_rl, "silicone"),
                  ("t_rl_concrete", rl_cast, "lid")]], f"{OUT}/tooling_rlid_section.glb", tol=0.03, ang=0.1)
else:
    # v3.0: оснащення в розрізі через плече Г-резервуара (сердечник із плечем, положення лиття)
    ya = (P.d["arm_y0"] + P.d["arm_y1"]) / 2 * M.K
    cut_a = M.box(-big, big, ya, big, -big, big)
    X.export_glb([(n, flip(s.cut(cut_a)), mk) for n, s, mk in items], f"{OUT}/tooling_arm_section.glb", tol=0.05, ang=0.15)

# купа стіків
if "--sim" in sys.argv:
    from stickbox import capacity_sim as C
    r = C.run_once(0, return_poses=True, n_max=220, tilt_x_deg=40.0 if (v(p.ARM_ON) and not v(p.FULL_LID_ON)) else 0.0)   # v3.0: нахил до плеча; v3.5 — не потрібен
    json.dump(r, open(f"{OUT}/sim_poses.json", "w"))
r = json.load(open(f"{OUT}/sim_poses.json"))
xc = P.d["cav_xc"]
sd, sl = v(p.STICK_D), v(p.STICK_L)
sticks = []
for k, ps in enumerate(r["poses"]):
    import mujoco
    R = np.zeros(9); mujoco.mju_quat2Mat(R, np.array(ps["quat"])); R = R.reshape(3, 3)
    ax = R[:, 2]
    c = np.array(ps["pos"]); c[0] += xc
    base = c - ax * sl / 2
    s = cq.Solid.makeCylinder(sd / 2, sl, Vector(*base), Vector(*ax))
    sticks.append(s)
comp = cq.Compound.makeCompound(sticks)
body = P.body(); lid = P.lid(); oring = P.oring()
RLID = P.relief_lid() if P.has_relief_lid() else None
RSEAL = P.relief_seal() if P.has_relief_lid() else None
NFC = P.nfc_tag() if v(p.NFC_ON) else None   # v3.3
nn = lambda L: [x for x in L if x[1] is not None]
cutf = M.box(-big, big, 0, big, -big, big)
X.export_glb(nn([("body_sec", body.cut(cutf), "body"), ("lid_sec", lid.cut(cutf), "lid"), ("oring_sec", oring.cut(cutf), "oring"),
              ("felt", P.felt_pad(), "liner"), ("rlid", RLID, "lid"), ("rseal", RSEAL, "oring"),
              ("logo_stick", P.logo_fill("GREY"), "liner"), ("logo_box", P.logo_fill("TEAL"), "oring"), ("device", P.device(), "device"), ("ctrl_led", P.device_controls()[0], "liner"), ("ctrl_btn", P.device_controls()[1], "liner"),
              ("stick_pile", comp, "stick")]), f"{OUT}/section_sticks.glb")
X.export_glb(nn([("body", body, "body"), ("lid", lid, "lid"), ("oring", oring, "oring"), ("felt", P.felt_pad(), "liner"),
              ("rlid", RLID, "lid"), ("rseal", RSEAL, "oring"), ("logo_stick", P.logo_fill("GREY"), "liner"),
              ("logo_box", P.logo_fill("TEAL"), "oring"), ("nfc_tag", NFC, "liner"), ("device", P.device(), "device"), ("ctrl_led", P.device_controls()[0], "liner"), ("ctrl_btn", P.device_controls()[1], "liner")]), f"{OUT}/assy.glb")
# v3.0: переріз через плече Г-резервуара (лишається задня частина, y > осі плеча) зі стіками
if v(p.ARM_ON):
    ya = (P.d["arm_y0"] + P.d["arm_y1"]) / 2
    cut_a = M.box(-big, big, -big, ya, -big, big)
    keep = [s for s in sticks if s.Center().y > ya - 4]
    X.export_glb([("body_seca", body.cut(cut_a), "body"), ("lid_seca", lid.cut(cut_a), "lid"), ("oring_seca", oring.cut(cut_a), "oring"),
                  ("stick_pile", cq.Compound.makeCompound(keep) if keep else comp, "stick")], f"{OUT}/section_arm_sticks.glb")
print("ok", len(sticks), "sticks")
