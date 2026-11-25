"""STICKBOX 01 — повний набір перевірок «чи вийде повноцінний виріб».

Запуск: python run_tests.py   (після build_all.py — він експортує STEP оснащення і пише reports/analysis.json)

1. Віртуальне лиття з файлів оснащення (stickbox/casting_check.py) → reports/casting_verification.json
2. Перевірки моделі виробу й каркаса форм (reports/analysis.json, reports/capacity_sim.json)
3. Критерії PASS / WARN / FAIL → reports/test_results.json і docs/15_virtual_casting_tests.md, рисунки renders/30–33
Вихід з кодом 1, якщо є хоч один FAIL.
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, ".."))

from stickbox import params as p, casting_check as CC  # noqa: E402
from stickbox.params import v  # noqa: E402

d = p.derived()
REV = "v3.7.1"


def checks(C, A, cap):
    out = []

    def add(group, cid, name, value, crit, ok, warn=False, note=""):
        st = "PASS" if ok else ("WARN" if warn else "FAIL")
        out.append(dict(group=group, id=cid, name=name, value=value, criterion=crit, status=st, note=note))

    # ---------------- A. Оснащення в збірці
    a = C["assembly"]
    add("A. Оснащення в положенні лиття", "A1", "Усі STEP-файли оснащення — коректні тіла",
        f"{sum(a['valid'].values())} / {len(a['valid'])}", "усі valid", all(a["valid"].values()))
    add("A. Оснащення в положенні лиття", "A2", "Сердечник торкається форми лише в задуманих місцях",
        "; ".join(f"{c['where']}: {c['volume_mm3']} мм³" for c in a["core_outer_contacts"]) or "контактів немає",
        "лише натяг вкладки виїмки і телескопічний стик шпильки Ø8 (кільце 0.05 мм)",
        not a["core_outer_unexpected"] and all(c["volume_mm3"] < 90 for c in a["core_outer_contacts"]),
        note="натяг вкладки 1.0 мм у стінку форми — задуманий (притискає вкладку, щоб не було облою)")
    ov = a["overlap_mm3"]
    add("A. Оснащення в положенні лиття", "A3", "Хребет, ребро, каркас не врізаються в силікон і одне в одне",
        ", ".join(f"{OVN.get(k, k)} {v_}" for k, v_ in ov.items()) + " мм³", "0", all((v_ or 0) < 0.01 for v_ in ov.values()))
    add("A. Оснащення в положенні лиття", "A4", "Отвори мосту під шпильки M5 співвісні з вушками каркаса",
        f"{a['rod_holes']['max_misalignment_mm']} мм ({len(a['rod_holes']['bridge'])} отвори)", "≤ 0.01 мм",
        a["rod_holes"]["max_misalignment_mm"] is not None and a["rod_holes"]["max_misalignment_mm"] <= 0.01 and len(a["rod_holes"]["bridge"]) == 4)
    add("A. Оснащення в положенні лиття", "A5", "Ніжки мосту лежать на торцях вушок каркаса",
        f"зазор {a['bridge_to_frame_gap_mm']} мм", "0 (контакт без перекриття)", a["bridge_to_frame_gap_mm"] <= 0.01)
    add("A. Оснащення в положенні лиття", "A6", "Ребро T04 повністю в силіконі (бетону не торкається)",
        f"{C['forming_T04_min_dist_mm']} мм до бетону", "≥ 4.0 мм", C["forming_T04_min_dist_mm"] >= 4.0)

    # ---------------- B. Виливок корпусу
    b = C["body_casting"]
    add("B. Виливок корпусу проти проєкту", "B1", "Бетон — одне суцільне тіло, з'єднане з площиною заливки",
        f"{b['concrete_solids']} тіло", "1", b["concrete_solids"] == 1)
    sv = b.get("sealed_voids", [])
    add("B. Виливок корпусу проти проєкту", "B2", "Замкнені порожнини в оснащенні лежать поза виробом",
        f"{len(sv)} шт., у виробі {sum(q['overlap_with_product_mm3'] for q in sv):.3f} мм³", "0 мм³ у виробі",
        all(q["overlap_with_product_mm3"] < 0.01 for q in sv),
        note="; ".join(f"{q['where']} {q['volume_mm3']} мм³" for q in sv))
    miss = b["finished"]["missing"]["total_mm3"]
    add("B. Виливок корпусу проти проєкту", "B3", "Бетону ніде не бракує (недоливи, «з'їдені» елементи)",
        f"{miss} мм³", "≤ 0.5 мм³", miss <= 0.5)
    ex = b["finished"]["extra"]["pieces"]
    notch = [q for q in ex if q["where"] == "виїмка язичка кришки (задня грань)"]
    other = [q for q in ex if q not in notch]
    add("B. Виливок корпусу проти проєкту", "B4", "Зайвого бетону немає (облой, «пера», заповнені щілини)",
        "; ".join(f"{q['where']}: {q['volume_mm3']} мм³" for q in other) or "немає",
        "0 поза задокументованою доводкою", not other)
    if notch:
        add("B. Виливок корпусу проти проєкту", "B5", "Кромки виїмки язичка — з форми гострі, R1 дає доводка",
            f"{notch[0]['volume_mm3']} мм³ на 3 кромках", "≤ 6 мм³ і притуплення в техкарті (крок 11)",
            notch[0]["volume_mm3"] <= 6.0, note="вкладка сердечника — прямокутна і з натягом входить у стінку форми")
    fv = b["finished"]
    add("B. Виливок корпусу проти проєкту", "B6", "Об'єм бетону готового корпусу",
        f"{fv['volume_ml']} мл (проєкт {fv['design_volume_ml']})", "± 0.1 %",
        abs(fv["volume_ml"] - fv["design_volume_ml"]) <= 0.001 * fv["design_volume_ml"])
    dv = C["deviation_body"]
    worst = max(dv["cast_to_design"]["p999_mm"], dv["design_to_cast"]["p999_mm"])
    add("B. Виливок корпусу проти проєкту", "B7", "Відхилення поверхні виливка від проєкту (99.9% точок)",
        f"{worst} мм (макс. {max(dv['cast_to_design']['max_mm'], dv['design_to_cast']['max_mm'])} мм)",
        "≤ 0.05 мм; більші — лише на кромках виїмки", worst <= 0.05 and all(
            k == "виїмка язичка кришки (задня грань)" for k in list(dv["cast_to_design"]["clusters_over_0p05"]) + list(dv["design_to_cast"]["clusters_over_0p05"])))

    # ---------------- C. Розміри на виливку
    m, md = C["measure"], C["measure_design"]
    tn = math.tan(math.radians(v(p.DRAFT_CAV)))
    soc_ok = all(abs(q["width_x"] - r["width_x"]) <= 0.02 and abs(q["depth_y"] - r["depth_y"]) <= 0.02 for q, r in zip(m["socket"], md["socket"]))
    add("C. Розміри, виміряні на виливку", "C1", "Гніздо кришки (прямокутне) на висотах 0.5 / 5.5 / 8.5 / 13.5",
        " · ".join(f"{q['width_x']:.2f}×{q['depth_y']:.2f}" for q in m["socket"]),
        f"як у проєкті ±0.02 (110 × 79.5 біля низу, ухил {v(p.DRAFT_CAV)}°)", soc_ok)
    add("C. Розміри, виміряні на виливку", "C2", "Стеля гнізда (низ колонки тримача) над кришкою",
        f"z = {m['socket_roof_z']}", f"{d['z_sock']} ± 0.02 (кришка 14.0 → зазор 0.5)", abs(m["socket_roof_z"] - d["z_sock"]) <= 0.02)
    rv = C["reservoir_ml"]
    add("C. Розміри, виміряні на виливку", "C3", "Резервуар над кришкою (повітря)",
        f"{rv['cast']} мл (проєкт {rv['design']})", "± 0.5 %", abs(rv["cast"] - rv["design"]) <= 0.005 * rv["design"])
    wv = C["water_fill_ml"]
    add("C. Розміри, виміряні на виливку", "C4", "Вода в закритому виробі до краю воронки",
        f"{wv['cast']} мл (проєкт {wv['design']})", "± 0.5 %", abs(wv["cast"] - wv["design"]) <= 0.005 * wv["design"])
    r_ = m["reservoir"]
    add("C. Розміри, виміряні на виливку", "C5", "Висота резервуара (стеля купола)",
        f"{r_['ceiling_z_main']} / {r_['ceiling_z_arm']} (основна частина / плече)",
        f"як у проєкті ±0.02 ({md['reservoir']['ceiling_z_main']} / {md['reservoir']['ceiling_z_arm']})",
        abs(r_["ceiling_z_main"] - md["reservoir"]["ceiling_z_main"]) <= 0.02 and abs(r_["ceiling_z_arm"] - md["reservoir"]["ceiling_z_arm"]) <= 0.02)
    pk, pkd = m["pocket"], md["pocket"]
    add("C. Розміри, виміряні на виливку", "C6", "Кишеня девайса: дно і глибина",
        f"дно z = {pk['floor_z']}, глибина {pk['depth']}", f"{d['pocket_floor']} / {pk['design_depth']} ± 0.02",
        abs(pk["floor_z"] - d["pocket_floor"]) <= 0.02)
    pw_ok = all(abs(q["x"] - r["x"]) <= 0.02 and abs(q["y_back_half"] - r["y_back_half"]) <= 0.02 for q, r in zip(pk["widths"], pkd["widths"]))
    add("C. Розміри, виміряні на виливку", "C7", "Кишеня девайса: ширина на 3 висотах (низ / середина / верх)",
        " · ".join(f"{q['x']:.2f}" for q in pk["widths"]) + " мм", "як у проєкті ± 0.02 (ухил 0.5°)", pw_ok)
    hd = m["hole"]["diameters"]
    add("C. Розміри, виміряні на виливку", "C8", "Отвір для стіків Ø8 (4 напрямки)",
        " / ".join(f"{q:.3f}" for q in hd), "8.00 ± 0.02", all(abs(q - v(p.HOLE_D)) <= 0.02 for q in hd))
    prof = m["hole_exit_profile"]
    lip = [q for q in prof if q["z"] < m["hole"]["straight_from_z"] and q["radius"] < v(p.FLARE_STEP_D) / 2 - 0.02]
    add("C. Розміри, виміряні на виливку", "C9", "Вихід отвору в резервуар: уступ розтруба без бетонного «пера»",
        "радіуси нижче уступу: " + ", ".join(f"{q['radius']:.2f}" for q in prof if q["z"] < m["hole"]["straight_from_z"]),
        f"≥ {v(p.FLARE_STEP_D) / 2:.2f} (Ø{v(p.FLARE_STEP_D)}) одразу під уступом", not lip)
    add("C. Розміри, виміряні на виливку", "C10", "Проріз-вітрина", f"{m['slot']['width']} мм", "8.00 ± 0.02",
        abs(m["slot"]["width"] - v(p.SLOT_W)) <= 0.02)
    add("C. Розміри, виміряні на виливку", "C11", "Виїмка язичка", f"{m['notch']['width']} × {m['notch']['top_z']} мм",
        "15.00 × 5.00 ± 0.02", abs(m["notch"]["width"] - 15) <= 0.02 and abs(m["notch"]["top_z"] - 5) <= 0.02)
    add("C. Розміри, виміряні на виливку", "C12", "Габарит корпусу після шліфування",
        f"{m['footprint'][0]} × {m['footprint'][1]} × {m['height']}", "120 × 90 × 95 ± 0.02",
        abs(m["footprint"][0] - 120) <= 0.02 and abs(m["footprint"][1] - 90) <= 0.02 and abs(m["height"] - 95) <= 0.02)

    # ---------------- D. Посадки
    f = C["fit"]
    dvc = f["device"]
    add("D. Посадки литих деталей", "D1", "Девайс у кишені литого корпусу",
        f"перекриття {dvc['interference_mm3']} мм³, мін. зазор {dvc['min_clearance_mm']} мм, виступ {dvc['protrusion_mm']} мм",
        f"0 мм³; зазор > 0; виступ {v(p.DEV_PROTRUDE)}", dvc["interference_mm3"] == 0 and dvc["min_clearance_mm"] > 0
        and abs(dvc["protrusion_mm"] - v(p.DEV_PROTRUDE)) <= 0.05)
    add("D. Посадки литих деталей", "D2", "Девайс з іншим кутовим радіусом (R7.0 / R7.5, реальний не опублікований)",
        f"перекриття {dvc['corner_R7.0']['interference_mm3']} / {dvc['corner_R7.5']['interference_mm3']} мм³, "
        f"зазор {dvc['corner_R7.0']['min_clearance_mm']} / {dvc['corner_R7.5']['min_clearance_mm']} мм", "0 мм³",
        dvc["corner_R7.0"]["interference_mm3"] == 0 and dvc["corner_R7.5"]["interference_mm3"] == 0)
    add("D. Посадки литих деталей", "D3", "Повстяна підкладка на дні кишені",
        f"перекриття з корпусом {dvc['felt_interference_mm3']} мм³, девайс на підкладці (зазор {dvc['device_on_felt_gap_mm']})", "0; 0",
        dvc["felt_interference_mm3"] == 0 and dvc["device_on_felt_gap_mm"] <= 0.01)
    lf = f["lid"]
    add("D. Посадки литих деталей", "D4", "Лита кришка в литому корпусі",
        f"перекриття {lf['interference_mm3']} мм³, мін. зазор {lf['min_clearance_mm']} мм", "0 мм³, зазор > 0",
        lf["interference_mm3"] == 0 and lf["min_clearance_mm"] > 0)
    add("D. Посадки литих деталей", "D5", "Низ кришки врівень з низом корпусу; зазор над кришкою",
        f"низ {lf['lid_bottom_z']} / {lf['body_bottom_z']}, верх кришки {lf['lid_top_z']} → зазор {round(m['socket_roof_z'] - lf['lid_top_z'], 3)}",
        "0 / 0; 0.5 ± 0.02", abs(lf["lid_bottom_z"]) <= 0.01 and abs(lf["body_bottom_z"]) <= 0.01
        and abs(m["socket_roof_z"] - lf["lid_top_z"] - v(p.SOCK_TOP_GAP)) <= 0.02)
    sl = f["seal"]
    add("D. Посадки литих деталей", "D6", "Шнур Ø4: стиснення між литою кришкою і литим корпусом",
        f"залоз {sl['gland_depth_min']}–{sl['gland_depth_max']} мм → {sl['squeeze_pct_min']}–{sl['squeeze_pct_max']} %",
        f"проєкт {sl['design_gland']} мм / {sl['design_squeeze_pct']} % (±1 %)",
        abs(sl["squeeze_pct_min"] - sl["design_squeeze_pct"]) <= 1 and abs(sl["squeeze_pct_max"] - sl["design_squeeze_pct"]) <= 1)
    tb = f["tab"]
    add("D. Посадки литих деталей", "D7", "Язичок кришки у виїмці корпусу",
        f"бокові зазори {tb['side_gap_left']} / {tb['side_gap_right']}, над кінчиком {tb['top_gap_tip']}, кінчик від задньої грані {tb['tip_inset_from_back_face']}",
        f"бокові {v(p.LID_TAB_GAP)}; кінчик не виступає ({v(p.LID_TAB_INSET)})",
        abs(tb["side_gap_left"] - v(p.LID_TAB_GAP)) <= 0.02 and abs(tb["side_gap_right"] - v(p.LID_TAB_GAP)) <= 0.02
        and tb["tip_inset_from_back_face"] >= v(p.LID_TAB_INSET) - 0.02)

    # ---------------- E. Виймання з форм
    dm = C["demold_body"]
    add("E. Виймання з форм", "E1", "Сердечник T07 виходить униз (жорстке тіло, без підтиску)",
        f"заблоковано {dm['T07']['blocked_area_mm2']} мм² з {dm['T07']['area_mm2']}", "0", dm["T07"]["blocked_area_mm2"] == 0)
    t05 = dm.get("T05", dict(area_mm2=0.0, blocked_area_mm2=0.0))
    add("E. Виймання з форм", "E2", "Хребет T05 бетону не формує", f"{C['forming']['T05']} мм²", "0", C["forming"]["T05"] < 1.0)
    t15 = dm["T15"]
    bz = t15["blocked_by_zone"]
    non_logo = {k: v_ for k, v_ in bz.items() if k != "напис STICKBOX (фронт)"}
    add("E. Виймання з форм", "E3", "Зовнішня форма T15 і «палець» знімаються вгору (виріб — униз)",
        f"заблоковано {t15['blocked_area_mm2']} мм² з {t15['area_mm2']}: " + (", ".join(f"{k} {v_}" for k, v_ in bz.items() if v_) or "—"),
        "лише рельєф напису на вертикальній фронтальній стінці", sum(non_logo.values()) < 0.5)
    pe = dm["T15_front_peel"]
    add("E. Виймання з форм", "E4", "Рельєф напису виходить, коли силікон відгортають від фронту (каркас розкрито)",
        f"заблоковано {pe['blocked_area_mm2']} мм² з {pe['area_mm2']}", "0", pe["blocked_area_mm2"] < 0.5,
        note="тому порядок розпалублення: розкрити каркас → відгорнути фронтальну стінку блока → зняти виріб із «пальця»")
    lt = C["lid_casting"]["demold"]["T16"]
    add("E. Виймання з форм", "E5", "Кришка з форми T16",
        f"заблоковано: канавка шнура {lt['blocked_in_cord_groove_mm2']} мм², інше {lt['blocked_elsewhere_mm2']} мм²",
        "лише валик канавки (задумане пружне піднутрення 2 мм)", lt["blocked_elsewhere_mm2"] < 0.5)

    # ---------------- F. Заповнення бетоном
    sh = C["shift"]
    g0 = sh["cases"][0]
    add("F. Заповнення бетоном", "F1", "Найвужча стінка між сердечником і формою, поперек стінки (вище заходної фаски)",
        f"{g0['min_gap_above_lead_in_mm']} мм ({g0['where_above']}, z = {g0['at_above'][2]})",
        "≥ 4.9 мм (≈ 5 × найбільше зерно 1.0 мм, `docs/05`; стінки 5.0, фронт 5.5)", g0["min_gap_above_lead_in_mm"] >= 4.9,
        warn=g0["min_gap_above_lead_in_mm"] >= 4.5,
        note=("локальна точка у верхній плиті — між краєм кишені NFC-мітки і воронкою; так само і в проєкті. Плита "
              "заливається першою (≈60% бетону до введення сердечника, техкарта, крок 5), тож вузького каналу тут немає. "
              "Перевірити розпилом першого виливка (Т25)") if g0["at_above"][2] > d["z_ceil_c"] else "")
    add("F. Заповнення бетоном", "F2", "Стінка біля самого низу — на заходній фасці шнура (z 0–2.5)",
        f"{g0['min_gap_mm']} мм (z = {g0['at'][2]})", "≥ 4.9 мм — інакше WARN", g0["min_gap_mm"] >= 4.9, warn=g0["min_gap_mm"] >= 3.5,
        note="фаска розширює вхід гнізда на ≈1 мм; ця смуга — біля площини заливки, бетон кладеться туди прямо з поверхні, "
             "а не тече вузьким каналом. Відоме з v3.6 (`analysis.json` → outer min). Кромку низу притуплюють лише зовні")
    add("F. Заповнення бетоном", "F3", "Ті самі стінки при зсуві сердечника на 0.3 мм у 8 напрямках (люфт шпильок M5)",
        f"вище фаски {sh['worst_above_lead_in_mm']} мм, на фасці {sh['worst_min_gap_mm']} мм; натяг вкладки ≥ {sh['tab_preload_at_worst_mm']} мм",
        "вище фаски ≥ 4.5 мм; натяг > 0", sh["worst_above_lead_in_mm"] >= 4.5 and sh["tab_preload_at_worst_mm"] > 0)
    up = C["uplift"]
    add("F. Заповнення бетоном", "F4", "Спливання сердечника (виштовхувальна сила бетону ρ 2300)",
        f"{up['core_uplift_N']} Н → {up['per_rod_N']} Н на шпильку", "шпилька M5 клас 4.6 ≈ 5.7 кН", up["per_rod_N"] < 100)
    traps = C["air_traps_body"]
    big = [t for t in traps if t["area_mm2"] >= 20]
    add("F. Заповнення бетоном", "F5", "«Стелі» в положенні лиття (повітря збирається під ними)",
        "; ".join(f"{t['where']} {t['area_mm2']} мм² (нахил {t['slope_deg_mean']}°)" for t in big[:5]) or "немає",
        "немає — або обмазка розчином і вібрація (техкарта, крок 4)", not big, warn=True,
        note="геометрично неминучі для форми догори дном; захід — грунтувальний шар і вібрація")

    # ---------------- G. Кришка
    lc = C["lid_casting"]
    add("G. Виливок кришки", "G1", "Кришка — одне тіло; бетону ніде не бракує",
        f"{lc['concrete_solids']} тіло; бракує {lc['finished']['missing']['total_mm3']} мм³", "1; ≤ 0.5 мм³ (крім задокументованого)",
        lc["concrete_solids"] == 1 and all(q["where"] in LID_DOC for q in lc["finished"]["missing"]["pieces"]))
    add("G. Виливок кришки", "G2", "Зайвий бетон кришки",
        "; ".join(f"{q['where']}: {q['volume_mm3']} мм³" for q in lc["finished"]["extra"]["pieces"]) or "немає",
        "лише кромка низу (R0.6 — доводка після шліфування)",
        all(q["where"] in LID_DOC for q in lc["finished"]["extra"]["pieces"]))

    # ---------------- H. Модель виробу (analysis.json)
    add("H. Модель виробу і форм", "H1", "Тіла виробу коректні", ", ".join(f"{k}" for k, v_ in A["validity"].items() if v_),
        "усі valid", all(A["validity"].values()))
    add("H. Модель виробу і форм", "H2", "Деталі збірки не перекриваються",
        f"макс. {max(A['interference_mm3'].values())} мм³", "0", max(A["interference_mm3"].values()) == 0)
    add("H. Модель виробу і форм", "H3", "Піднутрення порожнини й кишені (модель)",
        f"{A['undercut_rays']['cavity']['blocked_faces']} / {A['undercut_rays']['pocket']['blocked_faces']} граней", "0 / 0",
        A["undercut_rays"]["cavity"]["blocked_faces"] == 0 and A["undercut_rays"]["pocket"]["blocked_faces"] == 0)
    sw = [q for q in A["seal_wall"] if q["in_groove"]]
    add("H. Модель виробу і форм", "H4", "Стінка під шнуром суцільна по всьому периметру", f"{sum(q['closed'] for q in sw)} / {len(sw)} перерізів",
        "усі замкнені", all(q["closed"] for q in sw))
    lt_ = A["lid_tilt"]
    add("H. Модель виробу і форм", "H5", "Кришка знімається з перекосом до 12°", f"макс. перекриття {max(q['interference_mm3'] for q in lt_)} мм³",
        "0", max(q["interference_mm3"] for q in lt_) == 0)
    add("H. Модель виробу і форм", "H6", "Напруження в язичку кришки при 30 Н", f"{A['lid_hook']['tab_sigma_MPa']:.1f} МПа",
        "≤ 3.5 МПа (запас ≥ 2 до LOP 7 МПа)", A["lid_hook"]["tab_sigma_MPa"] <= 3.5)
    st = A["stability"]
    add("H. Модель виробу і форм", "H7", "Стійкість з девайсом", f"кут перекидання {st['tip_angle_deg']:.1f}°, бічна сила {st['force_at_device_top_N']:.2f} Н",
        "≥ 30°", st["tip_angle_deg"] >= 30)
    add("H. Модель виробу і форм", "H8", "Місткість (симуляція MuJoCo, стіки Ø7.2)",
        f"{cap['no_shake_mean']} без струшування / {cap['with_shake_mean']} зі струшуванням (мін. {cap['no_shake_min']})",
        "≥ 60 стіків", cap["no_shake_min"] >= 60,
        note="симуляція на проєктних стінках; віртуальне лиття показує той самий резервуар (C3, C5)")
    mf = A["mold_frame"]["body"]
    add("H. Модель виробу і форм", "H9", "Силікон форми корпусу: мінімум стінки «каркас ↔ майстер»",
        f"{mf['walls']['side_min_mm']:.1f} мм (верх {mf['walls']['top_min_mm']:.1f})", "≥ 12 мм", mf["walls"]["side_min_mm"] >= 11.95)
    dfl = mf["deflection"]["лиття бетону"]
    add("H. Модель виробу і форм", "H10", "Прогин каркаса під тиском бетону", f"{dfl['deflection_mm']:.3f} мм, {dfl['per_bolt_N']:.1f} Н на болт",
        "≤ 0.1 мм", dfl["deflection_mm"] <= 0.1)
    return out


LID_DOC = ("низ (відкрита грань, шліфування)",)
OVN = {"spine_outer": "хребет ↔ силікон форми", "spine_stiffener": "хребет ↔ ребро", "stiffener_core": "ребро ↔ чашка",
       "spine_core": "хребет ↔ чашка", "frames_outer": "каркас ↔ силікон", "frames_spine": "каркас ↔ міст"}


def write_md(res, C, path):
    from collections import OrderedDict
    groups = OrderedDict()
    for r in res:
        groups.setdefault(r["group"], []).append(r)
    n = {s: sum(r["status"] == s for r in res) for s in ("PASS", "WARN", "FAIL")}
    L = []
    L.append(f"# 15. Віртуальне лиття і повний набір перевірок ({REV})\n")
    L.append("Питання: **чи вийде з форм повноцінний виріб** — з резервуаром, кишенею девайса, гніздом і кришкою, що "
             "відповідають кресленню? Перевіряли не саму модель виробу, а **те, що дадуть файли оснащення**, які отримує "
             "виробник форм (`tooling/step`).\n")
    L.append("## Як перевірено\n")
    L.append("1. STEP-файли оснащення поставлено в положення лиття:\n"
             "    * силікон зовнішньої форми T15 у каркасі T02a/T02b;\n"
             "    * силіконова чашка сердечника T07 на хребті з мостом T05;\n"
             "    * ребро «пальця» T04.\n"
             "2. **Бетоном заповнено весь вільний простір** до площини заливки (відкритої грані). Заповнюється лише те, що з нею "
             "з'єднане.\n"
             "3. Виливок зменшено на усадку (1/K, K = 1.002) і зішліфовано припуск 0.5 мм знизу.\n"
             "4. Отриманий корпус:\n"
             "    * порівняно з CAD виробу — булеві різниці об'ємів і відхилення поверхні в 30 000 точках;\n"
             "    * проміряно променями (гніздо, резервуар, кишеня, отвір, проріз, виїмка);\n"
             "    * у нього вставлено девайс, литу кришку (відлиту так само з форми T16) і шнур.\n"
             "5. **Виймання:** кожну грань виливка віднесено до інструмента, що її формує. Для кожної грані перевірено, чи "
             "заважає щось інструменту вийти: сердечнику — вниз, зовнішній формі — вгору.\n"
             "6. **Заповнення:** перевірено найвужчий проміжок між сердечником і формою, також зі зсувом сердечника на люфт "
             "шпильок; «стелі», під якими збирається повітря; силу, з якою бетон виштовхує сердечник.\n")
    L.append("Це геометричні розрахунки на CAD-моделях, а не фізичне лиття. Поведінку суміші (текучість, усадку, бульбашки) "
             "підтверджують пробні виливки.\n")
    L.append(f"## Підсумок: {n['PASS']} PASS · {n['WARN']} WARN · {n['FAIL']} FAIL\n")
    for g, rows in groups.items():
        L.append(f"### {g}\n")
        L.append("| № | Перевірка | Результат | Критерій | Статус |")
        L.append("|---|---|---|---|---|")
        for r in rows:
            mark = {"PASS": "✅ PASS", "WARN": "⚠️ WARN", "FAIL": "❌ FAIL"}[r["status"]]
            note = f"<br><small>{r['note']}</small>" if r["note"] else ""
            L.append(f"| {r['id']} | {r['name']}{note} | {r['value']} | {r['criterion']} | {mark} |")
        L.append("")
    L.append(EXTRA_MD.get("findings", ""))
    traps = C["air_traps_body"]
    if traps:
        L.append("## «Стелі» в положенні лиття (де збирається повітря)\n")
        L.append("Форма стоїть догори дном, тож грані, звернені у виробі донизу, в бетоні дивляться вгору. Бульбашки, що "
                 "спливають, збираються під ними. Повна таблиця (площа ≥ 3 мм²):\n")
        L.append("| Місце | Площа, мм² | Висота z у виробі | Нахил, ° (середній) | Формує |")
        L.append("|---|---|---|---|---|")
        for t in traps[:14]:
            L.append(f"| {t['where']} | {t['area_mm2']} | {t['z_product'][0]}–{t['z_product'][1]} | {t['slope_deg_mean']} | {t['formed_by']} |")
        L.append("\nЗахід — техкарта, крок 4: перед заливкою обмазати ці поверхні сердечника тонким шаром розчину без фібри "
                 "і вібрувати під час заливки. Перший пробний виливок розпиляти по перерізах, як на рис. 34, і перевірити "
                 "раковини саме в цих місцях.\n")
    L.append("## Рисунки\n")
    for fn, cap in (("34_virtual_casting_sections.png", "Рис. 34. Оснащення з бетоном у положенні лиття (догори дном): сердечник "
                     "(помаранчевий) формує резервуар і гніздо кришки, «палець» форми на ребрі T04 — кишеню девайса"),
                    ("35_cast_vs_design.png", "Рис. 35. Готовий виливок (усадка 1/K, шліфування) — заливка; проєктний контур — "
                     "червоний пунктир. Контури збігаються"),
                    ("36_joint_details.png", "Рис. 36. Стик шпильки Ø8 і гнізда сердечника після виправлення v3.7.1; вкладка "
                     "виїмки з натягом 1 мм"),
                    ("37_lid_casting.png", "Рис. 37. Лиття кришки у формі T16")):
        L.append(f"![{cap}](../renders/{fn})\n\n*{cap}.*\n")
    L.append("Відтворити: `python build_all.py && python run_tests.py` (результати: `reports/casting_verification.json`, "
             "`reports/test_results.json`).\n")
    open(path, "w", encoding="utf-8").write("\n".join(L))


EXTRA_MD = {"findings": """## Що знайшла перевірка у файлах v3.7 і що виправлено у v3.7.1

