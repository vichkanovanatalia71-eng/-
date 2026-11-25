"""Пакет для виробника силіконових форм: ТЗ (PDF) + оснащення (STEP/STL/3MF) + довідкові файли → ZIP.

Запуск: python make_handoff.py   (після build_all.py, make_drawings.py і рендерів)
Результат: handoff/STICKBOX_01_v3.7.1_molds_handoff.zip і handoff/00_TZ_silicone_molds_v3.7.1.pdf
"""
import os
import sys
import zipfile

import markdown

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "handoff")
REV = "v3.7.1"
ZIP = os.path.join(OUT, f"STICKBOX_01_{REV}_molds_handoff.zip")
PDF = os.path.join(OUT, f"00_TZ_silicone_molds_{REV}.pdf")
PDF_FRAME = os.path.join(OUT, f"01_mold_frame_calc_{REV}.pdf")   # розбірний каркас: розрахунок і використання
PDF_TESTS = os.path.join(OUT, f"02_virtual_casting_tests_{REV}.pdf")   # віртуальне лиття: перевірка файлів оснащення

TOOL = ["T01_body_master", "T02a_body_frame_front", "T02b_body_frame_back", "T03_body_base_plate", "T04_finger_stiffener",
        "T05_core_spine_bridge", "T06_core_mold", "T07_ref_cast_part_core_silicone", "T08_lid_master",
        "T09a_lid_frame_front", "T09b_lid_frame_back", "T10_lid_base_plate",
        "T13_gauge_hole_go_7p90", "T14_gauge_stick_heets", "T17_stiffener_holder"]
TOOL_REF = ["T15_ref_outer_silicone_mold_body", "T16_ref_silicone_mold_lid"]
PRODUCT = ["exports/step/00_STICKBOX_01_Monolith_assembly.step", "exports/step/01_body_concrete.step",
           "exports/step/02_lid_concrete.step", "drawings/STICKBOX_01_Monolith_drawings_A3.pdf"]
RENDERS = ["20_tooling_body_casting_section.png", "21_tooling_body_exploded.png", "22_tooling_lid_section.png",
           "01_hero_front_left.png", "07_exploded.png", "13_lid_oring.png", "26_lid_tab_back.png", "27_notch_tab_from_below.png",
           "28_mold_frame_open_pour.png", "29_mold_frame_section_x0.png",
           "34_virtual_casting_sections.png", "35_cast_vs_design.png", "36_joint_details.png", "37_lid_casting.png"]

CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm; }
body { font-family: 'DejaVu Sans', 'Liberation Sans', Arial, sans-serif; font-size: 9.6pt; line-height: 1.42; color: #1d1d1f; }
h1 { font-size: 17pt; margin: 0 0 6pt; letter-spacing: -0.2pt; }
h2 { font-size: 12.5pt; margin: 16pt 0 5pt; padding-bottom: 2pt; border-bottom: 1.2pt solid #1f8f86; break-after: avoid; }
h3 { font-size: 10.8pt; margin: 11pt 0 4pt; break-after: avoid; }
p { margin: 4pt 0; }
ul, ol { margin: 3pt 0 3pt 0; padding-left: 16pt; }
li { margin: 1.5pt 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 8pt; font-size: 8.8pt; break-inside: auto; }
tr { break-inside: avoid; }
th, td { border: 0.6pt solid #9a9a9a; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #eef4f3; font-weight: bold; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.6pt; background: #f2f2f2; padding: 0 2pt; }
hr { border: 0; border-top: 0.6pt solid #bbb; margin: 8pt 0; }
strong { color: #000; }
img { max-width: 100%; display: block; margin: 6pt auto; break-inside: avoid; }
"""


def build_pdf(src="13_mold_maker_brief.md", dst=PDF, title="ТЗ на силіконові форми"):
    md = open(os.path.join(ROOT, "docs", src), encoding="utf-8").read()
    # Python-Markdown суворіший за GitHub: вкладені списки — 4 пробіли, перед списком — порожній рядок
    import re
    lines, out = md.split("\n"), []
    is_item = lambda t: bool(re.match(r"^\s*(\* |\d+\. )", t))
    for ln in lines:
        m_ = re.match(r"^( {2,3})(\* |\d+\. )", ln)
        if m_:
            ln = "    " + ln[len(m_.group(1)):]
        if is_item(ln) and out and out[-1].strip() and not is_item(out[-1]) and not out[-1].startswith((" ", "\t")):
            out.append("")
        out.append(ln)
    md = "\n".join(out)
    body = markdown.markdown(md, extensions=["tables", "sane_lists"])
    html = f"<!doctype html><html lang='uk'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
    tmp = os.path.join(OUT, "_tz.html")
    open(tmp, "w", encoding="utf-8").write(html)
    # PDF друкує Chromium через Node-Playwright (той самий, що й рендери)
    import json, subprocess
    footer = ("<div style='font-size:7pt;width:100%;text-align:center;color:#777'>"
              f"STICKBOX 01 Monolith · {title} · {REV} · "
              "<span class='pageNumber'></span>/<span class='totalPages'></span></div>")
    js = ("const { chromium } = require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage();"
          f"await p.goto({json.dumps('file://' + tmp)});"
          f"await p.pdf({{path:{json.dumps(dst)},format:'A4',printBackground:true,displayHeaderFooter:true,"
          f"headerTemplate:'<span></span>',footerTemplate:{json.dumps(footer)},"
          "margin:{top:'16mm',bottom:'16mm',left:'15mm',right:'15mm'}});await b.close();})();")
    subprocess.run(["node", "-e", js], check=True, cwd=os.path.join(ROOT, "cad", "render"))
    os.remove(tmp)


def build_zip():
    missing = []
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(PDF, os.path.basename(PDF))
        z.write(PDF_FRAME, os.path.basename(PDF_FRAME))
        z.write(PDF_TESTS, os.path.basename(PDF_TESTS))
        for n in TOOL:
            for ext, folder in (("step", "01_tooling_STEP"), ("stl", "02_tooling_print_STL"), ("3mf", "03_tooling_print_3MF")):
                src = os.path.join(ROOT, "tooling", ext, f"{n}.{ext}")
                if os.path.exists(src):
                    z.write(src, f"{folder}/{n}.{ext}")
                elif ext == "step":
                    missing.append(src)
        for n in TOOL_REF:
            src = os.path.join(ROOT, "tooling", "step", f"{n}.step")
            if os.path.exists(src):
                z.write(src, f"01_tooling_STEP/reference/{n}.step")
            else:
                missing.append(src)
        for rel in PRODUCT:
            src = os.path.join(ROOT, rel)
            if os.path.exists(src):
                z.write(src, f"04_reference_product/{os.path.basename(rel)}")
            else:
                missing.append(src)
        for r in RENDERS:
            src = os.path.join(ROOT, "renders", r)
            if os.path.exists(src):
                z.write(src, f"05_renders/{r}")
            else:
                missing.append(src)
    if missing:
        print("MISSING:", *missing, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    build_pdf()
    build_pdf("14_mold_frame.md", PDF_FRAME, "Розбірний каркас форм")
    build_pdf("15_virtual_casting_tests.md", PDF_TESTS, "Віртуальне лиття і перевірки")
    build_zip()
    with zipfile.ZipFile(ZIP) as z:
        n, size = len(z.infolist()), sum(i.file_size for i in z.infolist())
    print(f"ok {os.path.relpath(PDF, ROOT)}  {os.path.relpath(ZIP, ROOT)}: {n} файлів, "
          f"{size / 1e6:.1f} МБ → {os.path.getsize(ZIP) / 1e6:.1f} МБ")
