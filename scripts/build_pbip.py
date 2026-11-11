"""
Build the Power BI Project for the sheet-metal intake dashboard.
Usage:  python scripts/build_pbip.py   ->  powerbi/SheetMetalIntake.pbip
"""
from pathlib import Path

from pbip_lib import Model, Page, Style, build_project, categorical_filter, col, meas

ROOT = Path(__file__).resolve().parents[1]
F = "fReceipts"


def m(name):
    return meas(F, name)


TABLES = {
    "fReceipts": [
        ("receipt_id", "type text", "string", "none", None),
        ("po_number", "type text", "string", "none", None),
        ("po_date", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("supplier_id", "type text", "string", "none", None),
        ("material_id", "type text", "string", "none", None),
        ("sheet_size_mm", "type text", "string", "none", None),
        ("sheets_ordered", "Int64.Type", "int64", "sum", "#,0"),
        ("sheets_received", "Int64.Type", "int64", "sum", "#,0"),
        ("ordered_kg", "type number", "double", "sum", "#,0"),
        ("received_kg", "type number", "double", "sum", "#,0"),
        ("price_brl_kg", "type number", "double", "none", "#,0.00"),
        ("promised_date", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("received_date", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("inspection_result", "type text", "string", "none", None),
        ("nonconformity", "type text", "string", "none", None),
    ],
    "dSupplier": [
        ("supplier_id", "type text", "string", "none", None),
        ("supplier", "type text", "string", "none", None),
        ("supplier_type", "type text", "string", "none", None),
        ("promised_lead_time_days", "Int64.Type", "int64", "none", "0"),
    ],
    "dMaterial": [
        ("material_id", "type text", "string", "none", None),
        ("material", "type text", "string", "none", None),
        ("thickness_mm", "type number", "double", "none", "0.00"),
        ("material_description", "type text", "string", "none", None),
        ("density_kg_m3", "Int64.Type", "int64", "none", "0"),
        ("reference_price_brl_kg", "type number", "double", "none", "#,0.00"),
    ],
    "dCalendar": [
        ("date", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("year", "Int64.Type", "int64", "none", "0"),
        ("month_number", "Int64.Type", "int64", "none", "0"),
        ("year_month_number", "Int64.Type", "int64", "none", "0"),
        ("month_label", "type text", "string", "none", None),
        ("quarter", "type text", "string", "none", None),
    ],
}

CALC = {"fReceipts": [
    ("days_late", "int64", "0", None,
     ["INT ( fReceipts[received_date] - fReceipts[promised_date] )"]),
    ("accepted_kg", "double", "#,0", None, [
        "-- a rejected lot goes back to the supplier: it is not delivered and not paid",
        "IF ( fReceipts[inspection_result] = \"Rejected\", 0, fReceipts[received_kg] )",
    ]),
    ("spend_brl", "double", "#,0.00", None,
     ["fReceipts[accepted_kg] * fReceipts[price_brl_kg]"]),
]}

MEASURES = {"fReceipts": [
    ("Receipts", "1 Volume", "#,0", ["COUNTROWS ( fReceipts )"]),
    ("Accepted (t)", "1 Volume", "#,0.0", ["SUM ( fReceipts[accepted_kg] ) / 1000"]),
    ("Spend (BRL)", "1 Volume", "#,0", ["SUM ( fReceipts[spend_brl] )"]),
    ("Avg Price (BRL/kg)", "1 Volume", "#,0.00", [
        "-- weighted by kg, not a simple average of prices",
        "DIVIDE ( [Spend (BRL)], SUM ( fReceipts[accepted_kg] ) )",
    ]),
    ("On-Time %", "2 Delivery", "0.0%", [
        "DIVIDE (",
        "    CALCULATE ( COUNTROWS ( fReceipts ), fReceipts[days_late] <= 0 ),",
        "    [Receipts]",
        ")",
    ]),
    ("Late Receipts", "2 Delivery", "#,0",
     ["CALCULATE ( COUNTROWS ( fReceipts ), fReceipts[days_late] > 0 )"]),
    ("Avg Days Late", "2 Delivery", "#,0.0", [
        "-- only receipts that arrived after the promised date",
        "CALCULATE ( AVERAGE ( fReceipts[days_late] ), fReceipts[days_late] > 0 )",
    ]),
    ("Fill Rate %", "2 Delivery", "0.0%",
     ["DIVIDE ( SUM ( fReceipts[accepted_kg] ), SUM ( fReceipts[ordered_kg] ) )"]),
    ("Nonconformities", "3 Quality", "#,0",
     ["CALCULATE ( COUNTROWS ( fReceipts ), fReceipts[nonconformity] <> \"No issue\" )"]),
    ("Nonconformity Rate %", "3 Quality", "0.0%", ["DIVIDE ( [Nonconformities], [Receipts] )"]),
    ("Rejection Rate %", "3 Quality", "0.0%", [
        "DIVIDE (",
        "    CALCULATE ( COUNTROWS ( fReceipts ), fReceipts[inspection_result] = \"Rejected\" ),",
        "    [Receipts]",
        ")",
    ]),
    ("Price vs Reference %", "1 Volume", "+0.0%;-0.0%;0.0%", [
        "-- paid price compared with the material's reference price",
        "VAR paid = [Avg Price (BRL/kg)]",
        "VAR reference =",
        "    DIVIDE (",
        "        SUMX ( fReceipts, fReceipts[accepted_kg] * RELATED ( dMaterial[reference_price_brl_kg] ) ),",
        "        SUM ( fReceipts[accepted_kg] )",
        "    )",
        "RETURN DIVIDE ( paid - reference, reference )",
    ]),
]}

RELS = [
    ("fReceipts", "supplier_id", "dSupplier", "supplier_id", True),
    ("fReceipts", "material_id", "dMaterial", "material_id", True),
    ("fReceipts", "received_date", "dCalendar", "date", True),
]

STYLE = Style(dark="#0B2545", accent="#1F6FB2", subtitle="#8DB8E8", bg="#EEF3F8",
              palette=["#1F6FB2", "#0B2545", "#8DB8E8", "#E07A1F", "#5FA8A0", "#B8C4D6", "#C8553D"])
FOOT = "AC Metais\nNov 2025 – Oct 2026"

# Layout: dark sidebar on the left (title + filters), content on the right
SIDE = 232
X0, WIDE = SIDE + 16, 1280 - SIDE - 32            # content starts at 248, 1016 wide
CW = (WIDE - 3 * 12) // 4                          # 4 KPI cards
CX = [X0 + i * (CW + 12) for i in range(4)]
THIRD = (WIDE - 2 * 12) // 3
HALF = (WIDE - 12) // 2


def pages():
    s = STYLE
    p1 = Page("supplier_performance", "Supplier performance", s)
    p1.sidebar("Sheet metal intake", "Supplier performance",
               "", FOOT, SIDE)
    p1.add("slicer supplier", 16, 112, SIDE - 32, 84, p1.slicer(col("dSupplier", "supplier"), "Supplier"))
    p1.add("slicer material", 16, 208, SIDE - 32, 84, p1.slicer(col("dMaterial", "material"), "Material"))
    p1.add("slicer quarter", 16, 304, SIDE - 32, 84, p1.slicer(col("dCalendar", "quarter"), "Quarter"))
    for x, name in zip(CX, ["On-Time %", "Fill Rate %", "Nonconformity Rate %", "Avg Days Late"]):
        p1.add("card " + name, x, 16, CW, 96, p1.card(m(name)))
    p1.add("bar ontime supplier", X0, 124, THIRD, 276, p1.chart(
        "clusteredBarChart", col("dSupplier", "supplier"), m("On-Time %"),
        "On-time % by supplier", sort=m("On-Time %"), fill=s.accent))
    p1.add("line ontime month", X0 + THIRD + 12, 124, THIRD, 276, p1.chart(
        "lineChart", col("dCalendar", "month_label"), m("On-Time %"),
        "On-time % by month",
        sort=col("dCalendar", "month_label"), sort_dir="Ascending", fill=s.dark, labels=False))
    p1.add("col nonconf type", X0 + 2 * (THIRD + 12), 124, THIRD, 276, p1.chart(
        "clusteredBarChart", col("fReceipts", "nonconformity"), m("Receipts"),
        "Nonconformities by type", sort=m("Receipts"), fill="#E07A1F"),
        filters=[categorical_filter("fReceipts", "nonconformity",
                                    ["Surface rust / oxidation", "Thickness out of tolerance",
                                     "Wrong dimensions", "Damaged in transport",
                                     "Missing mill certificate"], "p1 nonconf")])
    p1.add("table scorecard", X0, 412, WIDE, 292, p1.table(
        [col("dSupplier", "supplier"), col("dSupplier", "supplier_type"), m("Receipts"),
         m("On-Time %"), m("Avg Days Late"), m("Fill Rate %"), m("Nonconformity Rate %"),
         m("Rejection Rate %"), m("Avg Price (BRL/kg)")],
        "Supplier scorecard", sort=m("Receipts")))

    p2 = Page("spend_and_price", "Spend and price", s)
    p2.sidebar("Sheet metal intake", "Spend and price",
               "", FOOT, SIDE)
    p2.add("slicer supplier", 16, 112, SIDE - 32, 84, p2.slicer(col("dSupplier", "supplier"), "Supplier"))
    p2.add("slicer material", 16, 208, SIDE - 32, 84, p2.slicer(col("dMaterial", "material"), "Material"))
    p2.add("slicer quarter", 16, 304, SIDE - 32, 84, p2.slicer(col("dCalendar", "quarter"), "Quarter"))
    for x, name in zip(CX, ["Spend (BRL)", "Accepted (t)", "Avg Price (BRL/kg)", "Receipts"]):
        p2.add("card " + name, x, 16, CW, 96, p2.card(m(name)))
    p2.add("line price", X0, 124, HALF, 276, p2.chart(
        "lineChart", col("dCalendar", "month_label"), m("Avg Price (BRL/kg)"),
        "Avg price by material (BRL/kg)", series=col("dMaterial", "material"),
        sort=col("dCalendar", "month_label"), sort_dir="Ascending", labels=False))
    p2.add("col spend month", X0 + HALF + 12, 124, HALF, 276, p2.chart(
        "clusteredColumnChart", col("dCalendar", "month_label"), m("Spend (BRL)"),
        "Spend by month (BRL)",
        sort=col("dCalendar", "month_label"), sort_dir="Ascending", fill=s.accent, labels=False))
    p2.add("donut spend supplier", X0, 412, THIRD, 292, p2.chart(
        "clusteredBarChart", col("dSupplier", "supplier"), m("Spend (BRL)"),
        "Spend by supplier (BRL)", sort=m("Spend (BRL)"), fill=s.dark))
    p2.add("table material", X0 + THIRD + 12, 412, WIDE - THIRD - 12, 292, p2.table(
        [col("dMaterial", "material_description"), m("Accepted (t)"), m("Spend (BRL)"),
         m("Avg Price (BRL/kg)"), m("Price vs Reference %"), m("On-Time %")],
        "Purchases by material and thickness", sort=m("Spend (BRL)")))
    return [p1, p2]


if __name__ == "__main__":
    model = Model("sheet_metal_intake.xlsx", TABLES, MEASURES, RELS, calc=CALC,
                  sort_by={("dCalendar", "month_label"): "year_month_number"},
                  data_folder="C:\\sheet-metal-intake-dashboard\\data\\")
    build_project(ROOT / "powerbi", "SheetMetalIntake", model, pages(), STYLE, "Sheet Metal Intake")
