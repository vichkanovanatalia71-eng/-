"""Рисунки віртуального лиття: перерізи оснащення з бетоном (положення лиття — догори дном) і виливок проти проєкту."""
import math

import numpy as np
import cadquery as cq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from shapely.geometry import Polygon
from shapely.ops import unary_union

from . import params as p
from . import parts as P
from . import casting_check as CC
from .params import v

d = p.derived()
K = CC.K

COL = {
    "frame": ("#55657a", "Каркас T02a/T02b (PETG)"),
    "T15": ("#7fcdc3", "Силікон зовнішньої форми T15"),
    "T04": ("#2f3a44", "Ребро «пальця» T04"),
    "T07": ("#f3b562", "Силіконова чашка сердечника T07"),
    "T05": ("#9c6b3c", "Хребет і міст T05 (PETG)"),
    "C": ("#bdb6ab", "Бетон (виливок)"),
    "T16": ("#7fcdc3", "Силікон форми кришки T16"),
    "frameL": ("#55657a", "Каркас T09a/T09b"),
    "LC": ("#bdb6ab", "Бетон кришки"),
}


def _wire_pts(w, defl=0.01):
    from OCP.BRepAdaptor import BRepAdaptor_CompCurve
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    c = BRepAdaptor_CompCurve(w.wrapped)
    q = GCPnts_QuasiUniformDeflection(c, defl)
    return [c.Value(q.Parameter(i)) for i in range(1, q.NbPoints() + 1)]


def section(shape, axis, val, defl=0.01):
    """Переріз тіла площиною axis = val → shapely (координати: для 'y' — (x, z), для 'x' — (y, z))."""
    n = (0, 1, 0) if axis == "y" else (1, 0, 0)
    base = (0, val, 0) if axis == "y" else (val, 0, 0)
    pl = cq.Face.makePlane(800, 800, basePnt=base, dir=n)
    try:
        sec = shape.intersect(pl)
    except Exception:
        return Polygon()
    pr = (lambda q: (q.X(), q.Z())) if axis == "y" else (lambda q: (q.Y(), q.Z()))
    polys = []
    for f in sec.Faces():
        try:
            outer = [pr(q) for q in _wire_pts(f.outerWire(), defl)]
            holes = [[pr(q) for q in _wire_pts(w, defl)] for w in f.innerWires()]
            pg = Polygon(outer, holes).buffer(0)
            if not pg.is_empty:
                polys.append(pg)
        except Exception:
            continue
    return unary_union(polys) if polys else Polygon()


def _fill(ax, geom, color, flip, scale=1.0, **kw):
    if geom.is_empty:
        return
    gs = getattr(geom, "geoms", [geom])
    for g in gs:
        if g.geom_type != "Polygon":
            continue
        x, y = np.array(g.exterior.xy)
        path = [(x / scale, (-y if flip else y) / scale)]
        from matplotlib.path import Path
        from matplotlib.patches import PathPatch
        verts, codes = [], []
        for ring in [g.exterior] + list(g.interiors):
            xx, yy = np.array(ring.xy)
            yy = -yy if flip else yy
            pts = np.c_[xx / scale, yy / scale]
            verts += pts.tolist()
            codes += [Path.MOVETO] + [Path.LINETO] * (len(pts) - 2) + [Path.CLOSEPOLY]
        ax.add_patch(PathPatch(Path(verts, codes), facecolor=color, edgecolor="#222", lw=0.35, **kw))


