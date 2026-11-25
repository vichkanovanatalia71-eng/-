"""Столи для друку оснащення (3MF для слайсера, як Bambu Studio / OrcaSlicer): деталі вже зорієнтовані для друку
й розкладені на столі 256 × 256 мм (Bambu Lab X1 / P1 / A1). Один файл = один стіл.

Запуск: python make_tooling_plates.py   (після build_all.py — бере tooling/stl/*.stl, уже повернуті «як друкувати»)
Результат: tooling/print/STICKBOX_01_<rev>_P1…P5_*.3mf, R1_resin_*.3mf і README.md
"""
import json
import os

import numpy as np
import trimesh

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "tooling", "stl")
OUT = os.path.join(ROOT, "tooling", "print")
REV = "v3.7.1"
BED = 256.0          # стіл Bambu Lab X1 / P1 / A1
MARGIN = 6.0         # від краю столу
GAP = 10.0           # між деталями

# стіл: (код, назва файлу, підпис, [(деталь, поворот навколо Z, °)], матеріал)
PLATES = [
    ("P1", "body_frame_T02a_T02b", "Каркас форми корпусу: половини T02a + T02b (друк стоячи, нескошеним обручем на столі)",
     [("T02a_body_frame_front", 0), ("T02b_body_frame_back", 0)], "PETG"),
    ("P2", "body_plate_T03_stiffener_T04", "Плита заливки силікону T03 + ребро «пальця» T04",
     [("T03_body_base_plate", 0), ("T04_finger_stiffener", 0)], "PETG"),
    ("P3", "core_spine_bridge_T05_holder_T17", "Хребет із мостом сердечника T05 + тримач ребра T17",
     [("T05_core_spine_bridge", 0), ("T17_stiffener_holder", 0)], "PETG"),
    ("P4", "lid_frame_T09a_T09b", "Каркас форми кришки: половини T09a + T09b",
     [("T09a_lid_frame_front", 0), ("T09b_lid_frame_back", 0)], "PETG"),
    ("P5", "lid_plate_T10", "Плита заливки силікону форми кришки T10",
     [("T10_lid_base_plate", 0)], "PETG"),
]
RESIN = [
    ("R1", "masters_T01_T08_gauges_T13_T14", "Майстер-моделі корпусу T01 і кришки T08 + калібри T13, T14",
     [("T01_body_master", 0), ("T08_lid_master", 0), ("T13_gauge_hole_go_7p90", 0), ("T14_gauge_stick_heets", 0)], "смола"),
    ("R2", "core_mold_T06", "Форма силіконової чашки сердечника T06",
     [("T06_core_mold", 0)], "смола"),
]


def load(name, rot):
    m = trimesh.load(os.path.join(SRC, name + ".stl"), force="mesh")
    m.merge_vertices()
    if rot:
        m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rot), [0, 0, 1]))
    m.apply_translation(-m.bounds[0])           # мінімум у (0, 0, 0): лежить на столі
    return m


def pack(meshes, bed):
    """Проста розкладка: у ряд уздовж X, якщо не влазить — новий ряд по Y; усе разом — по центру столу."""
    placed, x, y, row_h = [], 0.0, 0.0, 0.0
    for m in meshes:
        w, d = m.extents[0], m.extents[1]
        if placed and x + w > bed - 2 * MARGIN:
            x, y, row_h = 0.0, y + row_h + GAP, 0.0
        placed.append((m, x, y))
        x += w + GAP
        row_h = max(row_h, d)
    xs = max(px + m.extents[0] for m, px, _ in placed)
    ys = max(py + m.extents[1] for m, _, py in placed)
    ox, oy = (bed - xs) / 2, (bed - ys) / 2
    out = []
    for m, px, py in placed:
        m = m.copy()
        m.apply_translation([ox + px, oy + py, 0])
        out.append(m)
    fits = xs <= bed - 2 * MARGIN + 1e-6 and ys <= bed - 2 * MARGIN + 1e-6
    return out, (xs, ys), fits


