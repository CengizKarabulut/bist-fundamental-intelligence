from __future__ import annotations

import argparse, html, json, math, re, statistics
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf
import borsapy as bp
from tradingview_screener import Query, col
from history_engine import build_historical_analysis

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

FIELDS = [
    "name","description","exchange","close","market_cap_basic","sector","industry","index",
    "price_earnings_ttm","price_book_fq","enterprise_value_ebitda_current","price_free_cash_flow_ttm",
    "return_on_equity","return_on_assets","return_on_invested_capital",
    "total_revenue_yoy_growth_ttm","earnings_per_share_diluted_yoy_growth_ttm","net_income_yoy_growth_ttm",
    "gross_profit_margin_ttm","operating_margin_ttm","after_tax_margin","ebitda_margin_ttm",
    "current_ratio_fq","quick_ratio_fq","debt_to_equity_fq","net_debt_to_ebitda_fq",
    "shrhldrs_equity_to_total_assets_fq","free_cash_flow_margin_ttm","piotroski_f_score_ttm",
    "dividends_yield_current","Perf.3M","Perf.6M","Perf.Y",
]

M = {
    "pe":("price_earnings_ttm","F/K","Değerleme","low","x",1.0),
    "pb":("price_book_fq","PD/DD","Değerleme","low","x",0.7),
    "ev":("enterprise_value_ebitda_current","FD/FAVÖK","Değerleme","low","x",1.0),
    "pfcf":("price_free_cash_flow_ttm","Fiyat/FCF","Değerleme","low","x",0.8),
    "roe":("return_on_equity","ROE","Kârlılık","high","%",1.0),
    "roa":("return_on_assets","ROA","Kârlılık","high","%",0.7),
    "roic":("return_on_invested_capital","ROIC","Kârlılık","high","%",0.9),
    "gross":("gross_profit_margin_ttm","Brüt Marj","Kârlılık","high","%",0.5),
    "opm":("operating_margin_ttm","Faaliyet Marjı","Kârlılık","high","%",0.8),
    "netm":("after_tax_margin","Net Marj","Kârlılık","high","%",0.8),
    "ebitdam":("ebitda_margin_ttm","FAVÖK Marjı","Kârlılık","high","%",0.7),
    "rev_g":("total_revenue_yoy_growth_ttm","Ciro Büyümesi","Büyüme","high","%",1.0),
    "eps_g":("earnings_per_share_diluted_yoy_growth_ttm","EPS Büyümesi","Büyüme","high","%",1.0),
    "ni_g":("net_income_yoy_growth_ttm","Net Kâr Büyümesi","Büyüme","high","%",0.8),
    "curr":("current_ratio_fq","Cari Oran","Finansal Sağlık","high","x",0.6),
    "quick":("quick_ratio_fq","Likidite Oranı","Finansal Sağlık","high","x",0.5),
    "de":("debt_to_equity_fq","Borç/Özsermaye","Finansal Sağlık","low","x",0.8),
    "nde":("net_debt_to_ebitda_fq","Net Borç/FAVÖK","Finansal Sağlık","low","x",1.0),
    "eq_assets":("shrhldrs_equity_to_total_assets_fq","Özsermaye/Varlık","Finansal Sağlık","high","x",0.7),
    "fcfm":("free_cash_flow_margin_ttm","FCF Marjı","Nakit Kalitesi","high","%",1.0),
    "pio":("piotroski_f_score_ttm","Piotroski F-Score","Nakit Kalitesi","high","n",0.8),
    "div":("dividends_yield_current","Temettü Verimi","Bilgi","high","%",0.0),
}
CATS=["Büyüme","Kârlılık","Finansal Sağlık","Nakit Kalitesi","Değerleme"]

BANDS={
    "pe":("low",10,30),"pb":("low",1,4),"ev":("low",6,15),"pfcf":("low",12,30),
    "roe":("high",8,20),"roa":("high",3,10),"roic":("high",6,15),
    "gross":("high",15,35),"opm":("high",5,18),"netm":("high",3,15),"ebitdam":("high",8,22),
    "rev_g":("high",0,25),"eps_g":("high",0,30),"ni_g":("high",0,30),
    "curr":("high",0.9,1.7),"quick":("high",0.6,1.1),"de":("low",0.5,2),"nde":("low",1,4),
    "eq_assets":("high",0.2,0.5),"fcfm":("high",0,12),"pio":("high",3,7),
}
OVR={
    "Banka":{"pe":("low",5,12),"pb":("low",0.7,2),"roe":("high",12,25),"roa":("high",1,3),"eq_assets":("high",0.06,0.14),"eps_g":("high",0,30),"ni_g":("high",0,30)},
    "Sigorta":{"pe":("low",6,16),"pb":("low",1,3.5),"roe":("high",12,30),"roa":("high",1.5,5)},
    "Finansal":{"pe":("low",6,18),"pb":("low",0.8,3.5),"roe":("high",10,25),"roa":("high",1.5,6),"eps_g":("high",0,30),"ni_g":("high",0,30)},
    "Savunma/Teknoloji":{"pe":("low",18,55),"pb":("low",2,8),"ev":("low",10,30),"roe":("high",10,25),"roa":("high",4,12),"rev_g":("high",5,40),"eps_g":("high",5,50)},
}
FINANCIAL_SKIP={"ev","pfcf","roic","gross","opm","ebitdam","rev_g","curr","quick","de","nde","fcfm","pio"}
BANK_SKIP=set(FINANCIAL_SKIP)
INS_SKIP=set(FINANCIAL_SKIP)
OTHER_FIN_SKIP=set(FINANCIAL_SKIP)
YORT_SKIP=set(FINANCIAL_SKIP)
# GYO'larda klasik sanayi değerleme/nakit kalite oranları raporda gösterilebilir
# ancak NAD/PD-NAD yerine ana skora sokulmaz. Proje geliştirme kaynaklı işletme
# sermayesi hareketleri FCF ve Net Borç/FAVÖK'ü de aşırı oynatabilir.
GYO_NONSCORE={"pe","pb","ev","pfcf","eps_g","nde","fcfm","pio"}
HOLDING_NONSCORE={"pe","pb","ev","pfcf","rev_g","eps_g","gross","opm","ebitdam","nde","fcfm","pio"}
YORT_NONSCORE={"pe","pb","eps_g","ni_g","netm"}


def fnum(v):
    try:
        if v is None or pd.isna(v): return None
        x=float(v); return x if math.isfinite(x) else None
    except: return None

def fmt(v,k="n"):
    if v is None:return "N/A"
    return f"{v:.2f}%" if k=="%" else f"{v:.2f}x" if k=="x" else f"{v:.2f}"

def status(s):
    if s is None:return "N/A"
    return "Çok güçlü" if s>=75 else "Güçlü" if s>=60 else "Dengeli" if s>=45 else "Zayıf" if s>=30 else "Çok zayıf"

