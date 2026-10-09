from __future__ import annotations

import argparse
import json
import math
import signal
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd

import analyze as eng
from statement_reconciliation import calculate_ratios, reconcile
from history_engine import build_historical_analysis

OUT = Path("audit_results")

PROFILE_RULES = {
    "Banka": {"must_exclude": {"ev","pfcf","roic","gross","opm","ebitdam","rev_g","curr","quick","de","nde","fcfm","pio"}},
    "Sigorta": {"must_exclude": {"ev","pfcf","roic","gross","opm","ebitdam","rev_g","curr","quick","de","nde","fcfm","pio"}},
    "Finansal": {"must_exclude": {"ev","pfcf","roic","gross","opm","ebitdam","rev_g","curr","quick","de","nde","fcfm","pio"}},
    "GYO": {"must_nonscore": {"pe","pb","ev","pfcf","eps_g","nde","fcfm","pio"}},
    "Holding": {"must_nonscore": {"pe","pb","ev","pfcf","rev_g","eps_g","gross","opm","ebitdam","nde","fcfm","pio"}},
    "Yatırım Ortaklığı": {"must_nonscore": {"pe","pb","eps_g","ni_g","netm"}},
}

def sev_rank(s: str) -> int:
    return {"OK":0,"INFO":1,"WARNING":2,"CRITICAL":3,"ERROR":4}.get(s,0)

def add_issue(issues, severity, code, detail):
    issues.append({"severity": severity, "code": code, "detail": str(detail)})

def finite(v):
    try:
        return v is not None and math.isfinite(float(v))
    except Exception:
        return False

class SymbolAuditTimeout(TimeoutError):
    pass

def _timeout_handler(signum, frame):
    raise SymbolAuditTimeout("symbol audit timeout")

def audit_symbol_with_timeout(row, universe_df, xu100_set, qn, seconds):
    """Bound one symbol audit so a provider hang cannot block an entire shard."""
    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        return audit_symbol(row, universe_df, xu100_set, qn)

    previous = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(int(seconds))
    try:
        return audit_symbol(row, universe_df, xu100_set, qn)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)

