"""
Калькулятор собівартості STICKBOX 01 Monolith.
Кількості беруться з CAD (reports/analysis.json); ціни — ПРИПУЩЕННЯ (EUR), замініть на ціни ваших постачальників
у словнику PRICES і виконайте: python cost.py → docs/06_cost_estimate.md
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from stickbox import parts as P, params as p
from stickbox.params import v

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
R = json.load(open(f"{ROOT}/reports/analysis.json"))

PRICES = {  # EUR, орієнтовно — ПЕРЕВІРИТИ У ПОСТАЧАЛЬНИКІВ
    "concrete_mix_eur_per_kg": (1.5, 3.5),     # GFRC-премікс / декор. суміш з пігментом і фіброю
    "silicone_platinum_eur_per_kg": (25, 45),  # платиновий силікон для форм
    "felt_eur": (0.05, 0.3),                  # вирубка повсті з клейовою основою
    "paint_eur": (0.1, 0.4),                  # фарба для логотипа (на виріб)
    "nfc_tag_eur": (0.15, 0.8),               # v3.3: NFC-наліпка Ø25 + клей (тип чипа — на вибір замовника); припущення
    "oring_eur": (0.3, 1.5),                   # губчастий силіконовий шнур Ø4, ≈0.26 м + клей
    "sealer_eur_per_m2": (4, 10),              # просочення + 2 шари матового PU-лаку
    "pads_eur_set": (0.2, 0.6),
    "petg_eur_per_kg": (18, 30),
    "resin_eur_per_l": (30, 60),
    "labour_eur_per_h": (5, 12),
    "packaging_eur": (1.0, 3.0),
}
RL = P.has_relief_lid()
LABOUR_MIN = (26 if RL else 24) + (1 if v(p.NFC_ON) else 0)   # хв на комплект; v3.0: без кришечки −2; v3.3: вклеїти NFC-мітку +1 (припущення)
PAINT_MIN = 8 + (2 if v(p.NFC_ON) else 0)   # хв: напис (+ знак NFC) у 2 кольори з маскуванням (припущення; трафарет скорочує ~вдвічі)
MOLD_LIFE = (30, 60)     # виливків на комплект форм (припущення до тесту Т12)
LOSS = 1.10              # втрати суміші 10%

m = R["mass"]
concrete_kg = (m["body"]["mass_kg"] + m["lid"]["mass_kg"] + (m["relief_lid"]["mass_kg"] if "relief_lid" in m else 0.0)) * LOSS * 1.01  # + припуск на шліфування
area_m2 = (P.body().Area() + P.lid().Area() + (P.relief_lid().Area() if RL else 0.0)) / 1e6
sil = R["silicone"]
mold_sil_kg = (sil["outer_mold_body_kg"] + sil["core_cup_kg"] + sil["lid_mold_kg"] + sil.get("relief_lid_mold_kg", 0.0)) * 1.1
tool = R["tooling"]
fdm_keys = ["T02_body_sleeve", "T03_body_base_plate", "T04_finger_stiffener", "T05_core_spine_bridge", "T09_lid_sleeve", "T10_lid_base_plate", "T17_stiffener_holder", "T19_rlid_sleeve", "T20_rlid_base_plate"]
resin_keys = ["T01_body_master", "T06_core_mold", "T08_lid_master", "T18_rlid_master", "T13_gauge_hole_go_7p90", "T14_gauge_stick_heets"]
fdm_kg = sum(tool[k]["volume_ml"] for k in tool if any(k.startswith(x[:3]) and x in k for x in fdm_keys)) * 1.27 / 1000 * 0.45  # ~45% ефективне заповнення
resin_l = sum(tool[k]["volume_ml"] for k in tool if any(x in k for x in resin_keys)) / 1000 * 0.35  # порожнисті/з товщиною стінки

rows = []
def add(name, qty, unit, price_key, mult=1.0):
    lo, hi = PRICES[price_key]
    rows.append((name, f"{qty:.3g} {unit}", lo * qty * mult, hi * qty * mult))

add("Бетонна суміш (корпус + кришка, +10% втрат)", concrete_kg, "кг", "concrete_mix_eur_per_kg")
add("Повстяна підкладка (вирубка, клейова основа)", 1, "шт", "felt_eur")
if RL:
    add("Шнур-губка Ø3 кришечки (≈0.09 м) + клей", 1, "компл", "oring_eur", 0.5)
add("Фарба: напис зі знаком-I" + (" + знак NFC" if v(p.NFC_ON) else "") + " (2 кольори), ≈1 мл", 1, "компл", "paint_eur")
add("Ущільнювач: шнур-губка Ø4 (≈0.26 м) + клей", 1, "компл", "oring_eur")
add("Герметизація (усі поверхні)", area_m2, "м²", "sealer_eur_per_m2")
add("Опори", 1, "компл", "pads_eur_set")
if v(p.NFC_ON):
    add("NFC-мітка Ø25 + клей (вклеїти в кишеню стелі)", 1, "шт", "nfc_tag_eur")
add("Робота", LABOUR_MIN / 60, "год", "labour_eur_per_h")
add("Робота: фарбування напису і знака", PAINT_MIN / 60, "год", "labour_eur_per_h")
add("Упаковка", 1, "шт", "packaging_eur")
var_lo = sum(r[2] for r in rows); var_hi = sum(r[3] for r in rows)
mold_lo = mold_sil_kg * PRICES["silicone_platinum_eur_per_kg"][0]
mold_hi = mold_sil_kg * PRICES["silicone_platinum_eur_per_kg"][1]
tool_lo = fdm_kg * PRICES["petg_eur_per_kg"][0] + resin_l * PRICES["resin_eur_per_l"][0]
tool_hi = fdm_kg * PRICES["petg_eur_per_kg"][1] + resin_l * PRICES["resin_eur_per_l"][1]
amort_lo, amort_hi = mold_lo / MOLD_LIFE[1], mold_hi / MOLD_LIFE[0]

L = ["# 06. Орієнтовна собівартість\n",
     "> **Кількості — з CAD-моделі. Ціни — припущення (EUR), не котирування.** Замініть ціни на актуальні у `cad/cost.py` "
     "(словник `PRICES`) і перегенеруйте документ: `python cost.py`.\n",
     "## 1. Змінні витрати на 1 комплект\n", "| Стаття | Кількість | Мін, € | Макс, € |", "|---|---|---|---|"]
for n, q, lo, hi in rows:
    L.append(f"| {n} | {q} | {lo:.2f} | {hi:.2f} |")
L.append(f"| **Разом змінні** | | **{var_lo:.2f}** | **{var_hi:.2f}** |\n")
L.append("## 2. Одноразові витрати на оснащення (1 комплект форм)\n")
L.append("| Стаття | Кількість | Мін, € | Макс, € |\n|---|---|---|---|")
L.append(f"| Платиновий силікон форм (корпус + сердечник + кришка, +10%) | {mold_sil_kg:.2f} кг | {mold_lo:.0f} | {mold_hi:.0f} |")
L.append(f"| Друк FDM (гільзи, плити, хребет, ребро), ефективна маса | ≈{fdm_kg:.2f} кг | {fdm_kg*PRICES['petg_eur_per_kg'][0]:.0f} | {fdm_kg*PRICES['petg_eur_per_kg'][1]:.0f} |")
L.append(f"| Друк смолою (майстри, форма сердечника, майстер кришечки, калібри) | ≈{resin_l:.2f} л | {resin_l*PRICES['resin_eur_per_l'][0]:.0f} | {resin_l*PRICES['resin_eur_per_l'][1]:.0f} |")
L.append(f"| **Разом оснащення** | | **{mold_lo + tool_lo:.0f}** | **{mold_hi + tool_hi:.0f}** |\n")
L.append(f"Амортизація силіконових форм при ресурсі {MOLD_LIFE[0]}–{MOLD_LIFE[1]} виливків: **{amort_lo:.2f}–{amort_hi:.2f} € / комплект**. "
         "Друковане оснащення практично не зношується.\n")
L.append(f"## 3. Підсумок\n\nСобівартість комплекту (змінні + амортизація форм): **≈{var_lo + amort_lo:.1f}–{var_hi + amort_hi:.1f} €** "
         f"без накладних витрат, браку та логістики. Площа герметизації {area_m2*1e4:.0f} см², бетонна суміш {concrete_kg:.2f} кг на комплект.\n")
L.append("## 4. Резерви здешевлення\n")
L.append("* Головна стаття — робота: шліфування низу та герметизація. Шліфувальний стіл із кондуктором і лак-розпилювач "
         "скорочують час удвічі.\n* Кілька форм паралельно (2–4 комплекти) — повніше використання замісу й робочого часу.\n"
         "* Брак — найдорожча складова. Грунтувальний шар і вібрація окупаються першими ж виливками.\n"
         "* Губчастий шнур — купувати бухтою (50–100 м) і різати кондуктором на відрізи потрібної довжини.")
open(f"{ROOT}/docs/06_cost_estimate.md", "w").write("\n".join(L) + "\n")
print("cost ok", round(var_lo, 2), round(var_hi, 2), round(mold_lo + tool_lo), round(mold_hi + tool_hi))