def profile(r):
    sec=str(r.get("sector") or "").casefold()
    ind=str(r.get("industry") or "").casefold()
    d=str(r.get("description") or r.get("name") or "").casefold()

    # Company-name semantics override broad provider buckets. For example,
    # brokers sit under "Investment Banks/Brokers" and SAHOL may appear under
    # "Regional Banks"; a raw "bank" substring therefore creates false banks.
    if "gayrimenkul yatirim ortakligi" in d or "gayrimenkul yatırım ortaklığı" in d:
        return "GYO"
    if "holding" in d:
        return "Holding"
    if "real estate investment trust" in ind or ind.strip()=="reit":
        return "GYO"

    if "insurance" in ind or "sigorta" in d or "hayat ve emeklilik" in d:
        return "Sigorta"

    bank_name=any(x in d for x in [
        " bank ", "bank a.", "bankasi", "bankası", "katilim bank",
        "katılım bank", "kalkinma ve yatirim bank", "kalkınma ve yatırım bank",
    ]) or d.startswith("akbank") or d.startswith("sekerbank")
    if bank_name or ind in {"major banks","regional banks"}:
        return "Banka"

    if "yatirim ortakligi" in d or "yatırım ortaklığı" in d:
        return "Yatırım Ortaklığı"

    financial_name=any(x in d for x in [
        "menkul deger", "menkul değer", "faktoring", "finansal kiralama",
        "tasarruf finansman", "varlik yonetim", "varlık yönetim",
        "yatirim yonetim", "yatırım yönetim",
    ])
    if financial_name or ind in {"investment banks/brokers","investment managers"}:
        return "Finansal"

    if any(x in ind for x in ["aerospace","defense","electronic equipment","computer communications"]) or "electronic technology" in sec or "technology services" in sec:
        return "Savunma/Teknoloji"
    return "Genel"

def applicable(k,p):
    if p=="Banka" and k in BANK_SKIP:return False
    if p=="Sigorta" and k in INS_SKIP:return False
    if p=="Finansal" and k in OTHER_FIN_SKIP:return False
    if p=="Yatırım Ortaklığı" and k in YORT_SKIP:return False
    return True

def scoreable(k,p):
    if not applicable(k,p):return False
    if p=="GYO" and k in GYO_NONSCORE:return False
    if p=="Holding" and k in HOLDING_NONSCORE:return False
    if p=="Yatırım Ortaklığı" and k in YORT_NONSCORE:return False
    return True

def band(k,p): return OVR.get(p,{}).get(k) or BANDS.get(k)

def abs_score(v,b):
    if v is None or b is None:return None
    d,a,z=b
    if d=="high": return 0 if v<=a else 100 if v>=z else (v-a)/(z-a)*100
    return 100 if v<=a else 0 if v>=z else (z-v)/(z-a)*100

def symbol(t): return str(t).split(":")[-1].upper()

def entity(r):
    s=str(r.get("description") or r.get("name") or r.get("symbol") or "").casefold()
    s=re.sub(r"\b(class|series)\s+[a-z0-9]+\b","",s); s=re.sub(r"\b[a-z]\s+grubu\b","",s)
    return re.sub(r"\s+"," ",s).strip(" -.,")

def universe():
    _,df=(Query().select(*FIELDS).set_markets("turkey").where(col("exchange")=="BIST",col("type")=="stock").order_by("market_cap_basic",ascending=False,nulls_first=False).limit(1000).get_scanner_data())
    if df is None or df.empty: raise RuntimeError("BIST evreni alınamadı")
    df=df.copy()
    # TradingView may tag exchange-traded certificates as type=stock. They are
    # not ordinary listed-company shares and must not contaminate BIST equity
    # medians or company counts (e.g. Darphane ALTIN, DMLKT certificate).
    desc=df["description"].fillna("").astype(str)
    non_equity=desc.str.contains(r"certificate|sertifika",case=False,regex=True,na=False)
    df=df.loc[~non_equity].copy()
    df["symbol"]=df["ticker"].map(symbol)
    return df

def xu100(u):
    # BorsaPy provides BIST index components directly. This is preferred over
    # inferring membership from screener fields because it should return the
    # complete current constituent list.
    try:
        x={str(s).upper() for s in bp.Index("XU100").component_symbols}
        if len(x)>=90:
            return x
    except Exception:
        pass

    # Fallback: TradingView Screener index membership.
    try:
        _,d=Query().select("name","exchange").set_index("SYML:BIST;XU100").limit(200).get_scanner_data()
        x={symbol(t) for t in d["ticker"].tolist()} if d is not None and not d.empty else set()
        if len(x)>=80:return x
    except Exception:
        pass

    if "index" in u:
        m=u["index"].astype(str).str.contains(r"XU100|BIST 100",case=False,na=False,regex=True)
        x=set(u.loc[m,"symbol"])
        if x:return x
    return set()

def dedupe(df):
    d=df.copy(); d["_e"]=d.apply(entity,axis=1); d=d.sort_values("market_cap_basic",ascending=False,na_position="last").drop_duplicates("_e"); return d.drop(columns="_e")

def vals(df,k):
    fld=M[k][0]
    if df.empty or fld not in df:return pd.Series(dtype=float)
    s=pd.to_numeric(df[fld],errors="coerce").dropna().astype(float)
    if k in {"pe","pb","ev","pfcf"}:s=s[s>0]
    return s

def med(df,k):
    s=vals(df,k); return float(s.median()) if len(s) else None

def pct(df,k,v):
    if v is None:return None
    s=vals(df,k)
    if not len(s):return None
    return float(((s<=v) if M[k][3]=="high" else (s>=v)).mean()*100)

def wavg(items):
    q=[(s,w) for s,w in items if s is not None and w>0]
    return sum(s*w for s,w in q)/sum(w for _,w in q) if q else None

def groups(u,t,xset):
    du=dedupe(u); e=entity(t); p=du[du.apply(entity,axis=1)!=e]
    sec=str(t.get("sector") or ""); ind=str(t.get("industry") or "")
    return {
        "industry":p[p["industry"].astype(str).str.casefold()==ind.casefold()] if ind else p.iloc[0:0],
        "sector":p[p["sector"].astype(str).str.casefold()==sec.casefold()] if sec else p.iloc[0:0],
        "xu100":p[p["symbol"].isin(xset)] if xset else p.iloc[0:0],
        "bist":p,
        "all":du,
        "raw_count":len(u),
    }

def analyze(t,p,g):
    out={}
    for k,(fld,label,cat,direction,kind,weight) in M.items():
        v=fnum(t.get(fld))
        app=applicable(k,p)
        scr=scoreable(k,p)
        a=abs_score(v,band(k,p)) if scr else None
        gs={}
        for n in ["industry","sector","xu100","bist"]:
            gs[n]={"median":med(g[n],k),"pct":pct(g[n],k,v) if app else None,"n":len(vals(g[n],k))}
        out[k]={
            "label":label,"cat":cat,"dir":direction,"kind":kind,"w":weight,
            "v":v,"raw_v":v,"source":"TradingView","app":app,"scoreable":scr,
            "abs":a,"groups":gs
        }
    return out

def apply_profile_primary_source(a,p,history,g):
    """Apply profile-specific primary sources and accounting sanity guards."""
    if not history or history.get("error"):
        return a

    # GYO realised valuation: İş Yatırım company-card data takes priority.
    if p=="GYO" and not history.get("metadata_warning"):
        market=history.get("market",{})
        mapping={"pe":"pe","pb":"pb","ev":"ev_ebitda","div":"dividend_yield"}
        for k,mkey in mapping.items():
            if k not in a or mkey not in market:
                continue
            provider=fnum(market.get(mkey))
            x=a[k]
            x["v"]=provider
            x["source"]="İş Yatırım" if provider is not None else "İş Yatırım (A/D)"
            x["scoreable"]=scoreable(k,p)
            x["abs"]=abs_score(provider,band(k,p)) if x["scoreable"] and provider is not None else None
            for gn in ["industry","sector","xu100","bist"]:
                x["groups"][gn]["pct"]=pct(g[gn],k,provider) if provider is not None and x["app"] else None

    # Accounting denominator guard. Negative/zero equity can create extreme ROE,
    # P/B and Debt/Equity values that are mathematically defined by a provider but
    # economically unsuitable for a normal quality score.
    hs=history.get("summary",{})
    equity=fnum(hs.get("equity"))
    if p!="Banka" and equity is not None and equity <= 0:
        for k in ["roe","pb","de","eq_assets"]:
            if k in a:
                a[k]["scoreable"]=False
                a[k]["abs"]=None
                a[k]["score_exclusion_reason"]="Negatif/sıfır özkaynak nedeniyle oran normal kalite puanına alınmadı."

    return a