def audit_symbol(row, universe_df, xu100_set, qn):
    sym=str(row["symbol"]).upper()
    profile=eng.profile(row)
    issues=[]

    try:
        hist=build_historical_analysis(
            sym, profile, report_dir=None,
            quarterly_periods=qn, annual_periods=4,
            load_market_info=False,
        )
    except Exception as exc:
        hist={"error":f"{type(exc).__name__}: {exc}"}

    try:
        g=eng.groups(universe_df,row,xu100_set,profile)
        metrics=eng.analyze(row,profile,g)
        metrics=eng.apply_profile_primary_source(metrics,profile,hist,g)
        scores=eng.scores(metrics,profile)
    except Exception as exc:
        add_issue(issues,"ERROR","ENGINE_EXCEPTION",f"{type(exc).__name__}: {exc}")
        return {
            "symbol":sym,"profile":profile,"status":"ERROR",
            "issues":issues,"exception":traceback.format_exc(limit=3),
        }

    # 1) Hard engine invariants.
    for key,x in metrics.items():
        score=x.get("abs")
        if score is not None and not (0 <= float(score) <= 100):
            add_issue(issues,"ERROR","ABS_SCORE_RANGE",f"{key}={score}")
        for gn,gv in x.get("groups",{}).items():
            pct=gv.get("pct")
            if pct is not None and not (0 <= float(pct) <= 100):
                add_issue(issues,"ERROR","PERCENTILE_RANGE",f"{key}/{gn}={pct}")

    for name,val in {
        "quality":scores.get("quality"),
        "valuation":scores.get("valuation"),
        "composite":scores.get("composite"),
    }.items():
        if val is not None and not (0 <= float(val) <= 100):
            add_issue(issues,"ERROR","COMPOSITE_RANGE",f"{name}={val}")

    # 2) Profile-specific scoring invariants.
    rules=PROFILE_RULES.get(profile,{})
    for key in rules.get("must_exclude",set()):
        if key in metrics and metrics[key].get("app"):
            add_issue(issues,"ERROR","PROFILE_EXCLUSION",f"{profile}: {key} app=True")
    for key in rules.get("must_nonscore",set()):
        if key in metrics and metrics[key].get("scoreable"):
            add_issue(issues,"ERROR","PROFILE_NONSCORE",f"{profile}: {key} scoreable=True")

    if profile=="GYO":
        if scores.get("valuation") is not None:
            add_issue(issues,"CRITICAL","GYO_VALUATION_SCORE","GYO için klasik değerleme skoru üretilmiş.")
        if scores.get("composite") is not None:
            add_issue(issues,"CRITICAL","GYO_COMPOSITE_WITHOUT_NAV","NAD dışı metriklerden tam bileşik GYO skoru üretilmiş.")

    if profile in {"Holding","Yatırım Ortaklığı"}:
        if any(scores.get(k) is not None for k in ("quality","valuation","composite")):
            add_issue(
                issues,"CRITICAL","NAV_PROFILE_GENERIC_SCORE",
                f"{profile}: NAV/portföy yerine generic kalite/değerleme skoru üretilmiş."
            )
        bad=[k for k,x in metrics.items() if x.get("scoreable")]
        if bad:
            add_issue(
                issues,"ERROR","NAV_PROFILE_SCOREABLE_METRICS",
                f"{profile}: scoreable={','.join(bad)}"
            )

    if profile=="Banka" and metrics.get("fcfm",{}).get("app"):
        add_issue(issues,"CRITICAL","BANK_FCF_ACTIVE","Banka profilinde FCF metriği aktif.")
    if profile=="Sigorta" and metrics.get("eq_assets",{}).get("app"):
        add_issue(issues,"CRITICAL","INSURANCE_FAKE_SOLVENCY","Sigortada özkaynak/aktif solvency skoru gibi kullanılmış.")
    if profile in {"Banka","Sigorta","Finansal"} and metrics.get("netm",{}).get("app"):
        add_issue(issues,"CRITICAL","FINANCE_NET_MARGIN_ACTIVE",f"{profile}: sanayi tipi net marj aktif.")

    # 3) Historical statement/data-quality checks.
    if hist.get("error"):
        # Historical provider coverage can legitimately be absent for a listed
        # company (foreign issuer / unsupported statement schema). The core
        # cross-sectional report can still be valid, so provider unavailability
        # is a WARNING, not an engine failure.
        add_issue(issues,"WARNING","HISTORY_UNAVAILABLE",hist["error"])
    else:
        dq=hist.get("data_quality",{})
        found=dq.get("core_rows_found")
        expected=dq.get("core_rows_expected")
        if found is not None and expected:
            coverage=float(found)/float(expected)
            if coverage < .50:
                add_issue(issues,"CRITICAL","CORE_ROW_COVERAGE",f"{found}/{expected}")
            elif coverage < .75:
                add_issue(issues,"WARNING","CORE_ROW_COVERAGE",f"{found}/{expected}")

        qperiods=dq.get("quarterly_periods")
        if qperiods is not None and qperiods < 4:
            add_issue(issues,"WARNING","SHORT_HISTORY",f"quarterly_periods={qperiods}")

        if profile=="Banka":
            bop=dq.get("bank_operating_rows_found")
            if bop is not None and bop==0:
                add_issue(issues,"WARNING","BANK_OPERATING_ROW_COVERAGE","loan/deposit detail rows 0/2")
            elif bop is not None and bop==1:
                add_issue(issues,"INFO","BANK_OPERATING_ROW_COVERAGE","loan/deposit detail rows 1/2")

        sp=hist.get("special_profile_analysis",{})
        if profile=="Sigorta":
            if sp.get("status")!="INSURANCE_ENGINE":
                add_issue(issues,"CRITICAL","SPECIAL_PROFILE_ENGINE","Sigorta özel motoru çalışmadı")
            else:
                sm=sp.get("metrics",{})
                if sm.get("net_written_premium") is None:
                    add_issue(issues,"WARNING","INSURANCE_PREMIUM_MISSING","Net yazılan prim bulunamadı")
                if sm.get("technical_balance") is None:
                    add_issue(issues,"WARNING","INSURANCE_TECHNICAL_MISSING","Teknik denge bulunamadı")
        elif profile=="Finansal":
            if sp.get("status")!="FINANCIAL_ENGINE":
                add_issue(issues,"CRITICAL","SPECIAL_PROFILE_ENGINE","Finansal özel motor çalışmadı")
        elif profile in {"GYO","Holding","Yatırım Ortaklığı"}:
            if sp.get("status") not in {"NAV_REQUIRED","NAV_AVAILABLE"}:
                add_issue(issues,"CRITICAL","NAV_GATE_MISSING",f"{profile} için NAD kapısı oluşmadı")
        elif profile=="Banka":
            if sp.get("status")!="BANK_ENGINE":
                add_issue(issues,"CRITICAL","SPECIAL_PROFILE_ENGINE","Banka özel motoru çalışmadı")

        hs=hist.get("summary",{})
        equity=hs.get("equity")
        if finite(equity) and float(equity) <= 0:
            for key in ("roe","pb","de","eq_assets"):
                if metrics.get(key,{}).get("scoreable"):
                    add_issue(issues,"CRITICAL","NEG_EQUITY_GUARD",f"{key} negatif özkaynakta scoreable")

        stmt_nd=hs.get("net_debt_statement")
        provider_nd=hs.get("net_debt_provider")
        if finite(stmt_nd) and finite(provider_nd) and abs(float(provider_nd)) > 1:
            gap=abs(float(stmt_nd)-float(provider_nd))/abs(float(provider_nd))
            if gap > .25:
                add_issue(issues,"WARNING","NET_DEBT_SOURCE_GAP",f"{gap*100:.1f}%")

    # 3b) Independent statement arithmetic. A ratio is only computed if
    # the necessary accounting period, ownership basis and inputs are explicit.
    hs=hist.get("summary",{}) or {}
    selected_rows=hist.get("rows_found",{}) or {}
    profit_row=str(selected_rows.get("net_income") or "")
    equity_row=str(selected_rows.get("equity") or "")
    # Parent-company earnings and equity must be demonstrably attributable.
    parent_profit=(
        hs.get("ttm_net_income")
        if "ana ortakl" in profit_row.casefold() else None
    )
    parent_equity=(
        hs.get("equity")
        if "ana ortakl" in equity_row.casefold() else None
    )
    independent=calculate_ratios(
        market_cap_try=eng.fnum(row.get("market_cap_basic")),
        ttm_parent_profit_try=parent_profit,
        parent_equity_try=parent_equity,
        net_debt_try=hs.get("net_debt_statement"),
        # Do not substitute operating profit for EBITDA.
        ttm_ebitda_try=None,
    )
    vendor_reconciliation={
        key:{
            "calculated":independent[key],
            "tradingview":eng.fnum(row.get(eng.M[key][0])),
            "is_yatirim":eng.fnum(row.get(iykey)),
            "tv_comparison":reconcile(independent[key],eng.fnum(row.get(eng.M[key][0]))),
            "iy_comparison":reconcile(independent[key],eng.fnum(row.get(iykey))),
        }
        for key,iykey in (("pe","iy_pe"),("pb","iy_pb"),("ev","iy_ev_ebitda"))
    }

    # 4) Provider cross-section conflicts / suspicious ranges.
    for key,iy_col in {
        "pe":"iy_pe","pb":"iy_pb","ev":"iy_ev_ebitda","roe":"iy_roe","roa":"iy_roa"
    }.items():
        tv=eng.fnum(row.get(eng.M[key][0]))
        iy=eng.fnum(row.get(iy_col))
        if tv is None or iy is None:
            continue
        denom=max(abs(iy),1.0)
        rel=abs(tv-iy)/denom
        # valuation multiples are expected to be close; profitability can diverge
        threshold=.35 if key in {"pe","pb","ev"} else .50
        sign_conflict=(tv>0>iy) or (iy>0>tv)
        if sign_conflict:
            add_issue(issues,"WARNING","PROVIDER_BASIS_CONFLICT",f"{key}: TV={tv:.3f}, IY={iy:.3f}")
        elif rel > 2.0:
            add_issue(issues,"WARNING","PROVIDER_LARGE_GAP",f"{key}: TV={tv:.3f}, IY={iy:.3f}")
        elif rel > threshold:
            add_issue(issues,"WARNING","PROVIDER_CONFLICT",f"{key}: TV={tv:.3f}, IY={iy:.3f}")

    # Economic-validity invariants for valuation multiples.
    for key in ("pe","pb","ev","pfcf"):
        x=metrics.get(key,{})
        v=x.get("v")
        if v is not None and float(v)<=0:
            if x.get("scoreable") or x.get("abs") is not None:
                add_issue(issues,"CRITICAL","NONPOSITIVE_MULTIPLE_SCORED",f"{key}={v}")
            else:
                add_issue(issues,"INFO","NONPOSITIVE_MULTIPLE_AD",f"{key}={v}")

    # Outliers are review flags, not automatic model errors. Negative P/E/PB/EV
    # are handled above as A/D rather than being mislabeled "extreme".
    suspicious={
        "pe":(0,500),"pb":(0,100),"ev":(0,300),
        "roe":(-1000,1000),"roa":(-500,500),
        "rev_g":(-500,2000),"eps_g":(-5000,5000),"ni_g":(-5000,5000),
        "curr":(0,100),"de":(-100,100),"nde":(-100,100),
    }
    for key,(lo,hi) in suspicious.items():
        v=metrics.get(key,{}).get("v")
        if v is None:
            continue
        if key in {"pe","pb","ev"} and float(v)<=0:
            continue
        if float(v)<lo or float(v)>hi:
            add_issue(issues,"INFO","EXTREME_VALUE",f"{key}={v}")

    # 5) Universe/benchmark sanity.
    if len(g.get("all",[])) < 500:
        add_issue(issues,"CRITICAL","BIST_UNIVERSE_SMALL",f"n={len(g.get('all',[]))}")
    if profile=="GYO" and eng.sector_index_code(row,profile)!="XGMYO":
        add_issue(issues,"ERROR","GYO_INDEX","XGMYO eşleşmedi")
    if profile=="Banka" and eng.sector_index_code(row,profile)!="XBANK":
        add_issue(issues,"ERROR","BANK_INDEX","XBANK eşleşmedi")

    # Missing data is not automatically an error, but flag very thin company records.
    available=sum(1 for x in metrics.values() if x.get("v") is not None)
    if available < 5:
        add_issue(issues,"WARNING","THIN_METRIC_COVERAGE",f"{available}/{len(metrics)}")

    max_sev=max([sev_rank(x["severity"]) for x in issues],default=0)
    status={0:"OK",1:"INFO",2:"WARNING",3:"CRITICAL",4:"ERROR"}[max_sev]

    return {
        "symbol":sym,
        "name":str(row.get("description") or row.get("name") or ""),
        "profile":profile,
        "sector":str(row.get("sector") or ""),
        "industry":str(row.get("industry") or ""),
        "status":status,
        "issue_count":len(issues),
        "critical_count":sum(x["severity"] in {"CRITICAL","ERROR"} for x in issues),
        "warning_count":sum(x["severity"]=="WARNING" for x in issues),
        "metric_coverage":available,
        "history_error":hist.get("error"),
        "core_rows_found":hist.get("data_quality",{}).get("core_rows_found"),
        "core_rows_expected":hist.get("data_quality",{}).get("core_rows_expected"),
        "quarterly_periods":hist.get("data_quality",{}).get("quarterly_periods"),
        "financial_period":hist.get("summary",{}).get("latest_period"),
        "valuation_reconciliation":vendor_reconciliation,
        "valuation_input_rows":{"profit":profit_row,"equity":equity_row},
        "reconciled_metrics":{
            key:{
                "tradingview":eng.fnum(row.get(eng.M[key][0])),
                "is_yatirim":eng.fnum(row.get(iykey)),
                "statement_derived":eng.fnum(hist.get("summary",{}).get(stmtkey)),
                "statement_row":hist.get("rows_found",{}).get(rowkey),
                "statement_period":hist.get("summary",{}).get("latest_period"),
            }
            for key,iykey,stmtkey,rowkey in (
                ("roe","iy_roe","ttm_roe_proxy","equity"),
                ("roa","iy_roa","ttm_roa_proxy","total_assets"),
            )
        },
        "issues":issues,
    }

