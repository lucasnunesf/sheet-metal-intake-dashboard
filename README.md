# Sheet Metal Intake · Power BI

Power BI dashboard for **goods receiving of steel, stainless and aluminum sheets** in a metal fabrication shop: supplier delivery performance, quality at the dock, spend and price trends.

The use case is based on **AC Metais**, a Brazilian laser-cutting and metal fabrication company. **All data is synthetic**, generated in Python.

> 📸 *Screenshots: `docs/images/` (add after opening the report in Power BI Desktop)*

## The problem

Sheet metal is the main raw material of a laser-cutting shop. When a supplier is late, short or sends rusty sheets, the cutting plan breaks. Purchasing usually picks the cheapest offer without seeing the hidden cost of unreliable suppliers.

## Key findings (synthetic data, Nov 2025 – Oct 2026)

- 1,471 receipts · 1,312 t · BRL 20.0M · on-time 84.2% · fill rate 98.6% · nonconformity rate 6.0%.
- The **cheapest carbon-steel source** (mill direct, ~BRL 7.04/kg vs ~8.2–8.5 at service centers) is on time only **64%** of the time and delivers short more often.
- **Surface rust** is the most common nonconformity and peaks in the **rainy season (Dec–Mar)**.
- Carbon-steel prices rise about **9% from June 2026**.

## Dashboard

**Page 1 · Supplier performance** — *Are our suppliers delivering on time, complete and to spec?*
KPI cards (on-time %, fill rate %, nonconformity rate %, avg days late) · on-time by supplier · on-time trend · nonconformities by type · supplier scorecard.

**Page 2 · Spend and price** — *How much are we buying, from whom, and at what price?*
KPI cards (spend, tonnes, avg BRL/kg, receipts) · price trend by material · monthly spend · spend by supplier · materials table with price vs reference.

## Data model

Star schema, single-direction filters, imported from one Excel file.

```
 dSupplier 1 ──── * fReceipts * ──── 1 dMaterial
                       │ *
                       │ 1
                   dCalendar (received_date)
```

| Table | Grain | Rows |
|---|---|---|
| `fReceipts` | one receipt (PO line delivered) | 1,471 |
| `dSupplier` | supplier | 6 |
| `dMaterial` | material + thickness | 26 |
| `dCalendar` | day | 365 |

Highlights:

- Calculated columns for **days late** and **spend**.
- **12 DAX measures** in display folders (volume, delivery, quality). The average price is **weighted by kg**, and the price is compared with each material's reference price:

```DAX
Price vs Reference % =
VAR paid = [Avg Price (BRL/kg)]
VAR reference =
    DIVIDE (
        SUMX ( fReceipts, fReceipts[received_kg] * RELATED ( dMaterial[reference_price_brl_kg] ) ),
        SUM ( fReceipts[received_kg] )
    )
RETURN DIVIDE ( paid - reference, reference )
```

## Report as code

The report is a **Power BI Project (.pbip)** built by Python: semantic model in **TMDL**, report in **PBIR** (one JSON per page and visual) and a custom theme. `scripts/pbip_lib.py` is a small reusable builder; `scripts/build_pbip.py` only describes this dashboard (tables, measures, pages). Every JSON file is validated against Microsoft's official schemas.

## Repository

```
data/sheet_metal_intake.xlsx      synthetic data (4 sheets)
scripts/generate_data.py          data generator (seeded, reproducible)
scripts/pbip_lib.py               reusable TMDL + PBIR builder
scripts/build_pbip.py             dashboard definition
scripts/validate_pbir.py          schema validation
powerbi/SheetMetalIntake.pbip     open this in Power BI Desktop
docs/                             case study and screenshots
```

## How to run

```bash
pip install -r requirements.txt
python scripts/generate_data.py
python scripts/build_pbip.py
```

1. Open `powerbi/SheetMetalIntake.pbip` in Power BI Desktop (Windows).
2. *Transform data → Edit parameters →* set **DataFolder** to the full path of the `data` folder, ending with `\`.
3. *Refresh.*

Optional schema check: `git clone --depth 1 https://github.com/microsoft/json-schemas.git` and `python scripts/validate_pbir.py json-schemas`.

## Tools

Python (pandas, NumPy) · Excel · Power BI Desktop · Power Query (M) · DAX · TMDL · PBIR

## Author

[lucasnunesf](https://github.com/lucasnunesf)
