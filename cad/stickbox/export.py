"""Експорт: STEP (окремі деталі та збірка з назвами/кольорами), STL, 3MF, GLB."""
import os
import numpy as np
import cadquery as cq
import trimesh
from trimesh.visual.material import PBRMaterial

# Кольори/матеріали для GLB (sRGB 0..255) — CMF базового варіанту «Sand Speckle»
MATERIALS = {
    "body": ((214, 200, 180), 0.0, 0.85),     # декоративний бетон, бежевий
    "lid": ((214, 200, 180), 0.0, 0.85),
    "oring": ((32, 150, 128), 0.0, 0.55),     # силікон, бірюзовий акцент
    "liner": ((44, 46, 48), 0.0, 0.7),        # силікон, графіт
    "device": ((150, 112, 80), 0.9, 0.35),    # макет девайса (бронза)
    "stick": ((245, 245, 240), 0.0, 0.6),
    "master": ((235, 235, 235), 0.0, 0.6),
    "mold": ((120, 170, 200), 0.0, 0.6),
    "silicone": ((90, 175, 160), 0.0, 0.6),
    "print": ((240, 160, 60), 0.0, 0.6),
}


def mesh_of(shape, tol=0.02, ang=0.08):
    verts, tris = shape.tessellate(tol, ang)
    v = np.array([(p.x, p.y, p.z) for p in verts], dtype=np.float64)
    f = np.array(tris, dtype=np.int64)
    return trimesh.Trimesh(vertices=v, faces=f, process=False)


def export_step(shape, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cq.exporters.export(cq.Workplane().add(shape), path, exportType="STEP")


def export_stl(shape, path, tol=0.01, ang=0.05):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cq.exporters.export(cq.Workplane().add(shape), path, exportType="STL", tolerance=tol, angularTolerance=ang)


def export_3mf(shape, path, tol=0.01, ang=0.05):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cq.exporters.export(cq.Workplane().add(shape), path, exportType="3MF", tolerance=tol, angularTolerance=ang)


def export_glb(named_shapes, path, tol=0.03, ang=0.1):
    """named_shapes: list of (name, shape, material_key). Координати: мм, Z-up → glTF Y-up."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scene = trimesh.Scene()
    rot = trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])  # Z-up → Y-up
    for name, shape, mk in named_shapes:
        m = mesh_of(shape, tol, ang)
        m.apply_transform(rot)
        rgb, metal, rough = MATERIALS.get(mk, MATERIALS["master"])
        m.visual = trimesh.visual.TextureVisuals(material=PBRMaterial(
            name=mk, baseColorFactor=[*(c / 255 for c in rgb), 1.0],
            metallicFactor=metal, roughnessFactor=rough, doubleSided=False))
        scene.add_geometry(m, node_name=name, geom_name=name)
    scene.export(path)


def export_assembly_step(named_shapes, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    assy = cq.Assembly(name="STICKBOX_01_Monolith")
    for name, shape, mk in named_shapes:
        rgb, _, _ = MATERIALS.get(mk, MATERIALS["master"])
        assy.add(shape, name=name, color=cq.Color(*(c / 255 for c in rgb)))
    assy.save(path, exportType="STEP")
