from __future__ import annotations

import math
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
import borsapy as bp
from special_profiles import build_special_profile_analysis


INCOME_ROWS = {
    "revenue": [
        "Satış Gelirleri", "Hasılat", "Net Satışlar", "Satışlar",
    ],
    "gross_profit": [
        "BRÜT KAR (ZARAR)", "Brüt Kar", "Brüt Kâr",
    ],
    "operating_profit": [
        "FAALİYET KARI (ZARARI)", "Faaliyet Karı", "Faaliyet Kârı",
        "Esas Faaliyet Karı", "Esas Faaliyet Kârı",
        "XI. NET FAALİYET KARI/ZARARI (VIII-IX-X)",
    ],
    "net_income": [
        "Ana Ortaklık Payları", "Net Dönem Karı", "Dönem Net Kar",
        "DÖNEM KARI (ZARARI)", "SÜRDÜRÜLEN FAALİYETLER DÖNEM KARI",
        "XXIII. NET DÖNEM KARI/ZARARI (XVII+XXII)",
    ],
    "depreciation": [
        "Amortisman Giderleri", "Amortisman ve İtfa Giderleri",
        "Amortisman ve Tükenme Payları",
    ],
    # Bank / financial institution candidates
    "interest_income": [
        "Faiz Gelirleri", "Faiz ve Benzeri Gelirler",
    ],
    "net_interest_income": [
        "Net Faiz Geliri", "Net Faiz Gelirleri",
        "Faiz Gelirleri, Net",
        "III. NET FAİZ GELİRİ/GİDERİ (I - II)",
    ],
    "fee_income": [
        "Net Ücret ve Komisyon Gelirleri",
        "Ücret ve Komisyon Gelirleri, Net",
        "IV. NET ÜCRET VE KOMİSYON GELİRLERİ/GİDERLERİ",
    ],
}

PARENT_EQUITY_ROWS = [
    "Ana Ortaklığa Ait Özkaynaklar",
    "Ana Ortaklık Paylarına Ait Özkaynaklar",
    "Ana Ortaklığa Ait Özkaynak",
    "Ana Ortaklık Payları",
]

BALANCE_ROWS = {
    "cash": [
        "Nakit ve Nakit Benzerleri",
        "Nakit ve Nakit Benzeri Varlıklar",
        "I. NAKİT DEĞERLER VE MERKEZ BANKASI",
    ],
    "current_assets": ["Dönen Varlıklar"],
    "current_liabilities": ["Kısa Vadeli Yükümlülükler"],
    "total_assets": ["Toplam Varlıklar", "TOPLAM AKTİFLER", "Toplam Aktifler", "AKTİF TOPLAMI"],
    "equity": [
        "Özkaynaklar", "Toplam Özkaynaklar",
        "Özsermaye Toplamı", "ÖZKAYNAK",
        "Ana Ortaklığa Ait Özkaynaklar",
        "XVI. ÖZKAYNAKLAR",
    ],
    "loans": [
        "Krediler", "Krediler ve Alacaklar",
        "Nakdi Krediler", "VI. KREDİLER",
    ],
    "deposits": [
        "Mevduat", "Toplam Mevduat",
        "Mevduatlar", "I. MEVDUAT", "I. TOPLANAN FONLAR", "Toplanan Fonlar",
    ],
    "financial_investments": [
        "Finansal Yatırımlar",
    ],
}

CASHFLOW_ROWS = {
    "operating_cash_flow": [
        "İşletme Faaliyetlerinden Nakit Akışları",
        "İşletme Faaliyetlerinden Kaynaklanan Nakit Akışları",
        "İşletme Faaliyetlerinden Kaynaklanan Net Nakit",
        "İşletme Faaliyetlerinden Sağlanan Net Nakit",
        "İşletme Faaliyetlerinden Elde Edilen Nakit Akışları",
        "Faaliyetlerden Elde Edilen Nakit Akışları",
    ],
    "capex": [
        "Sabit Sermaye Yatırımları",
        "Maddi ve Maddi Olmayan Duran Varlık Alımları",
        "Maddi Duran Varlık Alımları",
        "Maddi ve Maddi Olmayan Duran Varlık Alımlarından Kaynaklanan Nakit Çıkışları",
        "Maddi Duran Varlık Alımından Kaynaklanan Nakit Çıkışları",
        "Yatırım Harcamaları",
    ],
    "free_cash_flow": [
        "Serbest Nakit Akım",
        "Serbest Nakit Akışı",
        "Free Cash Flow",
    ],
}

FINANCIAL_DEBT_KEYWORDS = [
    "Finansal Borçlar",
    "Finansal Borç",
    "Kısa Vadeli Borçlanmalar",
    "Uzun Vadeli Borçlanmalar",
    "Diğer Finansal Yükümlülükler",
]


def _retry_call(fn, attempts=2, base_delay=0.6):
    last=None
    for attempt in range(max(1,int(attempts))):
        try:
            return fn()
        except Exception as exc:
            last=exc
            if attempt+1 < attempts:
                time.sleep(base_delay*(attempt+1))
    if last is not None:
        raise last


def _norm(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("ı", "i")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _qkey(label: Any) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{4})Q([1-4])", str(label))
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2)))


def _year_key(label: Any) -> int:
    try:
        return int(str(label))
    except Exception:
        return 0


def _numeric_series(row: pd.Series | pd.DataFrame | None, quarterly: bool = True) -> pd.Series:
    if row is None:
        return pd.Series(dtype=float)
    # Duplicate financial-statement labels may cause df.loc[label] to return a
    # DataFrame. For single-row metrics use the first physical occurrence.
    if isinstance(row, pd.DataFrame):
        if row.empty:
            return pd.Series(dtype=float)
        row = row.iloc[0]
    s = pd.to_numeric(row, errors="coerce").dropna().astype(float)
    if s.empty:
        return s
    ordered = sorted(s.index, key=_qkey if quarterly else _year_key)
    return s.reindex(ordered)


def _find_row(df: pd.DataFrame | None, candidates: list[str], excludes: list[str] | None = None):
    if df is None or df.empty:
        return None
    excludes_n = [_norm(x) for x in (excludes or [])]
    index = list(df.index)
    normalized = {idx: _norm(idx) for idx in index}

    # Exact match first.
    for candidate in candidates:
        c = _norm(candidate)
        for idx in index:
            value = normalized[idx]
            if value == c and not any(x in value for x in excludes_n):
                return idx

    # Then substring match.
    for candidate in candidates:
        c = _norm(candidate)
        for idx in index:
            value = normalized[idx]
            if c in value and not any(x in value for x in excludes_n):
                return idx
    return None


