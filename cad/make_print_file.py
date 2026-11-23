"""Файл для друку (SLA / FDM): лише корпус і кришка, поруч на столі, без девайса, шнура, масок фарби й NFC-мітки.

Запуск: python make_print_file.py
Результат (exports/print/): STICKBOX_01_v3.7_body_lid.3mf (2 окремі об'єкти), .stl (обидві деталі), .step.
Заглиблення напису й знака NFC лишаються на корпусі (це геометрія виробу); фарбують їх після друку.
"""
import os

import numpy as np
import trimesh
from cadquery import Vector

from stickbox import params as p, parts as P
from stickbox import export as X

REV = "v3.7"
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "exports", "print"))
GAP = 15.0   # відстань між деталями на столі, мм


def main():
    os.makedirs(OUT, exist_ok=True)
    body, lid = P.body(), P.lid()
    bb, lb = body.BoundingBox(), lid.BoundingBox()
    # корпус — як стоїть (низ на столі), кришка — поруч праворуч, низом на столі
    body_p = body.translate(Vector(-bb.xmin, -bb.ymin, -bb.zmin))
    lid_p = lid.translate(Vector(bb.xlen + GAP - lb.xmin, -lb.ymin, -lb.zmin))
    parts = [("STICKBOX_body", body_p), ("STICKBOX_lid", lid_p)]
    base = os.path.join(OUT, f"STICKBOX_01_{REV}_body_lid")
    scene = trimesh.Scene()
    meshes = []
    for name, s in parts:
        m = X.mesh_of(s, 0.02, 0.08)
        m.merge_vertices()
        assert m.is_watertight, f"{name}: сітка не замкнена"
        meshes.append(m)
        scene.add_geometry(m, node_name=name, geom_name=name)
    scene.export(base + ".3mf")
    trimesh.util.concatenate(meshes).export(base + ".stl")
    X.export_assembly_step([(n, s, "body") for n, s in parts], base + ".step")
    back = trimesh.load(base + ".3mf")
    names = list(back.geometry.keys()) if isinstance(back, trimesh.Scene) else ["(одна сітка)"]
    for (name, s), m in zip(parts, meshes):
        b = s.BoundingBox()
        print(f"{name}: {s.Volume() / 1000:.1f} мл, {b.xlen:.1f} × {b.ylen:.1f} × {b.zlen:.1f} мм, "
              f"{len(m.faces)} трикутників, watertight={m.is_watertight}")
    print("3mf objects:", names)
    for ext in (".3mf", ".stl", ".step"):
        print(os.path.relpath(base + ext, os.path.dirname(OUT)), f"{os.path.getsize(base + ext) / 1e6:.1f} МБ")


if __name__ == "__main__":
    main()
