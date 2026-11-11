"""
Generate synthetic data for the sheet-metal intake (goods receiving) dashboard.

Scenario (inspired by AC Metais, a Brazilian laser-cutting and metal fabrication shop):
steel, stainless and aluminum sheets arrive from six suppliers. Each receipt is checked at
the dock (quantity, thickness, dimensions, surface, mill certificate). The cheapest supplier
is the least reliable; rust problems peak in the rainy season; steel prices rise mid-2026.

All numbers are synthetic. Output: data/sheet_metal_intake.xlsx
Sheets: fReceipts, dSupplier, dMaterial, dCalendar

Usage:  python scripts/generate_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 7
START, END = pd.Timestamp("2025-11-01"), pd.Timestamp("2026-10-31")
OUT = Path(__file__).resolve().parents[1] / "data" / "sheet_metal_intake.xlsx"
rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------- dMaterial
MATERIALS = [
    ("Carbon steel SAE 1020", 7850, 7.5, [1.5, 2.0, 3.0, 4.75, 6.35, 9.5, 12.7], 0.50),
    ("Galvanized steel",      7850, 9.2, [0.9, 1.25, 1.5, 2.0],                0.15),
    ("Stainless AISI 304",    7930, 29.0, [1.0, 1.5, 2.0, 3.0, 4.0, 6.0],      0.15),
    ("Stainless AISI 430",    7700, 18.5, [0.8, 1.0, 1.5, 2.0],                0.07),
    ("Aluminum 5052",         2680, 33.0, [1.5, 2.0, 3.0, 4.0, 6.0],           0.13),
]
rows, mix = [], []
for name, dens, cost, thicknesses, share in MATERIALS:
    for t in thicknesses:
        rows.append(dict(material_id=f"M{len(rows) + 1:03d}", material=name, thickness_mm=t,
                         material_description=f"{name} {t:g} mm", density_kg_m3=dens,
                         reference_price_brl_kg=cost))
        mix.append(share / len(thicknesses) * (1.4 if 1.5 <= t <= 4.75 else 0.8))
dMaterial = pd.DataFrame(rows)
mix = np.array(mix) / np.sum(mix)

# ---------------------------------------------------------------- dSupplier
# id, name, type, materials, promised lead time (days), on-time prob, price factor, nonconformity prob
SUPPLIERS = [
    ("S01", "Steel service center A", "Service center", ["Carbon steel SAE 1020", "Galvanized steel"], 5, 0.93, 1.03, 0.04),
    ("S02", "Steel service center B", "Service center", ["Carbon steel SAE 1020", "Galvanized steel"], 7, 0.85, 1.00, 0.06),
    ("S03", "Steel mill direct C",    "Mill (direct)",  ["Carbon steel SAE 1020"],                     21, 0.62, 0.90, 0.09),
    ("S04", "Stainless distributor D", "Distributor",   ["Stainless AISI 304", "Stainless AISI 430"],   10, 0.88, 1.00, 0.05),
    ("S05", "Stainless importer E",   "Importer",       ["Stainless AISI 304", "Stainless AISI 430"],   30, 0.70, 0.92, 0.08),
    ("S06", "Aluminum distributor F", "Distributor",    ["Aluminum 5052"],                              8, 0.90, 1.00, 0.05),
]
dSupplier = pd.DataFrame([dict(supplier_id=s[0], supplier=s[1], supplier_type=s[2],
                               promised_lead_time_days=s[4]) for s in SUPPLIERS])

NONCONF = ["Surface rust / oxidation", "Thickness out of tolerance", "Wrong dimensions",
           "Damaged in transport", "Missing mill certificate"]
SIZES = {"Carbon": ["3000 x 1500", "3000 x 1200", "6000 x 1500"], "Galvanized": ["3000 x 1200", "2000 x 1000"],
         "Stainless": ["3000 x 1500", "2000 x 1000"], "Aluminum": ["3000 x 1500", "2000 x 1000"]}


def price_index(d):
    """Steel price index: flat, then +9% from June 2026 (market increase)."""
    return 1.0 + (0.09 if d >= pd.Timestamp("2026-06-01") else 0) + 0.01 * np.sin(d.month)


# ---------------------------------------------------------------- fReceipts
records = []
po = 4500
for d in pd.date_range(START - pd.Timedelta(days=30), END, freq="B"):     # PO dates (business days)
    for _ in range(rng.poisson(5.5)):
        mat = dMaterial.iloc[rng.choice(len(dMaterial), p=mix)]
        cands = [s for s in SUPPLIERS if mat.material in s[3]]
        weights = np.array([1.0 if s[0] not in ("S03", "S05") else 0.7 for s in cands])
        s = cands[rng.choice(len(cands), p=weights / weights.sum())]
        sid, _, _, _, lead, p_on_time, pf, p_nc = s
        promised = d + pd.Timedelta(days=lead)
        late = 0 if rng.random() < p_on_time else int(rng.gamma(1.6, 2.5 if lead < 15 else 5)) + 1
        early = -int(rng.integers(0, 3)) if late == 0 else 0
        received = promised + pd.Timedelta(days=late + early)
        if not (START <= received <= END):
            continue
        po += 1
        family = mat.material.split()[0]
        size = rng.choice(SIZES[family])
        w, l = (int(x) for x in size.split(" x "))
        kg_sheet = w * l / 1e6 * mat.thickness_mm / 1000 * mat.density_kg_m3
        sheets = int(max(2, rng.gamma(2.2, 900 / max(kg_sheet, 1) / 2.2)))
        short = rng.random() < (0.10 if sid in ("S03", "S05") else 0.04)
        sheets_recv = sheets - int(np.ceil(sheets * rng.uniform(0.05, 0.3))) if short else sheets

        # nonconformity: rust is worse in the rainy season (Dec-Mar) and with long sea/road transport
        rainy = received.month in (12, 1, 2, 3)
        nc = "No issue"
        if rng.random() < p_nc * (2.2 if rainy else 0.8):
            p = np.array([0.35 * (2.5 if rainy else 0.6), 0.2, 0.15, 0.15, 0.15])
            nc = NONCONF[rng.choice(len(NONCONF), p=p / p.sum())]
        if nc == "No issue":
            result = "Approved"
        elif nc in ("Thickness out of tolerance", "Wrong dimensions") and rng.random() < 0.6:
            result = "Rejected"
        else:
            result = "Approved with deviation"

        index = price_index(received) if family in ("Carbon", "Galvanized") else 1.0
        price = mat.reference_price_brl_kg * pf * index * rng.normal(1, 0.025)
        records.append(dict(
            receipt_id=f"RC{len(records) + 1:05d}", po_number=f"PO-{po}", po_date=d,
            supplier_id=sid, material_id=mat.material_id, sheet_size_mm=size,
            sheets_ordered=sheets, sheets_received=sheets_recv,
            ordered_kg=round(sheets * kg_sheet, 1), received_kg=round(sheets_recv * kg_sheet, 1),
            price_brl_kg=round(price, 2), promised_date=promised, received_date=received,
            inspection_result=result, nonconformity=nc))
fReceipts = pd.DataFrame(records).sort_values("received_date").reset_index(drop=True)
fReceipts["receipt_id"] = [f"RC{i + 1:05d}" for i in range(len(fReceipts))]

# ---------------------------------------------------------------- dCalendar
cal = pd.DataFrame({"date": pd.date_range(START, END, freq="D")})
cal["year"] = cal.date.dt.year
cal["month_number"] = cal.date.dt.month
cal["year_month_number"] = cal.year * 100 + cal.month_number
cal["month_label"] = cal.date.dt.strftime("%b %Y")
cal["quarter"] = "Q" + cal.date.dt.quarter.astype(str) + " " + cal.year.astype(str)

OUT.parent.mkdir(parents=True, exist_ok=True)
with pd.ExcelWriter(OUT, engine="openpyxl", datetime_format="yyyy-mm-dd", date_format="yyyy-mm-dd") as w:
    fReceipts.to_excel(w, sheet_name="fReceipts", index=False)
    dSupplier.to_excel(w, sheet_name="dSupplier", index=False)
    dMaterial.to_excel(w, sheet_name="dMaterial", index=False)
    cal.to_excel(w, sheet_name="dCalendar", index=False)
print(f"{len(fReceipts):,} receipts written to {OUT}")