def _find_series(df: pd.DataFrame | None, candidates: list[str], quarterly: bool = True,
                 excludes: list[str] | None = None) -> tuple[pd.Series, str | None]:
    row = _find_row(df, candidates, excludes=excludes)
    if row is None:
        return pd.Series(dtype=float), None
    return _numeric_series(df.loc[row], quarterly=quarterly), str(row)


def _sum_matching_rows(df: pd.DataFrame | None, keywords: list[str], quarterly: bool = True) -> tuple[pd.Series, list[str]]:
    if df is None or df.empty:
        return pd.Series(dtype=float), []
    keys = [_norm(x) for x in keywords]
    mask = [any(k in _norm(idx) for k in keys) for idx in df.index]
    subset = df.loc[mask]
    if subset.empty:
        return pd.Series(dtype=float), []

    # BorsaPy merges financial-statement batches on row labels. When the source
    # has two legitimate rows with the same label (e.g. short- and long-term
    # "Finansal Borçlar"), multi-batch joins can repeat Cartesian combinations.
    # Summing all physical rows would therefore multiply debt. For each period
    # we sum UNIQUE numeric values under the matched label(s).
    data: dict[Any, float] = {}
    for colname in subset.columns:
        col = pd.to_numeric(subset[colname], errors="coerce").dropna()
        if col.empty:
            continue
        unique_vals = pd.unique(col.astype(float))
        data[colname] = float(sum(unique_vals))

    s = pd.Series(data, dtype=float)
    if not s.empty:
        ordered = sorted(s.index, key=_qkey if quarterly else _year_key)
        s = s.reindex(ordered)
    return s, list(dict.fromkeys(str(x) for x in subset.index))


def _yoy(series: pd.Series) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    if series.empty:
        return out
    lookup = {str(k): float(v) for k, v in series.items() if pd.notna(v)}
    for period, current in lookup.items():
        m = re.fullmatch(r"(\d{4})Q([1-4])", period)
        if not m:
            continue
        prev = f"{int(m.group(1))-1}Q{m.group(2)}"
        old = lookup.get(prev)
        if old is None or old == 0:
            out[period] = None
        else:
            out[period] = (current / old - 1.0) * 100.0
    return out


def _ratio(num: pd.Series, den: pd.Series, mult: float = 1.0) -> pd.Series:
    if num.empty or den.empty:
        return pd.Series(dtype=float)
    idx = sorted(set(num.index) & set(den.index), key=_qkey)
    data = {}
    for k in idx:
        a = float(num[k])
        b = float(den[k])
        if b != 0 and math.isfinite(a) and math.isfinite(b):
            data[k] = a / b * mult
    return pd.Series(data, dtype=float)


def _discrete_from_ytd(series: pd.Series) -> pd.Series:
    """Convert Q1/Q2/Q3/FY cumulative flow data to discrete quarters."""
    if series.empty:
        return series
    data = {str(k): float(v) for k, v in series.items() if pd.notna(v)}
    out: dict[str, float] = {}
    years = sorted({_qkey(k)[0] for k in data if _qkey(k)[0]})
    for year in years:
        previous = None
        for q in range(1, 5):
            key = f"{year}Q{q}"
            if key not in data:
                continue
            value = data[key]
            if q == 1:
                out[key] = value
            elif previous is not None:
                out[key] = value - previous
            previous = value
    return pd.Series(out, dtype=float).sort_index(key=lambda idx: idx.map(_qkey))


def _value_at(series: pd.Series, key) -> float | None:
    try:
        if series is None or series.empty or key not in series.index:
            return None
        value=series[key]
        if isinstance(value,pd.Series):
            value=value.iloc[-1]
        if value is None or pd.isna(value):
            return None
        value=float(value)
        return value if math.isfinite(value) else None
    except Exception:
        return None

def _latest(series: pd.Series) -> float | None:
    if series is None or series.empty:
        return None
    return float(series.iloc[-1])


def _same_quarter_year_ago(series: pd.Series) -> tuple[float | None, float | None]:
    if series is None or series.empty:
        return None, None
    key = str(series.index[-1])
    m = re.fullmatch(r"(\d{4})Q([1-4])", key)
    if not m:
        return _latest(series), None
    prior = f"{int(m.group(1))-1}Q{m.group(2)}"
    return _latest(series), float(series[prior]) if prior in series.index else None


def _pct_change(now: float | None, old: float | None) -> float | None:
    if now is None or old is None or old == 0:
        return None
    return (now / old - 1.0) * 100.0


def _pp_change(now: float | None, old: float | None) -> float | None:
    if now is None or old is None:
        return None
    return now - old


def _consecutive_quarters(series: pd.Series, count: int) -> list[str] | None:
    """Only accept actual contiguous fiscal quarters, never sparse last-N rows."""
    if series is None or series.empty:
        return None
    available = {str(k) for k, v in series.items() if pd.notna(v) and _qkey(k) != (0, 0)}
    if not available:
        return None
    year, quarter = max((_qkey(k) for k in available))
    keys = []
    for _ in range(count):
        key = f"{year}Q{quarter}"
        if key not in available:
            return None
        keys.append(key)
        quarter -= 1
        if quarter == 0:
            year, quarter = year - 1, 4
    return keys


def _ttm(discrete: pd.Series) -> float | None:
    keys = _consecutive_quarters(discrete, 4)
    return float(sum(float(discrete[k]) for k in keys)) if keys else None


def _ttm_yoy(discrete: pd.Series) -> float | None:
    keys = _consecutive_quarters(discrete, 8)
    if not keys:
        return None
    current = sum(float(discrete[k]) for k in keys[:4])
    previous = sum(float(discrete[k]) for k in keys[4:])
    if previous == 0:
        return None
    return (current / previous - 1.0) * 100.0


def _positive_count_last4(yoy_map: dict[str, float | None]) -> int | None:
    vals = [v for _, v in sorted(yoy_map.items(), key=lambda kv: _qkey(kv[0]), reverse=True) if v is not None][:4]
    return sum(v > 0 for v in vals) if vals else None