Перший прогін віртуального лиття на файлах v3.7 показав, що резервуар, кишеня, гніздо й кришка виходять за кресленням.
Але він знайшов **дві хиби телескопічного стику отвору Ø8** і одну розбіжність кромок. Попередні перевірки їх не бачили:
стик тоді перевіряли за параметрами, а не перетином реальних тіл оснащення.

| # | Що знайдено (v3.7) | Наслідок для виробу | Виправлення (v3.7.1) | Після виправлення |
|---|---|---|---|---|
| 1 | Гніздо Ø7.9 × 3 у конусі розтруба сердечника **заповнене куполом резервуара** на 2 з 3 мм. Шпилька Ø8 зовнішньої форми перекривається з силіконом сердечника суцільним диском — 101.6 мм³ на глибину 2.45 мм | М'яку шпильку довжиною ≈5 мм довелося б стиснути на ≈50%: отвір Ø8 вийшов би бочкою або з перекосом, а сердечник тиснув би вгору | Гніздо вирізається **останнім кроком** побудови сердечника (`molds.core_outer`, `parts.socket_tool`) | Контакт — лише кільце натягу 0.05 мм, 3.0 мм³ (A2) |
| 2 | Фаска на вході гнізда (Ø9.1) **ширша за уступ розтруба Ø8.6**. Між шпилькою і фаскою — кільцева щілина, яку заповнює бетон | Тонке бетонне «перо» 0.55 мм × ≤0.3 мм (3.5 мм³) по колу виходу отвору: радіус 4.0 там, де має бути 4.3–4.9. Крихке — відламується в резервуар | Вхід гнізда — **без фаски**; заходна фаска 0.6 мм перенесена на кінець шпильки (майстер T01), схована в гнізді | «Пера» немає (B4, C9) |
| 3 | Кромки виїмки язичка на задній грані **з форми гострі**: прямокутна вкладка сердечника входить у стінку форми з натягом 1 мм. У проєкті — R1 | 5.2 мм³ на 3 кромках, косметично | Притуплення R≈1 у доводці (техкарта, крок 11, уточнено) | Задокументовано (B5) |
| 4 | Майстер кришки: ухил пробки на припуску шліфування мав злам 6 мкм | Несуттєво | Ухил продовжено на припуск (`parts._lid_full`) | — |
| 5 | Техкарта (кроки 6, 10, 11, 14) і `docs/04` описували виймання сердечника «вздовж рампи» (v3.0) і шнур 258 мм | Помилка в інструкції | Оновлено під v3.7: сердечник виходить прямо вниз; шнур 338 мм | E1: 0 заблокованих граней |

