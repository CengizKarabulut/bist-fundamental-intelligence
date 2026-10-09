from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd


def _norm(v: Any) -> str:
    s=str(v or "").strip().casefold().replace("ı","i")
    s=unicodedata.normalize("NFKD",s)
    s="".join(ch for ch in s if not unicodedata.combining(ch))
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()


def _num(v):
    try:
        if v is None or pd.isna(v):
            return None
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _qkey(label):
    m=re.fullmatch(r"(\d{4})Q([1-4])",str(label))
    return (int(m.group(1)),int(m.group(2))) if m else (0,0)


def _series_from_row(df: pd.DataFrame, idx) -> pd.Series:
    obj=df.loc[idx]
    if isinstance(obj,pd.DataFrame):
        # Duplicate labels occur frequently in insurance statements. Keep the
        # economically largest row at the latest common period.
        best=None
        best_abs=-1.0
        for _,row in obj.iterrows():
            s=pd.to_numeric(row,errors="coerce").dropna().astype(float)
            if s.empty:
                continue
            latest=sorted(s.index,key=_qkey)[-1]
            val=abs(float(s[latest]))
            if val>best_abs:
                best=s; best_abs=val
        return best if best is not None else pd.Series(dtype=float)
    return pd.to_numeric(obj,errors="coerce").dropna().astype(float)


def _best_series(df: pd.DataFrame | None, candidates: list[str]) -> tuple[pd.Series,str|None]:
    if df is None or df.empty:
        return pd.Series(dtype=float),None
    cand=[_norm(x) for x in candidates]
    matches=[]
    for idx in df.index:
        n=_norm(idx)
        score=None
        for c in cand:
            if n==c:
                score=0; break
            if c in n:
                score=1
        if score is not None:
            s=_series_from_row(df,idx)
            if not s.empty:
                latest=sorted(s.index,key=_qkey)[-1]
                matches.append((score,-abs(float(s[latest])),str(idx),s))
    if not matches:
        return pd.Series(dtype=float),None
    matches.sort(key=lambda x:(x[0],x[1]))
    return matches[0][3],matches[0][2]


def _latest(s: pd.Series):
    if s is None or s.empty:
        return None
    idx=sorted(s.index,key=_qkey)[-1]
    return _num(s[idx])


def _series_has_signal(s: pd.Series | None) -> bool:
    """True when a row contains at least one economically non-zero observation.

    Generic XI_29 templates can contain finance-sector placeholder rows filled
    entirely with zeros. Those rows are structural placeholders, not real data.
    """
    if s is None or s.empty:
        return False
    vals=pd.to_numeric(s,errors="coerce").dropna().astype(float)
    if vals.empty:
        return False
    return bool((vals.abs()>1e-9).any())


def _yoy_latest(s: pd.Series):
    if s is None or s.empty:
        return None
    idx=sorted(s.index,key=_qkey)[-1]
    m=re.fullmatch(r"(\d{4})Q([1-4])",str(idx))
    if not m:
        return None
    prev=f"{int(m.group(1))-1}Q{m.group(2)}"
    if prev not in s.index:
        return None
    a=_num(s[idx]); b=_num(s[prev])
    if a is None or b in (None,0):
        return None
    return (a/b-1.0)*100.0


def _ratio(a,b,mult=1.0):
    a=_num(a); b=_num(b)
    if a is None or b in (None,0):
        return None
    return a/b*mult


def _load_nav(symbol: str, path: str|Path="data/nav_inputs.csv") -> dict[str,Any] | None:
    p=Path(path)
    if not p.exists():
        return None
    try:
        df=pd.read_csv(p)
    except Exception:
        return None
    if df.empty or "symbol" not in df.columns:
        return None
    row=df[df["symbol"].astype(str).str.upper()==symbol.upper()]
    if row.empty:
        return None
    r=row.iloc[-1].to_dict()
    nav=_num(r.get("nav_total_try"))
    if nav is None or nav<=0:
        return None
    return {
        "nav_total_try":nav,
        "as_of":None if pd.isna(r.get("as_of")) else str(r.get("as_of")),
        "source":None if pd.isna(r.get("source")) else str(r.get("source")),
        "note":None if pd.isna(r.get("note")) else str(r.get("note")),
    }


