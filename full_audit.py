from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import borsapy as bp

from analyze import (
    analyze as build_cross_section,
    apply_profile_primary_source,
    dedupe,
    fnum,
    groups,
    profile,
    scores,
    sector_index_code,
    source_validation,
    universe,
    xu100,
)
from history_engine import build_historical_analysis

OUT = Path("audit")


def expected_reporting_floor(now: datetime | None = None) -> str:
    now = now or datetime.now()
    y, m = now.year, now.month
    if m <= 2:
        return f"{y-1}Q3"
    if m <= 4:
        return f"{y-1}Q4"
    if m <= 7:
        return f"{y}Q1"
    if m <= 10:
        return f"{y}Q2"
    return f"{y}Q3"


def qkey(label: str | None) -> tuple[int, int]:
    if not label:
        return (0, 0)
    s = str(label)
    if len(s) == 6 and s[4] == "Q" and s[:4].isdigit() and s[5].isdigit():
        return (int(s[:4]), int(s[5]))
    return (0, 0)


def is_financial_like(row: pd.Series) -> bool:
    sec = str(row.get("sector") or "").casefold()
    ind = str(row.get("industry") or "").casefold()
    text = f"{sec} {ind}"
    needles = [
        "finance", "financial", "investment", "securit", "broker",
        "leasing", "factoring", "asset management", "consumer finance",
        "mortgage", "investment managers", "investment trust",
    ]
    return any(x in text for x in needles)


def official_profile_sets() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for code in ["XBANK","XSGRT","XGMYO","XYORT","XHOLD"]:
        try:
            out[code] = {str(x).upper() for x in bp.Index(code).component_symbols}
        except Exception:
            out[code] = set()
    return out


def profile_consistency(row: pd.Series, p: str) -> list[str]:
    sec = str(row.get("sector") or "").casefold()
    ind = str(row.get("industry") or "").casefold()
    issues: list[str] = []

    if "bank" in ind and p != "Banka":
        issues.append("PROFILE_BANK_MISMATCH")
    if "insurance" in ind and p != "Sigorta":
        issues.append("PROFILE_INSURANCE_MISMATCH")
    if ("real estate investment trust" in ind or "reit" in ind) and p != "GYO":
        issues.append("PROFILE_GYO_MISMATCH")
    if "financial conglomerate" in ind and p != "Holding":
        issues.append("PROFILE_HOLDING_MISMATCH")

    if is_financial_like(row) and p in {"Genel", "Savunma/Teknoloji"}:
        issues.append("SPECIAL_FINANCIAL_PROFILE_NEEDED")

    # TradingView can classify some software/technology names broadly. This is
    # not necessarily wrong, but is worth surfacing if a financial-sector name
    # accidentally lands in technology.
    if "finance" in sec and p == "Savunma/Teknoloji":
        issues.append("PROFILE_TECH_FINANCE_CONFLICT")

    return issues


