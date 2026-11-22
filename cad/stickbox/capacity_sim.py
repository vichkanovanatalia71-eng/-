"""
Симуляція місткості (MuJoCo, тверді тіла). Оцінка — не заміна фізичного тесту.

Модель:
  * порожнина — коробка за фактичними розмірами моделі (дно = верх пробки кришки,
    стеля — консервативно на висоті краю купола), кутові радіуси R16 замінені
    рівновеликими фасками;
  * стік — капсула Ø STICK_D, загальна довжина STICK_L (заокруглені торці — невелика
    систематична переоцінка щільності пакування);
  * кожен новий стік «проходить» крізь отвір: з'являється під стелею на осі отвору
    з випадковим нахилом ≤ 12° і швидкістю падіння 0.4 м/с;
  * якщо місце під отвором зайняте (перетин з купою > 0.3 мм) — до 6 спроб з іншим
    нахилом; якщо всі невдалі — отвір «заблоковано»;
  * режим «зі струшуванням»: при блокуванні виріб нахиляють/струшують (обертання вектора g
    ±20°, 1.5 с), після чого вкидання продовжується; ліміт — 4 струшування поспіль без успіху.
"""
import math
import json
import numpy as np
import mujoco

from . import params as p
from .params import v

d = p.derived()


def build_xml(n_sticks, stick_d=None, stick_l=None):
    sd = (stick_d or v(p.STICK_D)) / 1000
    sl = (stick_l or v(p.STICK_L)) / 1000
    r = sd / 2
    half_cyl = (sl - sd) / 2
    tan_c = math.tan(math.radians(v(p.DRAFT_CAV)))
    z_floor = d["z_plug_top"] / 1000
    z_tray = (v(p.LID_RECESS) + v(p.LID_FLOOR)) / 1000 if v(p.LID_TRAY) else z_floor
    z_ceil = d["z_ceil_edge"] / 1000
    mid = (d["z_plug_top"] + d["z_ceil_edge"]) / 2
    side = (v(p.CAV) - 2 * (mid - d["z_reb"]) * tan_c) / 1000  # середній переріз з ухилом
    hs = side / 2
    a = math.sqrt(2 * (1 - math.pi / 4)) * v(p.R_CAV) / 1000  # катет рівновеликої фаски
    t = 0.01
    hz = (z_ceil - z_floor) / 2
    zc = (z_ceil + z_floor) / 2
    zc_c = d["z_ceil_c"] / 1000            # стеля в центрі (отвір)
    plate = 0.002                           # пряма ділянка отвору Ø8 (2 мм)
    xh = (d["cav_xc"] - d["cav_xc"]) / 1000  # отвір на осі порожнини
    R_h = v(p.HOLE_D) / 2000
    ARM = bool(v(p.ARM_ON))
    if not ARM:
        walls = f"""
    <geom name="floor" type="box" size="{hs+t} {hs+t} {4*t}" pos="0 0 {z_tray - 4*t}"/>
    <geom type="box" size="{t} {hs+t} {hz + 0.01}" pos="{hs + t} 0 {zc}"/>
    <geom type="box" size="{t} {hs+t} {hz + 0.01}" pos="{-hs - t} 0 {zc}"/>
    <geom type="box" size="{hs+t} {t} {hz + 0.01}" pos="0 {hs + t} {zc}"/>
    <geom type="box" size="{hs+t} {t} {hz + 0.01}" pos="0 {-hs - t} {zc}"/>
    """
    else:
        # v3.0: Г-резервуар — права стінка лише для y < arm_y0; плече x ∈ [hs, x1], y ∈ [y0, hs]: рампа θ від порогу, торець,
        # перегородка до кишені, стеля; задня стінка продовжена до торця плеча
        y0 = d["arm_y0"] / 1000
        x1 = (d["arm_x1"] - d["cav_xc"]) / 1000
        sill = d["arm_sill_z"] / 1000
        th = math.radians(v(p.ARM_RAMP_DEG))
        xs = (d["cav_x1"] - d["cav_xc"] - (d["arm_sill_z"] - d["z_reb"]) * tan_c) / 1000
        wy = (y0 + hs + t) / 2
        za_c = (z_ceil + sill) / 2
        za_h = (z_ceil - sill) / 2
        Lr = (x1 - xs) / math.cos(th) + 0.004
        xm = (xs + x1) / 2
        zm = sill + (xm - xs) * math.tan(th)
        tp = 0.003
        walls = f"""
    <geom name="floor" type="box" size="{hs+t} {hs+t} {4*t}" pos="0 0 {z_tray - 4*t}"/>
    <geom type="box" size="{t} {wy} {hz + 0.01}" pos="{hs + t} {(-hs - t + y0) / 2} {zc}"/>
    <geom type="box" size="{t} {hs+t} {hz + 0.01}" pos="{-hs - t} 0 {zc}"/>
    <geom type="box" size="{(x1 + hs) / 2 + t} {t} {hz + 0.01}" pos="{(x1 - hs) / 2} {hs + t} {zc}"/>
    <geom type="box" size="{hs+t} {t} {hz + 0.01}" pos="0 {-hs - t} {zc}"/>
    <geom name="ramp" type="box" size="{Lr / 2} {(hs - y0) / 2 + t} {tp}" pos="{xm + tp * math.sin(th)} {(y0 + hs) / 2} {zm - tp * math.cos(th)}" euler="0 {-math.degrees(th)} 0"/>
    <geom type="box" size="{(x1 - hs) / 2 + t} {t} {za_h + 0.01}" pos="{(hs + x1) / 2} {y0 - t} {za_c}"/>
    <geom type="box" size="{t} {(hs - y0) / 2 + t} {za_h + 0.01}" pos="{x1 + t} {(y0 + hs) / 2} {za_c}"/>
    <geom type="box" size="{(x1 - hs) / 2 + t} {(hs - y0) / 2 + t} {t}" pos="{(hs + x1) / 2} {(y0 + hs) / 2} {z_ceil + t}"/>
    """
    if v(p.LID_TRAY):  # борт лотка кришки по периметру (6 мм) до верху пробки
        sk = (side - d["tray"] / 1000) / 2
        hzs = (z_floor - z_tray) / 2
        zs = (z_floor + z_tray) / 2
        walls += f"""
    <geom type="box" size="{hs} {sk/2} {hzs}" pos="0 {hs - sk/2} {zs}"/>
    <geom type="box" size="{hs} {sk/2} {hzs}" pos="0 {-hs + sk/2} {zs}"/>
    <geom type="box" size="{sk/2} {hs} {hzs}" pos="{hs - sk/2} 0 {zs}"/>
    <geom type="box" size="{sk/2} {hs} {hzs}" pos="{-hs + sk/2} 0 {zs}"/>
    """
    # стеля: 4 плити навколо центрального квадрата 24×24 мм + 12-кутне кільце (вписаний радіус = R отвору)
    q = 0.012
    ztop = z_ceil
    thick = (zc_c + plate - z_ceil) / 2 + 0.001
    zmid = z_ceil + thick
    walls += f"""
    <geom type="box" size="{hs+t} {(hs - q)/2 + t/2} {thick}" pos="0 {q + (hs - q)/2 + t/2} {zmid}"/>
    <geom type="box" size="{hs+t} {(hs - q)/2 + t/2} {thick}" pos="0 {-q - (hs - q)/2 - t/2} {zmid}"/>
    <geom type="box" size="{(hs - q)/2 + t/2} {q} {thick}" pos="{q + (hs - q)/2 + t/2} 0 {zmid}"/>
    <geom type="box" size="{(hs - q)/2 + t/2} {q} {thick}" pos="{-q - (hs - q)/2 - t/2} 0 {zmid}"/>
    """
    nseg = 12
    depth = 0.010
    wseg = 2 * (R_h + depth) * math.tan(math.pi / nseg) * 1.05
    for k in range(nseg):
        a = 2 * math.pi * k / nseg
        rc = R_h + depth / 2
        walls += (f'<geom type="box" size="{depth/2} {wseg/2} {plate/2}" '
                  f'pos="{rc*math.cos(a)} {rc*math.sin(a)} {zc_c + plate/2}" euler="0 0 {math.degrees(a)}"/>\n')
    # під кільцем (від стелі-купола до низу прямої ділянки) — розтруб, моделюємо відкритим конусом-сходинкою
    # кутові фаски: коробка, повернута на 45°, грань якої відтинає трикутник з катетом a
    off = (hs - a / 2) * 1.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            if v(p.ARM_ON) and sx > 0 and sy > 0:
                continue          # v3.0: кут (+,+) відкритий у плече вище порогу
            cx, cy = sx * hs, sy * hs
            # центр коробки зміщений від кута вздовж діагоналі назовні так, щоб грань проходила через фаску
            dist = a / math.sqrt(2) / 2  # відстань від кута до лінії фаски вздовж діагоналі = a/√2/... (рівнобедр.)
            dline = a / math.sqrt(2)     # відстань від кута до лінії фаски
            w = 0.02
            px = cx - sx * (dline - w) / math.sqrt(2)
            py = cy - sy * (dline - w) / math.sqrt(2)
            ang = 45 if sx * sy > 0 else -45
            walls += f'<geom type="box" size="{w} {0.05} {hz}" pos="{px} {py} {zc}" euler="0 0 {ang}"/>\n'
    sticks = ""
    for i in range(n_sticks):
        px = 1.0 + (i % 20) * 0.02
        py = 1.0 + (i // 20) * 0.02
        sticks += f"""
    <body name="s{i}" pos="{px} {py} 0.5" gravcomp="1">
      <freejoint/>
      <geom name="g{i}" type="capsule" size="{r} {half_cyl}" mass="0.0008" contype="0" conaffinity="0"
            friction="0.5 0.005 0.0001" condim="3"/>
    </body>"""
    xml = f"""
<mujoco>
  <option timestep="0.0004" gravity="0 0 -9.81" integrator="implicitfast" cone="elliptic" impratio="2"/>
  <default><geom solref="0.004 1" solimp="0.95 0.99 0.0005" margin="0.00002"/></default>
  <size memory="200M"/>
  <worldbody>
    {walls}
    {sticks}
  </worldbody>
</mujoco>"""
    return xml, dict(z_floor=z_tray, z_ceil=z_ceil, z_hole_top=d["z_ceil_c"] / 1000 + 0.002, side=side, r=r, half=half_cyl, sl=sl)


def quat_from_tilt(theta, phi):
    # вісь капсули — локальна Z; нахил θ від вертикалі в напрямку азимуту φ
    ax = np.array([-math.sin(phi), math.cos(phi), 0.0])
    q = np.zeros(4)
    mujoco.mju_axisAngle2Quat(q, ax, theta)
    return q


def run_once(seed=0, n_max=140, shake=True, stick_d=None, max_tilt_deg=8.0, verbose=False, return_poses=False, tilt_x_deg=0.0):
    xml, G = build_xml(n_max, stick_d)
    m = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(m)
    rng = np.random.default_rng(seed)
    gid = [mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, f"g{i}") for i in range(n_max)]
    bid = [mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, f"s{i}") for i in range(n_max)]
    qadr = [m.jnt_qposadr[m.body_jntadr[b]] for b in bid]
    vadr = [m.jnt_dofadr[m.body_jntadr[b]] for b in bid]
    mujoco.mj_forward(m, data)

    def settle(t):
        for _ in range(int(t / m.opt.timestep)):
            mujoco.mj_step(m, data)

    def place(i, th, ph):
        half_len = G["half"] + G["r"]
        ax = np.array([math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)])
        bottom = np.array([0.0, 0.0, G["z_hole_top"] + 0.0015])
        pos = bottom + ax * half_len
        data.qpos[qadr[i]:qadr[i] + 3] = pos
        data.qpos[qadr[i] + 3:qadr[i] + 7] = quat_from_tilt(th, ph)
        data.qvel[vadr[i]:vadr[i] + 6] = 0
        data.qvel[vadr[i] + 2] = -0.3
        m.geom_contype[gid[i]] = 1
        m.geom_conaffinity[gid[i]] = 1
        if hasattr(m, "body_contype"):
            m.body_contype[bid[i]] = 1
            m.body_conaffinity[bid[i]] = 1
        m.body_gravcomp[bid[i]] = 0
        mujoco.mj_forward(m, data)

    def top_z(i):
        half_len = G["half"] + G["r"]
        R = np.zeros(9)
        mujoco.mju_quat2Mat(R, data.qpos[qadr[i] + 3:qadr[i] + 7])
        ax = R.reshape(3, 3)[:, 2]
        c = data.qpos[qadr[i]:qadr[i] + 3]
        return max(c[2] + ax[2] * half_len, c[2] - ax[2] * half_len)

    def push(i, F=1.0, T=0.5):
        """Палець штовхає стік униз, поки верхній торець вище горла воронки."""
        z_finger = (v(p.H) - v(p.FUNNEL_DEPTH)) / 1000
        for _ in range(int(T / m.opt.timestep)):
            data.xfrc_applied[bid[i], :] = 0
            if top_z(i) > z_finger:
                data.xfrc_applied[bid[i], 2] = -F
            mujoco.mj_step(m, data)
        data.xfrc_applied[bid[i], :] = 0

    def try_insert(i):
        th = math.radians(rng.uniform(0, max_tilt_deg))
        ph = rng.uniform(0, 2 * math.pi)
        place(i, th, ph)
        push(i)
        settle(0.4)
        return top_z(i) < G["z_ceil"] + 0.0005  # верхній торець пройшов стелю

    def do_shake():
        """Струшування ±20°; tilt_x_deg > 0 — користувач додатково нахиляє виріб правим боком донизу (до плеча Г-резервуара)."""
        g0 = np.array([0, 0, -9.81])
        T = 1.5
        steps = int(T / m.opt.timestep)
        bias = math.radians(tilt_x_deg)
        for k in range(steps):
            tt = k * m.opt.timestep
            ramp_in = min(1.0, tt / 0.3)
            a = bias * ramp_in + math.radians(20 if not tilt_x_deg else 12) * math.sin(2 * math.pi * 2.0 * tt)
            b = math.radians(20) * math.sin(2 * math.pi * 1.3 * tt + 1.0)
            m.opt.gravity[:] = [9.81 * math.sin(a), 9.81 * math.sin(b), -9.81 * math.cos(a) * math.cos(b)]
            mujoco.mj_step(m, data)
        m.opt.gravity[:] = g0
        settle(0.6)

    n = 0
    n_no_shake = None
    shakes = 0
    while n < n_max:
        ok = try_insert(n)
        if ok:
            n += 1
            continue
        if n_no_shake is None:
            n_no_shake = n
            if not shake:
                break
        # застряг: користувач струшує виріб і ще раз дотискає стік
        recovered = False
        for _ in range(3):
            do_shake()
            shakes += 1
            push(n, F=1.0, T=0.4)
            settle(0.3)
            if top_z(n) < G["z_ceil"] + 0.0005:
                recovered = True
                break
        if recovered:
            n += 1
        else:
            break
    if n_no_shake is None:
        n_no_shake = n
    # перевірка: усі стіки всередині порожнини
    inside = 0
    for i in range(n):
        z = data.qpos[qadr[i] + 2]
        if G["z_floor"] - 0.005 < z < G["z_ceil"] + 0.005:
            inside += 1
    out = dict(seed=seed, no_shake=n_no_shake, with_shake=n, shakes=shakes, inside=inside)
    if return_poses:
        out["poses"] = [dict(pos=(data.qpos[qadr[i]:qadr[i] + 3] * 1000).tolist(),
                             quat=data.qpos[qadr[i] + 3:qadr[i] + 7].tolist()) for i in range(n)]
        out["center_xy_mm"] = [d["cav_xc"], 0.0]
    return out