def _avg_last4(yoy_map: dict[str, float | None]) -> float | None:
    vals = [v for _, v in sorted(yoy_map.items(), key=lambda kv: _qkey(kv[0]), reverse=True) if v is not None][:4]
    return sum(vals) / len(vals) if vals else None


def _cagr(series: pd.Series, periods: int = 3) -> float | None:
    s = series.dropna() if series is not None else pd.Series(dtype=float)
    if len(s) < periods + 1:
        return None
    latest = float(s.iloc[-1])
    old = float(s.iloc[-periods - 1])
    if latest <= 0 or old <= 0:
        return None
    return ((latest / old) ** (1.0 / periods) - 1.0) * 100.0


def _net_debt_if_complete(debt, cash, investments):
    """Conservative statement net debt: missing balance components are unknown, not zero."""
    if any(v is None or not math.isfinite(float(v)) for v in (debt, cash, investments)):
        return None
    return float(debt) - float(cash) - float(investments)


def _average_positive_balance(current, prior):
    """TTM returns require two valid balance observations; no last-balance substitute."""
    if any(v is None or not math.isfinite(float(v)) for v in (current, prior)):
        return None
    mean = (float(current) + float(prior)) / 2.0
    return mean if mean > 0 else None


def _safe_ratio(a: float | None, b: float | None, mult: float = 1.0) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b * mult


def _fmt(v: float | None, suffix: str = "", digits: int = 1) -> str:
    return "N/A" if v is None else f"{v:.{digits}f}{suffix}"


def _format_large(v: float | None) -> str:
    if v is None:
        return "N/A"
    a = abs(v)
    if a >= 1e12:
        return f"{v/1e12:.2f} trilyon TL"
    if a >= 1e9:
        return f"{v/1e9:.2f} milyar TL"
    if a >= 1e6:
        return f"{v/1e6:.1f} milyon TL"
    return f"{v:,.0f} TL"


