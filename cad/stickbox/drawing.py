"""
Генерація технічних креслень (SVG, A3) безпосередньо з B-Rep:
  * точний HLR (OpenCASCADE HLRBRep_Algo): видимі / невидимі лінії;
  * розрізи: тіло зрізається напівпростором, площина розрізу штрихується;
  * розміри задаються в координатах моделі → гарантована відповідність CAD.
"""
import math
import numpy as np
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
import cadquery as cq

VIEWS = {
    "front": ((0, -1, 0), (1, 0, 0)),
    "back": ((0, 1, 0), (-1, 0, 0)),
    "top": ((0, 0, 1), (1, 0, 0)),
    "bottom": ((0, 0, -1), (1, 0, 0)),
    "left": ((-1, 0, 0), (0, -1, 0)),
    "right": ((1, 0, 0), (0, 1, 0)),
}


def basis(view):
    D, X = VIEWS[view]
    D, X = np.array(D, float), np.array(X, float)
    Y = np.cross(D, X)
    return D, X, Y


def _edges_polylines(compound, defl=0.02):
    out = []
    if compound is None or compound.IsNull():
        return out
    exp = TopExp_Explorer(compound, TopAbs_EDGE)
    while exp.More():
        e = TopoDS.Edge_s(exp.Current())
        try:
            c = BRepAdaptor_Curve(e)
            disc = GCPnts_QuasiUniformDeflection(c, defl)
            if disc.IsDone() and disc.NbPoints() > 1:
                pts = [disc.Value(i) for i in range(1, disc.NbPoints() + 1)]
                out.append([(p.X(), p.Y()) for p in pts])
        except Exception:
            pass
        exp.Next()
    return out


def hlr(shape, view, hidden=True):
    D, X, _ = basis(view)
    algo = HLRBRep_Algo()
    algo.Add(shape.wrapped)
    ax = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*D), gp_Dir(*X))
    algo.Projector(HLRAlgo_Projector(ax))
    algo.Update()
    algo.Hide()
    h = HLRBRep_HLRToShape(algo)
    # габарит проєкції тіла: відкидаємо артефактні силуети (напр. повне коло сфери купола)
    bb = shape.BoundingBox()
    corners = np.array([[x, y, z] for x in (bb.xmin, bb.xmax) for y in (bb.ymin, bb.ymax) for z in (bb.zmin, bb.zmax)])
    _, Xb, Yb = basis(view)
    U, Vv = corners @ Xb, corners @ Yb
    lim = (U.min() - 0.5, U.max() + 0.5, Vv.min() - 0.5, Vv.max() + 0.5)
    ok = lambda pl: all(lim[0] <= u <= lim[1] and lim[2] <= w <= lim[3] for u, w in pl)
    vis = []
    for comp in (h.VCompound(), h.OutLineVCompound(), h.Rg1LineVCompound()):
        vis += [pl for pl in _edges_polylines(comp) if ok(pl)]
    hid = []
    if hidden:
        for comp in (h.HCompound(), h.OutLineHCompound()):
            hid += [pl for pl in _edges_polylines(comp) if ok(pl)]
    return vis, hid


def section_faces(cut_shape, plane_point, normal, view):
    """Полігони граней, що лежать у площині розрізу (для штрихування)."""
    D, X, Y = basis(view)
    n = np.array(normal, float)
    p0 = np.array(plane_point, float)
    polys = []
    for f in cut_shape.Faces():
        try:
            fn = f.normalAt()
        except Exception:
            continue
        fnv = np.array([fn.x, fn.y, fn.z])
        c = f.Center()
        if abs(abs(fnv @ n) - 1) < 1e-4 and abs((np.array([c.x, c.y, c.z]) - p0) @ n) < 1e-3:
            rings = []
            for w in [f.outerWire()] + f.innerWires():
                pts = []
                for e in w.Edges():
                    ps = e.positions(np.linspace(0, 1, max(2, int(e.Length() / 0.3) + 2)))
                    pts += [(np.array([q.x, q.y, q.z]) @ X, np.array([q.x, q.y, q.z]) @ Y) for q in ps]
                rings.append(pts)
            polys.append(rings)
    return polys