def plausibility_issues(metrics: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    bounds = {
        "pe": (-500, 1000),
        "pb": (-100, 200),
        "ev": (-500, 1000),
        "roe": (-1000, 1000),
        "roa": (-500, 500),
        "roic": (-1000, 1000),
        "gross": (-500, 500),
        "opm": (-500, 500),
        "netm": (-1000, 1000),
        "ebitdam": (-500, 500),
        "rev_g": (-1000, 5000),
        "eps_g": (-5000, 5000),
        "ni_g": (-5000, 5000),
        "curr": (0, 500),
        "quick": (0, 500),
        "de": (-1000, 5000),
        "nde": (-1000, 1000),
        "fcfm": (-1000, 1000),
        "pio": (0, 9),
    }
    for k, (lo, hi) in bounds.items():
        v = metrics.get(k, {}).get("raw_v")
        if v is None:
            continue
        try:
            x = float(v)
        except Exception:
            issues.append(f"NON_NUMERIC_{k.upper()}")
            continue
        if not math.isfinite(x):
            issues.append(f"NONFINITE_{k.upper()}")
        elif x < lo or x > hi:
            issues.append(f"IMPLAUSIBLE_{k.upper()}")
    return issues


def audit_one(
    row: pd.Series,
    u: pd.DataFrame,
    xset: set[str],
    floor: str,
    official_sets: dict[str, set[str]],
) -> dict[str, Any]:
    sym = str(row["symbol"])
    p = profile(row)
    issue_codes: list[str] = profile_consistency(row, p)
    error_text = None

    if sym in official_sets.get("XBANK", set()) and p != "Banka":
        issue_codes.append("INDEX_XBANK_PROFILE_MISMATCH")
    if sym in official_sets.get("XSGRT", set()) and p != "Sigorta":
        issue_codes.append("INDEX_XSGRT_PROFILE_MISMATCH")
    if sym in official_sets.get("XGMYO", set()) and p != "GYO":
        issue_codes.append("INDEX_XGMYO_PROFILE_MISMATCH")
    if sym in official_sets.get("XYORT", set()) and p != "Yatırım Ortaklığı":
        issue_codes.append("INDEX_XYORT_PROFILE_MISMATCH")
    if sym in official_sets.get("XHOLD", set()) and p not in {"Holding","Yatırım Ortaklığı"}:
        issue_codes.append("INDEX_XHOLD_PROFILE_REVIEW")

    try:
        hist = build_historical_analysis(
            sym,
            p,
            report_dir=None,
            quarterly_periods=8,
            annual_periods=0,
            load_market_info=True,
        )
    except Exception as exc:
        hist = {"error": str(exc), "profile": p}
        error_text = str(exc)

    if hist.get("error"):
        issue_codes.append("HISTORY_ERROR")
        error_text = str(hist.get("error"))

    dq = hist.get("data_quality", {}) if isinstance(hist, dict) else {}
    core_found = dq.get("core_rows_found")
    core_expected = dq.get("core_rows_expected")
    if core_found is not None and core_expected:
        if core_found == 0:
            issue_codes.append("CORE_ROWS_ZERO")
        elif core_found < core_expected:
            issue_codes.append("CORE_ROWS_INCOMPLETE")

    if hist.get("metadata_warning"):
        issue_codes.append("MARKET_METADATA_WARNING")

    latest = hist.get("summary", {}).get("latest_period")
    if latest and qkey(latest) < qkey(floor):
        issue_codes.append("STALE_FINANCIAL_PERIOD")
    elif not latest and not hist.get("error"):
        issue_codes.append("LATEST_PERIOD_MISSING")

    # Cross-section / scoring checks use the same production path.
    try:
        g = groups(u, row, xset)
        metrics = build_cross_section(row, p, g)
        metrics = apply_profile_primary_source(metrics, p, hist, g)
        sc = scores(metrics)
        valid = source_validation(row, metrics, hist)
    except Exception as exc:
        metrics = {}
        sc = {}
        valid = {"confidence": None, "critical_count": 0, "warning_count": 0, "checks": []}
        issue_codes.append("SCORING_PIPELINE_ERROR")
        error_text = (error_text + " | " if error_text else "") + str(exc)

    issue_codes.extend(plausibility_issues(metrics))

    if valid.get("critical_count", 0) >= 1:
        issue_codes.append("SOURCE_CRITICAL_DIFF")
    if valid.get("confidence") is not None and valid["confidence"] < 65:
        issue_codes.append("LOW_DATA_CONFIDENCE")

    if p == "GYO":
        if sc.get("valuation") is not None:
            issue_codes.append("GYO_VALUATION_SCORE_SHOULD_BE_NA")
        for k in ("pe", "pb", "ev", "pfcf", "eps_g", "nde", "fcfm", "pio"):
            if metrics.get(k, {}).get("scoreable") is True:
                issue_codes.append(f"GYO_SCOREABLE_{k.upper()}")

    if p == "Banka":
        for k in ("ev", "pfcf", "roic", "gross", "opm", "ebitdam", "rev_g", "curr", "quick", "de", "nde", "fcfm"):
            if metrics.get(k, {}).get("app") is True:
                issue_codes.append(f"BANK_INDUSTRIAL_METRIC_{k.upper()}")

    if p == "Holding":
        issue_codes.append("HOLDING_NAD_MODEL_PENDING")
    if p == "Yatırım Ortaklığı":
        issue_codes.append("INVESTMENT_TRUST_NAV_MODEL_PENDING")
    if p == "Sigorta":
        issue_codes.append("INSURANCE_SPECIAL_MODEL_REVIEW")
    if p == "Finansal":
        issue_codes.append("NONBANK_FINANCIAL_MODEL_REVIEW")

    hsum = hist.get("summary", {}) if isinstance(hist, dict) else {}
    nd_stmt = fnum(hsum.get("net_debt_statement"))
    nd_provider = fnum(hsum.get("net_debt_provider"))
    nd_gap_pct = None
    if nd_stmt is not None and nd_provider not in (None, 0):
        nd_gap_pct = (nd_stmt / nd_provider - 1.0) * 100.0
        if abs(nd_gap_pct) > 15:
            issue_codes.append("NET_DEBT_RECONCILIATION_FAIL")

    # Deduplicate while preserving order.
    issue_codes = list(dict.fromkeys(issue_codes))

    critical_prefixes = (
        "HISTORY_ERROR", "CORE_ROWS_ZERO", "PROFILE_", "SCORING_PIPELINE_ERROR",
        "GYO_VALUATION", "GYO_SCOREABLE", "BANK_INDUSTRIAL", "NET_DEBT_RECONCILIATION_FAIL",
    )
    hard_index_mismatch={
        "INDEX_XBANK_PROFILE_MISMATCH","INDEX_XSGRT_PROFILE_MISMATCH",
        "INDEX_XGMYO_PROFILE_MISMATCH","INDEX_XYORT_PROFILE_MISMATCH",
    }
    critical = [
        x for x in issue_codes
        if x.startswith(critical_prefixes)
        or x in {"SOURCE_CRITICAL_DIFF", "LOW_DATA_CONFIDENCE"}
        or x in hard_index_mismatch
    ]
    warnings = [x for x in issue_codes if x not in critical]

    severity = "CRITICAL" if critical else "WARNING" if warnings else "OK"

    return {
        "symbol": sym,
        "name": row.get("description") or row.get("name"),
        "profile": p,
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "severity": severity,
        "issue_count": len(issue_codes),
        "issue_codes": "|".join(issue_codes),
        "latest_period": latest,
        "expected_floor": floor,
        "core_rows_found": core_found,
        "core_rows_expected": core_expected,
        "quarterly_periods": dq.get("quarterly_periods"),
        "validation_confidence": valid.get("confidence"),
        "validation_critical_count": valid.get("critical_count", 0),
        "validation_warning_count": valid.get("warning_count", 0),
        "market_pe": hist.get("market", {}).get("pe") if isinstance(hist, dict) else None,
        "market_pb": hist.get("market", {}).get("pb") if isinstance(hist, dict) else None,
        "market_ev_ebitda": hist.get("market", {}).get("ev_ebitda") if isinstance(hist, dict) else None,
        "tv_pe": metrics.get("pe", {}).get("raw_v") if metrics else None,
        "tv_pb": metrics.get("pb", {}).get("raw_v") if metrics else None,
        "tv_ev_ebitda": metrics.get("ev", {}).get("raw_v") if metrics else None,
        "net_debt_statement": nd_stmt,
        "net_debt_provider": nd_provider,
        "net_debt_gap_pct": nd_gap_pct,
        "sector_index": sector_index_code(row, p),
        "history_error": error_text,
        "details": {
            "data_quality": dq,
            "rows_found": hist.get("rows_found", {}) if isinstance(hist, dict) else {},
            "source_validation": valid,
            "scores": sc,
            "metadata_warning": hist.get("metadata_warning") if isinstance(hist, dict) else None,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, required=True)
    ap.add_argument("--shards", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if args.shard < 0 or args.shard >= args.shards:
        raise SystemExit("Invalid shard")

    OUT.mkdir(exist_ok=True)
    print("[audit] BIST evreni alınıyor...")
    u = universe()
    du = dedupe(u).sort_values("symbol").reset_index(drop=True)
    xset = xu100(u)
    official_sets = official_profile_sets()
    floor = expected_reporting_floor()

    symbols = du.iloc[args.shard::args.shards].copy()
    if args.limit:
        symbols = symbols.head(args.limit)

    print(
        f"[audit] shard={args.shard}/{args.shards} "
        f"symbols={len(symbols)} universe={len(du)} floor={floor}"
    )

    rows: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []

    for idx, (_, row) in enumerate(symbols.iterrows(), start=1):
        sym = str(row["symbol"])
        print(f"[audit] {idx}/{len(symbols)} {sym}")
        try:
            result = audit_one(row, u, xset, floor, official_sets)
        except Exception as exc:
            result = {
                "symbol": sym,
                "name": row.get("description") or row.get("name"),
                "profile": profile(row),
                "sector": row.get("sector"),
                "industry": row.get("industry"),
                "severity": "CRITICAL",
                "issue_count": 1,
                "issue_codes": "AUDIT_UNHANDLED_EXCEPTION",
                "latest_period": None,
                "expected_floor": floor,
                "core_rows_found": None,
                "core_rows_expected": None,
                "quarterly_periods": None,
                "validation_confidence": None,
                "validation_critical_count": 0,
                "validation_warning_count": 0,
                "market_pe": None,
                "market_pb": None,
                "market_ev_ebitda": None,
                "tv_pe": None,
                "tv_pb": None,
                "tv_ev_ebitda": None,
                "net_debt_statement": None,
                "net_debt_provider": None,
                "net_debt_gap_pct": None,
                "sector_index": None,
                "history_error": str(exc),
                "details": {"exception": str(exc)},
            }

        details.append(result)
        rows.append({k: v for k, v in result.items() if k != "details"})
        time.sleep(0.12)

    csv_path = OUT / f"audit_shard_{args.shard:02d}.csv"
    json_path = OUT / f"audit_shard_{args.shard:02d}.json"
    pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(details, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    counts = pd.Series([r["severity"] for r in rows]).value_counts().to_dict() if rows else {}
    print(f"[audit] tamamlandı: {counts}")
    print(csv_path)
    print(json_path)


if __name__ == "__main__":
    main()
