"""Conservative, independently reproducible statement valuations.

All money amounts must be TRY in the same units. A snapshot market cap and
TTM accounting flows are deliberately kept separate from vendor ratios.
"""
from __future__ import annotations
import math


def _positive(value):
    try:
        n=float(value)
        return n if math.isfinite(n) and n>0 else None
    except (ValueError,TypeError):
        return None


def calculate_ratios(market_cap_try=None, ttm_parent_profit_try=None,
                     parent_equity_try=None, net_debt_try=None,
                     ttm_ebitda_try=None):
    """Return unavailable rather than backfill missing fields with zero."""
    cap=_positive(market_cap_try)
    profit=_positive(ttm_parent_profit_try)
    equity=_positive(parent_equity_try)
    ebitda=_positive(ttm_ebitda_try)
    pe=cap/profit if cap is not None and profit is not None else None
    pb=cap/equity if cap is not None and equity is not None else None
    net_debt=None
    try:
        if net_debt_try is not None and math.isfinite(float(net_debt_try)):
            net_debt=float(net_debt_try)
    except (ValueError,TypeError):
        pass
    ev=(cap+net_debt) if cap is not None and net_debt is not None else None
    ev_ebitda=ev/ebitda if ev is not None and ev>0 and ebitda is not None else None
    return {"pe":pe,"pb":pb,"ev":ev_ebitda,
            "inputs":{"market_cap_try":cap,"ttm_parent_profit_try":profit,
                      "parent_equity_try":equity,"net_debt_try":net_debt,
                      "ttm_ebitda_try":ebitda}}


def reconcile(calculated, vendor, tolerance=0.35):
    """Classification for each vendor comparison; never auto-overwrite a ratio."""
    if calculated is None or vendor is None:
        return "UNVERIFIABLE"
    try:
        a=float(calculated); b=float(vendor)
    except (TypeError,ValueError):
        return "UNVERIFIABLE"
    if not (math.isfinite(a) and math.isfinite(b)):
        return "UNVERIFIABLE"
    if a>0 and b>0 and abs(a-b)/max(abs(a),1.0)<=tolerance:
        return "WITHIN_TOLERANCE"
    return "REVIEW"
