from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT=Path("audit_downloads")
OUT=Path("audit_summary")
OUT.mkdir(exist_ok=True)

json_files=sorted(ROOT.rglob("audit_shard_*.json"))
if not json_files:
    raise SystemExit("Audit shard JSON bulunamadı.")

all_results=[]
universe_counts=[]
xu_counts=[]
for p in json_files:
    data=json.loads(p.read_text(encoding="utf-8"))
    all_results.extend(data.get("results",[]))
    universe_counts.append(data.get("universe_count"))
    xu_counts.append(data.get("xu100_count"))

# Keep one result per symbol in case of accidental duplicate artifact ingestion.
by_symbol={r["symbol"]:r for r in all_results if r.get("symbol")}
results=sorted(by_symbol.values(),key=lambda r:r["symbol"])

status_counts=Counter(r.get("status","ERROR") for r in results)
profile_counts=Counter(r.get("profile","N/A") for r in results)
issue_counts=Counter()
issue_symbol_sets=defaultdict(set)
for r in results:
    sym=r.get("symbol")
    for x in r.get("issues",[]):
        code=x.get("code","UNKNOWN")
        issue_counts[code]+=1
        if sym:
            issue_symbol_sets[code].add(sym)

summary={
    "generated_at":datetime.now().isoformat(timespec="seconds"),
    "symbols_checked":len(results),
    "universe_count_reported":max([x for x in universe_counts if x is not None],default=None),
    "xu100_count_reported":max([x for x in xu_counts if x is not None],default=None),
    "status_counts":dict(status_counts),
    "profile_counts":dict(profile_counts),
    "issue_counts":dict(issue_counts),
    "top_issues":[
        {
            "code":code,
            "occurrence_count":count,
            "company_count":len(issue_symbol_sets[code]),
            "symbols":sorted(issue_symbol_sets[code])[:100],
        }
        for code,count in issue_counts.most_common()
    ],
}
(OUT/"full_bist_audit_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")

def readiness_from_audit(r):
    """Conservative audit-only status, NOT a successfully rendered report's status."""
    codes={x.get("code") for x in r.get("issues",[])}
    profile=r.get("profile")
    if r.get("status") in {"ERROR","CRITICAL"}:
        return "REVIEW", "Motor-level failure"
    if "HISTORY_UNAVAILABLE" in codes or "SHORT_HISTORY" in codes:
        return "PARTIAL", "Missing or insufficient financial history"
    if profile in {"GYO","Holding","Yatırım Ortaklığı"}:
        return "VALUATION_PARTIAL", "Audit has no verified property/portfolio NAV evidence"
    if r.get("status")=="WARNING":
        return "REVIEW", "Provider/data warning requires reconciliation"
    return "READY", "Audit checks passed; not proof of external statement reconciliation"


rows=[]
for r in results:
    readiness,reason=readiness_from_audit(r)
    rows.append({
        "symbol":r.get("symbol"),"name":r.get("name"),"profile":r.get("profile"),
        "sector":r.get("sector"),"industry":r.get("industry"),"status":r.get("status"),
        "audit_readiness_provisional":readiness,"audit_readiness_reason":reason,
        "issue_count":r.get("issue_count",0),"critical_count":r.get("critical_count",0),
        "warning_count":r.get("warning_count",0),"metric_coverage":r.get("metric_coverage"),
        "core_rows_found":r.get("core_rows_found"),"core_rows_expected":r.get("core_rows_expected"),
        "quarterly_periods":r.get("quarterly_periods"),
        "issue_codes":";".join(sorted({x.get("code","") for x in r.get("issues",[])})),
        "issues":" | ".join(f"{x.get('severity')}:{x.get('code')}:{x.get('detail')}" for x in r.get("issues",[])),
    })
df=pd.DataFrame(rows)
df.to_csv(OUT/"full_bist_audit.csv",index=False,encoding="utf-8-sig")
summary["audit_readiness_provisional_counts"]=dict(Counter(df["audit_readiness_provisional"]))
(OUT/"full_bist_audit_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")

lines=[
    "# Tüm BIST Fundamental Intelligence Audit",
    "",
    f"- Tarih: {summary['generated_at']}",
    f"- Kontrol edilen benzersiz şirket: **{summary['symbols_checked']}**",
    f"- Raporlanan BIST evreni: **{summary['universe_count_reported']}**",
    f"- XU100 bileşen sayısı: **{summary['xu100_count_reported']}**",
    "",
    "## Durum",
]
for k in ["ERROR","CRITICAL","WARNING","INFO","OK"]:
    lines.append(f"- {k}: **{status_counts.get(k,0)}**")
lines += ["","## Geçici denetim hazırlığı (nihai tek-hisse raporu statüsü değildir)"]
for k,v in sorted(summary["audit_readiness_provisional_counts"].items()):
    lines.append(f"- {k}: {v}")
lines += ["","## En sık hata/uyarı kodları"]
for code,count in issue_counts.most_common(25):
    symbols=sorted(issue_symbol_sets[code])
    sample=", ".join(symbols[:20])
    lines.append(
        f"- **{code}**: {len(symbols)} şirket / {count} bulgu"
        + (f" — {sample}" if sample else "")
    )
lines += ["","## Profil dağılımı"]
for k,v in sorted(profile_counts.items()):
    lines.append(f"- {k}: {v}")
lines += ["","## Kritik / hata veren şirketler"]
critical=[r for r in results if r.get("status") in {"ERROR","CRITICAL"}]
if critical:
    for r in critical:
        codes=", ".join(sorted({x.get("code","") for x in r.get("issues",[])}))
        lines.append(f"- **{r['symbol']}** ({r.get('profile')}): {codes}")
else:
    lines.append("- Kritik/hata yok.")

(OUT/"full_bist_audit.md").write_text("\n".join(lines),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