def _one(args):
    s, sd, tx = args
    return run_once(s, stick_d=sd, tilt_x_deg=tx)


def run(seeds=(0, 1, 2, 3, 4), stick_d=None, procs=1, tilt_x_deg=0.0):
    if procs > 1:
        from multiprocessing import Pool
        with Pool(procs) as pool:
            res = pool.map(_one, [(s, stick_d, tilt_x_deg) for s in seeds])
    else:
        res = [run_once(s, stick_d=stick_d, tilt_x_deg=tilt_x_deg) for s in seeds]
    a = np.array([r["no_shake"] for r in res])
    b = np.array([r["inside"] for r in res])   # консервативно: лише стіки, що лишились у порожнині
    return dict(runs=res, no_shake_mean=float(a.mean()), no_shake_min=int(a.min()), no_shake_max=int(a.max()),
                with_shake_mean=float(b.mean()), with_shake_min=int(b.min()), with_shake_max=int(b.max()))


if __name__ == "__main__":
    import sys, time
    t = time.time()
    r = run(seeds=tuple(range(8)), procs=4)
    r["stick_d"] = v(p.STICK_D)
    r["elapsed_s"] = time.time() - t
    print(json.dumps(r, indent=1))
    if len(sys.argv) > 1:
        json.dump(r, open(sys.argv[1], "w"), indent=1)
