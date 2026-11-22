"""
Повна збірка пакета STICKBOX 01 Monolith:
  python build_all.py            — експорт усіх деталей, оснащення, GLB, аналізу
Результати: ../exports/{step,stl,3mf,glb}, ../tooling/{step,stl,3mf}, ../reports
"""
import json
import os
import sys
import time

import cadquery as cq
from cadquery import Vector

sys.path.insert(0, os.path.dirname(__file__))
from stickbox import params as p, parts as P, molds as M, export as X, analysis as A  # noqa: E402
from stickbox.params import v  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXP = os.path.join(ROOT, "exports")
TOOL = os.path.join(ROOT, "tooling")
REP = os.path.join(ROOT, "reports")
SCR = os.environ.get("RENDER_GLB_DIR", os.path.join(ROOT, "cad", "render", "glb"))


def flip(shape):
    return shape.rotate(Vector(0, 0, 0), Vector(1, 0, 0), 180)


def on_bed(shape):
    bb = shape.BoundingBox()
    return shape.translate(Vector(-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))


def main():
    t0 = time.time()
    os.makedirs(REP, exist_ok=True)
    os.makedirs(SCR, exist_ok=True)

    # ---------------- виріб ----------------
    body = P.body()
    lid = P.lid()
    oring = P.oring()
    oring_free = P.oring_free()
    felt = P.felt_pad()
    rlid = P.relief_lid()
    rseal = P.relief_seal()
    logo_s = P.logo_fill("GREY")   # STICK + стік-i знака → RAL 7016
    logo_b = P.logo_fill("TEAL")   # BOX + хвиля знака → бірюзовий
    dev = P.device()
    prod = [("01_body_concrete", body, "body"), ("02_lid_concrete", lid, "lid"),
            ("03_seal_silicone_sponge_cord_D4_installed", oring, "oring"), ("04_felt_pad_device_pocket", felt, "liner"),
            ("05_relief_lid_concrete", rlid, "lid"), ("06_relief_seal_sponge_cord_D3_installed", rseal, "oring"),
            ("07_paint_mask_GREY_RAL7016_STICK_and_mark_bar", logo_s, "liner"), ("08_paint_mask_TEAL_BOX_and_mark_swoosh", logo_b, "oring")]
    for name, sh, _ in prod:
        X.export_step(sh, f"{EXP}/step/{name}.step")
        X.export_stl(sh, f"{EXP}/stl/{name}.stl")
        X.export_3mf(sh, f"{EXP}/3mf/{name}.3mf")
    X.export_step(oring_free, f"{EXP}/step/03b_seal_sponge_cord_D4_free_loop.step")
    X.export_step(dev, f"{EXP}/step/90_ref_IQOS_ILUMA_ONE_envelope.step")
    assy = prod + [("90_ref_ILUMA_ONE_envelope", dev, "device")]
    X.export_assembly_step(assy, f"{EXP}/step/00_STICKBOX_01_Monolith_assembly.step")
    X.export_glb([("body", body, "body"), ("lid", lid, "lid"), ("oring", oring, "oring"), ("felt", felt, "liner"),
                  ("rlid", rlid, "lid"), ("rseal", rseal, "oring"), ("logo_stick", logo_s, "liner"), ("logo_box", logo_b, "oring"),
                  ("device", dev, "device")], f"{EXP}/glb/STICKBOX_01_Monolith_assembly.glb")
    print("product exported", round(time.time() - t0, 1))

    # ---------------- оснащення ----------------
    T = M.all_tooling()
    print_orient = {
        "body_master": lambda s: s, "body_sleeve": lambda s: s, "body_base_plate": lambda s: s,
        "finger_stiffener": flip, "stiffener_holder": flip, "core_silicone": lambda s: s, "core_spine_bridge": lambda s: s,
        "core_mold": flip, "lid_master": lambda s: s, "lid_sleeve": lambda s: s, "lid_base_plate": lambda s: s,
        "rlid_master": lambda s: s, "rlid_sleeve": lambda s: s, "rlid_base_plate": lambda s: s,
        "gauge_hole_go_7p90": lambda s: s, "gauge_stick_heets": lambda s: s,
    }
    numbering = {
        "body_master": "T01", "body_sleeve": "T02", "body_base_plate": "T03", "finger_stiffener": "T04",
        "core_spine_bridge": "T05", "core_mold": "T06", "core_silicone": "T07_ref_cast_part",
        "lid_master": "T08", "lid_sleeve": "T09", "lid_base_plate": "T10",
        "rlid_master": "T18", "rlid_sleeve": "T19", "rlid_base_plate": "T20",
        "gauge_hole_go_7p90": "T13", "gauge_stick_heets": "T14", "stiffener_holder": "T17",
    }
    tool_info = {}
    for k, sh in T.items():
        name = f"{numbering[k]}_{k}"
        X.export_step(sh, f"{TOOL}/step/{name}.step")           # координати збірки (базування)
        pr = on_bed(print_orient[k](sh))
        X.export_stl(pr, f"{TOOL}/stl/{name}.stl")
        X.export_3mf(pr, f"{TOOL}/3mf/{name}.3mf")
        bb = pr.BoundingBox()
        tool_info[name] = dict(valid=sh.isValid(), volume_ml=sh.Volume() / 1000,
                               print_bbox_mm=[round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1)])
    # силікон зовнішньої форми та форми кришки (об'єм заливки)
    ix0, ix1, iy0, iy1, z0, z1 = M._sleeve_dims()
    sleeve_in = M._rrp(((ix0 + ix1) / 2, (iy0 + iy1) / 2), ix1 - ix0, iy1 - iy0, 6, z0, z1 - z0)
    sil_body = sleeve_in.cut(T["body_master"]).cut(T["finger_stiffener"])
    lx0, lx1, ly0, ly1, lz0, lz1 = M._lid_sleeve_dims()
    lid_in = M._rrp(((lx0 + lx1) / 2, (ly0 + ly1) / 2), lx1 - lx0, ly1 - ly0, 6, lz0, lz1 - lz0)
    sil_lid = lid_in.cut(T["lid_master"])
    X.export_step(sil_body, f"{TOOL}/step/T15_ref_outer_silicone_mold_body.step")
    X.export_step(sil_lid, f"{TOOL}/step/T16_ref_silicone_mold_lid.step")
    rx0, rx1, ry0, ry1, rz0, rz1 = M._lid_sleeve_dims("relief")
    rl_in = M._rrp(((rx0 + rx1) / 2, (ry0 + ry1) / 2), rx1 - rx0, ry1 - ry0, 6, rz0, rz1 - rz0)
    sil_rlid = rl_in.cut(T["rlid_master"])
    rho_s = v(p.RHO_SILICONE)
    silicone = {
        "outer_mold_body_ml": sil_body.Volume() / 1000,
        "core_cup_ml": T["core_silicone"].Volume() / 1000,
        "lid_mold_ml": sil_lid.Volume() / 1000,
        "relief_lid_mold_ml": sil_rlid.Volume() / 1000,
    }
    silicone["outer_mold_body_kg"] = silicone["outer_mold_body_ml"] * rho_s / 1e6
    silicone["core_cup_kg"] = silicone["core_cup_ml"] * rho_s / 1e6
    silicone["lid_mold_kg"] = silicone["lid_mold_ml"] * rho_s / 1e6
    silicone["relief_lid_mold_kg"] = silicone["relief_lid_mold_ml"] * rho_s / 1e6
    print("tooling exported", round(time.time() - t0, 1))

    # GLB для рендерів: оснащення в базуванні лиття
    X.export_glb([("t_sleeve", T["body_sleeve"], "print"), ("t_silicone", sil_body, "silicone"),
                  ("t_core", T["core_silicone"], "silicone"), ("t_bridge", T["core_spine_bridge"], "print"),
                  ("t_stiff", T["finger_stiffener"], "print"), ("t_master", T["body_master"], "master")],
                 f"{SCR}/tooling_body.glb", tol=0.05, ang=0.15)
    X.export_glb([("t_lid_sleeve", T["lid_sleeve"], "print"), ("t_lid_sil", sil_lid, "silicone"),
                  ("t_lid_master", T["lid_master"], "master")], f"{SCR}/tooling_lid.glb", tol=0.05, ang=0.15)

    # перерізи для рендерів / креслень
    big = 400
    cut_y = M.box(-big, big, 0, big, -big, big)                       # переріз по осі воронки (y = 0)
    cut_x = M.box(-big, big, -big, big, -big, big).cut(M.box(d_x := P.d["pocket_cx"], big, -big, big, -big, big))
    sec_parts = [("body_sec", body.cut(cut_y), "body"), ("lid_sec", lid.cut(cut_y), "lid"),
                 ("oring_sec", oring.cut(cut_y), "oring")]
    X.export_glb(sec_parts, f"{SCR}/section_y0.glb")
    cut_p = M.box(-big, big, P.d["pocket_cy"], big, -big, big)
    X.export_glb([("body_secp", body.cut(cut_p), "body"), ("lid_secp", lid.cut(cut_p), "lid"),
                  ("felt_secp", felt.cut(cut_p), "liner"), ("device_secp", dev.cut(cut_p), "device"),
                  ("rlid_secp", rlid.cut(cut_p), "lid"), ("rseal_secp", rseal.cut(cut_p), "oring"),
                  ("oring_secp", oring.cut(cut_p), "oring")], f"{SCR}/section_pocket.glb")
    X.export_glb([("body", body, "body"), ("lid", lid, "lid"), ("oring", oring, "oring"), ("felt", felt, "liner"),
                  ("rlid", rlid, "lid"), ("rseal", rseal, "oring"), ("logo_stick", logo_s, "liner"), ("logo_box", logo_b, "oring"),
                  ("device", dev, "device")], f"{SCR}/assy.glb")
    # купа стіків у перерізі (з результатів симуляції, якщо є)
    print("glb exported", round(time.time() - t0, 1))

    # ---------------- аналіз ----------------
    R = A.run(f"{REP}/analysis.json")
    R["tooling"] = tool_info
    R["silicone"] = silicone
    with open(f"{REP}/analysis.json", "w") as f:
        json.dump(R, f, indent=2, ensure_ascii=False, default=float)
    with open(f"{REP}/parameters.json", "w") as f:
        json.dump({k: dict(value=val, status=st, note=nt) for k, val, st, nt in p.table()}, f, indent=2, ensure_ascii=False)
    print("analysis done", round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
