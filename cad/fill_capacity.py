"""Підставляє результати симуляції місткості (reports/capacity_sim.json) у документацію замість токенів {{...}}."""
import json, os, glob

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
r = json.load(open(f"{ROOT}/reports/capacity_sim.json"))
ns = [x["no_shake"] for x in r["runs"]]
ws = [x["inside"] for x in r["runs"]]
T = {
    "{{NRUNS}}": str(len(r["runs"])),
    "{{CAP_NS}}": f"{sum(ns) / len(ns):.0f}",
    "{{CAP_WS}}": f"{sum(ws) / len(ws):.0f}",
    "{{CAP_NS_RANGE}}": f"{min(ns)}–{max(ns)}",
    "{{CAP_WS_RANGE}}": f"{min(ws)}–{max(ws)}",
}
for f in [f"{ROOT}/README.md"] + glob.glob(f"{ROOT}/docs/*.md"):
    s = open(f).read()
    s2 = s
    for k, val in T.items():
        s2 = s2.replace(k, val)
    if s2 != s:
        open(f, "w").write(s2)
        print("filled", os.path.basename(f))
print(T)
