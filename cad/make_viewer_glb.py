"""GLB для веб-переглядача (viewer/): виріб без оснащення, base64 у viewer/stickbox.glb.b64.txt.
Запуск: cd cad && python make_viewer_glb.py"""
import sys, base64, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stickbox import parts as P, export as X
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
out = os.path.join(ROOT, "viewer", "stickbox.glb")
L = [('body', P.body(), 'body'), ('lid', P.lid(), 'lid'), ('oring', P.oring(), 'oring'), ('felt', P.felt_pad(), 'liner')]
if P.has_relief_lid():
    L += [('rlid', P.relief_lid(), 'lid'), ('rseal', P.relief_seal(), 'oring')]
if P.v(P.p.NFC_ON):
    L += [('nfc_tag', P.nfc_tag(), 'liner')]   # v3.3: NFC-мітка під верхом (видно в розрізі y = −15)
L += [('logo_stick', P.logo_fill('GREY'), 'liner'), ('logo_box', P.logo_fill('TEAL'), 'oring'),
      ('device', P.device(), 'device'), ('ctrl_led', P.device_controls()[0], 'liner'), ('ctrl_btn', P.device_controls()[1], 'liner')]
# v3.7: оснащення для режиму «Форма для лиття»: розбірний каркас T02a/b, силіконовий блок, майстер T01, плита T03, ребро T04
from stickbox import molds as MO
fr_f, fr_b = MO.frame_halves("body")
L += [('mold_frame_front', fr_f, 'print', (0.08, 0.25)), ('mold_frame_back', fr_b, 'print', (0.08, 0.25)),
      ('mold_silicone', MO.mold_silicone("body"), 'silicone', (0.08, 0.25)), ('mold_master', MO.body_master(), 'master', (0.08, 0.25)),
      ('mold_plate', MO.body_base_plate(), 'print', (0.1, 0.3)), ('mold_stiff', MO.finger_stiffener(), 'print', (0.1, 0.3))]
# v3.7.1: лиття бетону — сердечник T07 на хребті T05 і віртуальний виливок (бетон між файлами оснащення, stickbox/casting_check)
from stickbox import casting_check as CC
L += [('mold_core', CC.tool("T07"), 'silicone', (0.08, 0.25)), ('mold_spine', CC.tool("T05"), 'print', (0.1, 0.3)),
      ('mold_cast', CC.cast_body()[0][0], 'body', (0.06, 0.2))]

# v3.7.1: анімація виготовлення (viewer/process.html) і форма кришки в переглядачі
import math
import cadquery as cq
from cadquery import Vector


def _hexp(cx, cy, cz, af, h, axis):
    """Шестигранник «під ключ» af, висотою h уздовж осі axis ('y' або 'z') від точки (cx, cy, cz)."""
    r = af / math.sqrt(3)
    if axis == "y":
        return cq.Workplane("XZ", origin=(cx, cy, cz)).polygon(6, 2 * r).extrude(-h).val()
    return cq.Workplane("XY", origin=(cx, cy, cz)).polygon(6, 2 * r).extrude(h).val()


def frame_bolts(kind):
    """Болти M4 × 20 з гайками на фланцях роз'єму каркаса (головка спереду, гайка ззаду)."""
    sp = MO.frame_spec(kind)
    xo = sp["w"] / 2 + MO.FRAME_T
    sols = []
    for f in sp["bolts"]:
        zc = sp["z0"] + f * sp["hf"]
        for sx in (-1, 1):
            xb = sp["cx"] + sx * (xo + MO.FL_W / 2)
            y0 = sp["cy"] - MO.FL_T
            sols.append(_hexp(xb, y0 - 2.8, zc, 7.0, 2.8, "y"))
            sols.append(cq.Solid.makeCylinder(2.0, 20.0, Vector(xb, y0, zc), Vector(0, 1, 0)))
            sols.append(_hexp(xb, sp["cy"] + MO.FL_T, zc, 7.0, 3.2, "y"))
    return cq.Compound.makeCompound(sols)


def rods_and_nuts():
    """4 шпильки M5 × 150 крізь дошку, вушки каркаса й міст + гайки-баранці (координати виробу, до перевертання).
    Повертає (шпильки, баранці на мосту, баранці під дошкою)."""
    sp = MO.frame_spec("body")
    z_open = -MO.GA * MO.K
    zb0 = z_open - MO.BRIDGE_RAISE - MO.BRIDGE_T
    z_top = sp["z1"] + 12.0
    rods, nb, nd = [], [], []
    for (x, y) in MO.lug_positions():
        rods.append(cq.Solid.makeCylinder(2.5, 150.0, Vector(x, y, zb0 - 13.0)))
        for zn, sg, lst in ((zb0, -1, nb), (z_top, 1, nd)):   # гайка-баранець: шестигранник + «крила»
            z_ = zn if sg > 0 else zn - 4.0
            lst.append(_hexp(x, y, z_, 8.0, 4.0, "z"))
            lst.append(MO.box(x - 11, x + 11, y - 1.2, y + 1.2, z_ + 0.5, z_ + 3.5))
    return tuple(cq.Compound.makeCompound(q) for q in (rods, nb, nd))


def board():
    """Дошка-основа (фанера 12 мм) під перевернутим каркасом, 4 отвори Ø6 під шпильки."""
    sp = MO.frame_spec("body")
    b = MO.box(sp["cx"] - 115, sp["cx"] + 115, sp["cy"] - 92, sp["cy"] + 92, sp["z1"], sp["z1"] + 12.0)
    for (x, y) in MO.lug_positions():
        b = b.cut(MO.cyl(3.0, sp["z1"] - 1, sp["z1"] + 13, x, y))
    return b


lf, lb = MO.frame_halves("lid")
L += [('mold_holder', MO.stiffener_holder(), 'print', (0.1, 0.3)), ('mold_coremold', MO.core_mold(), 'mold', (0.1, 0.3)),
      ('mold_bolts', frame_bolts("body"), 'device', (0.1, 0.3)),
      *[(n_, s_, 'device', (0.1, 0.3)) for n_, s_ in zip(('mold_rods', 'mold_nuts_bridge', 'mold_nuts_board'), rods_and_nuts())],
      ('mold_board', board(), 'print', (0.1, 0.3)),
      ('lmold_frame_front', lf, 'print', (0.08, 0.25)), ('lmold_frame_back', lb, 'print', (0.08, 0.25)),
      ('lmold_silicone', MO.mold_silicone("lid"), 'silicone', (0.08, 0.25)), ('lmold_master', MO.lid_master(), 'master', (0.08, 0.25)),
      ('lmold_plate', MO.lid_base_plate(), 'print', (0.1, 0.3)), ('lmold_bolts', frame_bolts("lid"), 'device', (0.1, 0.3)),
      ('lmold_cast', CC.cast_lid()[0][0], 'body', (0.06, 0.2))]
X.export_glb(L, out, tol=0.06, ang=0.2)
b = open(out, 'rb').read()
open(os.path.join(ROOT, 'viewer', 'stickbox.glb.b64.txt'), 'w').write(base64.b64encode(b).decode())
os.remove(out)
print('viewer glb', len(b))
