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
    if v(p.ARM_ON):      # v3.0: плече Г-резервуара — сердечник виходить уздовж рампи (2 етапи)
        arm = ((pts[:, 0] > d["cav_x1"] - 1.5) & (pts[:, 0] < d["arm_x1"] + 1.0) & (pts[:, 1] > d["arm_y0"] - 1.0) & (pts[:, 1] < d["arm_y1"] + 1.0)
               & (pts[:, 2] > d["arm_sill_z"] - 1.0) & (pts[:, 2] < d["z_ceil_c"] + 0.5))
        # + заокруглений кут колонки (y до arm_y0 − R) і пласка ділянка порогу в куті R16 (виходять разом із плечем)
        corner = ((pts[:, 0] > d["cav_x1"] - 1.5) & (pts[:, 0] < d["cav_x1"] + v(p.ARM_CORNER_R) + 1.0)
                  & (pts[:, 1] > d["arm_y0"] - v(p.ARM_CORNER_R) - 1.0) & (pts[:, 2] > d["arm_sill_z"] - 1.0) & (pts[:, 2] < d["z_ceil_c"]))
        shelf = ((np.abs(pts[:, 2] - d["arm_sill_z"]) < 0.6) & (pts[:, 1] > d["cav_y1"] - v(p.R_CAV) - 0.5) & (pts[:, 0] > d["cav_x1"] - v(p.R_CAV) - 0.5))
        # стовп над «серпиком» порогу: зовні дуги R16 основної порожнини, вище порогу (квадратний кут плеча)
        tn_ = math.tan(math.radians(v(p.DRAFT_CAV)))
        ccx, ccy = d["cav_x1"] - v(p.R_CAV), d["cav_y1"] - v(p.R_CAV)
        rc = v(p.R_CAV) - (d["arm_sill_z"] - d["z_reb"]) * tn_
        cres = ((pts[:, 0] > ccx) & (pts[:, 0] < d["arm_x1"] + 1.0) & (pts[:, 1] > ccy) & (pts[:, 1] < d["arm_y1"] + 1.0)
                & (np.hypot(pts[:, 0] - ccx, pts[:, 1] - ccy) > rc - 0.4)
                & (pts[:, 2] > d["arm_sill_z"] - v(p.ARM_SILL_R) - 0.6) & (pts[:, 2] < d["z_ceil_c"]))
        sillz = ((pts[:, 2] > d["arm_sill_z"] - v(p.ARM_SILL_R) - 0.6) & (pts[:, 2] < d["arm_sill_z"] + 0.6)
                 & (pts[:, 0] > d["cav_x1"] - v(p.R_CAV) - 0.5) & (pts[:, 1] > d["arm_y0"] - 1.0))
        reg[(arm | corner | shelf | cres | sillz) & (reg != "pocket")] = "arm"
    logo = (pts[:, 1] < -v(p.D) / 2 + v(p.LOGO_DEPTH) + 0.05) & (np.abs(pts[:, 2] - v(p.LOGO_Z)) < 6) & (np.abs(pts[:, 0]) < 30)
    reg[logo] = "logo"
    if v(p.MARK_ON):
        mk = (pts[:, 1] < -v(p.D) / 2 + v(p.LOGO_DEPTH) + 0.05) & (np.abs(pts[:, 2] - v(p.MARK_Z)) < v(p.MARK_H) / 2 + 1) & (np.abs(pts[:, 0] - v(p.MARK_X)) < 20)
        reg[mk] = "logo"
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
                       ("funnel", np.array([0, 0, 1.0])), ("slot", np.array([0, -1.0, 0])), ("arm", arm_dir())):
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
    if v(p.ARM_ON):
        # етап 1: плече сердечника ковзає вздовж рампи, доки кожна точка не опиниться над основною частиною (x < cav_x1 − 1);
        # етап 2 — униз (−Z) через отвір, як основна частина. Піднутрення = перетин променя раніше, ніж точка вийде з плеча.
        msk = np.where(reg == "arm")[0]
        dvec = arm_dir()
        orig = c[msk] + n[msk] * 0.02
        # етап 1 — до лінії початку рампи (далі низ плеча ковзає горизонтально по порогу, потім униз)
        xs_eff = d["cav_x1"] - (d["arm_sill_z"] - d["z_reb"]) * math.tan(math.radians(v(p.DRAFT_CAV))) + 0.3
        need = np.maximum(0.0, (orig[:, 0] - xs_eff) / -dvec[0])
        loc, iray, _ = m.ray.intersects_location(orig, np.tile(dvec, (len(msk), 1)), multiple_hits=False)
        dist = np.full(len(msk), np.inf)
        dist[iray] = np.linalg.norm(loc - orig[iray], axis=1)
        hit = dist < need - 0.05
        res["arm"] = dict(faces=int(len(msk)), blocked_faces=int(hit.sum()), blocked_area_mm2=float(m.area_faces[msk][hit].sum()),
                          path="уздовж рампи до її початку → горизонтально по порогу → −Z", stage1_max_travel_mm=float(need.max()) if len(need) else 0.0)
    return res