def scores(a):
    cats={
        c:wavg([(x["abs"],x["w"]) for x in a.values() if x["cat"]==c and x.get("scoreable",x["app"])])
        for c in CATS
    }
    quality=wavg([
        (cats["Büyüme"],.25),(cats["Kârlılık"],.30),
        (cats["Finansal Sağlık"],.25),(cats["Nakit Kalitesi"],.20)
    ])
    val=cats["Değerleme"]
    rel={}
    for gn in ["industry","sector","xu100","bist"]:
        rc={
            c:wavg([
                (x["groups"][gn]["pct"],x["w"])
                for x in a.values()
                if x["cat"]==c and x.get("scoreable",x["app"])
            ])
            for c in CATS
        }
        rq=wavg([
            (rc["Büyüme"],.25),(rc["Kârlılık"],.30),
            (rc["Finansal Sağlık"],.25),(rc["Nakit Kalitesi"],.20)
        ])
        rel[gn]={
            "cats":rc,"quality":rq,"valuation":rc["Değerleme"],
            "overall":wavg([(rq,.7),(rc["Değerleme"],.3)])
        }
    return {
        "cats":cats,"quality":quality,"valuation":val,
        "composite":wavg([(quality,.7),(val,.3)]),"rel":rel
    }

def ref_text(k,p):
    b=band(k,p)
    if not b:return "Bilgi"
    d,a,z=b; kind=M[k][4]
    return f"Zayıf ≤ {fmt(a,kind)} · Güçlü ≥ {fmt(z,kind)}" if d=="high" else f"Güçlü ≤ {fmt(a,kind)} · Zayıf ≥ {fmt(z,kind)}"

def factor_comment(x,p):
    source=x.get("source","TradingView")
    raw=x.get("raw_v")

    if x["v"] is None:
        if p=="GYO" and "A/D" in source:
            raw_text=fmt(raw,x["kind"]) if raw is not None else "N/A"
            return (
                f"{x['label']}: İş Yatırım gerçekleşen oranı A/D (anlamsız/değerlendirilemez) olarak gösteriyor. "
                f"TradingView ham değeri {raw_text} olsa da GYO analizinde bu değer skorlanmadı. "
                "NAD/PD-NAD ve varlık kalitesi önceliklidir."
            )
        return f"{x['label']}: güncel veri bulunmadığı için yorumlanmadı."

    if not x["app"]:
        return (
            f"{x['label']} {fmt(x['v'],x['kind'])}. {p} profili için ana değerlendirme "
            "kriteri değildir ve skora dahil edilmedi."
        )

    pr=x["groups"]["industry"] if x["groups"]["industry"]["n"]>=4 else x["groups"]["sector"]
    name="endüstri" if x["groups"]["industry"]["n"]>=4 else "sektör"

    if not x.get("scoreable",True):
        reason=x.get("score_exclusion_reason")
        s=(
            f"{x['label']} {fmt(x['v'],x['kind'])} ({source}). Bu oran {p} profilinde "
            "karşılaştırmalı bilgi olarak gösterilir ancak ana skora dahil edilmez."
        )
        if reason:
            s+=" "+reason
        if p=="GYO" and x["cat"]=="Değerleme":
            s+=" GYO değerlemesinde gerçek NAD/PD-NAD, portföy ekspertiz değerleri ve proje yapısı daha belirleyicidir."
        elif p=="Holding" and x["cat"]=="Değerleme":
            s+=" Holding değerlemesinde iştirak bazlı NAD ve holding-seviye net nakit/borç ana referanstır."
        elif p=="Yatırım Ortaklığı" and x["cat"]=="Değerleme":
            s+=" Yatırım ortaklığında portföy/NAV iskontosu veya primi ana değerleme referansıdır."
        if pr["median"] is not None and pr["n"]>=3 and pr["pct"] is not None:
            s+=f" TradingView {name} medyanı {fmt(pr['median'],x['kind'])}; göreli konum {pr['pct']:.0f}/100."
        return s

    s=(
        f"{x['label']} {fmt(x['v'],x['kind'])}. Mutlak değerlendirme "
        f"{status(x['abs']).lower()} ({ref_text(next(k for k,v in M.items() if v[1]==x['label']),p)})."
    )
    if pr["median"] is not None and pr["n"]>=3:
        s+=f" {name.capitalize()} medyanı {fmt(pr['median'],x['kind'])}; göreli konum {pr['pct']:.0f}/100."
    q=x["groups"]["xu100"]
    if q["median"] is not None and q["n"]>=10:
        s+=f" BIST100 medyanı {fmt(q['median'],x['kind'])}; göreli konum {q['pct']:.0f}/100."
    b=x["groups"]["bist"]
    if b["median"] is not None and b["n"]>=20:
        s+=f" Tüm BIST medyanı {fmt(b['median'],x['kind'])}; göreli konum {b['pct']:.0f}/100."

    metric_key=next((k for k,v in M.items() if v[1]==x["label"]),None)
    if metric_key in {"rev_g","eps_g","ni_g"} and abs(x["v"])>300:
        s+=" Büyüme oranı çok yüksek baz etkisi taşıyor; mutlak yüzde tek başına sürdürülebilir büyüme kabul edilmedi."
    if metric_key in {"gross","opm","netm","ebitdam","fcfm"} and abs(x["v"])>200:
        s+=" Oranın aşırı seviyesi düşük/oynak payda etkisine işaret edebilir; mali tablo kalemleriyle teyit edilmelidir."
    if metric_key=="roe" and abs(x["v"])>300:
        s+=" ROE'nin aşırı seviyesi özkaynak tabanının küçüklüğü/negatifliği açısından ayrıca kontrol edilmelidir."
    if metric_key=="pe" and x["v"]>200:
        s+=" Çok yüksek F/K, düşük kâr paydasının çarpanı bozduğu bir fiyatlama yapısına işaret edebilir."
    if metric_key=="curr" and x["v"]>100:
        s+=" Aşırı yüksek cari oran çok düşük kısa vadeli yükümlülük paydasından kaynaklanabilir."
    return s

def index_perf():
    # Prefer BorsaPy/TradingView index history for BIST100.
    try:
        d=bp.Index("XU100").history(period="2y")
        if d is not None and not d.empty:
            c=pd.to_numeric(d["Close"],errors="coerce").dropna().astype(float)
            def p(n):return (float(c.iloc[-1])/float(c.iloc[-n-1])-1)*100 if len(c)>n else None
            return {"3m":p(63),"6m":p(126),"12m":p(252)}
    except Exception:
        pass

    # Fallback to Yahoo Finance.
    for s in ["XU100.IS","^XU100"]:
        try:
            d=yf.download(s,period="2y",interval="1d",auto_adjust=False,progress=False,threads=False)
            if not d.empty:
                c=d["Close"]; c=c.iloc[:,0] if isinstance(c,pd.DataFrame) else c; c=c.dropna().astype(float)
                def p(n):return (float(c.iloc[-1])/float(c.iloc[-n-1])-1)*100 if len(c)>n else None
                return {"3m":p(63),"6m":p(126),"12m":p(252)}
        except Exception:
            pass
    return {"3m":None,"6m":None,"12m":None}

