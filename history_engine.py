from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
import borsapy as bp


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
    ],
    "net_income": [
        "Ana Ortaklık Payları", "Net Dönem Karı", "Dönem Net Kar",
        "DÖNEM KARI (ZARARI)", "SÜRDÜRÜLEN FAALİYETLER DÖNEM KARI",
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
    ],
    "fee_income": [
        "Net Ücret ve Komisyon Gelirleri",
        "Ücret ve Komisyon Gelirleri, Net",
    ],
}

BALANCE_ROWS = {
    "cash": [
        "Nakit ve Nakit Benzerleri",
        "Nakit ve Nakit Benzeri Varlıklar",
    ],
    "current_assets": ["Dönen Varlıklar"],
    "current_liabilities": ["Kısa Vadeli Yükümlülükler"],
    "total_assets": ["Toplam Varlıklar", "TOPLAM AKTİFLER", "Toplam Aktifler"],
    "equity": [
        "Özkaynaklar", "Toplam Özkaynaklar",
        "Ana Ortaklığa Ait Özkaynaklar",
    ],
    "loans": [
        "Krediler", "Krediler ve Alacaklar",
        "Nakdi Krediler",
    ],
    "deposits": [
        "Mevduat", "Toplam Mevduat",
        "Mevduatlar",
    ],
}

CASHFLOW_ROWS = {
    "operating_cash_flow": [
        "İşletme Faaliyetlerinden Nakit Akışları",
        "İşletme Faaliyetlerinden Kaynaklanan Nakit Akışları",
        "İşletme Faaliyetlerinden Sağlanan Net Nakit",
        "İşletme Faaliyetlerinden Elde Edilen Nakit Akışları",
        "Faaliyetlerden Elde Edilen Nakit Akışları",
    ],
    "capex": [
        "Maddi ve Maddi Olmayan Duran Varlık Alımları",
        "Maddi Duran Varlık Alımları",
        "Maddi ve Maddi Olmayan Duran Varlık Alımlarından Kaynaklanan Nakit Çıkışları",
        "Maddi Duran Varlık Alımından Kaynaklanan Nakit Çıkışları",
        "Yatırım Harcamaları",
    ],
}

FINANCIAL_DEBT_KEYWORDS = [
    "Finansal Borçlar",
    "Finansal Borç",
    "Kısa Vadeli Borçlanmalar",
    "Uzun Vadeli Borçlanmalar",
]


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


def _numeric_series(row: pd.Series | None, quarterly: bool = True) -> pd.Series:
    if row is None:
        return pd.Series(dtype=float)
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
    rows: list[Any] = []
    for idx in df.index:
        n = _norm(idx)
        if any(k in n for k in keys):
            rows.append(idx)

    if not rows:
        return pd.Series(dtype=float), []

    result = None
    for idx in rows:
        s = _numeric_series(df.loc[idx], quarterly=quarterly)
        result = s if result is None else result.add(s, fill_value=0.0)
    return (result if result is not None else pd.Series(dtype=float)), [str(x) for x in rows]


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