# --------------------------------------------------------------------------
class Sheet:
    """Аркуш A3 (420×297), одиниці SVG — мм."""

    def __init__(self, title, part, material, scale_txt, sheet_no, sheets, w=420, h=297, notes=None, mass=None):
        self.w, self.h = w, h
        self.el = []
        self.title, self.part, self.material = title, part, material
        self.scale_txt, self.sheet_no, self.sheets = scale_txt, sheet_no, sheets
        self.notes = notes or []
        self.mass = mass

    # ---- примітиви ----
    def line(self, a, b, cls="v"):
        self.el.append(f'<line class="{cls}" x1="{a[0]:.3f}" y1="{a[1]:.3f}" x2="{b[0]:.3f}" y2="{b[1]:.3f}"/>')

    def poly(self, pts, cls="v"):
        if len(pts) < 2:
            return
        dd = " ".join(f"{x:.3f},{y:.3f}" for x, y in pts)
        self.el.append(f'<polyline class="{cls}" points="{dd}"/>')

    def text(self, p, s, size=3.2, anchor="middle", rot=0, cls="t", weight="normal"):
        tr = f' transform="rotate({rot} {p[0]:.3f} {p[1]:.3f})"' if rot else ""
        s = s.replace("&", "&amp;").replace("<", "&lt;")
        self.el.append(f'<text class="{cls}" x="{p[0]:.3f}" y="{p[1]:.3f}" font-size="{size}" '
                       f'text-anchor="{anchor}" font-weight="{weight}"{tr}>{s}</text>')

    def arrow(self, tip, direction, size=2.6):
        d = np.array(direction, float)
        d /= np.linalg.norm(d)
        n = np.array([-d[1], d[0]])
        a = np.array(tip) - d * size + n * size * 0.28
        b = np.array(tip) - d * size - n * size * 0.28
        self.el.append(f'<polygon class="arr" points="{tip[0]:.3f},{tip[1]:.3f} {a[0]:.3f},{a[1]:.3f} {b[0]:.3f},{b[1]:.3f}"/>')

    # ---- вид ----
    def view(self, shape, view, origin, scale, hidden=True, label=None, section=None, label_dy=22):
        """section = (cut_shape, plane_point, normal) — штрихування площини розрізу."""
        V = View(self, view, origin, scale)
        vis, hid = hlr(shape, view, hidden)
        if section is not None:
            cut_shape, pp, nn = section
            for rings in section_faces(cut_shape, pp, nn, view):
                dpath = ""
                for ring in rings:
                    pts = [V.p(u, v) for u, v in ring]
                    dpath += "M " + " L ".join(f"{x:.3f},{y:.3f}" for x, y in pts) + " Z "
                self.el.append(f'<path class="hatch" d="{dpath}" fill-rule="evenodd"/>')
        for pl in hid:
            self.poly([V.p(u, v) for u, v in pl], "h")
        for pl in vis:
            self.poly([V.p(u, v) for u, v in pl], "v")
        if label:
            bb = shape.BoundingBox()
            cs = np.array([[x, y, z] for x in (bb.xmin, bb.xmax) for y in (bb.ymin, bb.ymax) for z in (bb.zmin, bb.zmax)])
            _, Xb, Yb = basis(view)
            us, vs = cs @ Xb, cs @ Yb
            px = origin[0] + scale * (us.min() + us.max()) / 2
            py = origin[1] - scale * vs.min() + label_dy
            self.text((px, py), label, 4.0, weight="bold")
        return V

    # ---- рамка та основний напис ----
    def frame(self):
        w, h = self.w, self.h
        self.el.append(f'<rect class="frame" x="20" y="5" width="{w - 25}" height="{h - 10}"/>')
        x0, y0 = w - 5 - 185, h - 5 - 55
        rows = [(0, 10), (10, 10), (20, 10), (30, 10), (40, 15)]
        self.el.append(f'<rect class="frame" x="{x0}" y="{y0}" width="185" height="55"/>')
        for yy in (10, 20, 30, 40):
            self.line((x0, y0 + yy), (x0 + 185, y0 + yy), "thin")
        self.line((x0 + 120, y0), (x0 + 120, y0 + 40), "thin")
        self.text((x0 + 3, y0 + 7), "STICKBOX 01 Monolith — " + self.title, 4.2, "start", weight="bold")
        self.text((x0 + 3, y0 + 17), self.part, 3.6, "start")
        self.text((x0 + 3, y0 + 27), "Матеріал: " + self.material, 3.0, "start")
        self.text((x0 + 3, y0 + 37), "Розміри — мм. Загальні допуски — див. примітки.", 2.8, "start")
        self.text((x0 + 123, y0 + 7), f"Масштаб {self.scale_txt}", 3.2, "start")
        self.text((x0 + 123, y0 + 17), f"Аркуш {self.sheet_no} / {self.sheets}", 3.2, "start")
        self.text((x0 + 123, y0 + 27), "Формат A3", 3.2, "start")
        if self.mass:
            self.text((x0 + 123, y0 + 37), self.mass, 3.0, "start")
        self.text((x0 + 3, y0 + 46), "Ревізія v3.3 (NFC-мітка й знак NFC зверху; знак — літера I напису) · 1-й кут (ISO E)", 2.8, "start")
        self.text((x0 + 3, y0 + 52), "Згенеровано з параметричної CAD-моделі; перед виробництвом — перевірка прототипу", 2.6, "start")
        ny = 12
        for n in self.notes:
            self.text((25, ny), n, 2.9, "start")
            ny += 4.6

    def svg(self):
        self.frame()
        css = """
        .v{fill:none;stroke:#111;stroke-width:0.35;stroke-linecap:round;stroke-linejoin:round}
        .h{fill:none;stroke:#777;stroke-width:0.18;stroke-dasharray:1.6 0.8}
        .c{fill:none;stroke:#555;stroke-width:0.15;stroke-dasharray:6 1 1 1}
        .d{fill:none;stroke:#1a5fb4;stroke-width:0.18}
        .thin{fill:none;stroke:#111;stroke-width:0.25}
        .frame{fill:none;stroke:#111;stroke-width:0.6}
        .arr{fill:#1a5fb4;stroke:none}
        .t{font-family:'Inter','DejaVu Sans',sans-serif;fill:#111}
        .dt{font-family:'Inter','DejaVu Sans',sans-serif;fill:#1a5fb4}
        .hatch{fill:url(#hatch);stroke:none}
        .sec{fill:none;stroke:#111;stroke-width:0.7}
        """
        defs = ('<defs><pattern id="hatch" patternUnits="userSpaceOnUse" width="1.6" height="1.6" '
                'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="1.6" stroke="#444" stroke-width="0.16"/>'
                '</pattern></defs>')
        body = "\n".join(self.el)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}mm" height="{self.h}mm" '
                f'viewBox="0 0 {self.w} {self.h}"><style>{css}</style>{defs}'
                f'<rect x="0" y="0" width="{self.w}" height="{self.h}" fill="white"/>{body}</svg>')