def arm_dir():
    """Напрямок виходу плеча сердечника (у координатах виробу): уздовж рампи до отвору."""
    t = math.radians(v(p.ARM_RAMP_DEG))
    return np.array([-math.cos(t), 0.0, -math.sin(t)])


def seal_wall_check():
    """v3.0: стінка під губчастим ущільнювачем має бути суцільною по периметру пробки (плече відкривається лише вище порогу).
    Переріз корпусу на висотах смуги ущільнення: контур порожнини не виходить за x = cav_x1."""
    import cadquery as cq
    body = P.body()
    out = []
    z0 = v(p.LID_RECESS)
    for z in (z0 + d["groove_z0"], z0 + (d["groove_z0"] + d["groove_z1"]) / 2, z0 + d["groove_z1"], d["arm_sill_z"] - 0.3):
        s = body.intersect(cq.Solid.makeBox(400, 400, 0.02, pnt=cq.Vector(-200, -200, z - 0.01)))
        loops = [w for f in s.Faces() if abs(f.normalAt().z) > 0.99 and f.Center().z > z for w in f.innerWires()]
        cav = [w for w in loops if w.BoundingBox().xmin < d["cav_xc"]]
        xmax = max(w.BoundingBox().xmax for w in cav) if cav else float("nan")
        out.append(dict(z=z, cavity_loop_xmax=xmax, closed=bool(cav) and xmax <= d["cav_x1"] + 0.6))
    return out


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
    out = dict(F_N=F, contact_width_mm=b, arm_mm=arm, sigma_MPa=sigma)
    if v(p.LID_TAB_ON):   # v2.9: язичок — консоль від кромки фланця, сила на кінці (запас)
        L = v(p.D) / 2 - v(p.LID_TAB_INSET) - d["flange"] / 2
        bt, tt = v(p.RECESS_W) - 2 * v(p.LID_TAB_GAP), v(p.LID_TAB_T)
        out.update(tab_len_mm=L, tab_w_mm=bt, tab_t_mm=tt, tab_sigma_MPa=6 * F * L / (bt * tt * tt),
                   finger_gap_above_tab_mm=d["recess_top"] - v(p.LID_RECESS) - tt)
    return out