def body_tool_sections(planes, title, path, zoom=None):
    """Перерізи оснащення корпусу з бетоном у положенні лиття (вісь z виробу — вниз)."""
    inside, outside, z_open = CC.cast_body()
    shapes = [("frame", CC.tool("T02a")), ("frame", CC.tool("T02b")), ("T15", CC.tool("T15")), ("T04", CC.tool("T04")),
              ("T05", CC.tool("T05")), ("T07", CC.tool("T07")), ("C", inside[0])]
    n = len(planes)
    cols = 2 if n > 1 else 1
    rows = math.ceil(n / cols)
    fig, axs = plt.subplots(rows, cols, figsize=(8.2 * cols, 6.0 * rows), dpi=150)
    axs = np.atleast_1d(axs).ravel()
    for ax, (axis, val, sub, lim) in zip(axs, planes):
        for key, sh in shapes:
            _fill(ax, section(sh, axis, val * K), COL[key][0], True)
        ax.set_aspect("equal")
        if lim:
            ax.set_xlim(lim[0], lim[1])
            ax.set_ylim(lim[2], lim[3])
        else:
            ax.autoscale_view()
        ax.axhline(-z_open, color="#c0392b", lw=0.8, ls="--")
        ax.set_title(sub, fontsize=10)
        ax.set_xlabel(("x" if axis == "y" else "y") + ", мм (форма, масштаб K)", fontsize=8)
        ax.set_ylabel("висота в положенні лиття, мм", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.text(0.01, 0.995, "відкрита грань = рівень заливки (червона лінія)", transform=ax.transAxes, fontsize=7,
                va="top", color="#c0392b")
    for ax in axs[n:]:
        ax.axis("off")
    keys = ["frame", "T15", "T04", "T07", "T05", "C"]
    fig.legend(handles=[Patch(facecolor=COL[k][0], edgecolor="#222", label=COL[k][1]) for k in keys],
               loc="lower center", ncol=3, fontsize=8, frameon=False)
    fig.suptitle(title, fontsize=12)
    fig.tight_layout(rect=(0, 0.09, 1, 0.97))
    fig.savefig(path)
    plt.close(fig)


def cast_vs_design(planes, F, B, title, path, LF=None, LB=None):
    """Готовий виливок (після усадки 1/K і шліфування) — заливка; проєкт — червоний контур."""
    n = len(planes)
    cols = 2 if n > 1 else 1
    rows = math.ceil(n / cols)
    fig, axs = plt.subplots(rows, cols, figsize=(8.2 * cols, 5.6 * rows), dpi=150)
    axs = np.atleast_1d(axs).ravel()
    for ax, (axis, val, sub, lim) in zip(axs, planes):
        sF, sB = section(F, axis, val), section(B, axis, val)
        _fill(ax, sF, COL["C"][0], False)
        if LF is not None:
            _fill(ax, section(LF, axis, val), "#d8d2c8", False)
        for g in getattr(sB, "geoms", [sB]):
            if g.geom_type == "Polygon":
                for ring in [g.exterior] + list(g.interiors):
                    xx, yy = ring.xy
                    ax.plot(xx, yy, color="#c0392b", lw=0.7, ls=(0, (4, 2)))
        if LB is not None:
            sL = section(LB, axis, val)
            for g in getattr(sL, "geoms", [sL]):
                if g.geom_type == "Polygon":
                    for ring in [g.exterior] + list(g.interiors):
                        xx, yy = ring.xy
                        ax.plot(xx, yy, color="#c0392b", lw=0.7, ls=(0, (4, 2)))
        ax.set_aspect("equal")
        if lim:
            ax.set_xlim(lim[0], lim[1])
            ax.set_ylim(lim[2], lim[3])
        else:
            ax.autoscale_view()
        ax.set_title(sub, fontsize=10)
        ax.tick_params(labelsize=7)
        ax.set_xlabel(("x" if axis == "y" else "y") + ", мм (виріб)", fontsize=8)
        ax.set_ylabel("z, мм (виріб)", fontsize=8)
    for ax in axs[n:]:
        ax.axis("off")
    hand = [Patch(facecolor=COL["C"][0], edgecolor="#222", label="Виливок корпусу з оснащення (після усадки й шліфування)"),
            plt.Line2D([], [], color="#c0392b", ls=(0, (4, 2)), label="Проєктний контур (CAD виробу)")]
    if LF is not None:
        hand.insert(1, Patch(facecolor="#d8d2c8", edgecolor="#222", label="Виливок кришки з форми T16"))
    fig.legend(handles=hand, loc="lower center", ncol=3, fontsize=8, frameon=False)
    fig.suptitle(title, fontsize=12)
    fig.tight_layout(rect=(0, 0.09, 1, 0.97))
    fig.savefig(path)
    plt.close(fig)


def lid_tool_section(path):
    inside, z_open = CC.cast_lid()
    shapes = [("frameL", CC.tool("T09a")), ("frameL", CC.tool("T09b")), ("T16", CC.tool("T16")), ("LC", inside[0])]
    fig, axs = plt.subplots(1, 2, figsize=(16.4, 4.6), dpi=150)
    for ax, (axis, val, sub) in zip(axs, (("y", 1.0, "Переріз y = 1 (уздовж кришки)"), ("x", 0.0, "Переріз x = 0 (через язичок)"))):
        for key, sh in shapes:
            _fill(ax, section(sh, axis, val * K), COL[key][0], True)
        ax.axhline(-z_open, color="#c0392b", lw=0.8, ls="--")
        ax.set_aspect("equal")
        ax.autoscale_view()
        ax.set_title(sub, fontsize=10)
        ax.tick_params(labelsize=7)
    fig.legend(handles=[Patch(facecolor=COL[k][0], edgecolor="#222", label=COL[k][1]) for k in ("frameL", "T16", "LC")],
               loc="lower center", ncol=3, fontsize=8, frameon=False)
    fig.suptitle("Віртуальне лиття кришки у формі T16 (догори дном; червона лінія — рівень заливки)", fontsize=12)
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(path)
    plt.close(fig)