def source_validation(t,metrics,history):
    """Cross-check TradingView with İş Yatırım/BorsaPy.

    The selected stock can have different provider definitions (especially GYO
    valuation multiples and TMS 29 growth). Differences are surfaced explicitly.
    """
    if not history or history.get("error"):
        return {"confidence":None,"status":"N/A","checks":[],"critical_count":0,"warning_count":0}

    h=history.get("summary",{})
    market=history.get("market",{})
    checks=[]
    critical=0
    warning=0

    # TTM / statement-derived checks.
    specs=[
        ("Ciro Büyümesi TTM","rev_g",h.get("revenue_ttm_yoy"),"%",10.0,True),
        ("Net Kâr Büyümesi TTM","ni_g",h.get("net_income_ttm_yoy"),"%",15.0,True),
        ("Faaliyet Marjı TTM","opm",h.get("ttm_operating_margin"),"%",5.0,False),
        ("Net Marj TTM","netm",h.get("ttm_net_margin"),"%",5.0,False),
        ("FCF Marjı TTM","fcfm",h.get("fcf_margin"),"%",5.0,False),
        ("Cari Oran","curr",h.get("current_ratio"),"x",0.25,False),
    ]

    for label,key,hval,kind,tol,basis_sensitive in specs:
        tv=metrics.get(key,{}).get("raw_v",metrics.get(key,{}).get("v"))
        if tv is None or hval is None:
            checks.append({"label":label,"tradingview":tv,"borsapy":hval,"difference":None,"status":"N/A","kind":kind})
            continue
        diff=tv-hval
        sign_conflict=(tv>0>hval) or (hval>0>tv)
        if sign_conflict and kind=="%" and max(abs(tv),abs(hval))>=3:
            st="KRİTİK FARK"; critical+=1
        elif abs(diff)>tol*2 and basis_sensitive:
            st="BAZ/FRESHNESS FARKI"; warning+=1
        elif abs(diff)>tol*2:
            st="BÜYÜK FARK"; critical+=1
        elif abs(diff)>tol:
            st="İZLE"; warning+=1
        else:
            st="UYUMLU"
        checks.append({"label":label,"tradingview":tv,"borsapy":hval,"difference":diff,"status":st,"kind":kind})

    # Current valuation/company-card checks from İş Yatırım itself.
    current_specs=[
        ("Cari F/K","pe","pe","x",0.75),
        ("Cari PD/DD","pb","pb","x",0.10),
        ("Cari FD/FAVÖK","ev","ev_ebitda","x",1.00),
    ]
    for label,key,mkey,kind,tol in current_specs:
        tv=metrics.get(key,{}).get("raw_v",metrics.get(key,{}).get("v"))
        iy=market.get(mkey)
        iy=fnum(iy)
        if tv is not None and iy is None:
            # In GYO valuation fields İş Yatırım frequently reports A/D when
            # realised earnings/EBITDA make the multiple economically meaningless.
            # Outside that profile, a missing scrape is treated as N/A rather than
            # automatically assuming A/D.
            is_gyo_ad=(history.get("profile")=="GYO" and key in {"pe","ev"})
            st="İŞ YATIRIM A/D" if is_gyo_ad else "N/A"
            checks.append({
                "label":label,"tradingview":tv,"borsapy":None,"difference":None,
                "status":st,"kind":kind
            })
            if is_gyo_ad:
                critical+=1
        elif tv is None or iy is None:
            checks.append({"label":label,"tradingview":tv,"borsapy":iy,"difference":None,"status":"N/A","kind":kind})
        else:
            diff=tv-iy
            if abs(diff)>tol*2:
                st="BÜYÜK FARK"; critical+=1
            elif abs(diff)>tol:
                st="İZLE"; warning+=1
            else:
                st="UYUMLU"
            checks.append({"label":label,"tradingview":tv,"borsapy":iy,"difference":diff,"status":st,"kind":kind})

    # Market cap check.
    tv_mcap=fnum(t.get("market_cap_basic"))
    iy_mcap=fnum(market.get("market_cap"))
    if tv_mcap is not None and iy_mcap is not None and iy_mcap!=0:
        diff_pct=(tv_mcap/iy_mcap-1.0)*100.0
        if abs(diff_pct)>10:
            st="BÜYÜK FARK"; critical+=1
        elif abs(diff_pct)>2:
            st="İZLE"; warning+=1
        else:
            st="UYUMLU"
        checks.append({
            "label":"Piyasa Değeri","tradingview":tv_mcap/1e9,"borsapy":iy_mcap/1e9,
            "difference":(tv_mcap-iy_mcap)/1e9,"status":st,"kind":"B TL"
        })

    # Net-debt reconciliation: financial statements vs İş Yatırım company card.
    stmt_nd=fnum(h.get("net_debt_statement"))
    iy_nd=fnum(market.get("net_debt"))
    if stmt_nd is not None and iy_nd is not None and iy_nd!=0:
        diff_pct=(stmt_nd/iy_nd-1.0)*100.0
        if abs(diff_pct)>15:
            st="BÜYÜK FARK"; critical+=1
        elif abs(diff_pct)>5:
            st="İZLE"; warning+=1
        else:
            st="UYUMLU"
        checks.append({
            "label":"Net Borç","tradingview":stmt_nd/1e9,"borsapy":iy_nd/1e9,
            "difference":(stmt_nd-iy_nd)/1e9,"status":st,"kind":"B TL"
        })

    confidence=max(0.0,100.0-critical*15.0-warning*5.0)
    status_text="YÜKSEK" if confidence>=85 else "ORTA" if confidence>=65 else "DÜŞÜK"
    return {
        "confidence":confidence,
        "status":status_text,
        "checks":checks,
        "critical_count":critical,
        "warning_count":warning,
    }

def bist_index_perf(code):
    if not code:
        return {"3m":None,"6m":None,"12m":None}
    try:
        d=bp.Index(code).history(period="2y")
        if d is not None and not d.empty:
            closes=pd.to_numeric(d["Close"],errors="coerce").dropna().astype(float)
            def p(n):
                return (float(closes.iloc[-1])/float(closes.iloc[-n-1])-1)*100 if len(closes)>n else None
            return {"3m":p(63),"6m":p(126),"12m":p(252)}
    except Exception:
        pass
    return {"3m":None,"6m":None,"12m":None}


def sector_index_code(t,p):
    """Return a conservative BIST sector-index mapping.

    Ambiguous industries deliberately return None instead of forcing a weak
    benchmark. This keeps relative-price commentary economically coherent.
    """
    if p=="Banka":return "XBANK"
    if p=="Sigorta":return "XSGRT"
    if p=="GYO":return "XGMYO"
    if p=="Holding":return "XHOLD"
    if p=="Yatırım Ortaklığı":return "XYORT"
    if p=="Finansal":return "XUMAL"
    if p=="Savunma/Teknoloji":return "XUTEK"

    sec=str(t.get("sector") or "").casefold()
    ind=str(t.get("industry") or "").casefold()
    if "transport" in sec or "airline" in ind or "transport" in ind:return "XULAS"
    if "communication" in sec or "telecommunication" in ind:return "XILTM"
    if "electric utilit" in ind or "alternative power" in ind:return "XELKT"
    if "food" in ind or "food" in sec:return "XGIDA"
    if any(x in sec for x in ["producer manufacturing","process industries","non-energy minerals"]):return "XUSIN"
    return None