def run(write_to=None):
    rho_c = v(p.RHO_CONCRETE)
    rho_s = v(p.RHO_SILICONE)
    body = P.body()
    lid = P.lid()
    oring = P.oring()
    felt = P.felt_pad()
    RL = P.has_relief_lid()
    rlid = P.relief_lid() if RL else None
    rseal = P.relief_seal() if RL else None
    dev = P.device()
    R = {}
    R["mass"] = {
        "body": mass_props(body, rho_c),
        "lid": mass_props(lid, rho_c),
        "oring": mass_props(oring, rho_s),
        "felt": mass_props(felt, 400.0),
        "device_dummy_volume_ml": dev.Volume() / 1000,
    }
    if RL:
        R["mass"]["relief_lid"] = mass_props(rlid, rho_c)
        R["mass"]["relief_seal"] = mass_props(rseal, rho_s)
    parts_m = [(R["mass"][k]["mass_kg"], np.array(R["mass"][k]["com"])) for k in ("body", "lid", "oring", "relief_lid", "relief_seal", "felt") if k in R["mass"]]
    m_tot = sum(m for m, _ in parts_m)
    com = sum(m * c for m, c in parts_m) / m_tot
    dev_c = np.array(mass_props(dev, 1)["com"])
    m_dev = v(p.DEV_MASS)
    com_dev = (com * m_tot + dev_c * m_dev) / (m_tot + m_dev)
    R["assembly"] = dict(mass_kg=m_tot, com=com.tolist(), mass_with_device_kg=m_tot + m_dev,
                         com_with_device=com_dev.tolist())
    R["validity"] = {k: s.isValid() for k, s in (("body", body), ("lid", lid), ("oring", oring), ("felt", felt),
                                                     ("relief_lid", rlid), ("relief_seal", rseal)) if s is not None}

    shapes = dict(body=body, lid=lid, oring=oring, felt=felt, relief_lid=rlid, relief_seal=rseal, device=dev)
    pairs = [("body", "lid"), ("body", "oring"), ("lid", "oring"), ("body", "felt"), ("felt", "device"),
             ("body", "device")] + ([("body", "relief_lid"), ("body", "relief_seal"), ("relief_lid", "relief_seal"),
             ("lid", "relief_lid")] if RL else [])
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
    arm_ml = 0.0
    if v(p.ARM_ON):   # повітря плеча поза контуром основної обвідної призми
        xe = xc + (v(p.CAV) + 8) / 2
        abox = P.prism_rrect(d["arm_x1"] + 2 - xe, d["arm_y1"] + 2 - (d["arm_y0"] - 1), 0.5, d["arm_sill_z"] - 1, d["z_ceil_c"] + 1,
                             cx=(xe + d["arm_x1"] + 2) / 2, cy=(d["arm_y0"] - 1 + d["arm_y1"] + 2) / 2)
        arm_air = abox.cut(body)
        arm_ml = max((s_.Volume() for s_ in arm_air.Solids()), default=0.0) / 1000
    R["cavity"] = dict(net_volume_ml=cav_air.Volume() / 1000 + arm_ml, arm_ml=arm_ml, main_ml=cav_air.Volume() / 1000,
                       stick_volume_ml=math.pi * (v(p.STICK_D) / 2) ** 2 * v(p.STICK_L) / 1000)
    R["cavity"]["sticks_at_packing"] = {str(phi): R["cavity"]["net_volume_ml"] * phi / R["cavity"]["stick_volume_ml"]
                                        for phi in (0.40, 0.50, 0.60)}

    # товщини стінок
    m, pts, nrm, th = wall_thickness(body)
    reg = classify_regions(pts, nrm)
    ok = ~np.isnan(th)
    wt = {}
    for name in ("outer", "cavity", "arm", "pocket", "funnel", "slot", "logo"):
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
    R["lid_tilt"] = lid_tilt_check()
    if RL:
        R["relief_lid_tilt"] = rl_tilt_check()
        R["relief_lid_hook"] = rl_hook_check()
    if v(p.ARM_ON):
        R["seal_wall"] = seal_wall_check()
    R["device_fit"] = device_fit_check()
    R["slot_controls"] = slot_controls_check()
    R["seal_force"] = seal_force_estimate()
    R["derived"] = d
    if write_to:
        with open(write_to, "w") as f:
            json.dump(R, f, indent=2, ensure_ascii=False, default=float)
    return R


if __name__ == "__main__":
    import sys
    r = run(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps({k: r[k] for k in r if k != "derived"}, indent=1, ensure_ascii=False, default=float))


def lid_tilt_check(angles=(1, 3, 5, 7, 8, 10, 12)):
    """Зняття кришки за передній край: поворот навколо задньої верхньої кромки фланця (упор),
    передня кромка йде вниз. Повертає об'єм перетину жорсткої кришки з корпусом (без О-кільця)."""
    from cadquery import Vector
    body, lid = P.body(), P.lid()
    s_ = 1 if v(p.RECESS_SIDE) > 0 else -1          # v2.7: тягнуть за задній край, упор — передня кромка
    xc, yb, zp = d["cav_xc"], -s_ * d["flange"] / 2, d["z_reb"]
    out = []
    for a in angles:
        l = lid.rotate(Vector(xc - 50, yb, zp), Vector(xc + 50, yb, zp), -s_ * a)
        out.append(dict(angle_deg=a, interference_mm3=l.intersect(body).Volume(),
                        pull_edge_drop_mm=v(p.LID_RECESS) - l.BoundingBox().zmin))
    return out