def _ttm(discrete: pd.Series) -> float | None:
    if discrete is None or len(discrete.dropna()) < 4:
        return None
    return float(discrete.dropna().iloc[-4:].sum())


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
        if eq_yoy is not None and assets_yoy is not None:
            paragraphs.append(
                f"Özkaynak büyümesi {_fmt(eq_yoy,'%')}, aktif büyümesi {_fmt(assets_yoy,'%')}; "
                "banka bilançosu sanayi şirketi borç/nakit metrikleriyle değerlendirilmedi."
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
    if fcf_margin is not None:
        (strengths if fcf_margin >= 8 else risks if fcf_margin < 0 else watch).append(
            f"TTM serbest nakit akışı marjı {_fmt(fcf_margin,'%')}."
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

    return {"paragraphs": paragraphs, "strengths": strengths, "risks": risks, "watch": watch}


def build_historical_analysis(symbol: str, profile: str, report_dir: Path | None = None) -> dict[str, Any]:
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
    }

    try:
        stock = bp.Ticker(symbol)
        info = stock.info.todict() if hasattr(stock.info, "todict") else dict(stock.info)
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

        group = "UFRS" if profile == "Banka" else "XI_29"
        bs_q = stock.get_balance_sheet(quarterly=True, financial_group=group, last_n=12)
        inc_q = stock.get_income_stmt(quarterly=True, financial_group=group, last_n=12)
        try:
            inc_a = stock.get_income_stmt(quarterly=False, financial_group=group, last_n=5)
        except Exception:
            inc_a = pd.DataFrame()

        cf_q = pd.DataFrame()
        if profile != "Banka":
            try:
                cf_q = stock.get_cashflow(quarterly=True, financial_group=group, last_n=12)
            except Exception:
                cf_q = pd.DataFrame()

        if report_dir:
            report_dir.mkdir(parents=True, exist_ok=True)
            bs_q.to_csv(report_dir / f"{symbol}_balance_sheet_12q.csv", encoding="utf-8-sig")
            inc_q.to_csv(report_dir / f"{symbol}_income_stmt_12q.csv", encoding="utf-8-sig")
            if not cf_q.empty:
                cf_q.to_csv(report_dir / f"{symbol}_cashflow_12q.csv", encoding="utf-8-sig")
            if not inc_a.empty:
                inc_a.to_csv(report_dir / f"{symbol}_income_stmt_annual_5y.csv", encoding="utf-8-sig")

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

        # Cash flow
        cashflow: dict[str, pd.Series] = {}
        if not cf_q.empty:
            for key, candidates in CASHFLOW_ROWS.items():
                s, row = _find_series(cf_q, candidates, quarterly=True)
                cashflow[key] = s
                if row:
                    found[key] = row

        # Annual series
        annual_rev, annual_rev_row = _find_series(inc_a, INCOME_ROWS["revenue"], quarterly=False)
        annual_ni, annual_ni_row = _find_series(inc_a, INCOME_ROWS["net_income"], quarterly=False)
        if annual_rev_row:
            found["annual_revenue"] = annual_rev_row
        if annual_ni_row:
            found["annual_net_income"] = annual_ni_row

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
        ocf_d = _discrete_from_ytd(cashflow.get("operating_cash_flow", pd.Series(dtype=float)))
        capex_d = _discrete_from_ytd(cashflow.get("capex", pd.Series(dtype=float)))

        ttm_rev = _ttm(revenue_d)
        ttm_ni = _ttm(net_income_d)
        ttm_ocf = _ttm(ocf_d)
        ttm_capex = None
        if capex_d is not None and len(capex_d.dropna()) >= 4:
            ttm_capex = float(capex_d.dropna().iloc[-4:].abs().sum())
        ttm_fcf = ttm_ocf - ttm_capex if ttm_ocf is not None and ttm_capex is not None else None

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
        equity_now, equity_old = _same_quarter_year_ago(balance.get("equity", pd.Series(dtype=float)))
        assets_now, assets_old = _same_quarter_year_ago(balance.get("total_assets", pd.Series(dtype=float)))
        ca_now, ca_old = _same_quarter_year_ago(balance.get("current_assets", pd.Series(dtype=float)))
        cl_now, cl_old = _same_quarter_year_ago(balance.get("current_liabilities", pd.Series(dtype=float)))

        net_debt_now = (debt_now - cash_now) if debt_now is not None and cash_now is not None else None
        net_debt_old = (debt_old - cash_old) if debt_old is not None and cash_old is not None else None
        current_ratio_now = _safe_ratio(ca_now, cl_now)
        current_ratio_old = _safe_ratio(ca_old, cl_old)

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
            "ttm_revenue": ttm_rev,
            "ttm_net_income": ttm_ni,
            "ttm_operating_cash_flow": ttm_ocf,
            "ttm_capex": ttm_capex,
            "ttm_free_cash_flow": ttm_fcf,
            "cash_conversion": _safe_ratio(ttm_ocf, ttm_ni) if ttm_ni is not None and ttm_ni > 0 else None,
            "fcf_margin": _safe_ratio(ttm_fcf, ttm_rev, 100.0),
            "cash": cash_now,
            "cash_yoy": _pct_change(cash_now, cash_old),
            "financial_debt": debt_now,
            "financial_debt_yoy": _pct_change(debt_now, debt_old),
            "net_debt": net_debt_now,
            "net_debt_yoy": _pct_change(net_debt_now, net_debt_old)
                if net_debt_old is not None and net_debt_old > 0 else None,
            "equity": equity_now,
            "equity_yoy": _pct_change(equity_now, equity_old),
            "total_assets": assets_now,
            "assets_yoy": _pct_change(assets_now, assets_old),
            "current_ratio": current_ratio_now,
            "current_ratio_yoy_change": _pp_change(current_ratio_now, current_ratio_old),
        }

        # Bank-specific balance growth metrics.
        loans_now, loans_old = _same_quarter_year_ago(balance.get("loans", pd.Series(dtype=float)))
        dep_now, dep_old = _same_quarter_year_ago(balance.get("deposits", pd.Series(dtype=float)))
        summary["loans_yoy"] = _pct_change(loans_now, loans_old)
        summary["deposits_yoy"] = _pct_change(dep_now, dep_old)

        result["summary"] = summary

        # Detail table: newest first, maximum 8 periods for report readability.
        periods = sorted(
            set(revenue.index) | set(net_income.index) | set(net_margin.index) |
            set(operating_margin.index) | set(ocf_d.index),
            key=_qkey,
            reverse=True,
        )[:8]
        rows = []
        for period in periods:
            rows.append({
                "period": str(period),
                "revenue": float(revenue[period]) if period in revenue.index else None,
                "revenue_yoy": revenue_yoy.get(str(period)),
                "net_income": float(net_income[period]) if period in net_income.index else None,
                "net_income_yoy": profit_yoy.get(str(period)),
                "gross_margin": float(gross_margin[period]) if period in gross_margin.index else None,
                "operating_margin": float(operating_margin[period]) if period in operating_margin.index else None,
                "net_margin": float(net_margin[period]) if period in net_margin.index else None,
                "operating_cash_flow_discrete": float(ocf_d[period]) if period in ocf_d.index else None,
            })
        result["quarterly"] = rows

        found_core = sum(
            1 for k in ["revenue", "net_income", "total_assets", "equity"] if k in found
        )
        found_cash = sum(
            1 for k in ["operating_cash_flow", "capex"] if k in found
        )
        result["data_quality"] = {
            "core_rows_found": found_core,
            "core_rows_expected": 4,
            "cashflow_rows_found": found_cash if profile != "Banka" else None,
            "quarterly_periods": len(latest_periods),
            "annual_periods": max(len(annual_rev), len(annual_ni)),
        }

        result["commentary"] = _build_commentary(summary, profile)
        return result

    except Exception as exc:
        result["error"] = str(exc)
        return result