def overall(t,p,s,perf,history=None,validation=None,sector_code=None,sector_perf=None):
    c=s["cats"]
    if p=="GYO":
        words=[
            f"{t['symbol']} için GYO-uyumlu temel kalite skoru {fmt(s['quality'])}/100 ve "
            f"bileşik temel skor {fmt(s['composite'])}/100 düzeyindedir. "
            "Klasik F/K, PD/DD, FD/FAVÖK ve Fiyat/FCF oranlarından otomatik GYO değerleme skoru "
            "üretilmedi; gerçek değerleme için NAD/PD-NAD ve portföy ekspertiz verisi gereklidir."
        ]
    elif p=="Holding":
        words=[
            f"{t['symbol']} için holding-uyumlu temel kalite skoru {fmt(s['quality'])}/100 ve "
            f"bileşik temel skor {fmt(s['composite'])}/100 düzeyindedir. "
            "Klasik sanayi değerleme çarpanları holding iskontosunun yerine kullanılmadı; "
            "esas değerleme için iştirak bazlı NAD ve net nakit/borç gerekir."
        ]
    elif p=="Yatırım Ortaklığı":
        words=[
            f"{t['symbol']} için yatırım ortaklığı-uyumlu temel kalite skoru {fmt(s['quality'])}/100 ve "
            f"bileşik temel skor {fmt(s['composite'])}/100 düzeyindedir. "
            "Portföy/NAV verisi olmadan klasik F/K-PD/DD çarpanlarından otomatik değerleme skoru üretilmedi."
        ]
    else:
        words=[
            f"{t['symbol']} için temel kalite skoru {fmt(s['quality'])}/100, "
            f"değerleme skoru {fmt(s['valuation'])}/100 ve bileşik temel skor "
            f"{fmt(s['composite'])}/100 düzeyindedir."
        ]

    good=sorted(
        [(k,v) for k,v in c.items() if k!="Değerleme" and v is not None and v>=65],
        key=lambda z:z[1],reverse=True
    )[:2]
    bad=sorted(
        [(k,v) for k,v in c.items() if k!="Değerleme" and v is not None and v<45],
        key=lambda z:z[1]
    )[:2]

    if good:
        words.append(
            "Çapraz kesit ve mutlak oran setinde öne çıkan güçlü alanlar "
            +" ve ".join(f"{k.lower()} ({v:.0f}/100)" for k,v in good)+"."
        )
    if bad:
        words.append(
            "Görece zayıf alanlar "
            +" ve ".join(f"{k.lower()} ({v:.0f}/100)" for k,v in bad)+"."
        )

    if s["valuation"] is not None:
        words.append(
            "Değerleme çarpanları kalite skoruna kıyasla daha zayıf; güçlü şirket ile ucuz hisse ayrımı korunmalı."
            if s["valuation"]<35 else
            "Değerleme şirket kalitesini destekliyor; yine de sektör ve tarihsel bantlarla birlikte okunmalı."
            if s["valuation"]>=65 else
            "Değerleme dengeli bölgede; kalite ve büyümenin sürdürülebilirliğiyle birlikte değerlendirilmesi daha sağlıklı."
        )

    # Historical financial statement synthesis.
    if history and not history.get("error"):
        hs=history.get("summary",{})
        period=hs.get("latest_period")
        rev=hs.get("revenue_yoy")
        ni=hs.get("net_income_yoy")
        if p=="Banka":
            if ni is not None:
                words.append(
                    f"{period or 'Son rapor dönemi'} net kârı yıllık {ni:+.1f}% değişim gösterdi."
                )
            ey=hs.get("equity_yoy")
            ay=hs.get("assets_yoy")
            ly=hs.get("loans_yoy")
            dy=hs.get("deposits_yoy")
            nii=hs.get("net_interest_income_yoy")
            fee=hs.get("fee_income_yoy")
            eqa=hs.get("equity_to_assets")
            if ey is not None or ay is not None:
                words.append(
                    f"Bilanço tarafında özkaynak büyümesi {fmt(ey,'%')}, aktif büyümesi {fmt(ay,'%')}; "
                    "banka profili için sanayi tipi net borç/FCF metrikleri ana karar setine alınmadı."
                )
            if ly is not None or dy is not None:
                words.append(
                    f"Kredi büyümesi {fmt(ly,'%')}, mevduat büyümesi {fmt(dy,'%')}; "
                    "fonlama ile kredi genişlemesinin dengesi birlikte izleniyor."
                )
            if nii is not None or fee is not None:
                words.append(
                    f"Gelir kompozisyonunda net faiz geliri yıllık {fmt(nii,'%')}, "
                    f"net ücret/komisyon geliri {fmt(fee,'%')} değişti."
                )
            if eqa is not None:
                words.append(f"Özkaynak/aktif oranı {eqa:.1f}% seviyesinde.")
        else:
            if rev is not None or ni is not None:
                words.append(
                    f"{period or 'Son rapor dönemi'} finansallarında ciro yıllık {fmt(rev,'%')}, "
                    f"net kâr {fmt(ni,'%')} değişti."
                )
            nm=hs.get("net_margin_yoy_pp")
            om=hs.get("operating_margin_yoy_pp")
            if nm is not None or om is not None:
                words.append(
                    f"Marj dinamiğinde net marj yıllık {fmt(nm,' puan')}, "
                    f"faaliyet marjı {fmt(om,' puan')} değişim gösterdi."
                )
            conv=hs.get("cash_conversion")
            fcfm=hs.get("fcf_margin")
            if conv is not None:
                words.append(
                    f"Kârın nakde dönüşümü TTM bazında {conv:.2f}x"
                    + (f" ve FCF marjı {fcfm:.1f}%." if fcfm is not None else ".")
                )
            nd=hs.get("net_debt_yoy")
            if nd is not None:
                words.append(
                    f"Net borcun yıllık değişimi {nd:+.1f}%; bu hareket bilanço riskinin yönü açısından ayrıca izlenmeli."
                )

        hc=history.get("commentary",{})
        strengths=hc.get("strengths",[])
        risks=hc.get("risks",[])
        if strengths:
            words.append("Tarihsel teyitte güçlü sinyaller: "+" ".join(strengths[:2]))
        if risks:
            words.append("Başlıca tarihsel risk/izleme alanları: "+" ".join(risks[:2]))

    rs=s["rel"]["sector"]["overall"]
    rx=s["rel"]["xu100"]["overall"]
    rb=s["rel"]["bist"]["overall"]
    if rs is not None:
        words.append(f"Tüm sektör şirketlerine göre göreli temel skor {rs:.0f}/100.")
    if rx is not None:
        words.append(
            f"BIST100 temel dağılımına göre {rx:.0f}/100"
            +(f", tüm BIST'e göre {rb:.0f}/100." if rb is not None else ".")
        )

    sp=fnum(t.get("Perf.Y"))
    xp=perf["12m"]
    if sp is not None and xp is not None:
        alpha=sp-xp
        words.append(
            f"Son 12 aylık fiyat performansı BIST100'e göre {alpha:+.2f} puan relatif fark taşıyor; "
            +("fiyat davranışı temel görünümü destekliyor." if alpha>10 else
              "fiyat davranışı temel görünümün gerisinde kalıyor." if alpha<-10 else
              "relatif fiyatlama belirgin bir ayrışma üretmiyor.")
        )

    if sp is not None and sector_code and sector_perf and sector_perf.get("12m") is not None:
        salpha=sp-sector_perf["12m"]
        words.append(
            f"Aynı dönemde {sector_code} sektör endeksine göre relatif fark {salpha:+.2f} puan; "
            +("hisse sektör endeksinin üzerinde." if salpha>5 else
              "hisse sektör endeksinin altında." if salpha<-5 else
              "hisse sektör endeksine yakın seyrediyor.")
        )

    if validation and validation.get("critical_count",0)>0:
        conflicts=[
            x for x in validation.get("checks",[])
            if x.get("status") in {"KRİTİK FARK","BÜYÜK FARK"}
        ]
        names=", ".join(x["label"] for x in conflicts[:3])
        words.append(
            f"Kaynak doğrulamasında {validation['critical_count']} önemli ayrışma bulundu"
            +(f" ({names})" if names else "")
            +"; bu metriklerde tek kaynağa dayalı kesin yorum yerine mali tablo türetimi öncelikle kontrol edilmelidir."
        )

    if p=="GYO":
        hs=(history or {}).get("summary",{})
        bed=hs.get("book_equity_discount")
        if bed is not None:
            words.append(
                f"Piyasa değeri/defter özkaynağı üzerinden görülen yaklaşık %{bed:.1f} iskonto yalnızca "
                "defter değeri iskontosudur; gerçek NAD iskontosu değildir."
            )
        words.append(
            "GYO sonucunda NAD, ekspertiz değerleri, arsa/proje portföyü, satış-teslim takvimi ve finansman yapısı "
            "klasik sanayi çarpanlarının önünde tutulmalıdır."
        )
    elif p=="Holding":
        words.append(
            "PD/DD gerçek NAD iskontosu olarak kabul edilmez; iştirak değerleri, holding-seviye net nakit/borç "
            "ve halka açık/kapalı iştirak değerleri ayrıca toplanmadan defter değeri NAD kabul edilmez."
        )
    elif p=="Yatırım Ortaklığı":
        words.append(
            "Yatırım ortaklıklarında portföy/NAV verisi ana değerleme referansıdır; muhasebe kârı ve "
            "tek dönem çarpanları portföy değer değişimleri nedeniyle tek başına yeterli değildir."
        )
    elif p=="Finansal":
        words.append(
            "Banka dışı finansal şirketlerde sanayi tipi FD/FAVÖK, FCF ve işletme sermayesi oranları "
            "ana skordan çıkarıldı; kârlılık, özkaynak verimliliği ve bilanço yapısı önceliklidir."
        )

    return " ".join(words)

