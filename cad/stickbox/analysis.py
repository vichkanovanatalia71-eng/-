"""
Інженерна перевірка геометрії STICKBOX 01 Monolith.

Що обчислюється (фактично, на B-Rep / сітці; без імітації):
  1. Об'єми, маси, центри мас деталей і збірки (OCC GProp)
  2. Валідність B-Rep, замкнутість (watertight) сіток STL
  3. Перетини між деталями збірки (булеве «спільне», мм³)
  4. Мінімальні зазори між парами деталей (BRepExtrema)
  5. Карта товщини стінок корпусу (ray casting по нормалях)
  6. Аналіз ухилів і піднутрень для напрямків виймання (сердечник / «палець» форми)
  7. Прохідність стіка крізь отвір (геометрична умова для циліндра)
  8. Стійкість від перекидання (кут, сила на верхівці девайса)
  9. Інженерні оцінки міцності (кромка фланця кришки при знятті)
"""
import json
import math
import numpy as np
import trimesh
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

from . import params as p
from .params import v
from . import parts as P
from .export import mesh_of

d = p.derived()


def mass_props(shape, rho):
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, g)
    c = g.CentreOfMass()
    vol = g.Mass()  # мм³
    return dict(volume_mm3=vol, volume_ml=vol / 1000, mass_kg=vol * 1e-9 * rho,
                com=[c.X(), c.Y(), c.Z()])


def min_distance(a, b):
    ext = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    ext.Perform()
    if not ext.IsDone():
        return None
    return ext.Value()


def common_volume(a, b):
    try:
        return a.intersect(b).Volume()
    except Exception:
        return float("nan")


# --------------------------------------------------------------------------
def wall_thickness(body_shape, n_samples=60000, seed=1):
    """Товщина в точці = відстань уздовж -нормалі до наступного перетину з поверхнею."""
    m = mesh_of(body_shape, tol=0.05, ang=0.15)
    m.merge_vertices()
    rng = np.random.default_rng(seed)
    pts, fid = trimesh.sample.sample_surface_even(m, n_samples, seed=seed) if hasattr(trimesh.sample, "sample_surface_even") else trimesh.sample.sample_surface(m, n_samples)
    nrm = m.face_normals[fid]
    origins = pts - nrm * 1e-3
    dirs = -nrm
    loc, idx_ray, idx_tri = m.ray.intersects_location(origins, dirs, multiple_hits=False)
    th = np.full(len(pts), np.nan)
    dist = np.linalg.norm(loc - origins[idx_ray], axis=1)
    th[idx_ray] = dist
    return m, pts, nrm, th


def classify_regions(pts, nrm):
    """Грубе маркування поверхонь корпусу за областями (для звіту)."""
    H = v(p.H)
    reg = np.full(len(pts), "outer", dtype=object)
    xc = d["cav_xc"]
    inside_cav = (np.abs(pts[:, 0] - xc) < v(p.CAV) / 2 + 3.2) & (np.abs(pts[:, 1]) < v(p.CAV) / 2 + 3.2) & (pts[:, 2] < d["z_ceil_c"] + 0.5)
    reg[inside_cav] = "cavity"
    pk = (np.abs(pts[:, 0] - d["pocket_cx"]) < d["pocket_x"] / 2 + 0.3) & (np.abs(pts[:, 1] - d["pocket_cy"]) < d["pocket_y"] / 2 + 0.3) & (pts[:, 2] > d["pocket_floor"] - 0.3)
    reg[pk] = "pocket"
    if v(p.SLOT_ON):
        sl = (np.abs(pts[:, 0] - d["pocket_cx"]) < v(p.SLOT_W) / 2 + 1.2) & (pts[:, 1] < -v(p.D) / 2 + v(p.T_FRONT_POCKET) + 0.6) & (pts[:, 2] > v(p.H) - v(p.SLOT_DEPTH) - 0.5)
        reg[sl] = "slot"
    fn = (np.hypot(pts[:, 0] - xc, pts[:, 1]) < v(p.FUNNEL_D) / 2 + 0.3) & (pts[:, 2] > d["z_ceil_c"] + v(p.FLARE_H) + 0.01)
    reg[fn] = "funnel"
    fl = (np.hypot(pts[:, 0] - xc, pts[:, 1]) < v(p.FLARE_D) / 2 + 1.0) & (pts[:, 2] > d["z_ceil_c"] - 0.3) & (pts[:, 2] <= d["z_ceil_c"] + v(p.FLARE_H) + 0.01)
    reg[fl] = "cavity"   # розтруб формує сердечник
    logo = (pts[:, 1] < -v(p.D) / 2 + v(p.LOGO_DEPTH) + 0.05) & (np.abs(pts[:, 2] - v(p.LOGO_Z)) < 6) & (np.abs(pts[:, 0]) < 30)
    reg[logo] = "logo"
    return reg


