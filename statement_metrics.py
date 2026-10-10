"""Statement-first fundamental factor engine.

Derives standardized ratios from downloaded historical financial statements.
Market capitalization is an external *price input*, never a vendor multiple.
A missing, stale, or ambiguously labeled statement item yields N/A, not a
substitute TradingView/Is Yatirim/EkoFin ratio.

Every metric includes definition, reporting period and input provenance.
"""
from __future__ import annotations

import math
from typing import Any

from statement_reconciliation import calculate_ratios

STANDARD_KEYS = (
    "pe","pb","ev","roe","roa","curr","quick","de","nde","eq_assets",
    "gross","opm","netm","ebitdam","rev_g","ni_g","fcfm","pfcf",
)
NOT_INDUSTRIAL = {"Banka","Sigorta","Finansal","Holding","Yatırım Ortaklığı","GYO"}
FINANCIAL_MODELS = {"Banka","Sigorta","Finansal"}


def _number(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _divide(numerator, denominator, *, percent=False, require_positive_num=False):
    n=_number(numerator); d=_number(denominator)
    if n is None or d is None or d <= 0 or (require_positive_num and n <= 0):
        return None
    return n/d*(100.0 if percent else 1.0)


def derive_statement_ratios(history: dict[str,Any] | None,
                            market_cap_try: float | None,
                            profile: str = "Genel") -> dict[str,dict[str,Any]]:
    """Calculate ratios using one fiscal statement period and documented bases.

    For TTM flows, the history engine has already verified four contiguous
    quarters. This layer further requires their last quarter to agree with
    the selected balance/reporting date.
    """
    history=history or {}
    hs=history.get("summary") or {}
    rows=history.get("rows_found") or {}
    period=hs.get("latest_period")
    balances=hs.get("balance_input_periods") or {}
    flows=hs.get("flow_input_periods") or {}
    cap=_number(market_cap_try)
    if cap is not None and cap <= 0: cap=None
    industrial=profile not in NOT_INDUSTRIAL
    nonfinancial=profile not in FINANCIAL_MODELS
    group=history.get("financial_group_used")
    statement_origin=history.get("statement_origin") or "BORSAPY_IS_YATIRIM"
    source=f"{statement_origin} financial statements ({group or 'unknown schema'})"

    def balance(key):
        return _number(hs.get(key)) if period and balances.get(key)==period else None

    def flow(key, field):
        return _number(hs.get(field)) if period and flows.get(key)==period else None

    def record(key, value, formula, inputs, *, applicable=True, note=None):
        value=_number(value) if applicable and period and not history.get("error") else None
        return {
            "value":value,
            "status":("NOT_APPLICABLE" if not applicable
                      else "CALCULATED" if value is not None
                      else "UNAVAILABLE"),
            "method":"STANDARD_FINANCIAL_STATEMENT",
            "formula":formula,
            "inputs":inputs,
            "reporting_period":period,
            "financial_group":group,
            "statement_source":source,
            "market_value_source":("TradingView snapshot market capitalization"
                                   if cap is not None else None),
            "note":note,
        }

    parent_row=str(rows.get("net_income") or "")
    has_parent_profit="ana ortakl" in parent_row.casefold()
    parent_profit=flow("net_income","ttm_net_income") if has_parent_profit else None
    total_profit=flow("total_net_income","ttm_total_net_income")
    parent_eq=balance("parent_equity")
    total_assets=balance("total_assets")
    financial_debt=balance("financial_debt")
    ca=balance("current_assets")
    cl=balance("current_liabilities")
    stocks=balance("inventories")
    revenue=flow("revenue","ttm_revenue")
    # For average returns both current and same-quarter-prior balance entries
    # must be explicitly present; history engine checks positive average.
    parent_avg=_number(hs.get("avg_parent_equity_ttm")) if parent_eq is not None else None
    assets_avg=_number(hs.get("avg_assets_ttm")) if total_assets is not None else None
    ebitda=(_number(hs.get("ttm_ebitda"))
            if period and hs.get("ttm_ebitda_reporting_period")==period else None)
    if ebitda is not None and ebitda <= 0:
        ebitda_pos=None
    else:
        ebitda_pos=ebitda
    nd=(_number(hs.get("net_debt_statement"))
        if hs.get("net_debt_statement_period_aligned") and period else None)

    # Operating cashflow and capital expenditure must both cover the same TTM.
    fcf=_number(hs.get("ttm_free_cash_flow"))
    fcf_origin=hs.get("ttm_free_cash_flow_source","UNAVAILABLE")
    if fcf_origin=="EXPLICIT_CASHFLOW":
        if flows.get("free_cash_flow")!=period: fcf=None
    elif fcf_origin=="RECONSTRUCTED_CFO_MINUS_CAPEX":
        if flows.get("operating_cash_flow")!=period or flows.get("capex")!=period:
            fcf=None
    else:
        fcf=None

    ratios={}
    common={"market_cap_try":cap}
    inputs={"ttm_parent_net_profit":parent_profit,**common}
    ratios["pe"]=record("pe",_divide(cap,parent_profit,require_positive_num=True),
                         "Market capitalization / TTM parent-attributable net profit",
                         {**inputs,"income_row":parent_row})
    ratios["pb"]=record("pb",_divide(cap,parent_eq),
                         "Market capitalization / parent-attributable equity",
                         {**common,"parent_equity":parent_eq,"equity_row":rows.get("parent_equity")})
    # Enterprise value based only on debt less cash/financial investment is
    # indicative; it omits minority interests, lease adjustments, etc.
    ev_inputs={"market_cap_try":cap,"statement_net_debt":nd,
               "ttm_ebitda":ebitda,"ebitda_source":hs.get("ttm_ebitda_source")}
    indicative_ev=calculate_ratios(
        market_cap_try=cap,net_debt_try=nd,ttm_ebitda_try=ebitda_pos
    )["ev"] if industrial else None
    ratios["ev"]=record("ev",indicative_ev,
        "(Market capitalization + documented net debt) / TTM EBITDA",
        ev_inputs,applicable=industrial,
        note="Indicative: minority interests, leases and other EV adjustments not reconciled")

    ratios["roe"]=record("roe",_divide(parent_profit,parent_avg,percent=True),
        "100 * TTM parent net profit / average parent-attributable equity",
        {"ttm_parent_net_profit":parent_profit,"average_parent_equity":parent_avg})
    ratios["roa"]=record("roa",_divide(total_profit,assets_avg,percent=True),
        "100 * TTM consolidated net profit / average total assets",
        {"ttm_consolidated_profit":total_profit,"average_assets":assets_avg,
         "total_profit_row":rows.get("total_net_income")})
    ratios["curr"]=record("curr",_divide(ca,cl),
        "Current assets / current liabilities",{"current_assets":ca,"current_liabilities":cl},
        applicable=nonfinancial)
    quick_n=(ca-stocks) if ca is not None and stocks is not None and ca>=stocks>=0 else None
    ratios["quick"]=record("quick",_divide(quick_n,cl),
        "(Current assets - inventories) / current liabilities",
        {"current_assets":ca,"inventories":stocks,"current_liabilities":cl},
        applicable=nonfinancial)
    ratios["de"]=record("de",_divide(financial_debt,parent_eq),
        "Statement financial debt / parent-attributable equity",
        {"financial_debt":financial_debt,"parent_equity":parent_eq},
        applicable=industrial, note="Debt here is financial borrowings only")
    ratios["eq_assets"]=record("eq_assets",_divide(parent_eq,total_assets),
        "Parent-attributable equity / total assets",
        {"parent_equity":parent_eq,"total_assets":total_assets})

    ratios["nde"]=record("nde",_divide(nd,ebitda_pos),
        "Documented net debt / TTM EBITDA",
        {"net_debt":nd,"ttm_ebitda":ebitda,"ebitda_source":hs.get("ttm_ebitda_source")},
        applicable=industrial)
    gp=flow("gross_profit","ttm_gross_profit")
    op=flow("operating_profit","ttm_operating_profit")
    ratios["gross"]=record("gross",_divide(gp,revenue,percent=True),
        "100 * TTM gross profit / TTM revenue",{"gross_profit":gp,"revenue":revenue},
        applicable=industrial)
    ratios["opm"]=record("opm",_divide(op,revenue,percent=True),
        "100 * TTM operating profit / TTM revenue",
        {"operating_profit":op,"revenue":revenue},applicable=industrial)
    ratios["netm"]=record("netm",_divide(total_profit,revenue,percent=True),
        "100 * TTM consolidated profit / TTM revenue",
        {"total_profit":total_profit,"revenue":revenue},applicable=industrial)
    ratios["ebitdam"]=record("ebitdam",_divide(ebitda,revenue,percent=True),
        "100 * TTM EBITDA / TTM revenue",
        {"ttm_ebitda":ebitda,"revenue":revenue,
         "ebitda_source":hs.get("ttm_ebitda_source")},
        applicable=industrial,note="May use labeled reconstructed EBITDA")
    rev_growth=_number(hs.get("revenue_ttm_yoy")) if revenue is not None else None
    ni_growth=_number(hs.get("net_income_ttm_yoy")) if flow("net_income","ttm_net_income") is not None else None
    ratios["rev_g"]=record("rev_g",rev_growth,
        "100 * (TTM revenue / preceding TTM revenue - 1)",
        {"ttm_revenue":revenue,"basis":"8 contiguous quarters"},applicable=nonfinancial)
    ratios["ni_g"]=record("ni_g",ni_growth,
        "100 * (TTM net profit / preceding TTM net profit - 1)",
        {"ttm_net_profit":flow("net_income","ttm_net_income"),
         "basis":"8 contiguous quarters"},
        note="Negative base years may produce unstable growth values")
    ratios["fcfm"]=record("fcfm",_divide(fcf,revenue,percent=True),
        "100 * TTM free cash flow / TTM revenue",
        {"ttm_fcf":fcf,"ttm_revenue":revenue,"fcf_source":fcf_origin},
        applicable=industrial)
    ratios["pfcf"]=record("pfcf",_divide(cap,fcf,require_positive_num=True),
        "Market capitalization / positive TTM free cash flow",
        {"market_cap_try":cap,"ttm_fcf":fcf,"fcf_source":fcf_origin},
        applicable=industrial)
    assert set(ratios)==set(STANDARD_KEYS), "Incomplete standardized accounting factor table"
    return ratios