def scoretxt(v):
    return "N/A" if v is None else f"{v:.0f}/100"

def _hist_num(v,suffix="",digits=1):
    return "N/A" if v is None else f"{v:.{digits}f}{suffix}"

def _hist_money(v):
    if v is None:return "N/A"
    a=abs(v)
    if a>=1e12:return f"{v/1e12:.2f}T TL"
    if a>=1e9:return f"{v/1e9:.2f}B TL"
    if a>=1e6:return f"{v/1e6:.1f}M TL"
    return f"{v:,.0f} TL"

def validation_html(validation):
    if not validation or validation.get("confidence") is None:
        return '<div class="note">Kaynaklar arası doğrulama için yeterli ortak metrik yok.</div>'
    e=lambda z:html.escape(str(z))
    rows=[]
    for x in validation.get("checks",[]):
        kind=x.get("kind","")
        def fv(v):
            if v is None:return "N/A"
            if kind=="%":return f"{v:.2f}%"
            if kind=="x":return f"{v:.2f}x"
            if kind=="B TL":return f"{v:.2f} mlr TL"
            return f"{v:.2f}"
        rows.append(
            "<tr>"
            f"<td>{e(x.get('label',''))}</td>"
            f"<td>{e(fv(x.get('tradingview')))}</td>"
            f"<td>{e(fv(x.get('borsapy')))}</td>"
            f"<td>{e('N/A' if x.get('difference') is None else fv(x.get('difference')))}</td>"
            f"<td>{e(x.get('status','N/A'))}</td>"
            "</tr>"
        )
    return (
        '<h2>Kaynaklar Arası Veri Doğrulaması</h2>'
        f'<div class="card"><small>Veri Güveni</small><b>{validation["confidence"]:.0f}/100</b>'
        f'<span>{e(validation.get("status","N/A"))}</span></div>'
        '<div class="note">TradingView çapraz-kesit verileri; İş Yatırım şirket kartı ve '
        'BorsaPy/İş Yatırım mali tablolarından türetilen metriklerle karşılaştırılır. '
        'Farklar otomatik olarak gizlenmez. GYO gibi profillerde İş Yatırım bir çarpanı '
        'A/D olarak sınıflandırıyorsa TradingView sayısı ana skora zorla sokulmaz. '
        'Büyüme oranlarında TMS 29, karşılaştırmalı dönemlerin yeniden ifadesi ve güncelleme '
        'zamanı farklı bazlar oluşturabilir.</div>'
        '<div class="table"><table><tr><th>Metrik</th><th>TradingView / Tablo Türetilmiş</th>'
        '<th>İş Yatırım</th><th>Fark</th><th>Durum</th></tr>'+''.join(rows)+'</table></div>'
    )

