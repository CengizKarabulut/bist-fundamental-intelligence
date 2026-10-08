from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd


def split_codes(value: str) -> list[str]:
    if not value or pd.isna(value):
        return []
    return [x for x in str(value).split("|") if x]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir")
    ap.add_argument("output_dir")
    args = ap.parse_args()

    inp = Path(args.input_dir)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    csvs = sorted(inp.rglob("audit_shard_*.csv"))
    jsons = sorted(inp.rglob("audit_shard_*.json"))
    if not csvs:
        raise SystemExit("No audit CSV files found")

    frames = [pd.read_csv(p) for p in csvs]
    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["symbol"], keep="last")
    severity_order = {"CRITICAL": 0, "WARNING": 1, "OK": 2}
    df["_sev"] = df["severity"].map(severity_order).fillna(9)
    df = df.sort_values(["_sev", "profile", "symbol"]).drop(columns="_sev")

    full_csv = out / "FULL_BIST_AUDIT.csv"
    df.to_csv(full_csv, index=False, encoding="utf-8-sig")

    details = []
    for p in jsons:
        try:
            details.extend(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    by_symbol = {str(x.get("symbol")): x for x in details if x.get("symbol")}
    full_json = out / "FULL_BIST_AUDIT.json"
    full_json.write_text(
        json.dumps([by_symbol[s] for s in sorted(by_symbol)], ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    issue_counter = Counter()
    for value in df["issue_codes"].fillna(""):
        issue_counter.update(split_codes(value))

    profile_counts = df.groupby(["profile", "severity"]).size().unstack(fill_value=0)
    sector_critical = (
        df[df["severity"] == "CRITICAL"]
        .groupby("sector")
        .size()
        .sort_values(ascending=False)
        .head(20)
    )

    critical = df[df["severity"] == "CRITICAL"].copy()
    warning = df[df["severity"] == "WARNING"].copy()

    md = []
    md.append("# FULL BIST AUDIT")
    md.append("")
    md.append(f"- Taranan benzersiz şirket: **{len(df)}**")
    md.append(f"- Critical: **{len(critical)}**")
    md.append(f"- Warning: **{len(warning)}**")
    md.append(f"- OK: **{int((df['severity']=='OK').sum())}**")
    md.append("")

    md.append("## Profil x durum")
    md.append("")
    md.append("| Profil | Critical | Warning | OK | Toplam |")
    md.append("|---|---:|---:|---:|---:|")
    for profile, row in profile_counts.sort_index().iterrows():
        c = int(row.get("CRITICAL", 0))
        w = int(row.get("WARNING", 0))
        o = int(row.get("OK", 0))
        md.append(f"| {profile} | {c} | {w} | {o} | {c+w+o} |")
    md.append("")

    md.append("## En sık hata kodları")
    md.append("")
    md.append("| Hata kodu | Adet |")
    md.append("|---|---:|")
    for code, count in issue_counter.most_common(40):
        md.append(f"| {code} | {count} |")
    md.append("")

    if not sector_critical.empty:
        md.append("## Critical hata yoğunluğu - sektör")
        md.append("")
        md.append("| Sektör | Adet |")
        md.append("|---|---:|")
        for sec, count in sector_critical.items():
            md.append(f"| {sec} | {int(count)} |")
        md.append("")

    md.append("## Critical şirketler")
    md.append("")
    md.append("| Sembol | Profil | Sektör | Endüstri | Hatalar | Son dönem | Güven |")
    md.append("|---|---|---|---|---|---|---:|")
    for _, r in critical.head(250).iterrows():
        md.append(
            f"| {r.get('symbol','')} | {r.get('profile','')} | {r.get('sector','')} | "
            f"{r.get('industry','')} | {r.get('issue_codes','')} | {r.get('latest_period','')} | "
            f"{'' if pd.isna(r.get('validation_confidence')) else round(float(r.get('validation_confidence')),1)} |"
        )
    md.append("")

    md.append("## Otomatik model önerileri")
    md.append("")
    suggestions = []
    if issue_counter["SPECIAL_FINANCIAL_PROFILE_NEEDED"]:
        suggestions.append(
            f"- **Finansal şirketler için yeni profil gerekli:** "
            f"{issue_counter['SPECIAL_FINANCIAL_PROFILE_NEEDED']} şirket Genel/Savunma profilinde kalmış."
        )
    if issue_counter["INSURANCE_SPECIAL_MODEL_REVIEW"]:
        suggestions.append(
            f"- **Sigorta özel motoru:** {issue_counter['INSURANCE_SPECIAL_MODEL_REVIEW']} sigorta şirketi "
            "sanayi tipi tarihsel tablo mantığından ayrıca ayrıştırılmalı."
        )
    if issue_counter["HOLDING_NAD_MODEL_PENDING"]:
        suggestions.append(
            f"- **Holding NAD motoru:** {issue_counter['HOLDING_NAD_MODEL_PENDING']} holding için "
            "PD/DD yerine iştirak/NAD odaklı değerleme tamamlanmalı."
        )
    if issue_counter["CORE_ROWS_INCOMPLETE"] or issue_counter["CORE_ROWS_ZERO"]:
        suggestions.append(
            f"- **Mali tablo satır sözlüğü genişletilmeli:** eksik çekirdek satır problemi "
            f"{issue_counter['CORE_ROWS_INCOMPLETE'] + issue_counter['CORE_ROWS_ZERO']} şirkette görüldü."
        )
    if issue_counter["NET_DEBT_RECONCILIATION_FAIL"]:
        suggestions.append(
            f"- **Net borç sözlüğü/profile göre ayrıştırılmalı:** "
            f"{issue_counter['NET_DEBT_RECONCILIATION_FAIL']} şirkette İş Yatırım ile >%15 fark var."
        )
    if issue_counter["SOURCE_CRITICAL_DIFF"]:
        suggestions.append(
            f"- **Kaynak baz/freshness ayrımı:** {issue_counter['SOURCE_CRITICAL_DIFF']} şirkette "
            "kritik sağlayıcı farkı var; skor öncesi kaynak önceliği/profile kuralı gerekli."
        )
    if not suggestions:
        suggestions.append("- Otomatik olarak baskın bir model problemi tespit edilmedi.")
    md.extend(suggestions)

    summary_md = out / "FULL_BIST_AUDIT_SUMMARY.md"
    summary_md.write_text("\n".join(md), encoding="utf-8")

    summary_json = {
        "companies": len(df),
        "critical": len(critical),
        "warning": len(warning),
        "ok": int((df["severity"] == "OK").sum()),
        "issues": dict(issue_counter.most_common()),
        "profiles": profile_counts.to_dict(orient="index"),
    }
    (out / "FULL_BIST_AUDIT_SUMMARY.json").write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2, default=int),
        encoding="utf-8",
    )

    print(summary_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