def build(code, slug, title, items, material, bed=BED):
    meshes = [load(n, r) for n, r in items]
    # найбільша деталь — першою (стабільніша розкладка)
    order = sorted(range(len(meshes)), key=lambda i: -meshes[i].extents[0] * meshes[i].extents[1])
    meshes_o = [meshes[i] for i in order]
    names_o = [items[i][0] for i in order]
    placed, size, fits = pack(meshes_o, bed)
    scene = trimesh.Scene()
    for n, m in zip(names_o, placed):
        scene.add_geometry(m, node_name=n, geom_name=n)
    fn = f"STICKBOX_01_{REV}_{code}_{slug}.3mf"
    path = os.path.join(OUT, fn)
    scene.export(path)
    back = trimesh.load(path)
    n_obj = len(back.geometry) if isinstance(back, trimesh.Scene) else 1
    hmax = max(m.extents[2] for m in placed)
    info = dict(file=fn, title=title, material=material, parts=names_o, objects_in_file=n_obj,
                layout_mm=[round(float(size[0]), 1), round(float(size[1]), 1)], max_height_mm=round(float(hmax), 1), fits_256=bool(fits),
                watertight=bool(all(m.is_watertight for m in placed)),
                size_mb=round(os.path.getsize(path) / 1e6, 2))
    return info


def main():
    os.makedirs(OUT, exist_ok=True)
    res = [build(*p) for p in PLATES] + [build(*p) for p in RESIN]
    for r in res:
        print(f"{r['file']}: {r['objects_in_file']} об'єкти, розкладка {r['layout_mm'][0]} × {r['layout_mm'][1]} мм, "
              f"висота {r['max_height_mm']} мм, вміщується в 256: {r['fits_256']}, watertight {r['watertight']}, {r['size_mb']} МБ")
    json.dump(res, open(os.path.join(OUT, "plates.json"), "w"), indent=1, ensure_ascii=False)
    write_readme(res)


def write_readme(res):
    L = [f"# Столи для друку оснащення ({REV})", "",
         "Файли 3MF для слайсера (Bambu Studio, OrcaSlicer, PrusaSlicer): деталі вже повернуті так, як їх друкувати, і "
         "розкладені на столі **256 × 256 мм** (Bambu Lab X1 / P1 / A1). Один файл — один стіл. Каркаси 184 мм "
         "у стіл 180 × 180 (A1 mini) не вміщуються.", "",
         "## FDM — PETG", "",
         "| Файл | Що на столі | Розкладка, мм | Висота, мм |", "|---|---|---|---|"]
    for r in res:
        if r["material"] == "PETG":
            L.append(f"| `{r['file']}` | {r['title']} | {r['layout_mm'][0]} × {r['layout_mm'][1]} | {r['max_height_mm']} |")
    L += ["", "Налаштування (як у `docs/14` §4): 4–5 периметрів, заповнення 30–40 %; вушка, фланці й обручі — суцільні "
          "(модифікатор або більше периметрів). Каркаси друкуються стоячи без підтримок: обручі знизу скошені під 45°. "
          "Внутрішню поверхню каркасів із ключами — зашліфувати P240 і покрити лаком.", "",
          "## Смола — SLA / MSLA", "",
          "| Файл | Що на столі | Розкладка, мм | Висота, мм |", "|---|---|---|---|"]
    for r in res:
        if r["material"] == "смола":
            L.append(f"| `{r['file']}` | {r['title']} | {r['layout_mm'][0]} × {r['layout_mm'][1]} | {r['max_height_mm']} |")
    L += ["", "Майстри й форма сердечника формують поверхні виробу — їх друкують смолою і шліфують до гладкості. Стіл смоляних "
          "принтерів менший за 256 мм, тож у слайсері смоли деталі R1 розставляють за розміром свого столу (або друкують окремо: "
          "`../stl/`). Орієнтацію й підтримки для смоли задає слайсер смоли.", "",
          "Повний склад оснащення, розміри і призначення — `docs/04_mold_making.md`, `docs/13_mold_maker_brief.md`, "
          "розбірні каркаси — `docs/14_mold_frame.md`. Силіконові форми (T15, T16) і чашка сердечника (T07) — не друкуються, "
          "їх відливають у цьому оснащенні.", ""]
    open(os.path.join(OUT, "README.md"), "w", encoding="utf-8").write("\n".join(L))


if __name__ == "__main__":
    main()