def history_html(history):
    if not history:
        return '<div class="note">Tarihsel mali tablo katmanı çalıştırılmadı.</div>'
    if history.get("error"):
        return f'<div class="note">Tarihsel mali tablo katmanı: {html.escape(str(history["error"]))}</div>'

    e=lambda z:html.escape(str(z))
    h=history.get("summary",{})
    q=history.get("quarterly",[])
    comm=history.get("commentary",{})
    dq=history.get("data_quality",{})
    prof=history.get("profile","")

    if prof=="Banka":
        cards=[
            ("Son Rapor",h.get("latest_period") or "N/A",""),
            ("Net Kâr YoY",_hist_num(h.get("net_income_yoy"),"%"),""),
            ("Net Faiz Geliri YoY",_hist_num(h.get("net_interest_income_yoy"),"%"),""),
            ("Ücret/Komisyon YoY",_hist_num(h.get("fee_income_yoy"),"%"),""),
            ("Kredi Büyümesi",_hist_num(h.get("loans_yoy"),"%"),""),
            ("Mevduat Büyümesi",_hist_num(h.get("deposits_yoy"),"%"),""),
            ("Özkaynak Büyümesi",_hist_num(h.get("equity_yoy"),"%"),""),
            ("Özkaynak/Aktif",_hist_num(h.get("equity_to_assets"),"%"),""),
        ]
    else:
        cards=[
            ("Son Rapor",h.get("latest_period") or "N/A",""),
            ("Ciro YoY",_hist_num(h.get("revenue_yoy"),"%"),""),
            ("Net Kâr YoY",_hist_num(h.get("net_income_yoy"),"%"),""),
            ("Net Marj",_hist_num(h.get("net_margin"),"%"),""),
            ("Nakit Dönüşümü",_hist_num(h.get("cash_conversion"),"x",2),""),
            ("FCF Marjı",_hist_num(h.get("fcf_margin"),"%"),""),
            ("Net Borç",_hist_money(h.get("net_debt")),""),
            ("3Y Ciro CAGR",_hist_num(h.get("revenue_cagr_3y"),"%"),""),
        ]

    cards_html="".join(
        f'<div class="card"><small>{e(n)}</small><b>{e(v)}</b><span>{e(s)}</span></div>'
        for n,v,s in cards
    )

    rows=[]
    if prof=="Banka":
        for r in q:
            rows.append(
                "<tr>"
                f"<td>{e(r.get('period',''))}</td>"
                f"<td>{e(_hist_money(r.get('net_interest_income')))}</td>"
                f"<td>{e(_hist_money(r.get('fee_income')))}</td>"
                f"<td>{e(_hist_money(r.get('net_income')))}</td>"
                f"<td>{e(_hist_num(r.get('net_income_yoy'),'%'))}</td>"
                f"<td>{e(_hist_money(r.get('loans')))}</td>"
                f"<td>{e(_hist_money(r.get('deposits')))}</td>"
                "</tr>"
            )
        header=(
            '<tr><th>Dönem</th><th>Net Faiz Geliri/YTD</th><th>Net Ücret-Komisyon/YTD</th>'
            '<th>Net Kâr/YTD</th><th>Net Kâr YoY</th><th>Krediler</th><th>Mevduat</th></tr>'
        )
    else:
        for r in q:
            rows.append(
                "<tr>"
                f"<td>{e(r.get('period',''))}</td>"
                f"<td>{e(_hist_money(r.get('revenue')))}</td>"
                f"<td>{e(_hist_num(r.get('revenue_yoy'),'%'))}</td>"
                f"<td>{e(_hist_money(r.get('net_income')))}</td>"
                f"<td>{e(_hist_num(r.get('net_income_yoy'),'%'))}</td>"
                f"<td>{e(_hist_num(r.get('operating_margin'),'%'))}</td>"
                f"<td>{e(_hist_num(r.get('net_margin'),'%'))}</td>"
                f"<td>{e(_hist_money(r.get('operating_cash_flow_discrete')))}</td>"
                "</tr>"
            )
        header=(
            '<tr><th>Dönem</th><th>Ciro/YTD</th><th>Ciro YoY</th><th>Net Kâr/YTD</th>'
            '<th>Net Kâr YoY</th><th>Faaliyet Marjı</th><th>Net Marj</th><th>Çeyreklik OCF</th></tr>'
        )

    def list_html(items,cls):
        if not items:return ""
        return f'<div class="note {cls}"><ul>'+"".join(f"<li>{e(x)}</li>" for x in items)+"</ul></div>"

    paragraphs="".join(f"<p>{e(x)}</p>" for x in comm.get("paragraphs",[]))
    quality=(
        f"Çekirdek satır kapsaması {dq.get('core_rows_found','N/A')}/{dq.get('core_rows_expected','N/A')} · "
        f"Çeyrek sayısı {dq.get('quarterly_periods','N/A')} · "
        f"Yıllık dönem sayısı {dq.get('annual_periods','N/A')}"
    )

    return (
        '<h2>12 Çeyreklik Tarihsel Finansal Analiz</h2>'
        f'<div class="grid">{cards_html}</div>'
        f'<div class="note">{e(quality)}</div>'
        f'<div class="note expert">{paragraphs or "Tarihsel yorum üretmek için yeterli veri yok."}</div>'
        '<div class="history-lists">'
        +list_html(comm.get("strengths",[]),"positive")
        +list_html(comm.get("risks",[]),"negative")
        +list_html(comm.get("watch",[]),"")
        +'</div>'
        '<div class="table"><table>'+header+''.join(rows)+'</table></div>'
    )

