from __future__ import annotations

import json
from pathlib import Path

from analyze import profile, apply_profile_primary_source, economically_valid, scoreable
from version import __version__

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
    # Single source-of-truth guard for release metadata.
    version_file=Path("VERSION").read_text(encoding="utf-8").strip()
    assert version_file == __version__, f"VERSION dosyası ({version_file}) ile version.py ({__version__}) farklı"

    # Provider-industry labels can be broad/misleading; company semantics must win.
    assert profile({"description":"Haci Omer Sabanci Holding A.S.","industry":"Regional Banks","sector":"Finance"}) == "Holding"
    assert profile({"description":"Is Yatirim Menkul Degerler AS","industry":"Investment Banks/Brokers","sector":"Finance"}) == "Finansal"
    assert profile({"description":"Turkiye Sinai Kalkinma Bankasi A.S.","industry":"Investment Banks/Brokers","sector":"Finance"}) == "Banka"
    assert profile({"description":"Adra Gayrimenkul Yatirim Ortakligi A.S.","industry":"Financial Conglomerates","sector":"Finance"}) == "GYO"
    assert profile({"description":"Gozde Girisim Sermayesi Yatirim Ortakligi A.S.","industry":"Investment Banks/Brokers","sector":"Finance"}) == "Yatırım Ortaklığı"
    assert profile({"description":"TAV Havalimanlari Holding A.S.","industry":"Other Transportation","sector":"Transportation"}) == "Genel"
    assert profile({"symbol":"TAVHL","description":"TAV Havalimanlari Holding A.S.","industry":"Other Transportation","sector":"Transportation"}) == "Genel"
    assert profile({"symbol":"SISE","description":"Turkiye Sise ve Cam Fabrikalari A.S.","industry":"Home Furnishings","sector":"Consumer Durables"}) == "Genel"
    assert profile({"symbol":"ATSYH","description":"Atlantis Yatirim Holding A.S.","industry":"Investment Trusts/Mutual Funds","sector":"Miscellaneous"}) == "Holding"
    assert profile({"symbol":"ISBIR","description":"Isbir Holding AS","industry":"Textiles","sector":"Process Industries"}) == "Holding"
    assert profile({"symbol":"KERVN","description":"Kervansaray Yatirim Holding A.S.","industry":"Hotels/Resorts/Cruise lines","sector":"Consumer Services"}) == "Holding"
    assert profile({"description":"Petkim Petrokimya Holding A.S.","industry":"Chemicals: Specialty","sector":"Process Industries"}) == "Genel"
    assert profile({"description":"Deva Holding A.S.","industry":"Pharmaceuticals: Major","sector":"Health Technology"}) == "Genel"

    # Non-positive valuation multiples are A/D, never "cheap".
    assert economically_valid("pe",-5.0) is False
    assert economically_valid("pb",0.0) is False
    assert economically_valid("ev",-1.0) is False
    assert economically_valid("pfcf",12.0) is True

    # Portfolio/NAD-driven profiles must not receive generic consolidated scores.
    assert scoreable("roe","Holding") is False
    assert scoreable("pe","Holding") is False
    assert scoreable("roe","Yatırım Ortaklığı") is False
    assert scoreable("pb","Yatırım Ortaklığı") is False

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
    albrk = load("ALBRK")
    ekg = load("EKGYO")
    kchol = load("KCHOL")
    ages = load("AGESA")
    glbmd = load("GLBMD")
    isfin = load("ISFIN")

    assert ase["profile"] == "Savunma/Teknoloji", ase["profile"]
    assert akb["profile"] == "Banka", akb["profile"]
    assert albrk["profile"] == "Banka", albrk["profile"]
    assert ekg["profile"] == "GYO", ekg["profile"]
    assert kchol["profile"] == "Holding", kchol["profile"]

    # Participation-bank row aliases must resolve completely.
    ah=albrk["historical_analysis"]
    adq=ah.get("data_quality",{})
    assert not ah.get("error"), ah.get("error")
    assert adq.get("core_rows_found") == adq.get("core_rows_expected") == 3, adq
    assert adq.get("bank_operating_rows_found") == 2, adq
    assert ages["profile"] == "Sigorta", ages["profile"]
    assert glbmd["profile"] == "Finansal", glbmd["profile"]
    assert isfin["profile"] == "Finansal", isfin["profile"]

    # Supported financial institutions must resolve to a valid statement
    # schema. Insurers use UFRS; some non-bank financials are available only via
    # XI_29 and the engine should fall back transparently.
    ah=ages["historical_analysis"]
    assert not ah.get("error"), ah.get("error")
    assert ah.get("financial_group_used") == "UFRS", ah.get("financial_group_used")

    gh=glbmd["historical_analysis"]
    assert not gh.get("error"), gh.get("error")
    assert gh.get("financial_group_used") in {"UFRS","XI_29"}, gh.get("financial_group_used")

    # A provider can legitimately have no historical statements for a listed
    # symbol. The report must degrade gracefully instead of crashing.
    ih=isfin["historical_analysis"]
    assert ih.get("error"), "ISFIN is expected to exercise the no-history fallback"
    assert isfin["scores"] is not None

    # Special-profile engines must expose profile-appropriate metrics.
    ekg_sp=ekg["historical_analysis"].get("special_profile_analysis",{})
    assert ekg_sp.get("status") in {"NAV_REQUIRED","NAV_AVAILABLE"}, ekg_sp
    if ekg_sp.get("status")=="NAV_REQUIRED":
        assert ekg_sp.get("valuation",{}).get("pd_nav_discount_pct") is None

    kh_sp=kchol["historical_analysis"].get("special_profile_analysis",{})
    assert kh_sp.get("status") in {"NAV_REQUIRED","NAV_AVAILABLE"}, kh_sp
    assert kchol["scores"]["quality"] is None, kchol["scores"]["quality"]
    assert kchol["scores"]["valuation"] is None, kchol["scores"]["valuation"]
    assert kchol["scores"]["composite"] is None, kchol["scores"]["composite"]

    ag_sp=ages["historical_analysis"].get("special_profile_analysis",{})
    assert ag_sp.get("status")=="INSURANCE_ENGINE", ag_sp
    assert ag_sp.get("metrics",{}).get("net_written_premium") is not None, ag_sp
    assert ag_sp.get("metrics",{}).get("technical_balance") is not None, ag_sp

    gl_sp=glbmd["historical_analysis"].get("special_profile_analysis",{})
    assert gl_sp.get("status")=="FINANCIAL_ENGINE", gl_sp
    assert gl_sp.get("metrics",{}).get("activity_result") not in (None,0), gl_sp
    assert gl_sp.get("metrics",{}).get("receivables") not in (None,0), gl_sp
    gchecks={x["label"]:x for x in glbmd["source_validation"]["checks"]}
    assert gchecks["Cari FD/FAVÖK"]["status"] == "PROFİLDE SKOR DIŞI", gchecks["Cari FD/FAVÖK"]

    # Statement-derived target metrics must override generic provider TTM
    # values when İş Yatırım financial statements can reconstruct them.
    assert ekg["metrics"]["rev_g"]["source"] == "İş Yatırım Mali Tablo (TTM)"
    assert near(
        ekg["metrics"]["rev_g"]["v"],
        ekg["historical_analysis"]["summary"]["revenue_ttm_yoy"],
        rel=0.001,
    )
    assert glbmd["metrics"]["ni_g"]["source"] == "İş Yatırım Mali Tablo (TTM)"
    assert near(
        glbmd["metrics"]["ni_g"]["v"],
        glbmd["historical_analysis"]["summary"]["net_income_ttm_yoy"],
        rel=0.001,
    )

    # Financial institutions must not use industrial net-margin scoring.
    for r in (akb,albrk,ages,glbmd,isfin):
        assert r["metrics"]["netm"]["app"] is False, (r["symbol"],r["metrics"]["netm"])
    # Insurance equity/assets is informative, not a solvency-capital score.
    assert ages["metrics"]["eq_assets"]["app"] is False, ages["metrics"]["eq_assets"]
    assert "solvency oranının yerine kullanılmadı" in " ".join(
        ages["historical_analysis"]["commentary"].get("watch",[])
    )
    assert not any(
        x.startswith("Özkaynak/aktif oranı")
        for x in ages["historical_analysis"]["commentary"].get("risks",[])
    )
    assert "tarihsel finansal teyit içermez" in isfin["overall"].lower()

    # GYO: classic industrial valuation multiples must not create a valuation score.
    assert ekg["scores"]["valuation"] is None, ekg["scores"]["valuation"]
    assert ekg["scores"]["quality"] is not None, ekg["scores"]["quality"]
    assert ekg["scores"]["composite"] is None, ekg["scores"]["composite"]
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

    # Special profiles must use official BIST comparison universes instead
    # of the generic provider "Finance" sector.
    assert ekg["benchmark_context"]["sector_benchmark_code"] == "XGMYO", ekg["benchmark_context"]
    assert akb["benchmark_context"]["sector_benchmark_code"] == "XBANK", akb["benchmark_context"]
    assert ages["benchmark_context"]["sector_benchmark_code"] == "XSGRT", ages["benchmark_context"]

    # GYO price benchmark should also be the BIST GYO index.
    assert ekg["sector_index"]["code"] == "XGMYO", ekg["sector_index"]["code"]

    # Cross-source ciro-growth conflict must be visible, not silently averaged away.
    checks = {x["label"]: x for x in ekg["source_validation"]["checks"]}
    assert "Ciro Büyümesi TTM" in checks
    assert checks["Ciro Büyümesi TTM"]["status"] in {
        "KRİTİK FARK",
        "BAZ/FRESHNESS FARKI",
        "KAYNAK FARKI - BİRİNCİL KAYNAK UYGULANDI",
    }

    # Bank profile must not use industrial cash-flow / net-debt scoring.
    for k in ("nde", "fcfm", "ev"):
        assert akb["metrics"][k]["app"] is False, (k, akb["metrics"][k])

    print("Semantic regression checks passed: ASELS + AKBNK + ALBRK + EKGYO + KCHOL + AGESA + GLBMD + ISFIN")


if __name__ == "__main__":
    main()