def build_special_profile_analysis(
    symbol: str,
    profile: str,
    inc_q: pd.DataFrame | None,
    bs_q: pd.DataFrame | None,
    market: dict[str,Any] | None,
    summary: dict[str,Any] | None,
    nav_path: str|Path="data/nav_inputs.csv",
) -> dict[str,Any]:
    market=market or {}
    summary=summary or {}
    out={
        "profile":profile,
        "status":"STANDARD",
        "metrics":{},
        "commentary":[],
        "valuation":{},
        "rows_found":{},
    }

    if profile=="Sigorta":
        premium,premium_row=_best_series(inc_q,[
            "1.1- Yazılan Primler (Reasürör payı Düşülmüş Olarak)",
            "Brüt Yazılan Primler",
        ])
        tech,tech_row=_best_series(inc_q,[
            "J- Genel Teknik Bölüm Dengesi",
            "Genel Teknik Bölüm Dengesi",
        ])
        net_income,ni_row=_best_series(inc_q,[
            "N- Dönem Net Karı veya Zararı",
            "Dönem Net Karı",
            "Ana Ortaklık Payları",
        ])
        p=_latest(premium); tb=_latest(tech); ni=_latest(net_income)
        out["rows_found"]={"premium":premium_row,"technical_balance":tech_row,"net_income":ni_row}
        out["metrics"]={
            "net_written_premium":p,
            "premium_yoy":_yoy_latest(premium),
            "technical_balance":tb,
            "technical_balance_yoy":_yoy_latest(tech),
            "technical_margin":_ratio(tb,p,100.0),
            "net_income_special":ni,
            "net_income_yoy_special":_yoy_latest(net_income),
            "equity_yoy":summary.get("equity_yoy"),
            "assets_yoy":summary.get("assets_yoy"),
            "equity_to_assets":summary.get("equity_to_assets"),
        }
        out["status"]="INSURANCE_ENGINE"
        if out["metrics"]["premium_yoy"] is not None:
            out["commentary"].append(
                f"Net yazılan primler yıllık %{out['metrics']['premium_yoy']:.1f} değişti."
            )
        if out["metrics"]["technical_margin"] is not None:
            out["commentary"].append(
                f"Genel teknik denge/net yazılan prim oranı %{out['metrics']['technical_margin']:.1f}; teknik sonuç ayrı izleniyor."
            )
        if out["metrics"]["technical_balance"] is not None:
            out["commentary"].append(
                "Teknik denge pozitiftir." if out["metrics"]["technical_balance"]>0
                else "Teknik denge negatiftir; yatırım gelirleri net kârı maskeleyebilir."
            )
        return out

    if profile=="Finansal":
        activity,activity_row=_best_series(inc_q,[
            "Finans Sektörü Faaliyetlerinden Brüt Kar (Zarar)",
            "Faiz, Ücret, Prim, Komisyon ve Diğer Gelirler",
        ])
        activity_basis="Finans sektörü faaliyet sonucu"
        if not _series_has_signal(activity):
            activity,activity_row=_best_series(inc_q,[
                "Net Faaliyet Kar/Zararı",
                "Net Faaliyet Karı/Zararı",
                "Finansman Gideri Öncesi Faaliyet Karı/Zararı",
                "Esas Faaliyet Karı (Zararı)",
                "Faaliyet Karı (Zararı)",
            ])
            activity_basis="Faaliyet sonucu"

        recv,recv_row=_best_series(bs_q,[
            "Finans Sektörü Faaliyetlerinden Alacaklar",
            "Finansal Kiralama Alacakları",
        ])
        recv_basis="Finans sektörü alacakları"
        if not _series_has_signal(recv):
            recv,recv_row=_best_series(bs_q,[
                "Ticari Alacaklar",
                "Diğer Alacaklar",
            ])
            recv_basis="Faaliyet/ticari alacaklar"

        liab,liab_row=_best_series(bs_q,[
            "Finans Sektörü Faaliyetlerinden Borçlar",
            "Finansal Borçlar",
        ])
        liab_basis="Finans sektörü yükümlülükleri"
        if not _series_has_signal(liab):
            liab,liab_row=_best_series(bs_q,[
                "Finansal Borçlar",
                "Diğer Finansal Yükümlülükler",
                "Ticari Borçlar",
            ])
            liab_basis="Finansal/faaliyet yükümlülükleri"

        out["rows_found"]={
            "activity_result":activity_row,
            "receivables":recv_row,
            "liabilities":liab_row,
        }
        out["metric_labels"]={
            "activity_result":activity_basis,
            "receivables":recv_basis,
            "liabilities":liab_basis,
        }
        out["metrics"]={
            "activity_result":_latest(activity) if _series_has_signal(activity) else None,
            "activity_result_yoy":_yoy_latest(activity) if _series_has_signal(activity) else None,
            "receivables":_latest(recv) if _series_has_signal(recv) else None,
            "receivables_yoy":_yoy_latest(recv) if _series_has_signal(recv) else None,
            "liabilities":_latest(liab) if _series_has_signal(liab) else None,
            "liabilities_yoy":_yoy_latest(liab) if _series_has_signal(liab) else None,
            # Backward-compatible aliases.
            "finance_gross_profit":_latest(activity) if _series_has_signal(activity) else None,
            "finance_gross_profit_yoy":_yoy_latest(activity) if _series_has_signal(activity) else None,
            "finance_receivables":_latest(recv) if _series_has_signal(recv) else None,
            "finance_receivables_yoy":_yoy_latest(recv) if _series_has_signal(recv) else None,
            "finance_liabilities":_latest(liab) if _series_has_signal(liab) else None,
            "finance_liabilities_yoy":_yoy_latest(liab) if _series_has_signal(liab) else None,
            "net_income_yoy":summary.get("net_income_yoy"),
            "equity_yoy":summary.get("equity_yoy"),
            "equity_to_assets":summary.get("equity_to_assets"),
        }
        out["status"]="FINANCIAL_ENGINE"
        if out["metrics"]["activity_result_yoy"] is not None:
            out["commentary"].append(
                f"{activity_basis} yıllık %{out['metrics']['activity_result_yoy']:.1f} değişti."
            )
        if out["metrics"]["receivables_yoy"] is not None:
            out["commentary"].append(
                f"{recv_basis} yıllık %{out['metrics']['receivables_yoy']:.1f} değişti."
            )
        if activity_row and activity_basis=="Faaliyet sonucu":
            out["commentary"].append(
                "Finans sektörü UFRS satırları sıfır şablon değer taşıdığı için XI_29 faaliyet sonucu fallback'i kullanıldı."
            )
        out["commentary"].append(
            "Sanayi tipi FAVÖK, FCF ve net borç/FAVÖK metrikleri ana skora zorlanmadı."
        )
        return out

    if profile in {"GYO","Holding","Yatırım Ortaklığı"}:
        nav=_load_nav(symbol,nav_path)
        mcap=_num(market.get("market_cap"))
        equity=_num(summary.get("equity"))
        book_discount=(1.0-mcap/equity)*100.0 if mcap is not None and equity not in (None,0) and equity>0 else None
        out["metrics"]={
            "market_cap":mcap,
            "book_equity":equity,
            "book_value_discount_pct":book_discount,
            "net_debt":summary.get("net_debt"),
        }
        if nav:
            discount=(1.0-mcap/nav["nav_total_try"])*100.0 if mcap is not None else None
            out["valuation"]={
                "nav_total_try":nav["nav_total_try"],
                "pd_nav_discount_pct":discount,
                "as_of":nav.get("as_of"),
                "source":nav.get("source"),
                "note":nav.get("note"),
                "status":"NAV_AVAILABLE",
            }
            out["status"]="NAV_AVAILABLE"
            if discount is not None:
                out["commentary"].append(
                    f"Sağlanan NAD'a göre piyasa değeri iskontosu %{discount:.1f}."
                )
        else:
            out["valuation"]={
                "nav_total_try":None,
                "pd_nav_discount_pct":None,
                "status":"NAV_REQUIRED",
            }
            out["status"]="NAV_REQUIRED"
            out["commentary"].append(
                "Gerçek NAD/portföy NAV verisi bulunmadığı için otomatik değerleme puanı üretilmedi."
            )
        if book_discount is not None:
            out["commentary"].append(
                f"Defter özkaynağına göre görünen %{book_discount:.1f} iskonto/prim, NAD iskontosu değildir."
            )
        return out

    if profile=="Banka":
        out["status"]="BANK_ENGINE"
        out["metrics"]={
            "net_income_yoy":summary.get("net_income_yoy"),
            "net_interest_income_yoy":summary.get("net_interest_income_yoy"),
            "fee_income_yoy":summary.get("fee_income_yoy"),
            "loans_yoy":summary.get("loans_yoy"),
            "deposits_yoy":summary.get("deposits_yoy"),
            "equity_yoy":summary.get("equity_yoy"),
            "assets_yoy":summary.get("assets_yoy"),
            "equity_to_assets":summary.get("equity_to_assets"),
        }
        out["commentary"].append(
            "Banka motorunda sanayi tipi FAVÖK, FCF ve net borç/FAVÖK kullanılmaz."
        )
        return out

    return out