def _build_commentary(summary: dict[str, Any], profile: str) -> dict[str, Any]:
    strengths: list[str] = []
    risks: list[str] = []
    watch: list[str] = []
    paragraphs: list[str] = []

    latest_period = summary.get("latest_period")
    rev_yoy = summary.get("revenue_yoy")
    ni_yoy = summary.get("net_income_yoy")
    rev_pos = summary.get("revenue_positive_4q")
    ni_pos = summary.get("profit_positive_4q")

    if profile == "Banka":
        if ni_yoy is not None:
            paragraphs.append(
                f"{latest_period or 'Son dönem'} itibarıyla net kâr yıllık bazda {_fmt(ni_yoy,'%')} değişti."
            )
            (strengths if ni_yoy > 15 else risks if ni_yoy < 0 else watch).append(
                f"Net kâr yıllık değişimi {_fmt(ni_yoy,'%')}."
            )
        eq_yoy = summary.get("equity_yoy")
        assets_yoy = summary.get("assets_yoy")
        loans_yoy = summary.get("loans_yoy")
        dep_yoy = summary.get("deposits_yoy")
        nii_yoy = summary.get("net_interest_income_yoy")
        fee_yoy = summary.get("fee_income_yoy")
        eq_assets = summary.get("equity_to_assets")

        if eq_yoy is not None or assets_yoy is not None:
            paragraphs.append(
                f"Özkaynak büyümesi {_fmt(eq_yoy,'%')}, aktif büyümesi {_fmt(assets_yoy,'%')}; "
                "banka bilançosu sanayi şirketi borç/nakit metrikleriyle değerlendirilmedi."
            )
        if loans_yoy is not None or dep_yoy is not None:
            paragraphs.append(
                f"Kredi büyümesi {_fmt(loans_yoy,'%')}, mevduat büyümesi {_fmt(dep_yoy,'%')}."
            )
            if loans_yoy is not None and dep_yoy is not None:
                gap=loans_yoy-dep_yoy
                if gap>10:
                    watch.append(
                        f"Kredi büyümesi mevduat büyümesini {gap:.1f} puan aşıyor; fonlama yapısı ve kredi/mevduat dengesi izlenmeli."
                    )
                elif gap<-10:
                    strengths.append(
                        f"Mevduat büyümesi kredi büyümesinin {abs(gap):.1f} puan üzerinde; fonlama tabanı görece destekleyici."
                    )
        if nii_yoy is not None:
            (strengths if nii_yoy>15 else risks if nii_yoy<0 else watch).append(
                f"Net faiz geliri yıllık {_fmt(nii_yoy,'%')} değişti."
            )
        if fee_yoy is not None:
            (strengths if fee_yoy>15 else risks if fee_yoy<0 else watch).append(
                f"Net ücret/komisyon geliri yıllık {_fmt(fee_yoy,'%')} değişti."
            )
        if eq_assets is not None:
            (strengths if eq_assets>=10 else risks if eq_assets<7 else watch).append(
                f"Özkaynak/aktif oranı {_fmt(eq_assets,'%')}."
            )
        return {"paragraphs": paragraphs, "strengths": strengths, "risks": risks, "watch": watch}

    if profile in {"Holding","Yatırım Ortaklığı"}:
        eq_yoy=summary.get("equity_yoy")
        assets_yoy=summary.get("assets_yoy")
        if ni_yoy is not None:
            paragraphs.append(
                f"{latest_period or 'Son dönem'} konsolide net kârı yıllık {_fmt(ni_yoy,'%')} değişti; "
                "bu değişim iştirak ve portföy değer hareketlerinden etkilenebileceği için operasyonel şirket kârı gibi yorumlanmadı."
            )
        if eq_yoy is not None or assets_yoy is not None:
            paragraphs.append(
                f"Özkaynak büyümesi {_fmt(eq_yoy,'%')}, aktif büyümesi {_fmt(assets_yoy,'%')}."
            )
        net_debt=summary.get("net_debt")
        if net_debt is not None:
            watch.append(
                f"Konsolide net borç {_format_large(net_debt)}; holding/portföy değerlemesinde bunun holding-seviye "
                "net nakit/borçtan farklı olabileceği dikkate alınmalı."
            )
        if profile=="Holding":
            paragraphs.append(
                "Holdinglerde konsolide ciro, marj ve FCF ana kalite skoru olarak kullanılmadı; iştirak bazlı NAD, "
                "holding seviyesindeki net nakit/borç ve holding iskontosu esas değerleme çerçevesidir."
            )
        else:
            paragraphs.append(
                "Yatırım ortaklıklarında portföy/NAV ve piyasa değerine iskonto/prim ana referanstır; "
                "dönem kârı ve konsolide oranlar portföy değer değişimleri nedeniyle karar skoruna dönüştürülmedi."
            )
        return {"paragraphs": paragraphs, "strengths": strengths, "risks": risks, "watch": watch}

    if profile in {"Sigorta","Finansal"}:
        if ni_yoy is not None:
            paragraphs.append(
                f"{latest_period or 'Son dönem'} net kârı yıllık {_fmt(ni_yoy,'%')} değişti."
            )
            (strengths if ni_yoy>15 else risks if ni_yoy<0 else watch).append(
                f"Net kâr yıllık değişimi {_fmt(ni_yoy,'%')}."
            )
        eq_yoy=summary.get("equity_yoy")
        assets_yoy=summary.get("assets_yoy")
        if eq_yoy is not None or assets_yoy is not None:
            paragraphs.append(
                f"Özkaynak büyümesi {_fmt(eq_yoy,'%')}, aktif büyümesi {_fmt(assets_yoy,'%')}. "
                f"{profile} profili sanayi şirketi FAVÖK/FCF ve işletme sermayesi metrikleriyle zorlanmadı."
            )
        eq_assets=summary.get("equity_to_assets")
        if eq_assets is not None:
            if profile=="Sigorta":
                watch.append(
                    f"Özkaynak/aktif oranı {_fmt(eq_assets,'%')} yalnız bilanço bilgisi olarak gösteriliyor; "
                    "sigorta sermaye yeterliliği/solvency oranının yerine kullanılmadı."
                )
            else:
                (strengths if eq_assets>=10 else risks if eq_assets<7 else watch).append(
                    f"Özkaynak/aktif oranı {_fmt(eq_assets,'%')}."
                )
        return {"paragraphs": paragraphs, "strengths": strengths, "risks": risks, "watch": watch}

    if rev_yoy is not None or ni_yoy is not None:
        paragraphs.append(
            f"{latest_period or 'Son dönem'} finansallarında ciro yıllık {_fmt(rev_yoy,'%')}, "
            f"net kâr {_fmt(ni_yoy,'%')} değişim gösterdi."
        )

    if rev_pos is not None:
        text = f"Son dört rapor döneminin {rev_pos}/4'ünde ciro büyümesi pozitif."
        (strengths if rev_pos >= 3 else risks if rev_pos <= 1 else watch).append(text)
    if ni_pos is not None:
        text = f"Son dört rapor döneminin {ni_pos}/4'ünde net kâr büyümesi pozitif."
        (strengths if ni_pos >= 3 else risks if ni_pos <= 1 else watch).append(text)

    if rev_yoy is not None and ni_yoy is not None:
        gap = ni_yoy - rev_yoy
        if gap > 20:
            paragraphs.append(
                "Net kâr büyümesi ciro büyümesini belirgin aşıyor; büyümenin yalnız hacimden değil, "
                "marj/operasyonel kaldıraç veya dönemsel kalemlerden de beslendiği görülüyor."
            )
        elif gap < -20:
            risks.append(
                "Ciro büyümesi net kâra aynı ölçüde taşınmıyor; marj baskısı veya maliyet/finansman etkisi izlenmeli."
            )

    net_margin = summary.get("net_margin")
    net_margin_delta = summary.get("net_margin_yoy_pp")
    op_margin_delta = summary.get("operating_margin_yoy_pp")
    if net_margin is not None:
        paragraphs.append(
            f"Net kâr marjı {_fmt(net_margin,'%')} seviyesinde; geçen yılın aynı dönemine göre "
            f"{_fmt(net_margin_delta,' puan')} değişim var."
        )
    if op_margin_delta is not None:
        (strengths if op_margin_delta > 1 else risks if op_margin_delta < -1 else watch).append(
            f"Faaliyet marjı yıllık {op_margin_delta:+.1f} puan değişti."
        )
    if net_margin_delta is not None and op_margin_delta is not None and net_margin_delta > 2 and op_margin_delta < -2:
        risks.append(
            "Net marj genişlerken faaliyet marjı daralıyor; kâr iyileşmesinin çekirdek operasyon dışı "
            "kalemlerden de destek aldığı ve bu katkının sürdürülebilirliğinin ayrıca test edilmesi gerektiği görülüyor."
        )

    rev_cagr = summary.get("revenue_cagr_3y")
    ni_cagr = summary.get("net_income_cagr_3y")
    if rev_cagr is not None or ni_cagr is not None:
        paragraphs.append(
            f"Yıllık finansallarda yaklaşık 3 yıllık ciro CAGR {_fmt(rev_cagr,'%')}, "
            f"net kâr CAGR {_fmt(ni_cagr,'%')}."
        )

    conv = summary.get("cash_conversion")
    fcf_margin = summary.get("fcf_margin")
    if conv is not None:
        if conv >= 1:
            strengths.append(f"TTM faaliyet nakit akışı/net kâr dönüşümü {conv:.2f}x; muhasebe kârı nakitle güçlü destekleniyor.")
        elif conv < 0.6:
            risks.append(f"TTM faaliyet nakit akışı/net kâr dönüşümü {conv:.2f}x; kârın nakde dönüşümü zayıf.")
        else:
            watch.append(f"TTM faaliyet nakit akışı/net kâr dönüşümü {conv:.2f}x.")
    capex_to_ocf=summary.get("capex_to_ocf")
    if fcf_margin is not None:
        if profile in {"GYO","Holding","Yatırım Ortaklığı"}:
            watch.append(
                f"TTM serbest nakit akışı marjı {_fmt(fcf_margin,'%')}. {profile} yapısında iştirak/portföy/"
                "proje yatırımları ve sınıflandırma farkları nakit akışını dönemsel olarak bozabildiğinden bu oran "
                "sanayi şirketlerindeki gibi tek başına kalite cezası olarak yorumlanmadı."
            )
        else:
            (strengths if fcf_margin >= 8 else risks if fcf_margin < 0 else watch).append(
                f"TTM serbest nakit akışı marjı {_fmt(fcf_margin,'%')}."
            )
    if conv is not None and conv >= 1 and fcf_margin is not None and fcf_margin < 0 and capex_to_ocf is not None:
        watch.append(
            f"Faaliyet nakit üretimi güçlü olsa da yatırım harcamaları OCF'nin {capex_to_ocf:.2f} katına ulaşıyor; "
            "negatif FCF'nin tahsilat zayıflığından mı yoksa büyüme amaçlı yatırım yoğunluğundan mı kaynaklandığı ayrıştırılmalı."
        )

    net_debt = summary.get("net_debt")
    net_debt_yoy = summary.get("net_debt_yoy")
    if net_debt is not None:
        paragraphs.append(
            f"Son bilanço net borç pozisyonu {_format_large(net_debt)}"
            + (f"; yıllık değişim {_fmt(net_debt_yoy,'%')}." if net_debt_yoy is not None else ".")
        )
        if net_debt < 0:
            strengths.append("Şirket net nakit pozisyonunda.")
        elif net_debt_yoy is not None and net_debt_yoy > 30:
            risks.append("Net borç yıllık bazda belirgin artmış.")
        elif net_debt_yoy is not None and net_debt_yoy < -20:
            strengths.append("Net borç yıllık bazda gerilemiş.")

    current_ratio = summary.get("current_ratio")
    if current_ratio is not None:
        (strengths if current_ratio >= 1.5 else risks if current_ratio < 1 else watch).append(
            f"Cari oran {current_ratio:.2f}x."
        )

    if profile=="GYO":
        bed=summary.get("book_equity_discount")
        if bed is not None:
            paragraphs.append(
                f"Piyasa değeri defter özkaynağına göre yaklaşık %{bed:.1f} iskontolu görünmektedir; "
                "bu gösterge NAD iskontosu değildir ve portföy ekspertiz değerinin yerini tutmaz."
            )
        paragraphs.append(
            "GYO/proje geliştirici şirketlerde satış ve kârlar teslim takvimine bağlı olarak dönemler arasında "
            "yüksek oynaklık gösterebilir; bu nedenle tek çeyrek büyüme yerine NAD, proje stoğu, teslimatlar, "
            "ön satışlar ve finansman ihtiyacı birlikte okunmalıdır."
        )
    elif profile=="Holding":
        paragraphs.append(
            "Holdinglerde konsolide gelir tablosu iştirak yapısını tam yansıtmayabilir; değerleme için iştirak bazlı "
            "NAD, holding seviyesindeki net nakit/borç ve iskonto birlikte analiz edilmelidir."
        )
    elif profile=="Yatırım Ortaklığı":
        paragraphs.append(
            "Yatırım ortaklıklarında dönem kârı portföy değer değişimlerinden güçlü biçimde etkilenebilir; "
            "portföy/NAV ve piyasa değerine iskonto/prim ana referans olmalıdır."
        )
    elif profile=="Finansal":
        paragraphs.append(
            "Banka dışı finansal kuruluşlarda sanayi şirketlerine özgü FAVÖK/FCF ve işletme sermayesi oranları "
            "tek başına kullanılmamalı; özkaynak verimliliği, kârlılık ve fonlama yapısı önceliklidir."
        )

    return {"paragraphs": paragraphs, "strengths": strengths, "risks": risks, "watch": watch}