class View:
    def __init__(self, sheet, view, origin, scale):
        self.s, self.view, self.o, self.k = sheet, view, origin, scale
        _, self.X, self.Y = basis(view)

    def p(self, u, v):
        return (self.o[0] + self.k * u, self.o[1] - self.k * v)

    def uv(self, pt3):
        q = np.array(pt3, float)
        return q @ self.X, q @ self.Y

    def P(self, pt3):
        return self.p(*self.uv(pt3))

    # розмір між двома 3D-точками; dir 'h' або 'v'; off — відступ розмірної лінії на аркуші (мм)
    def dim(self, a3, b3, orient="h", off=8.0, txt=None, size=3.0):
        a, b = np.array(self.P(a3)), np.array(self.P(b3))
        val = abs((np.array(b3) - np.array(a3)) @ (self.X if orient == "h" else self.Y))
        t = txt if txt is not None else f"{val:.1f}".rstrip("0").rstrip(".")
        S = self.s
        if orient == "h":
            y = min(a[1], b[1]) - off if off > 0 else max(a[1], b[1]) - off
            S.line((a[0], a[1]), (a[0], y + (-1.5 if off > 0 else 1.5)), "d")
            S.line((b[0], b[1]), (b[0], y + (-1.5 if off > 0 else 1.5)), "d")
            S.line((a[0], y), (b[0], y), "d")
            l, r = sorted((a[0], b[0]))
            S.arrow((l, y), (-1, 0))
            S.arrow((r, y), (1, 0))
            S.text(((a[0] + b[0]) / 2, y - 1.0), t, size, cls="dt")
        else:
            x = max(a[0], b[0]) + off if off > 0 else min(a[0], b[0]) + off
            S.line((a[0], a[1]), (x + (1.5 if off > 0 else -1.5), a[1]), "d")
            S.line((b[0], b[1]), (x + (1.5 if off > 0 else -1.5), b[1]), "d")
            S.line((x, a[1]), (x, b[1]), "d")
            tp, bt = sorted((a[1], b[1]))
            S.arrow((x, tp), (0, -1))
            S.arrow((x, bt), (0, 1))
            S.text((x - 1.0, (a[1] + b[1]) / 2), t, size, rot=-90, cls="dt")

    def leader(self, pt3, dx, dy, txt, size=3.0):
        a = np.array(self.P(pt3))
        b = a + np.array([dx, dy])
        S = self.s
        S.line(a, b, "d")
        S.arrow(tuple(a), tuple(a - b))
        L = max(len(txt) * size * 0.52, 6)
        e = b + np.array([L if dx >= 0 else -L, 0])
        S.line(b, e, "d")
        S.text(((b[0] + e[0]) / 2, b[1] - 1.0), txt, size, cls="dt")

    def center_v(self, pt3, half):
        x, y = self.P(pt3)
        self.s.line((x, y - half), (x, y + half), "c")

    def center_h(self, pt3, half):
        x, y = self.P(pt3)
        self.s.line((x - half, y), (x + half, y), "c")