def flatten_issue_codes(issues):
    return ";".join(sorted({x["code"] for x in issues}))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--shard-index",type=int,default=0)
    ap.add_argument("--shard-count",type=int,default=1)
    ap.add_argument("--quarterly",type=int,default=8)
    ap.add_argument("--limit",type=int,default=0)
    ap.add_argument("--symbol-timeout",type=int,default=45,
                    help="Bir hissenin audit'i için azami saniye (Linux CI'da SIGALRM).")
    args=ap.parse_args()

    OUT.mkdir(exist_ok=True)

    print("[audit] BIST + İş Yatırım evreni hazırlanıyor...")
    u=eng.universe(include_isyatirim=True)
    u=eng.dedupe(u).sort_values("symbol").reset_index(drop=True)
    xs=eng.xu100(u)

    selected=u.iloc[args.shard_index::args.shard_count].copy()
    if args.limit>0:
        selected=selected.head(args.limit)

    results=[]
    for pos,(_,row) in enumerate(selected.iterrows(),1):
        sym=str(row["symbol"]).upper()
        print(f"[audit {args.shard_index}/{args.shard_count}] {pos}/{len(selected)} {sym}",flush=True)
        try:
            results.append(audit_symbol_with_timeout(
                row,u,xs,args.quarterly,args.symbol_timeout
            ))
        except SymbolAuditTimeout as exc:
            results.append({
                "symbol":sym,"profile":eng.profile(row),"status":"CRITICAL",
                "issue_count":1,"critical_count":1,"warning_count":0,
                "issues":[{"severity":"CRITICAL","code":"AUDIT_TIMEOUT",
                           "detail":f"{args.symbol_timeout}s içinde tamamlanamadı"}],
            })
        except Exception as exc:
            results.append({
                "symbol":sym,"profile":eng.profile(row),"status":"ERROR",
                "issue_count":1,"critical_count":1,"warning_count":0,
                "issues":[{"severity":"ERROR","code":"AUDIT_EXCEPTION","detail":f"{type(exc).__name__}: {exc}"}],
                "exception":traceback.format_exc(limit=5),
            })

    stamp=datetime.now().isoformat(timespec="seconds")
    payload={
        "generated_at":stamp,
        "shard_index":args.shard_index,
        "shard_count":args.shard_count,
        "universe_count":len(u),
        "xu100_count":len(xs),
        "symbols_checked":len(results),
        "results":results,
    }

    base=f"audit_shard_{args.shard_index:02d}"
    (OUT/f"{base}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

    rows=[]
    for r in results:
        rows.append({
            "symbol":r.get("symbol"),"name":r.get("name"),"profile":r.get("profile"),
            "sector":r.get("sector"),"industry":r.get("industry"),"status":r.get("status"),
            "issue_count":r.get("issue_count",0),"critical_count":r.get("critical_count",0),
            "warning_count":r.get("warning_count",0),"metric_coverage":r.get("metric_coverage"),
            "core_rows_found":r.get("core_rows_found"),"core_rows_expected":r.get("core_rows_expected"),
            "quarterly_periods":r.get("quarterly_periods"),
            "issue_codes":flatten_issue_codes(r.get("issues",[])),
            "issues":" | ".join(f"{x['severity']}:{x['code']}:{x['detail']}" for x in r.get("issues",[])),
        })
    pd.DataFrame(rows).to_csv(OUT/f"{base}.csv",index=False,encoding="utf-8-sig")

    counts=pd.Series([r.get("status","ERROR") for r in results]).value_counts().to_dict()
    print(f"[audit] tamamlandı: {counts}")

if __name__=="__main__":
    main()
