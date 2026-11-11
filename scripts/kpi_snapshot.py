"""
Print the main numbers of the dashboard straight from the Excel file, using pandas.

The logic mirrors the DAX measures in build_pbip.py, so the numbers can be checked
without Power BI (and the tests compare both).
Usage:  python scripts/kpi_snapshot.py
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data" / "sheet_metal_intake.xlsx"
RAINY = (12, 1, 2, 3)


def load(path=DATA):
    x = pd.read_excel(path, sheet_name=None)
    r = x["fReceipts"].merge(x["dSupplier"], on="supplier_id").merge(x["dMaterial"], on="material_id")
    r["days_late"] = (r.received_date - r.promised_date).dt.days
    r["accepted_kg"] = r.received_kg.where(r.inspection_result != "Rejected", 0.0)
    r["spend_brl"] = r.accepted_kg * r.price_brl_kg
    return r


def price(r):
    return r.spend_brl.sum() / r.accepted_kg.sum()


def by_supplier(r):
    g = r.groupby("supplier")
    return pd.DataFrame({
        "receipts": g.size(),
        "on_time": g.days_late.apply(lambda s: (s <= 0).mean()),
        "fill_rate": g.accepted_kg.sum() / g.ordered_kg.sum(),
        "nonconformity": g.nonconformity.apply(lambda s: (s != "No issue").mean()),
    })


def kpis(r):
    carbon = r[r.material == "Carbon steel SAE 1020"]
    carbon_price = carbon.groupby("supplier").apply(price, include_groups=False)
    rust = r.nonconformity.str.startswith("Surface rust")
    rainy = r.received_date.dt.month.isin(RAINY)
    before, after = carbon[carbon.received_date < "2026-06-01"], carbon[carbon.received_date >= "2026-06-01"]
    return {
        "receipts": len(r),
        "accepted_t": r.accepted_kg.sum() / 1000,
        "spend_brl": r.spend_brl.sum(),
        "on_time": (r.days_late <= 0).mean(),
        "fill_rate": r.accepted_kg.sum() / r.ordered_kg.sum(),
        "nonconformity": (r.nonconformity != "No issue").mean(),
        "rejected_lots": int((r.inspection_result == "Rejected").sum()),
        "carbon_price_by_supplier": carbon_price,
        "suppliers": by_supplier(r),
        "rust_rainy_vs_dry": rust[rainy].mean() / rust[~rainy].mean(),
        "carbon_price_change": price(after) / price(before) - 1,
    }


if __name__ == "__main__":
    k = kpis(load())
    print(f"Receipts                   {k['receipts']:,}")
    print(f"Accepted                   {k['accepted_t']:,.0f} t   spend BRL {k['spend_brl'] / 1e6:.1f}M")
    print(f"On time                    {k['on_time']:.1%}")
    print(f"Fill rate (accepted kg)    {k['fill_rate']:.1%}   rejected lots: {k['rejected_lots']}")
    print(f"Nonconformity rate         {k['nonconformity']:.1%}")
    print(f"Rust, rainy vs dry months  {k['rust_rainy_vs_dry']:.1f}x")
    print(f"Carbon steel price change  {k['carbon_price_change']:+.1%} from June 2026")
    print("\nCarbon steel, BRL/kg by supplier")
    print(k["carbon_price_by_supplier"].round(2).to_string())
    print("\nSupplier scorecard")
    print(k["suppliers"].sort_values("on_time").to_string(
        formatters={c: "{:.1%}".format for c in ("on_time", "fill_rate", "nonconformity")}))
