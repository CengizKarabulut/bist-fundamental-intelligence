from __future__ import annotations

import json
from pathlib import Path

from analyze import profile, apply_profile_primary_source, economically_valid

R = Path("reports")


def load(symbol: str) -> dict:
    p = R / f"{symbol}_report.json"
    if not p.exists():
        raise AssertionError(f"Missing report: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def near(a, b, rel=0.02):
    if a is None or b is None:
        return False
    return abs(a-b) <= max(abs(b)*rel, 1e-9)


def main():
    # Provider-industry labels can be broad/misleading; company semantics must win.
    assert profile({"description":"Haci Omer Sabanci Holding A.S.","industry":"Regional Banks","sector":"Finance"}) == "Holding"
    assert profile({"description":"Is Yatirim Menkul Degerler AS","industry":"Investment Banks/Brokers","sector":"Finance"}) == "Finansal"
    assert profile({"description":"Turkiye Sinai Kalkinma Bankasi A.S.","industry":"Investment Banks/Brokers","sector":"Finance"}) == "Banka"
    assert profile({"description":"Adra Gayrimenkul Yatirim Ortakligi A.S.","industry":"Financial Conglomerates","sector":"Finance"}) == "GYO"
    assert profile({"description":"Gozde Girisim Sermayesi Yatirim Ortakligi A.S.","industry":"Investment Banks/Brokers","sector":"Finance"}) == "Yatırım Ortaklığı"
    assert profile({"description":"TAV Havalimanlari Holding A.S.","industry":"Other Transportation","sector":"Transportation"}) == "Genel"
    assert profile({"description":"Petkim Petrokimya Holding A.S.","industry":"Chemicals: Specialty","sector":"Process Industries"}) == "Genel"
    assert profile({"description":"Deva Holding A.S.","industry":"Pharmaceuticals: Major","sector":"Health Technology"}) == "Genel"

    # Non-positive valuation multiples are A/D, never "cheap".
    assert economically_valid("pe",-5.0) is False
    assert economically_valid("pb",0.0) is False
    assert economically_valid("ev",-1.0) is False
    assert economically_valid("pfcf",12.0) is True

    # Negative-equity denominator guard must prevent misleading ratio scores.
    dummy={
        "roe":{"scoreable":True,"abs":100.0},
        "pb":{"scoreable":True,"abs":100.0},
        "de":{"scoreable":True,"abs":100.0},
        "eq_assets":{"scoreable":True,"abs":0.0},
    }
    guarded=apply_profile_primary_source(
        dummy,"Genel",{"summary":{"equity":-1.0}},{}
    )
    for k in ("roe","pb","de","eq_assets"):
        assert guarded[k]["scoreable"] is False, (k,guarded[k])
        assert guarded[k]["abs"] is None, (k,guarded[k])

    ase = load("ASELS")
    akb = load("AKBNK")
    ekg = load("EKGYO")
    ages = load("AGESA")
    isfin = load("ISFIN")

    assert ase["profile"] == "Savunma/Teknoloji", ase["profile"]
    assert akb["profile"] == "Banka", akb["profile"]
    assert ekg["profile"] == "GYO", ekg["profile"]
    assert ages["profile"] == "Sigorta", ages["profile"]
    assert isfin["profile"] == "Finansal", isfin["profile"]

    # Financial institutions should prefer UFRS and must not fail simply because
    # XI_29 industrial statements are unavailable.
    for r in (ages,isfin):
        hist=r["historical_analysis"]
        assert not hist.get("error"), hist.get("error")
        assert hist.get("financial_group_used") == "UFRS", hist.get("financial_group_used")

    # GYO: classic industrial valuation multiples must not create a valuation score.
    assert ekg["scores"]["valuation"] is None, ekg["scores"]["valuation"]
    assert ekg["metrics"]["pb"]["scoreable"] is False
    assert ekg["metrics"]["ev"]["scoreable"] is False
    assert ekg["metrics"]["pe"]["scoreable"] is False
    assert ekg["metrics"]["fcfm"]["scoreable"] is False

    # İş Yatırım realised company-card values have priority for GYO.
    assert ekg["metrics"]["pb"]["source"] == "İş Yatırım"
    assert near(ekg["metrics"]["pb"]["v"], 0.5, rel=0.15)
    assert ekg["metrics"]["ev"]["v"] is None
    assert "A/D" in ekg["metrics"]["ev"]["source"]

    # Net debt derived from statements must reconcile to İş Yatırım company card.
    h = ekg["historical_analysis"]["summary"]
    assert h["net_debt_statement"] is not None
    assert h["net_debt_provider"] is not None
    assert near(h["net_debt_statement"], h["net_debt_provider"], rel=0.01), (
        h["net_debt_statement"], h["net_debt_provider"]
    )

    # GYO benchmark should be the BIST GYO index.
    assert ekg["sector_index"]["code"] == "XGMYO", ekg["sector_index"]["code"]

    # Cross-source ciro-growth conflict must be visible, not silently averaged away.
    checks = {x["label"]: x for x in ekg["source_validation"]["checks"]}
    assert "Ciro Büyümesi TTM" in checks
    assert checks["Ciro Büyümesi TTM"]["status"] in {"KRİTİK FARK", "BAZ/FRESHNESS FARKI"}

    # Bank profile must not use industrial cash-flow / net-debt scoring.
    for k in ("nde", "fcfm", "ev"):
        assert akb["metrics"][k]["app"] is False, (k, akb["metrics"][k])

    print("Semantic regression checks passed: ASELS + AKBNK + EKGYO + AGESA + ISFIN")


if __name__ == "__main__":
    main()
