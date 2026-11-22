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
ix0, ix1, iy0, iy1, z0, z1 = M._sleeve_dims()
sleeve_in = M._rrp(((ix0 + ix1) / 2, (iy0 + iy1) / 2), ix1 - ix0, iy1 - iy0, 6, z0, z1 - z0)
sil = sleeve_in.cut(T["body_master"]).cut(T["finger_stiffener"])
casting = M.S(P.body(product=False, height_extra=M.GA))
items = [("t_sleeve", T["body_sleeve"], "print"), ("t_silicone", sil, "silicone"),
         ("t_core", T["core_silicone"], "silicone"), ("t_bridge", T["core_spine_bridge"], "print"),
         ("t_stiff", T["finger_stiffener"], "print"), ("t_concrete", casting, "body")]
# положення лиття: догори дном; переріз по y=0
sec = [(n, flip(s.cut(half)), mk) for n, s, mk in items]
X.export_glb(sec, f"{OUT}/tooling_body_section.glb", tol=0.05, ang=0.15)
# вибухова схема оснащення (повні тіла, положення лиття)
X.export_glb([(n, flip(s), mk) for n, s, mk in items if n != "t_concrete"] + [("t_master", flip(T["body_master"]), "master")],
             f"{OUT}/tooling_body_full.glb", tol=0.05, ang=0.15)
# форма кришки в розрізі (пробкою донизу)
lx0, lx1, ly0, ly1, lz0, lz1 = M._lid_sleeve_dims()
lid_in = M._rrp(((lx0 + lx1) / 2, (ly0 + ly1) / 2), lx1 - lx0, ly1 - ly0, 6, lz0, lz1 - lz0)
sil_lid = lid_in.cut(T["lid_master"])
lid_cast = M.S(P.lid(product=False, grind_allow=M.GA))
X.export_glb([(n, flip(s.cut(half)), mk) for n, s, mk in [("t_lid_sleeve", T["lid_sleeve"], "print"), ("t_lid_sil", sil_lid, "silicone"),
              ("t_lid_concrete", lid_cast, "lid")]], f"{OUT}/tooling_lid_section.glb", tol=0.04, ang=0.12)
# форма вставки в розрізі
cup, core = M.liner_mold()
cut_l = M.box(-big, big, P.d["pocket_cy"], big, -big, big)
X.export_glb([("t_cup", cup.cut(cut_l), "print"), ("t_lcore", core.cut(cut_l), "print_grey"), ("liner_cast", P.liner().cut(cut_l), "liner")],
             f"{OUT}/tooling_liner_section.glb", tol=0.03, ang=0.1)

# купа стіків
if "--sim" in sys.argv:
    from stickbox import capacity_sim as C
    r = C.run_once(0, return_poses=True)
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
cutf = M.box(-big, big, 0, big, -big, big)
X.export_glb([("body_sec", body.cut(cutf), "body"), ("lid_sec", lid.cut(cutf), "lid"), ("oring_sec", oring.cut(cutf), "oring"),
              ("liner", P.liner(), "liner"), ("device", P.device(), "device"),
              ("stick_pile", comp, "stick")], f"{OUT}/section_sticks.glb")
X.export_glb([("body", body, "body"), ("lid", lid, "lid"), ("oring", oring, "oring"), ("liner", P.liner(), "liner"),
              ("device", P.device(), "device")], f"{OUT}/assy.glb")
print("ok", len(sticks), "sticks")