def build_historical_analysis(
    symbol: str,
    profile: str,
    report_dir: Path | None = None,
    quarterly_periods: int = 12,
    annual_periods: int = 5,
    load_market_info: bool = True,
) -> dict[str, Any]:
    """Fetch and analyze selected-stock historical financial statements.

    Cross-sectional universe comparisons remain outside this module. This module
    intentionally performs heavier statement calls only for the selected company.
    """
    result: dict[str, Any] = {
        "source": "borsapy / İş Yatırım / KAP",
        "profile": profile,
        "rows_found": {},
        "summary": {},
        "quarterly": [],
        "commentary": {"paragraphs": [], "strengths": [], "risks": [], "watch": []},
        "data_quality": {},
        "market_source_available": False,
    }

    try:
        stock = bp.Ticker(symbol)

        # Quote/KAP metadata is useful but must never block financial-statement
        # analysis. TradingView quote endpoints can be temporarily unavailable
        # while İş Yatırım financial statements are still accessible.
        info = {}
        if load_market_info:
            try:
                info_obj = _retry_call(lambda: stock.info, attempts=2, base_delay=0.5)
                info = info_obj.todict() if hasattr(info_obj, "todict") else dict(info_obj)
                result["market_source_available"] = True
            except Exception as exc:
                result["metadata_warning"] = str(exc)

        result["kap"] = {
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "website": info.get("website"),
            "business_summary": info.get("longBusinessSummary"),
        }
        result["market"] = {
            "market_cap": info.get("marketCap"),
            "pe": info.get("trailingPE"),
            "pb": info.get("priceToBook"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "net_debt": info.get("netDebt"),
            "foreign_ratio": info.get("foreignRatio"),
            "dividend_yield": info.get("dividendYield"),
        }

        # İş Yatırım exposes two statement schemas. Banks, insurers and
        # non-bank financial institutions are generally reported in UFRS; some
        # symbols/providers can still be available only in XI_29. Try the
        # economically appropriate schema first and fall back instead of failing
        # the whole report.
        financial_profiles={"Banka","Sigorta","Finansal"}
        group_candidates=["UFRS","XI_29"] if profile in financial_profiles else ["XI_29","UFRS"]
        qn=max(4,int(quarterly_periods))
        bs_q=pd.DataFrame()
        inc_q=pd.DataFrame()
        group=None
        group_errors=[]
        for candidate in group_candidates:
            try:
                bs_try=_retry_call(
                    lambda candidate=candidate: stock.get_balance_sheet(
                        quarterly=True, financial_group=candidate, last_n=qn
                    ),
                    attempts=2, base_delay=0.7,
                )
                inc_try=_retry_call(
                    lambda candidate=candidate: stock.get_income_stmt(
                        quarterly=True, financial_group=candidate, last_n=qn
                    ),
                    attempts=2, base_delay=0.7,
                )
                if bs_try is not None and inc_try is not None and not bs_try.empty and not inc_try.empty:
                    bs_q=bs_try
                    inc_q=inc_try
                    group=candidate
                    break
                group_errors.append(f"{candidate}: empty")
            except Exception as exc:
                group_errors.append(f"{candidate}: {exc}")

        if group is None:
            raise RuntimeError(
                "No financial data available; tried "
                + " | ".join(group_errors)
            )

        result["financial_group_used"]=group
        result["financial_group_fallback_used"]=(group != group_candidates[0])

        inc_a = pd.DataFrame()
        bs_a = pd.DataFrame()
        if annual_periods and annual_periods > 0:
            try:
                inc_a = _retry_call(
                    lambda: stock.get_income_stmt(
                        quarterly=False,
                        financial_group=group,
                        last_n=max(4,int(annual_periods)),
                    ),
                    attempts=2, base_delay=0.7,
                )
            except Exception:
                inc_a = pd.DataFrame()
            try:
                bs_a = _retry_call(
                    lambda: stock.get_balance_sheet(
                        quarterly=False,
                        financial_group=group,
                        last_n=max(4,int(annual_periods)),
                    ),
                    attempts=2, base_delay=0.7,
                )
            except Exception:
                bs_a = pd.DataFrame()

        cf_q = pd.DataFrame()
        # UFRS financial institutions do not expose a comparable industrial
        # cash-flow statement in BorsaPy. Do not turn that absence into a failure.
        if group=="XI_29" and profile not in financial_profiles:
            try:
                cf_q = _retry_call(
                    lambda: stock.get_cashflow(
                        quarterly=True, financial_group=group, last_n=qn
                    ),
                    attempts=2, base_delay=0.7,
                )
            except Exception:
                cf_q = pd.DataFrame()

        if report_dir:
            report_dir.mkdir(parents=True, exist_ok=True)
            bs_q.to_csv(report_dir / f"{symbol}_balance_sheet_{qn}q.csv", encoding="utf-8-sig")
            inc_q.to_csv(report_dir / f"{symbol}_income_stmt_{qn}q.csv", encoding="utf-8-sig")
            if not cf_q.empty:
                cf_q.to_csv(report_dir / f"{symbol}_cashflow_{qn}q.csv", encoding="utf-8-sig")
            if not inc_a.empty:
                inc_a.to_csv(report_dir / f"{symbol}_income_stmt_annual_{max(4,int(annual_periods))}y.csv", encoding="utf-8-sig")
            if not bs_a.empty:
                bs_a.to_csv(report_dir / f"{symbol}_balance_sheet_annual_{max(4,int(annual_periods))}y.csv", encoding="utf-8-sig")

        found: dict[str, Any] = {}

        # Income statement
        income: dict[str, pd.Series] = {}
        for key, candidates in INCOME_ROWS.items():
            s, row = _find_series(inc_q, candidates, quarterly=True)
            income[key] = s
            if row:
                found[key] = row

        # Balance sheet
        balance: dict[str, pd.Series] = {}
        for key, candidates in BALANCE_ROWS.items():
            excludes = ["ana ortakliga ait"] if key == "equity" else None
            s, row = _find_series(bs_q, candidates, quarterly=True, excludes=excludes)
            if s.empty and key == "equity":
                s, row = _find_series(bs_q, candidates, quarterly=True)
            balance[key] = s
            if row:
                found[key] = row

        debt, debt_rows = _sum_matching_rows(bs_q, FINANCIAL_DEBT_KEYWORDS, quarterly=True)
        balance["financial_debt"] = debt
        if debt_rows:
            found["financial_debt"] = debt_rows

        # Explicit parent equity. Consolidated total equity can include
        # non-controlling interests and must not silently substitute for it.
        parent_equity_series,parent_equity_row=_find_series(
            bs_q,PARENT_EQUITY_ROWS,quarterly=True
        )
        if parent_equity_row:
            found["parent_equity"]=parent_equity_row
        # Cash flow
        cashflow: dict[str, pd.Series] = {}
        if not cf_q.empty:
            for key, candidates in CASHFLOW_ROWS.items():
                s, row = _find_series(cf_q, candidates, quarterly=True)
                cashflow[key] = s
                if row:
                    found[key] = row

        # Annual series for the company's own historical trend.
        annual_rev, annual_rev_row = _find_series(inc_a, INCOME_ROWS["revenue"], quarterly=False)
        annual_ni, annual_ni_row = _find_series(inc_a, INCOME_ROWS["net_income"], quarterly=False)
        annual_eq, annual_eq_row = _find_series(bs_a, BALANCE_ROWS["equity"], quarterly=False)
        annual_assets, annual_assets_row = _find_series(bs_a, BALANCE_ROWS["total_assets"], quarterly=False)
        if annual_rev_row:
            found["annual_revenue"] = annual_rev_row
        if annual_ni_row:
            found["annual_net_income"] = annual_ni_row
        if annual_eq_row:
            found["annual_equity"] = annual_eq_row
        if annual_assets_row:
            found["annual_total_assets"] = annual_assets_row

        result["rows_found"] = found

        # Growth and margins (YTD values vs same period last year is valid).
        revenue = income["revenue"]
        net_income = income["net_income"]
        gross_profit = income["gross_profit"]
        operating_profit = income["operating_profit"]

        revenue_yoy = _yoy(revenue)
        profit_yoy = _yoy(net_income)
        net_margin = _ratio(net_income, revenue, 100.0)
        gross_margin = _ratio(gross_profit, revenue, 100.0)
        operating_margin = _ratio(operating_profit, revenue, 100.0)

        # Discrete quarters for TTM flow calculation.
        revenue_d = _discrete_from_ytd(revenue)
        net_income_d = _discrete_from_ytd(net_income)
        gross_profit_d = _discrete_from_ytd(gross_profit)
        operating_profit_d = _discrete_from_ytd(operating_profit)
        ocf_d = _discrete_from_ytd(cashflow.get("operating_cash_flow", pd.Series(dtype=float)))
        capex_d = _discrete_from_ytd(cashflow.get("capex", pd.Series(dtype=float)))
        fcf_d = _discrete_from_ytd(cashflow.get("free_cash_flow", pd.Series(dtype=float)))

        ttm_rev = _ttm(revenue_d)
        ttm_ni = _ttm(net_income_d)
        ttm_gross_profit = _ttm(gross_profit_d)
        ttm_operating_profit = _ttm(operating_profit_d)
        ttm_ocf = _ttm(ocf_d)
        ttm_capex = None
        capex_keys = _consecutive_quarters(capex_d, 4)
        if capex_keys:
            ttm_capex = float(sum(abs(float(capex_d[k])) for k in capex_keys))

        # Prefer the provider's explicit "Serbest Nakit Akım" row. If missing,
        # reconstruct FCF as operating cash flow minus absolute capex.
        ttm_fcf = _ttm(fcf_d)
        if ttm_fcf is None and ttm_ocf is not None and ttm_capex is not None:
            ttm_fcf = ttm_ocf - ttm_capex

        latest_periods = sorted(
            set(revenue.index) | set(net_income.index) | set(balance.get("total_assets", pd.Series(dtype=float)).index),
            key=_qkey,
        )
        latest_period = str(latest_periods[-1]) if latest_periods else None

        rev_yoy_latest = revenue_yoy.get(latest_period) if latest_period else None
        ni_yoy_latest = profit_yoy.get(latest_period) if latest_period else None

        nm_now, nm_old = _same_quarter_year_ago(net_margin)
        gm_now, gm_old = _same_quarter_year_ago(gross_margin)
        om_now, om_old = _same_quarter_year_ago(operating_margin)

        cash_now, cash_old = _same_quarter_year_ago(balance.get("cash", pd.Series(dtype=float)))
        debt_now, debt_old = _same_quarter_year_ago(balance.get("financial_debt", pd.Series(dtype=float)))
        fininv_now, fininv_old = _same_quarter_year_ago(balance.get("financial_investments", pd.Series(dtype=float)))
        equity_now, equity_old = _same_quarter_year_ago(balance.get("equity", pd.Series(dtype=float)))
        parent_equity_now, parent_equity_old = _same_quarter_year_ago(parent_equity_series)
        assets_now, assets_old = _same_quarter_year_ago(balance.get("total_assets", pd.Series(dtype=float)))
        ca_now, ca_old = _same_quarter_year_ago(balance.get("current_assets", pd.Series(dtype=float)))
        cl_now, cl_old = _same_quarter_year_ago(balance.get("current_liabilities", pd.Series(dtype=float)))

        # İş Yatırım's company-card net debt includes other financial liabilities
        # and deducts cash/financial investments. This is materially important for
        # project-heavy GYOs such as EKGYO.
        net_debt_now = _net_debt_if_complete(debt_now, cash_now, fininv_now)
        net_debt_old = _net_debt_if_complete(debt_old, cash_old, fininv_old)
        current_ratio_now = _safe_ratio(ca_now, cl_now)
        current_ratio_old = _safe_ratio(ca_old, cl_old)

        avg_equity_ttm = _average_positive_balance(equity_now, equity_old)
        avg_assets_ttm = _average_positive_balance(assets_now, assets_old)

        # Own-history metrics. ROE/ROA use end-period balances as a
        # consistent approximation because average balances are not guaranteed
        # across all provider schemas.
        annual_history=[]
        annual_years=sorted(
            set(str(x) for x in annual_rev.index)
            | set(str(x) for x in annual_ni.index)
            | set(str(x) for x in annual_eq.index)
            | set(str(x) for x in annual_assets.index),
            key=lambda x: int(x) if str(x).isdigit() else 0,
        )
        for year in annual_years:
            rev_a=_value_at(annual_rev,year)
            ni_a=_value_at(annual_ni,year)
            eq_a=_value_at(annual_eq,year)
            assets_a=_value_at(annual_assets,year)
            annual_history.append({
                "year":year,
                "revenue":rev_a,
                "net_income":ni_a,
                "equity":eq_a,
                "assets":assets_a,
                "net_margin":_safe_ratio(ni_a,rev_a,100.0),
                "roe_proxy":_safe_ratio(ni_a,eq_a,100.0),
                "roa_proxy":_safe_ratio(ni_a,assets_a,100.0),
            })

        summary = {
            "latest_period": latest_period,
            "revenue_yoy": rev_yoy_latest,
            "net_income_yoy": ni_yoy_latest,
            "revenue_positive_4q": _positive_count_last4(revenue_yoy),
            "profit_positive_4q": _positive_count_last4(profit_yoy),
            "revenue_yoy_avg_4q": _avg_last4(revenue_yoy),
            "profit_yoy_avg_4q": _avg_last4(profit_yoy),
            "net_margin": nm_now,
            "net_margin_yoy_pp": _pp_change(nm_now, nm_old),
            "gross_margin": gm_now,
            "gross_margin_yoy_pp": _pp_change(gm_now, gm_old),
            "operating_margin": om_now,
            "operating_margin_yoy_pp": _pp_change(om_now, om_old),
            "revenue_cagr_3y": _cagr(annual_rev, 3),
            "net_income_cagr_3y": _cagr(annual_ni, 3),
            "equity_cagr_3y": _cagr(annual_eq, 3),
            "assets_cagr_3y": _cagr(annual_assets, 3),
            "annual_self_history": annual_history,
            "ttm_revenue": ttm_rev,
            "ttm_net_income": ttm_ni,
            "revenue_ttm_yoy": _ttm_yoy(revenue_d),
            "net_income_ttm_yoy": _ttm_yoy(net_income_d),
            "ttm_gross_margin": _safe_ratio(ttm_gross_profit, ttm_rev, 100.0),
            "ttm_operating_margin": _safe_ratio(ttm_operating_profit, ttm_rev, 100.0),
            "ttm_net_margin": _safe_ratio(ttm_ni, ttm_rev, 100.0),
            "ttm_roe_proxy": _safe_ratio(ttm_ni, avg_equity_ttm, 100.0),
            "ttm_roa_proxy": _safe_ratio(ttm_ni, avg_assets_ttm, 100.0),
            "ttm_operating_cash_flow": ttm_ocf,
            "ttm_capex": ttm_capex,
            "ttm_free_cash_flow": ttm_fcf,
            "cash_conversion": _safe_ratio(ttm_ocf, ttm_ni) if ttm_ni is not None and ttm_ni > 0 else None,
            "capex_to_ocf": _safe_ratio(ttm_capex, ttm_ocf) if ttm_ocf is not None and ttm_ocf > 0 else None,
            "fcf_margin": _safe_ratio(ttm_fcf, ttm_rev, 100.0),
            "cash": cash_now,
            "cash_yoy": _pct_change(cash_now, cash_old),
            "financial_debt": debt_now,
            "financial_debt_yoy": _pct_change(debt_now, debt_old),
            "financial_investments": fininv_now,
            "net_debt_statement": net_debt_now,
            "net_debt_provider": result.get("market",{}).get("net_debt"),
            "net_debt": (
                result.get("market",{}).get("net_debt")
                if result.get("market",{}).get("net_debt") is not None
                else net_debt_now
            ),
            "net_debt_yoy": _pct_change(net_debt_now, net_debt_old)
                if net_debt_old is not None and net_debt_old > 0 else None,
            "equity": equity_now,
            "parent_equity": parent_equity_now,
            "parent_equity_previous": parent_equity_old,
            "equity_yoy": _pct_change(equity_now, equity_old),
            "total_assets": assets_now,
            "assets_yoy": _pct_change(assets_now, assets_old),
            "current_ratio": current_ratio_now,
            "current_ratio_yoy_change": _pp_change(current_ratio_now, current_ratio_old),
        }

        # Bank-specific operating / balance growth metrics.
        loans_now, loans_old = _same_quarter_year_ago(balance.get("loans", pd.Series(dtype=float)))
        dep_now, dep_old = _same_quarter_year_ago(balance.get("deposits", pd.Series(dtype=float)))
        nii_now, nii_old = _same_quarter_year_ago(income.get("net_interest_income", pd.Series(dtype=float)))
        fee_now, fee_old = _same_quarter_year_ago(income.get("fee_income", pd.Series(dtype=float)))

        summary["loans_yoy"] = _pct_change(loans_now, loans_old)
        summary["deposits_yoy"] = _pct_change(dep_now, dep_old)
        summary["net_interest_income_yoy"] = _pct_change(nii_now, nii_old)
        summary["fee_income_yoy"] = _pct_change(fee_now, fee_old)
        summary["equity_to_assets"] = _safe_ratio(equity_now, assets_now, 100.0)
        mcap = result.get("market",{}).get("market_cap")
        summary["book_equity_discount"] = (
            (1.0 - (mcap / equity_now)) * 100.0
            if mcap is not None and equity_now is not None and equity_now > 0 else None
        )
        provider_nd = result.get("market",{}).get("net_debt")
        summary["net_debt_source_gap_pct"] = (
            ((net_debt_now / provider_nd) - 1.0) * 100.0
            if provider_nd not in (None,0) and net_debt_now is not None else None
        )

        result["summary"] = summary
        result["special_profile_analysis"] = build_special_profile_analysis(
            symbol=symbol,
            profile=profile,
            inc_q=inc_q,
            bs_q=bs_q,
            market=result.get("market",{}),
            summary=summary,
        )

        # Detail table: newest first, maximum 8 periods for report readability.
        if profile == "Banka":
            nii = income.get("net_interest_income", pd.Series(dtype=float))
            fee = income.get("fee_income", pd.Series(dtype=float))
            periods = sorted(
                set(net_income.index) | set(nii.index) | set(fee.index) |
                set(balance.get("loans", pd.Series(dtype=float)).index) |
                set(balance.get("deposits", pd.Series(dtype=float)).index),
                key=_qkey,
                reverse=True,
            )[:8]
        else:
            periods = sorted(
                set(revenue.index) | set(net_income.index) | set(net_margin.index) |
                set(operating_margin.index) | set(ocf_d.index),
                key=_qkey,
                reverse=True,
            )[:8]

        rows = []
        for period in periods:
            row={
                "period": str(period),
                "net_income": float(net_income[period]) if period in net_income.index else None,
                "net_income_yoy": profit_yoy.get(str(period)),
            }
            if profile == "Banka":
                nii=income.get("net_interest_income", pd.Series(dtype=float))
                fee=income.get("fee_income", pd.Series(dtype=float))
                loans=balance.get("loans", pd.Series(dtype=float))
                deposits=balance.get("deposits", pd.Series(dtype=float))
                row.update({
                    "net_interest_income": float(nii[period]) if period in nii.index else None,
                    "fee_income": float(fee[period]) if period in fee.index else None,
                    "loans": float(loans[period]) if period in loans.index else None,
                    "deposits": float(deposits[period]) if period in deposits.index else None,
                })
            else:
                row.update({
                    "revenue": float(revenue[period]) if period in revenue.index else None,
                    "revenue_yoy": revenue_yoy.get(str(period)),
                    "gross_margin": float(gross_margin[period]) if period in gross_margin.index else None,
                    "operating_margin": float(operating_margin[period]) if period in operating_margin.index else None,
                    "net_margin": float(net_margin[period]) if period in net_margin.index else None,
                    "operating_cash_flow_discrete": float(ocf_d[period]) if period in ocf_d.index else None,
                })
            rows.append(row)
        result["quarterly"] = rows

        if profile=="Banka":
            # Net income, assets and equity are universal bank anchors. Loans and
            # deposits/funds are operating-detail rows whose naming differs for
            # participation/development banks and therefore are tracked separately.
            core_keys=["net_income","total_assets","equity"]
        elif profile in {"Sigorta","Finansal"}:
            # Revenue/cash-flow definitions are not comparable with industrial
            # companies. Require profit + balance-sheet anchors instead.
            core_keys=["net_income","total_assets","equity"]
        else:
            core_keys=["revenue","net_income","total_assets","equity"]

        found_core = sum(1 for k in core_keys if k in found)
        found_cash = sum(1 for k in ["operating_cash_flow","capex"] if k in found)
        result["data_quality"] = {
            "core_rows_found": found_core,
            "core_rows_expected": len(core_keys),
            "bank_operating_rows_found": (
                sum(1 for k in ["loans","deposits"] if k in found)
                if profile=="Banka" else None
            ),
            "bank_operating_rows_expected": 2 if profile=="Banka" else None,
            "cashflow_rows_found": found_cash if group=="XI_29" and profile not in financial_profiles else None,
            "quarterly_periods": len(latest_periods),
            "annual_periods": max(len(annual_rev), len(annual_ni)),
            "financial_group_used": group,
            "financial_group_fallback_used": result.get("financial_group_fallback_used",False),
        }

        result["commentary"] = _build_commentary(summary, profile)
        return result

    except Exception as exc:
        result["error"] = str(exc)
        return result
