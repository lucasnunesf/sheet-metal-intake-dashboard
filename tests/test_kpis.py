"""The numbers quoted in the README come from the data (pandas mirror of the DAX measures)."""
import subprocess
import sys

import pytest

from conftest import ROOT
from kpi_snapshot import kpis, load
from pbip_check import read_model
from project import NAME


@pytest.fixture(scope="module")
def r():
    return load()


@pytest.fixture(scope="module")
def k(r):
    return kpis(r)


def test_headline_numbers(k):
    assert k["receipts"] == 1471
    assert round(k["accepted_t"]) == 1295
    assert round(k["spend_brl"] / 1e6, 1) == 19.7
    assert round(k["on_time"], 3) == 0.842
    assert round(k["fill_rate"], 3) == 0.974
    assert round(k["nonconformity"], 3) == 0.060
    assert k["rejected_lots"] == 19


def test_cheapest_source_is_the_least_reliable(k):
    price = k["carbon_price_by_supplier"].round(2)
    assert price.idxmin() == "Steel mill direct C"
    assert price.to_dict() == {"Steel mill direct C": 7.04, "Steel service center A": 7.96,
                               "Steel service center B": 7.80}
    s = k["suppliers"]
    assert s.on_time.idxmin() == "Steel mill direct C"
    assert round(s.on_time["Steel mill direct C"], 2) == 0.64
    assert round(s.on_time["Steel service center A"], 3) == 0.948


def test_rust_and_price_trends(k):
    assert round(k["rust_rainy_vs_dry"], 1) == 3.8
    assert round(k["carbon_price_change"], 2) == 0.09


def test_rejected_lot_is_not_delivered_or_paid(r):
    rejected = r[r.inspection_result == "Rejected"]
    assert len(rejected) > 0
    assert (rejected.accepted_kg == 0).all() and (rejected.spend_brl == 0).all()


def test_model_uses_accepted_kg_for_fill_rate_spend_and_price():
    tables, _ = read_model(ROOT / "powerbi" / f"{NAME}.SemanticModel")
    f = tables["fReceipts"]
    assert '"Rejected", 0' in f["calc"]["accepted_kg"]
    assert "accepted_kg" in f["calc"]["spend_brl"]
    for name in ("Fill Rate %", "Avg Price (BRL/kg)", "Accepted (t)", "Price vs Reference %"):
        assert "accepted_kg" in f["measures"][name], name
        assert "received_kg" not in f["measures"][name], name


def test_avg_price_is_weighted_by_kg(r):
    weighted = r.spend_brl.sum() / r.accepted_kg.sum()
    simple = r.price_brl_kg.mean()
    assert round(weighted, 2) == 15.22 and round(simple, 2) == 15.00   # simple average is off


def test_snapshot_script_runs():
    out = subprocess.run([sys.executable, "scripts/kpi_snapshot.py"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    assert "Fill rate (accepted kg)    97.4%" in out