![Знахідки у файлах v3.7](../renders/36a_joint_v3.7_before_fix.png)

*Рис. 36a. Файли v3.7. Зліва: шпилька форми (бірюзова) впирається в купол сердечника (помаранчевий), біля кромок —
бетонні «зубці» у фасці гнізда. Справа: вкладка виїмки заходить у стінку форми, кромка виїмки гостра.*
"""}


def figures(C):
    from stickbox import casting_figs as CF
    K = CC.K
    F, B, LF = CC._C["F"], CC._C["B"], CC._C["LF"]
    xc, zc = d["cav_xc"] * K, (d["z_ceil_c"] + 1) * K
    pcy = d["pocket_cy"]
    R = os.path.join(ROOT, "renders")
    CF.body_tool_sections([
        ("y", 1.0, "y = 1: отвір Ø8 зі шпилькою форми, резервуар, гніздо кришки", None),
        ("y", pcy, f"y = {pcy}: кишеня девайса («палець» на ребрі T04) і резервуар", None),
        ("x", 0.0, "x = 0: виїмка язичка (вкладка сердечника), резервуар, гніздо", None),
        ("x", d["pocket_cx"], f"x = {d['pocket_cx']}: кишеня, перегородка прорізу, плече резервуара", None)],
        "Віртуальне лиття корпусу: оснащення + бетон у положенні лиття (догори дном)", os.path.join(R, "34_virtual_casting_sections.png"))
    CF.cast_vs_design([
        ("y", 1.0, "y = 1", None), ("y", pcy, f"y = {pcy}", None), ("x", 0.0, "x = 0", None), ("x", d["pocket_cx"], f"x = {d['pocket_cx']}", None)],
        F, B, "Готовий виливок (усадка 1/K, шліфування 0.5) проти проєкту: контури збігаються", os.path.join(R, "35_cast_vs_design.png"),
        LF=LF, LB=__import__("stickbox.parts", fromlist=["lid"]).lid())
    CF.body_tool_sections([
        ("y", 0.0, "Стик шпильки Ø8 форми і гнізда Ø7.9 × 3 сердечника (y = 0)", (xc - 9, xc + 9, -zc - 6, -zc + 6)),
        ("x", 0.0, "Вкладка виїмки: натяг 1.0 мм у стінку форми (x = 0)", (36, 52, -9, 2))],
        "Деталі стиків оснащення (після виправлення v3.7.1)", os.path.join(R, "36_joint_details.png"))
    CF.lid_tool_section(os.path.join(R, "37_lid_casting.png"))


def main():
    t0 = time.time()
    cv = os.path.join(ROOT, "reports", "casting_verification.json")
    if "--reuse" in sys.argv:      # лише критерії і звіт з уже порахованого (рисунки — з попереднього прогону)
        C = json.load(open(cv, encoding="utf-8"))
        sys.argv.append("--no-figs")
    else:
        C = CC.run(cv)
        C["measure_design"] = CC.measure(CC._C["B"])
        json.dump(C, open(cv, "w"), indent=1, ensure_ascii=False, default=float)
    A = json.load(open(os.path.join(ROOT, "reports", "analysis.json"), encoding="utf-8"))
    cap = json.load(open(os.path.join(ROOT, "reports", "capacity_sim.json"), encoding="utf-8"))
    res = checks(C, A, cap)
    json.dump(res, open(os.path.join(ROOT, "reports", "test_results.json"), "w"), indent=1, ensure_ascii=False)
    if "--no-figs" not in sys.argv:
        figures(C)
    write_md(res, C, os.path.join(ROOT, "docs", "15_virtual_casting_tests.md"))
    for r in res:
        print(f"{r['status']:4}  {r['id']:4} {r['name']}: {r['value']}")
    nf = sum(r["status"] == "FAIL" for r in res)
    print(f"--- {sum(r['status'] == 'PASS' for r in res)} PASS, {sum(r['status'] == 'WARN' for r in res)} WARN, {nf} FAIL"
          f"  ({time.time() - t0:.0f} s)")
    sys.exit(1 if nf else 0)


if __name__ == "__main__":
    main()