def rl_tilt_check(angles=(2, 5, 8, 12, 16)):
    """v2.7: кришечку полегшення тягнуть за правий край через виїмку; упор — ліва верхня кромка фланця."""
    from cadquery import Vector
    body, rl = P.body(), P.relief_lid()
    cx, cy = (d["rel_x0"] + d["rel_x1"]) / 2, (d["rel_y0"] + d["rel_y1"]) / 2
    xp, zp = cx - d["rl_flange_w"] / 2, d["rl_z_reb"]
    out = []
    for a in angles:
        l = rl.rotate(Vector(xp, cy - 50, zp), Vector(xp, cy + 50, zp), a)   # +a: правий край (виїмка) іде вниз
        out.append(dict(angle_deg=a, interference_mm3=l.intersect(body).Volume()))
    return out


def rl_hook_check(F=15.0):
    """Уступ фланця кришечки під пальцем у виїмці правої грані (консоль)."""
    b = v(p.RL_RECESS_W) - 2 * 1.5
    t = v(p.RL_FLANGE_T)
    arm = (v(p.RL_SHOULDER) - v(p.RL_GAP) + v(p.RL_PLUG_GAP)) / 2
    out = dict(F_N=F, contact_width_mm=b, ledge_mm=v(p.RL_SHOULDER) - v(p.RL_GAP) + v(p.RL_PLUG_GAP),
               sigma_MPa=6 * F * arm / (b * t * t), groove_above_recess_mm=d["rl_groove_z0"] - d["rl_recess_top"])
    if v(p.LID_TAB_ON):
        L = v(p.W) / 2 - v(p.LID_TAB_INSET) - ((d["rel_x0"] + d["rel_x1"]) / 2 + d["rl_flange_w"] / 2)
        bt, tt = v(p.RL_RECESS_W) - 2 * v(p.LID_TAB_GAP), v(p.LID_TAB_T)
        out.update(tab_len_mm=L, tab_w_mm=bt, tab_t_mm=tt, tab_sigma_MPa=6 * F * L / (bt * tt * tt),
                   finger_gap_above_tab_mm=d["rl_recess_top"] - v(p.LID_RECESS) - tt)
    return out


def device_fit_check(radii=(7.0, 7.5, 8.2)):
    """v2.7: посадка девайса для різних кутових радіусів перерізу (реальний — не опублікований).
    Для кожного: перетин з корпусом і мінімальний зазор до бетону (кишеня R4, ухил 0.5°)."""
    body = P.body()
    out = []
    for r in radii:
        dv = P.device(corner_r=r)
        out.append(dict(corner_r_mm=r, interference_mm3=common_volume(body, dv), min_clearance_mm=min_distance(body, dv)))
    return out


def slot_controls_check():
    """v2.8: де опиняються світлова смужка й кнопка девайса (USB-C донизу; відлік від торця зі стіком — 2 фото замовника).
    Вимога: смужка повністю над корпусом; кнопка над корпусом або над прорізом (місце для пальця)."""
    H = v(p.H)
    btn_len = d["btn_z1"] - d["btn_z0"]
    above = max(0.0, d["btn_z1"] - max(d["btn_z0"], H))
    return dict(led_z=[d["btn_z1"], d["led_z1"]], button_z=[d["btn_z0"], d["btn_z1"]], body_top_z=H,
                led_fully_above=bool(d["btn_z1"] >= H), button_above_mm=above, button_len_mm=btn_len,
                button_below_top_mm=max(0.0, H - d["btn_z0"]),
                slot_z=[d["slot_tip_z"], H], slot_under_button=bool(d["btn_z0"] >= d["slot_straight_z0"]),
                slot_w_mm=v(p.SLOT_W), ctrl_w_mm=v(p.DEV_CTRL_W))


def seal_force_estimate(cld_kpa=(30.0, 60.0), mu=(0.3, 0.7), contact_w=3.0):
    """Оцінка сили витягування кришки з губчастим шнуром (НЕ вимірювання):
    F_n = p(25–30% стиснення) × ширина контакту × довжина; F = μ·F_n.
    p (CLD) — типовий діапазон м'якої/середньої силіконової губки; уточнити за даташитом."""
    L = d["seal_center_len"]
    out = {}
    for p_ in cld_kpa:
        Fn = p_ * 1e-3 * contact_w * L
        out[f"cld_{p_:.0f}kPa"] = dict(normal_N=Fn, pull_N=[Fn * m for m in mu])
    return dict(length_mm=L, contact_w_mm=contact_w, mu=mu, cases=out)