def html_report(t,p,a,s,g,xset,perf,comments,gen,history=None,validation=None,sector_code=None,sector_perf=None):
    e=lambda z:html.escape(str(z)); cards=[]
    for n,v in [("Temel Kalite",s["quality"]),("Değerleme",s["valuation"]),("Bileşik",s["composite"]),("Sektör Relatif",s["rel"]["sector"]["overall"]),("BIST100 Relatif",s["rel"]["xu100"]["overall"]),("Tüm BIST Relatif",s["rel"]["bist"]["overall"])]:
        cards.append(f'<div class="card"><small>{e(n)}</small><b>{e(scoretxt(v))}</b><span>{e(status(v))}</span></div>')
    rows=[]; blocks=[]
    for k,x in a.items():
        if x["v"] is None:continue
        G=x["groups"]
        def grp(n):
            q=G[n]
            return f"{e(fmt(q['median'],x['kind']))}<small>n={q['n']} · {e(scoretxt(q['pct']))}</small>"
        rows.append(
            f"<tr><td>{e(x['label'])}</td><td>{e(fmt(x['v'],x['kind']))}</td>"
            f"<td>{e('Uygulanmaz' if not x['app'] else 'Skor dışı' if not x.get('scoreable',True) else status(x['abs']))}</td>"
            f"<td>{grp('industry')}</td><td>{grp('sector')}</td><td>{grp('xu100')}</td><td>{grp('bist')}</td></tr>"
        )
        blocks.append(f"<section><h3>{e(x['label'])} — {e(fmt(x['v'],x['kind']))}</h3><p>{e(comments[k])}</p></section>")
    cr=[]
    for c in CATS:
        cr.append(
            f"<tr><td>{e(c)}</td><td>{e(scoretxt(s['cats'][c]))}</td>"
            f"<td>{e(scoretxt(s['rel']['sector']['cats'][c]))}</td>"
            f"<td>{e(scoretxt(s['rel']['xu100']['cats'][c]))}</td>"
            f"<td>{e(scoretxt(s['rel']['bist']['cats'][c]))}</td></tr>"
        )
    pr=[]
    sector_perf=sector_perf or {"3m":None,"6m":None,"12m":None}
    for k,n in [("3m","3 Ay"),("6m","6 Ay"),("12m","12 Ay")]:
        sp=fnum(t.get({"3m":"Perf.3M","6m":"Perf.6M","12m":"Perf.Y"}[k]))
        xp=perf[k]
        sip=sector_perf.get(k)
        al=sp-xp if sp is not None and xp is not None else None
        sal=sp-sip if sp is not None and sip is not None else None
        pr.append(
            f"<tr><td>{n}</td><td>{fmt(sp,'%')}</td><td>{fmt(xp,'%')}</td>"
            f"<td>{'N/A' if al is None else f'{al:+.2f} puan'}</td>"
            f"<td>{fmt(sip,'%')}</td><td>{'N/A' if sal is None else f'{sal:+.2f} puan'}</td></tr>"
        )
    sec=str(t.get('sector') or 'N/A'); ind=str(t.get('industry') or 'N/A'); name=str(t.get('description') or t.get('name') or t['symbol'])
    return f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(t['symbol'])} — BIST Fundamental Intelligence</title><style>body{{font-family:Arial;background:#0d1117;color:#e6edf3;margin:0;line-height:1.5}}main{{max-width:1500px;margin:auto;padding:28px}}small{{display:block;color:#8b949e}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:20px 0}}.card,section,.note{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:15px}}.card b{{display:block;font-size:26px}}.table{{overflow:auto;margin:18px 0}}table{{width:100%;min-width:1100px;border-collapse:collapse;background:#161b22}}th,td{{padding:9px;border:1px solid #30363d;text-align:right;vertical-align:top}}th:first-child,td:first-child{{text-align:left}}th{{background:#21262d}}section{{margin:10px 0}}section h3{{margin:0 0 6px;font-size:16px}}section p{{margin:0}}.note{{border-left:4px solid #d29922}}.expert{{border-left-color:#3fb950}}</style></head><body><main><h1>{e(t['symbol'])} — Fundamental Intelligence Report</h1><p>{e(name)} · Profil: {e(p)} · Sektör: {e(sec)} · Endüstri: {e(ind)} · {e(gen)}</p><div class="grid">{''.join(cards)}</div><h2>Profesyonel Genel Değerlendirme</h2><div class="note expert">{e(overall(t,p,s,perf,history,validation,sector_code,sector_perf))}</div>{history_html(history)}{validation_html(validation)}<h2>Kategori Özeti</h2><div class="table"><table><tr><th>Kategori</th><th>Mutlak</th><th>Sektör</th><th>BIST100</th><th>Tüm BIST</th></tr>{''.join(cr)}</table></div><h2>Tüm Finansal Faktörler</h2><div class="note">Karşılaştırma sabit emsal sayısıyla değil, güncel tam BIST evreninden otomatik sektör/endüstri, BIST100 ve tüm BIST dağılımlarıyla yapılır. 100 puan göreli olarak daha avantajlı konumu gösterir.</div><div class="table"><table><tr><th>Metrik</th><th>{e(t['symbol'])}</th><th>Mutlak</th><th>Endüstri</th><th>Sektör</th><th>BIST100</th><th>Tüm BIST</th></tr>{''.join(rows)}</table></div><h2>Faktör Bazlı Uzman Yorumları</h2>{''.join(blocks)}<h2>Endeks ve Sektör Fiyat Relatif Performansı</h2><div class="table"><table><tr><th>Dönem</th><th>{e(t['symbol'])}</th><th>XU100</th><th>XU100 Alfa</th><th>{e(sector_code or 'Sektör Endeksi N/A')}</th><th>Sektör Alfa</th></tr>{''.join(pr)}</table></div><h2>Kapsam</h2><div class="grid"><div class="card"><small>BIST Pay/Kotasyon</small><b>{g.get('raw_count','N/A')}</b></div><div class="card"><small>Benzersiz BIST Şirketi</small><b>{len(g['all'])}</b></div><div class="card"><small>Sektör</small><b>{len(g['sector'])}</b><span>{e(sec)}</span></div><div class="card"><small>Endüstri</small><b>{len(g['industry'])}</b><span>{e(ind)}</span></div><div class="card"><small>BIST100 üyeleri</small><b>{len(xset) if xset else 'N/A'}</b></div></div><p class="note">Eksik veri uydurulmaz. Mutlak referans bantları evrensel kesinlik değil, finansal oran mantığı + profil kalibrasyonudur. GYO/Holding için PD/DD gerçek NAD iskontosu değildir. Araştırma amaçlıdır; yatırım tavsiyesi değildir.</p></main></body></html>'''

def borsapy_target_context(sym,p):
    """BIST-specific deep context for the selected stock.

    Uses BorsaPy for KAP metadata, exact market metrics, and financial statement
    availability. Heavy statement retrieval is only done for the selected stock,
    never for the whole BIST universe.
    """
    out={"source":"borsapy","kap":{},"market":{},"financials":{}}
    try:
        stock=bp.Ticker(sym)
        info=stock.info.todict() if hasattr(stock.info,"todict") else dict(stock.info)
        out["kap"]={
            "sector":info.get("sector"),
            "industry":info.get("industry"),
            "website":info.get("website"),
            "business_summary":info.get("longBusinessSummary"),
        }
        out["market"]={
            "market_cap":info.get("marketCap"),
            "pe":info.get("trailingPE"),
            "pb":info.get("priceToBook"),
            "ev_ebitda":info.get("enterpriseToEbitda"),
            "net_debt":info.get("netDebt"),
            "foreign_ratio":info.get("foreignRatio"),
            "dividend_yield":info.get("dividendYield"),
        }

        group="UFRS" if p=="Banka" else "XI_29"
        try:
            bs=stock.get_balance_sheet(quarterly=True,financial_group=group,last_n=8)
            out["financials"]["balance_sheet_periods"]=list(bs.columns)
            out["financials"]["balance_sheet_rows"]=int(len(bs))
        except Exception as exc:
            out["financials"]["balance_sheet_error"]=str(exc)

        try:
            inc=stock.get_income_stmt(quarterly=True,financial_group=group,last_n=8)
            out["financials"]["income_stmt_periods"]=list(inc.columns)
            out["financials"]["income_stmt_rows"]=int(len(inc))
        except Exception as exc:
            out["financials"]["income_stmt_error"]=str(exc)

        if p!="Banka":
            try:
                cf=stock.get_cashflow(quarterly=True,financial_group=group,last_n=8)
                out["financials"]["cashflow_periods"]=list(cf.columns)
                out["financials"]["cashflow_rows"]=int(len(cf))
            except Exception as exc:
                out["financials"]["cashflow_error"]=str(exc)
    except Exception as exc:
        out["error"]=str(exc)
    return out

def safe(v):
    if isinstance(v,dict):return {str(k):safe(x) for k,x in v.items()}
    if isinstance(v,list):return [safe(x) for x in v]
    if isinstance(v,set):return sorted(v)
    if isinstance(v,pd.Series):return safe(v.to_dict())
    if isinstance(v,(str,int,float,bool)) or v is None:return v
    return None if pd.isna(v) else str(v)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("symbol"); a=ap.parse_args(); sym=a.symbol.upper().replace("BIST:","").replace(".IS","").strip()
    print("[1/11] Tüm BIST evreni alınıyor..."); u=universe(); h=u[u.symbol==sym]
    if h.empty:raise SystemExit(f"{sym} bulunamadı")
    t=h.iloc[0].copy(); t["symbol"]=sym; p=profile(t)
    print("[2/11] BIST100 üyeleri alınıyor..."); xs=xu100(u)
    print("[3/11] BorsaPy/KAP ve 12 çeyreklik mali tablolar analiz ediliyor..."); REPORTS.mkdir(exist_ok=True); hist=build_historical_analysis(sym,p,REPORTS)
    print("[4/11] Tüm sektör / endüstri / BIST karşılaştırmaları..."); g=groups(u,t,xs); an=analyze(t,p,g); an=apply_profile_primary_source(an,p,hist,g); sc=scores(an)
    print("[5/11] Her faktör yorumlanıyor..."); cm={k:factor_comment(v,p) for k,v in an.items()}
    print("[6/11] XU100 ve sektör endeksi performansı..."); ip=index_perf(); secidx=sector_index_code(t,p); sip=bist_index_perf(secidx)
    print("[7/11] Tarihsel büyüme, marj, nakit ve bilanço trendleri birleştiriliyor...")
    print("[8/11] Kaynaklar arası veri doğrulaması yapılıyor..."); valid=source_validation(t,an,hist)
    print("[9/11] Sektör endeksi relatif fiyat görünümü birleştiriliyor...")
    print("[10/11] Profesyonel rapor hazırlanıyor..."); gen=datetime.now().isoformat(timespec="seconds")
    hp=REPORTS/f"{sym}_report.html"; jp=REPORTS/f"{sym}_report.json"; cp=REPORTS/f"{sym}_universe_snapshot.csv"
    hp.write_text(html_report(t,p,an,sc,g,xs,ip,cm,gen,hist,valid,secidx,sip),encoding="utf-8")
    jp.write_text(json.dumps(safe({"symbol":sym,"target":t,"profile":p,"metrics":an,"scores":sc,"xu100_count":len(xs),"index_performance":ip,"sector_index":{"code":secidx,"performance":sip},"historical_analysis":hist,"source_validation":valid,"comments":cm,"overall":overall(t,p,sc,ip,hist,valid,secidx,sip),"generated_at":gen}),ensure_ascii=False,indent=2),encoding="utf-8")
    g["all"].to_csv(cp,index=False,encoding="utf-8-sig")
    print(f"[11/11] Hazır: BIST pay={g.get('raw_count')}, benzersiz şirket={len(g['all'])}, sektör={len(g['sector'])}, endüstri={len(g['industry'])}, XU100={len(xs) if xs else 'N/A'}, veri güveni={valid.get('confidence')}")
    print(hp); print(jp); print(cp)

if __name__=="__main__":main()