def draft_analysis(body_shape):
    """Кут ухилу кожного трикутника відносно напрямку виймання для своєї області."""
    m = mesh_of(body_shape, tol=0.03, ang=0.1)
    centers = m.triangles_center
    nrm = m.face_normals
    area = m.area_faces
    reg = classify_regions(centers, nrm)
    out = {}
    # сердечник виходить униз (-Z відносно корпусу): поверхні порожнини мають «дивитися» вниз
    # палець форми і воронка виходять угору (+Z): поверхні кишені/воронки «дивляться» вгору
    for name, pull in (("cavity", np.array([0, 0, -1.0])), ("pocket", np.array([0, 0, 1.0])),
                       ("funnel", np.array([0, 0, 1.0])), ("slot", np.array([0, -1.0, 0]))):
        msk = reg == name
        if not msk.any():
            continue
        cosang = nrm[msk] @ pull
        draft_deg = np.degrees(np.arcsin(np.clip(cosang, -1, 1)))
        a = area[msk]
        neg = draft_deg < -0.05
        zero = (draft_deg >= -0.05) & (draft_deg < 0.45)
        out[name] = dict(
            area_mm2=float(a.sum()),
            undercut_area_mm2=float(a[neg].sum()),
            near_zero_draft_area_mm2=float(a[zero].sum()),
            min_draft_deg=float(draft_deg.min()),
            draft_p05_deg=float(np.percentile(draft_deg, 5)),
        )
    return out, m, reg


def undercut_rays(body_shape):
    """Промені з поверхонь порожнини в напрямку виходу сердечника: перетин = піднутрення."""
    m = mesh_of(body_shape, tol=0.03, ang=0.1)
    m.merge_vertices()
    c = m.triangles_center
    n = m.face_normals
    reg = classify_regions(c, n)
    res = {}
    for name, pull in (("cavity", np.array([0, 0, -1.0])), ("pocket", np.array([0, 0, 1.0]))):
        msk = np.where(reg == name)[0]
        orig = c[msk] + n[msk] * 0.02
        dirs = np.tile(pull, (len(msk), 1))
        hit = m.ray.intersects_any(orig, dirs)
        res[name] = dict(faces=int(len(msk)), blocked_faces=int(hit.sum()),
                         blocked_area_mm2=float(m.area_faces[msk][hit].sum()))
    return res


# --------------------------------------------------------------------------
def stick_passage(hole_d=None, hole_len=None, stick_d=None):
    """Максимальний кут нахилу θ довгого циліндра Ø d у короткому каналі Ø D довжиною L
       (2D-оцінка у площині нахилу): d/cosθ + L·tanθ ≤ D."""
    D = hole_d or v(p.HOLE_D)
    L = hole_len if hole_len is not None else (v(p.H) - v(p.FUNNEL_DEPTH) - (d["z_ceil_c"] + v(p.FLARE_H)))
    out = []
    for sd in ([stick_d] if stick_d else [7.0, 7.2, 7.3, 7.42, 7.6, 7.8]):
        # розв'язок d cos θ + L sin θ = D
        if True:
            lo, hi = 0.0, math.radians(60)
            f = lambda t: sd / math.cos(t) + L * math.tan(t) - D
            if f(0) > 0:
                theta = -1.0
            else:
                for _ in range(80):
                    mid = (lo + hi) / 2
                    if f(mid) > 0:
                        hi = mid
                    else:
                        lo = mid
                theta = math.degrees(lo)
        out.append(dict(stick_d=sd, diametral_clearance=D - sd, max_tilt_deg=theta))
    return dict(hole_d=D, straight_len=L, cases=out)


def stability(assy_mass, com_z, device_mass, base_half_min):
    """Кут статичного перекидання та горизонтальна сила на верхівці девайса, що перекидає виріб."""
    ang = math.degrees(math.atan2(base_half_min, com_z))
    g = 9.81
    h_top = v(p.H) + v(p.DEV_PROTRUDE)
    F_tip = assy_mass * g * base_half_min / h_top
    return dict(tip_angle_deg=ang, force_at_device_top_N=F_tip, lever_height_mm=h_top)


def lid_hook_check(F=30.0):
    """Кромка фланця кришки під пальцем: консоль виліт = SHOULDER, ширина = зона пальця,
       товщина = FLANGE_T. σ = 6·M/(b·t²). Порівняння з міцністю бетону на розтяг при згині."""
    b = 16.0  # ширина контакту пальця, мм
    t = v(p.FLANGE_T)
    arm = v(p.SHOULDER) / 2 + v(p.LID_GAP)
    M = F * arm
    sigma = 6 * M / (b * t * t)
    return dict(F_N=F, contact_width_mm=b, arm_mm=arm, sigma_MPa=sigma)


