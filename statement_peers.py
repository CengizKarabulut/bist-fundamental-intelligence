"""Comparable BIST peer statistics from independently calculated statement ratios.

Only same-method, sufficiently recent fiscal-period calculations enter the
reference distribution. Vendor screener ratios are NEVER a fallback here.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import math
import re

import pandas as pd

from statement_metrics import STANDARD_KEYS

SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "statement_peer_snapshot.csv"
REQUIRED = {"symbol", "sector", "industry", "profile", "financial_period",
            "is_xu100", "status"}
MULTIPLES = {"pe", "pb", "ev", "pfcf"}
SECTOR_PROFILES = {"Banka", "Sigorta", "Finansal", "GYO",
                   "Holding", "Yatırım Ortaklığı"}


def _quarter_key(value):
    match = re.fullmatch(r"(20\d\d)Q([1-4])", str(value))
    return int(match[1]) * 4 + int(match[2]) if match else None


def make_snapshot(audit_df, *, engine_version, created_at=None):
    """Build a distribution dataset; bad statuses and raw provider fields excluded.

    A result can enter peers only if the audit says the *same calculation*
    succeeded and its fiscal quarter is identifiable.
    """
    missing = REQUIRED - set(audit_df.columns)
    if missing:
        raise ValueError("Required audit columns missing: " + ", ".join(sorted(missing)))
    columns = sorted(REQUIRED) + [
        "statement_" + key for key in STANDARD_KEYS
    ] + ["snapshot_version", "snapshot_utc"]
    source = audit_df.copy()
    source["symbol"] = source["symbol"].astype(str).str.upper().str.strip()
    source = source[~source["status"].isin(("ERROR", "CRITICAL"))]
    source = source[source["financial_period"].map(lambda x: _quarter_key(x) is not None)]
    if source["symbol"].duplicated().any():
        raise ValueError("Duplicate issuer representatives in audit data")
    created_at = created_at or datetime.now(timezone.utc)
    stamp = created_at.astimezone(timezone.utc).isoformat()
    result = source.loc[:, sorted(REQUIRED)].copy()
    for key in STANDARD_KEYS:
        col = "statement_" + key
        status = col + "_status"
        if col not in source or status not in source:
            raise ValueError(f"Missing independent computation provenance for {key}")
        value = pd.to_numeric(source[col], errors="coerce")
        valid = source[status].eq("CALCULATED") & value.map(
            lambda x: math.isfinite(x) if pd.notna(x) else False
        )
        if key in MULTIPLES:
            valid &= value.gt(0)
        result[col] = value.where(valid)
    result["is_xu100"] = result["is_xu100"].astype(str).str.lower().isin(["true", "1"])
    result["snapshot_version"] = str(engine_version)
    result["snapshot_utc"] = stamp
    return result.loc[:, columns].sort_values("symbol").reset_index(drop=True)


def read_snapshot(path=SNAPSHOT_PATH, *, engine_version, max_age_days=10, now=None):
    """Fail-closed for a missing, stale, incompatible or malformed peer cache."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        df = pd.read_csv(path, dtype={"symbol": "str", "financial_period": "str"})
        if df.empty or not REQUIRED.issubset(df.columns):
            return None
        if any("statement_" + k not in df for k in STANDARD_KEYS):
            return None
        if set(df["snapshot_version"].astype(str)) != {str(engine_version)}:
            return None
        dates = pd.to_datetime(df["snapshot_utc"], utc=True, errors="coerce")
        if dates.isna().any() or dates.nunique() != 1:
            return None
        reference = now or datetime.now(timezone.utc)
        age = reference - dates.iloc[0].to_pydatetime()
        if age > timedelta(days=max_age_days) or age < -timedelta(minutes=10):
            return None
        if df["symbol"].duplicated().any():
            return None
        df["is_xu100"] = df["is_xu100"].astype(str).str.lower().isin(["true", "1"])
        return df
    except (ValueError, KeyError, TypeError, OSError, pd.errors.ParserError):
        return None


def peer_distributions(snapshot, *, symbol, sector, industry, profile,
                       quarter, metrics, directions, min_n=3, max_quarter_lag=2):
    """Exclude self, future reports, old periods, non-applicable and outliers.

    Percentiles use the established score direction; no artificial percentiles
    for data-unavailable selected stocks.
    """
    if snapshot is None or snapshot.empty:
        return {}
    target_q = _quarter_key(quarter)
    if target_q is None:
        return {}
    pool = snapshot[snapshot["symbol"].astype(str).str.upper() != str(symbol).upper()].copy()
    qkeys = pool["financial_period"].map(_quarter_key)
    pool = pool[(qkeys <= target_q) & (qkeys >= target_q-max_quarter_lag)]
    if pool.empty:
        return {}
    sec = pool["sector"].fillna("").astype(str).str.casefold()
    ind = pool["industry"].fillna("").astype(str).str.casefold()
    sector_mask = sec.eq(str(sector).casefold())
    if profile in SECTOR_PROFILES:
        sector_mask &= pool["profile"].fillna("").astype(str).eq(profile)
    cohorts = {
        "industry": pool[ind.eq(str(industry).casefold())] if industry else pool.iloc[0:0],
        "sector": pool[sector_mask] if sector else pool.iloc[0:0],
        "xu100": pool[pool["is_xu100"].astype(bool)],
        "bist": pool,
    }
    result = {}
    for key in STANDARD_KEYS:
        result[key] = {}
        for label, peers in cohorts.items():
            values = pd.to_numeric(peers["statement_" + key], errors="coerce").dropna()
            values = values[values.map(math.isfinite)]
            if key in MULTIPLES:
                values = values[values > 0]
            # Minimum sample count avoids fake "100th percentile" statistics.
            entry = {"median": None, "pct": None, "n": len(values),
                     "basis": "STANDARD_FINANCIAL_STATEMENT",
                     "snapshot_utc": str(snapshot["snapshot_utc"].iloc[0])}
            if len(values) >= min_n:
                entry["median"] = float(values.median())
                own = metrics.get(key)
                own = float(own) if own is not None and math.isfinite(float(own)) else None
                if own is not None and (key not in MULTIPLES or own > 0):
                    if directions.get(key) == "high":
                        entry["pct"] = float((values <= own).mean()*100)
                    else:
                        entry["pct"] = float((values >= own).mean()*100)
            result[key][label] = entry
    return result


def export_metadata(snapshot):
    return {
        "generated_at": str(snapshot["snapshot_utc"].iloc[0]),
        "engine_version": str(snapshot["snapshot_version"].iloc[0]),
        "symbols": len(snapshot),
        "definition": "Independent financial-statement ratios only",
        "metric_coverage": {
            key: int(snapshot["statement_" + key].count()) for key in STANDARD_KEYS
        },
    }
