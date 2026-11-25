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
X.export_glb(L, out, tol=0.06, ang=0.2)
b = open(out, 'rb').read()
open(os.path.join(ROOT, 'viewer', 'stickbox.glb.b64.txt'), 'w').write(base64.b64encode(b).decode())
os.remove(out)
print('viewer glb', len(b))