def clip_begin(sheet, cid, cx, cy, r):
    sheet.el.append(f'<clipPath id="{cid}"><circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}"/></clipPath><g clip-path="url(#{cid})">')


def clip_end(sheet, cx, cy, r, label):
    sheet.el.append("</g>")
    sheet.el.append(f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" fill="none" stroke="#111" stroke-width="0.35"/>')
    sheet.text((cx, cy + r + 6), label, 3.6, weight="bold")


def table(sheet, x, y, cols, rows, widths, size=2.8, rh=5.2):
    tw = sum(widths)
    sheet.el.append(f'<rect class="thin" x="{x}" y="{y}" width="{tw}" height="{rh * (len(rows) + 1)}"/>')
    cx = x
    for w, c in zip(widths, cols):
        sheet.text((cx + 1.2, y + rh - 1.5), c, size, "start", weight="bold")
        cx += w
    for i, r in enumerate(rows):
        yy = y + rh * (i + 1)
        sheet.line((x, yy), (x + tw, yy), "thin")
        cx = x
        for w, c in zip(widths, r):
            sheet.text((cx + 1.2, yy + rh - 1.5), str(c), size, "start")
            cx += w
    cx = x
    for w in widths[:-1]:
        cx += w
        sheet.line((cx, y), (cx, y + rh * (len(rows) + 1)), "thin")
