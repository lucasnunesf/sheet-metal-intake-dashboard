"""The synthetic dataset: reproducible, consistent keys, and the receiving rules hold."""
import pandas as pd
import pytest

from conftest import ROOT, load

DATA = ROOT / "data" / "sheet_metal_intake.xlsx"


@pytest.fixture(scope="module")
def x():
    return load(DATA)


def test_generator_is_reproducible(fresh):
    work, logs = fresh
    assert "1,471 receipts" in logs["generate"]
    new = load(work / "data" / "sheet_metal_intake.xlsx")
    for sheet, df in load(DATA).items():
        pd.testing.assert_frame_equal(new[sheet], df, obj=sheet)


def test_keys(x):
    r = x["fReceipts"]
    assert r.receipt_id.is_unique and r.po_number.is_unique
    assert r.supplier_id.isin(x["dSupplier"].supplier_id).all()
    assert r.material_id.isin(x["dMaterial"].material_id).all()
    assert r.received_date.isin(x["dCalendar"].date).all()


def test_each_supplier_only_sells_its_materials(x):
    r = x["fReceipts"].merge(x["dMaterial"], on="material_id")
    sells = r.groupby("supplier_id").material.unique().apply(set)
    assert sells["S03"] == {"Carbon steel SAE 1020"}
    assert sells["S06"] == {"Aluminum 5052"}
    assert sells["S04"] <= {"Stainless AISI 304", "Stainless AISI 430"}


def test_quantities(x):
    r = x["fReceipts"]
    assert (r.sheets_received <= r.sheets_ordered).all()
    assert (r.received_kg <= r.ordered_kg).all()
    assert (r.sheets_received > 0).all()


def test_weight_comes_from_sheet_size_and_density(x):
    r = x["fReceipts"].merge(x["dMaterial"], on="material_id")
    wl = r.sheet_size_mm.str.split(" x ", expand=True).astype(int)
    kg_sheet = wl[0] * wl[1] / 1e6 * r.thickness_mm / 1000 * r.density_kg_m3
    assert ((r.ordered_kg - r.sheets_ordered * kg_sheet).abs() <= 0.06).all()


def test_dates(x):
    r = x["fReceipts"]
    assert (r.promised_date > r.po_date).all()
    assert r.received_date.between("2025-11-01", "2026-10-31").all()


def test_inspection_result_matches_nonconformity(x):
    r = x["fReceipts"]
    ok = r.nonconformity == "No issue"
    assert (r.loc[ok, "inspection_result"] == "Approved").all()
    assert (r.loc[~ok, "inspection_result"] != "Approved").all()
    # only measurable defects lead to a rejected lot
    rejected = r.loc[r.inspection_result == "Rejected", "nonconformity"]
    assert set(rejected) <= {"Thickness out of tolerance", "Wrong dimensions"}