def run(write_to=None):
    rho_c = v(p.RHO_CONCRETE)
    rho_s = v(p.RHO_SILICONE)
    body = P.body()
    lid = P.lid()
    oring = P.oring()
    liner = P.liner()
    dev = P.device()
    R = {}
    R["mass"] = {
        "body": mass_props(body, rho_c),
        "lid": mass_props(lid, rho_c),
        "oring": mass_props(oring, rho_s),
        "liner": mass_props(liner, rho_s),
        "device_dummy_volume_ml": dev.Volume() / 1000,
    }
    parts_m = [(R["mass"][k]["mass_kg"], np.array(R["mass"][k]["com"])) for k in ("body", "lid", "oring", "liner")]
    m_tot = sum(m for m, _ in parts_m)
    com = sum(m * c for m, c in parts_m) / m_tot
    dev_c = np.array(mass_props(dev, 1)["com"])
    m_dev = v(p.DEV_MASS)
    com_dev = (com * m_tot + dev_c * m_dev) / (m_tot + m_dev)
    R["assembly"] = dict(mass_kg=m_tot, com=com.tolist(), mass_with_device_kg=m_tot + m_dev,
                         com_with_device=com_dev.tolist())
    R["validity"] = {k: s.isValid() for k, s in (("body", body), ("lid", lid), ("oring", oring), ("liner", liner))}

    shapes = dict(body=body, lid=lid, oring=oring, liner=liner, device=dev)
    pairs = [("body", "lid"), ("body", "oring"), ("lid", "oring"), ("body", "liner"), ("liner", "device"),
             ("body", "device"), ("lid", "liner")]
    R["interference_mm3"] = {f"{a}-{b}": common_volume(shapes[a], shapes[b]) for a, b in pairs}
    R["min_clearance_mm"] = {f"{a}-{b}": min_distance(shapes[a], shapes[b]) for a, b in pairs}

    # порожнина: «повітряний» об'єм над пробкою кришки
    import cadquery as cq
    xc = d["cav_xc"]
    env = P.prism_rrect(v(p.CAV) + 8, v(p.CAV) + 8, 18, d["z_plug_top"], d["z_ceil_c"] + 1, cx=xc)
    air = env.cut(body).cut(lid)
    # залишити лише частину всередині порожнини (обрізати шматки ззовні)
    sols = sorted(air.Solids(), key=lambda s: -s.Volume())
    cav_air = sols[0]
    R["cavity"] = dict(net_volume_ml=cav_air.Volume() / 1000,
                       stick_volume_ml=math.pi * (v(p.STICK_D) / 2) ** 2 * v(p.STICK_L) / 1000)
    R["cavity"]["sticks_at_packing"] = {str(phi): R["cavity"]["net_volume_ml"] * phi / R["cavity"]["stick_volume_ml"]
                                        for phi in (0.40, 0.50, 0.60)}

    # товщини стінок
    m, pts, nrm, th = wall_thickness(body)
    reg = classify_regions(pts, nrm)
    ok = ~np.isnan(th)
    wt = {}
    for name in ("outer", "cavity", "pocket", "funnel", "slot", "logo"):
        msk = ok & (reg == name)
        if msk.any():
            wt[name] = dict(min=float(np.nanmin(th[msk])), p01=float(np.percentile(th[msk], 1)),
                            p05=float(np.percentile(th[msk], 5)), median=float(np.median(th[msk])))
    R["wall_thickness_mm"] = wt
    np.savez_compressed("/tmp/wt_samples.npz", pts=pts, th=th, reg=reg.astype(str))

    dr, _, _ = draft_analysis(body)
    R["draft"] = dr
    R["undercut_rays"] = undercut_rays(body)
    R["stick_passage"] = stick_passage()
    base_half_min = v(p.D) / 2 - 1.0  # опорний контур (з урахуванням притуплення)
    R["stability"] = stability(R["assembly"]["mass_with_device_kg"], R["assembly"]["com_with_device"][2],
                               m_dev, min(base_half_min, v(p.W) / 2 - abs(R["assembly"]["com_with_device"][0])))
    R["lid_hook"] = lid_hook_check()
    R["derived"] = d
    if write_to:
        with open(write_to, "w") as f:
            json.dump(R, f, indent=2, ensure_ascii=False, default=float)
    return R


if __name__ == "__main__":
    import sys
    r = run(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps({k: r[k] for k in r if k != "derived"}, indent=1, ensure_ascii=False, default=float))
