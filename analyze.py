from __future__ import annotations

import argparse
import html
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "universe.csv"
REPORT_DIR = ROOT / "reports"

PROFILE_THRESHOLDS = {
    "Banka": {
        "pe": ("low", 5.0, 12.0),
        "pb": ("low", 0.7, 2.0),
        "roe": ("high", 12.0, 25.0),
        "roa": ("high", 1.0, 3.0),
        "revenue_growth": ("high", 0.0, 20.0),
        "earnings_growth": ("high", 0.0, 30.0),
    },
    "Savunma/Teknoloji": {
        "pe": ("low", 18.0, 55.0),
        "pb": ("low", 2.0, 8.0),
        "roe": ("high", 10.0, 25.0),
        "roa": ("high", 4.0, 12.0),
        "revenue_growth": ("high", 5.0, 40.0),
        "earnings_growth": ("high", 5.0, 50.0),
    },
    "Genel": {
        "pe": ("low", 8.0, 30.0),
        "pb": ("low", 0.8, 4.0),
        "roe": ("high", 8.0, 25.0),
        "roa": ("high", 3.0, 12.0),
        "revenue_growth": ("high", 0.0, 30.0),
        "earnings_growth": ("high", 0.0, 30.0),
    },
}

METRIC_LABELS = {
    "pe": "F/K",
    "pb": "PD/DD",
    "roe": "ROE",
    "roa": "ROA",
    "revenue_growth": "Ciro Büyümesi",
    "earnings_growth": "Kâr / EPS Büyümesi",
    "operating_margin": "Faaliyet Marjı",
    "profit_margin": "Net Kâr Marjı",
    "debt_to_equity": "Borç / Özsermaye",
    "current_ratio": "Cari Oran",
    "enterprise_to_ebitda": "FD/FAVÖK",
    "fcf_yield": "FCF Verimi",
    "dividend_yield": "Temettü Verimi",
}

PCT_KEYS = {
    "roe", "roa", "revenue_growth", "earnings_growth",
    "operating_margin", "profit_margin", "fcf_yield", "dividend_yield",
}


def clean_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def pct_from_fraction(value: Any) -> float | None:
    x = clean_float(value)
    if x is None:
        return None
    return x * 100.0 if abs(x) <= 5 else x


def yahoo_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper().replace(".IS", "")
    return f"{symbol}.IS"


def get_info(symbol: str) -> dict[str, Any]:
    ticker = yf.Ticker(yahoo_symbol(symbol))
    try:
        info = ticker.info or {}
    except Exception:
        info = {}
    try:
        fast = dict(ticker.fast_info or {})
    except Exception:
        fast = {}

    price = clean_float(
        fast.get("last_price")
        or info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose")
    )
    eps = clean_float(info.get("trailingEps"))
    bvps = clean_float(info.get("bookValue"))
    market_cap = clean_float(fast.get("market_cap") or info.get("marketCap"))
    fcf = clean_float(info.get("freeCashflow"))

    pe = clean_float(info.get("trailingPE"))
    if pe is None and price and eps and eps > 0:
        pe = price / eps

    pb = clean_float(info.get("priceToBook"))
    if pb is None and price and bvps and bvps > 0:
        pb = price / bvps

    return {
        "symbol": symbol.upper().replace(".IS", ""),
        "name": info.get("longName") or info.get("shortName") or symbol,
        "provider_symbol": yahoo_symbol(symbol),
        "sector_provider": info.get("sector") or "",
        "industry_provider": info.get("industry") or "",
        "currency": info.get("currency") or "TRY",
        "price": price,
        "market_cap": market_cap,
        "pe": pe,
        "pb": pb,
        "roe": pct_from_fraction(info.get("returnOnEquity")),
        "roa": pct_from_fraction(info.get("returnOnAssets")),
        "revenue_growth": pct_from_fraction(info.get("revenueGrowth")),
        "earnings_growth": pct_from_fraction(
            info.get("earningsGrowth")
            if info.get("earningsGrowth") is not None
            else info.get("earningsQuarterlyGrowth")
        ),
        "operating_margin": pct_from_fraction(info.get("operatingMargins")),
        "profit_margin": pct_from_fraction(info.get("profitMargins")),
        "debt_to_equity": clean_float(info.get("debtToEquity")),
        "current_ratio": clean_float(info.get("currentRatio")),
        "enterprise_to_ebitda": clean_float(info.get("enterpriseToEbitda")),
        "dividend_yield": pct_from_fraction(info.get("dividendYield")),
        "free_cash_flow": fcf,
        "fcf_yield": (fcf / market_cap * 100.0)
        if fcf is not None and market_cap and market_cap > 0
        else None,
    }


def get_close(symbol: str, period: str = "2y") -> pd.Series:
    candidates = [yahoo_symbol(symbol)]
    if symbol.upper() == "XU100":
        candidates = ["XU100.IS", "^XU100"]

    for candidate in candidates:
        try:
            data = yf.download(
                candidate,
                period=period,
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
        except Exception:
            continue

        if data.empty:
            continue

        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        close = close.dropna().astype(float)
        if not close.empty:
            return close

    return pd.Series(dtype=float)


def load_universe() -> pd.DataFrame:
    df = pd.read_csv(DATA_FILE)
    for col in ("symbol", "profile", "sector_group", "industry_group"):
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


def metadata_for(df: pd.DataFrame, symbol: str) -> dict[str, str]:
    hit = df[df["symbol"].str.upper() == symbol.upper()]
    if hit.empty:
        return {
            "symbol": symbol.upper(),
            "profile": "Genel",
            "sector_group": "",
            "industry_group": "",
        }
    return hit.iloc[0].to_dict()


def choose_peers(
    df: pd.DataFrame,
    symbol: str,
    meta: dict[str, str],
    max_peers: int = 25,
) -> tuple[list[str], str]:
    symbol = symbol.upper()
    industry = meta.get("industry_group", "")
    sector = meta.get("sector_group", "")
    profile = meta.get("profile", "Genel")

    if industry:
        group = df[
            (df["industry_group"].str.casefold() == industry.casefold())
            & (df["symbol"].str.upper() != symbol)
        ]
        if len(group) >= 2:
            return (
                group["symbol"].str.upper().drop_duplicates().head(max_peers).tolist(),
                f"Endüstri: {industry}",
            )

    if sector:
        group = df[
            (df["sector_group"].str.casefold() == sector.casefold())
            & (df["symbol"].str.upper() != symbol)
        ]
        if len(group) >= 3:
            return (
                group["symbol"].str.upper().drop_duplicates().head(max_peers).tolist(),
                f"Sektör: {sector}",
            )

    group = df[
        (df["profile"].str.casefold() == profile.casefold())
        & (df["symbol"].str.upper() != symbol)
    ]
    return (
        group["symbol"].str.upper().drop_duplicates().head(max_peers).tolist(),
        f"Profil: {profile}",
    )


def clip(x: float) -> float:
    return max(0.0, min(100.0, x))


def score_low(value: float | None, good: float, bad: float) -> float | None:
    if value is None:
        return None
    if value <= good:
        return 100.0
    if value >= bad:
        return 0.0
    return clip((bad - value) / (bad - good) * 100.0)


def score_high(value: float | None, bad: float, good: float) -> float | None:
    if value is None:
        return None
    if value <= bad:
        return 0.0
    if value >= good:
        return 100.0
    return clip((value - bad) / (good - bad) * 100.0)


def metric_score(
    value: float | None,
    rule: tuple[str, float, float],
) -> float | None:
    mode, a, b = rule
    return score_low(value, a, b) if mode == "low" else score_high(value, a, b)


def weighted_average(items: list[tuple[float | None, float]]) -> float | None:
    valid = [(s, w) for s, w in items if s is not None]
    if not valid:
        return None
    return sum(s * w for s, w in valid) / sum(w for _, w in valid)


def status(score: float | None) -> str:
    if score is None:
        return "N/A"
    if score >= 67:
        return "İYİ"
    if score >= 40:
        return "NÖTR"
    return "ZAYIF"


def score_company(metrics: dict[str, Any], profile: str) -> dict[str, Any]:
    thresholds = PROFILE_THRESHOLDS.get(profile, PROFILE_THRESHOLDS["Genel"])
    scores = {
        key: metric_score(metrics.get(key), rule)
        for key, rule in thresholds.items()
    }

    if profile == "Banka":
        total = weighted_average([
            (scores["pe"], 0.20),
            (scores["pb"], 0.20),
            (scores["roe"], 0.30),
            (scores["roa"], 0.15),
            (scores["earnings_growth"], 0.15),
        ])
    else:
        total = weighted_average([
            (scores["pe"], 0.15),
            (scores["pb"], 0.10),
            (scores["roe"], 0.20),
            (scores["roa"], 0.10),
            (scores["revenue_growth"], 0.20),
            (scores["earnings_growth"], 0.25),
        ])

    return {
        "metrics": scores,
        "total": total,
        "status": status(total),
    }


def median(values: list[float | None]) -> float | None:
    vals = [
        float(v)
        for v in values
        if v is not None and math.isfinite(float(v))
    ]
    return statistics.median(vals) if vals else None


def relative_low(
    current: float | None,
    benchmark: float | None,
) -> float | None:
    if current is None or benchmark is None or current <= 0 or benchmark <= 0:
        return None
    return clip(50.0 + ((benchmark - current) / benchmark) * 50.0)


def relative_high(
    current: float | None,
    benchmark: float | None,
) -> float | None:
    if current is None or benchmark is None:
        return None
    denom = max(abs(benchmark), 10.0)
    return clip(50.0 + ((current - benchmark) / denom) * 35.0)


def build_benchmark(
    current: dict[str, Any],
    peers: list[dict[str, Any]],
) -> dict[str, Any]:
    keys = (
        "pe", "pb", "roe", "roa",
        "revenue_growth", "earnings_growth",
    )

    bench = {
        key: median([p.get(key) for p in peers])
        for key in keys
    }

    rel = {
        "pe": relative_low(current.get("pe"), bench["pe"]),
        "pb": relative_low(current.get("pb"), bench["pb"]),
        "roe": relative_high(current.get("roe"), bench["roe"]),
        "roa": relative_high(current.get("roa"), bench["roa"]),
        "revenue_growth": relative_high(
            current.get("revenue_growth"),
            bench["revenue_growth"],
        ),
        "earnings_growth": relative_high(
            current.get("earnings_growth"),
            bench["earnings_growth"],
        ),
    }

    total = weighted_average([
        (rel["pe"], 0.15),
        (rel["pb"], 0.10),
        (rel["roe"], 0.20),
        (rel["roa"], 0.10),
        (rel["revenue_growth"], 0.20),
        (rel["earnings_growth"], 0.25),
    ])

    counts = {
        key: sum(1 for p in peers if p.get(key) is not None)
        for key in keys
    }

    return {
        "median": bench,
        "relative": rel,
        "total": total,
        "counts": counts,
    }


def performance(series: pd.Series, periods: int) -> float | None:
    if series.empty or len(series) <= periods:
        return None
    old = float(series.iloc[-periods - 1])
    now = float(series.iloc[-1])
    return None if old == 0 else (now / old - 1.0) * 100.0


def relative_performance(symbol: str) -> dict[str, float | None]:
    stock = get_close(symbol)
    index = get_close("XU100")
    out: dict[str, float | None] = {}

    for label, bars in (("3m", 63), ("6m", 126), ("12m", 252)):
        sp = performance(stock, bars)
        xp = performance(index, bars)
        out[f"stock_{label}"] = sp
        out[f"index_{label}"] = xp
        out[f"alpha_{label}"] = (
            sp - xp if sp is not None and xp is not None else None
        )

    return out


def fmt(value: float | None, key: str = "", digits: int = 2) -> str:
    if value is None:
        return "N/A"

    suffix = (
        "%"
        if key in PCT_KEYS
        else "x"
        if key in {"pe", "pb", "enterprise_to_ebitda"}
        else ""
    )
    return f"{value:.{digits}f}{suffix}"


def score_color(score: float | None) -> str:
    if score is None:
        return "na"
    if score >= 67:
        return "good"
    if score >= 40:
        return "neutral"
    return "bad"


def build_comments(
    metrics: dict[str, Any],
    scores: dict[str, Any],
    benchmark: dict[str, Any],
    perf: dict[str, Any],
) -> list[str]:
    if scores["total"] is None:
        comments = ["Bireysel temel skor için veri yetersiz."]
    else:
        comments = [
            f"Bireysel temel skor {scores['total']:.0f}/100 "
            f"({scores['status']})."
        ]

    for key in (
        "pe", "pb", "roe",
        "revenue_growth", "earnings_growth",
    ):
        value = metrics.get(key)
        b = benchmark["median"].get(key)

        if value is None:
            continue

        if b is None:
            comments.append(
                f"{METRIC_LABELS[key]} {fmt(value, key)}; "
                "emsal medyanı için yeterli veri yok."
            )
            continue

        if key in {"pe", "pb"}:
            wording = "daha düşük" if value < b else "daha yüksek"
        else:
            wording = "üzerinde" if value > b else "altında"

        comments.append(
            f"{METRIC_LABELS[key]} {fmt(value, key)}; "
            f"emsal medyanı {fmt(b, key)} ve şirket bu referansa göre {wording}."
        )

    alpha = perf.get("alpha_12m")
    if alpha is not None:
        comments.append(
            f"Son 12 ayda BIST100'e göre relatif performans "
            f"{alpha:+.2f} puan."
        )

    return comments


def render_html(context: dict[str, Any]) -> str:
    m = context["metrics"]
    s = context["scores"]
    b = context["benchmark"]
    p = context["performance"]
    meta = context["metadata"]

    def esc(x: Any) -> str:
        return html.escape(str(x))

    rows = []
    ordered_keys = (
        "pe", "pb", "roe", "roa",
        "revenue_growth", "earnings_growth",
        "operating_margin", "profit_margin",
        "debt_to_equity", "current_ratio",
        "enterprise_to_ebitda", "fcf_yield",
        "dividend_yield",
    )

    for key in ordered_keys:
        value = m.get(key)
        if value is None:
            continue

        abs_score = s["metrics"].get(key)
        bench = b["median"].get(key)
        rel = b["relative"].get(key)

        rows.append(
            f"<tr><td>{esc(METRIC_LABELS[key])}</td>"
            f"<td>{esc(fmt(value, key))}</td>"
            f"<td>{esc('N/A' if abs_score is None else f'{abs_score:.0f}/100')}</td>"
            f"<td>{esc(fmt(bench, key) if bench is not None else 'N/A')}</td>"
            f"<td>{esc('N/A' if rel is None else f'{rel:.0f}/100')}</td></tr>"
        )

    perf_rows = []
    period_labels = {"3m": "3 Ay", "6m": "6 Ay", "12m": "12 Ay"}

    for key in ("3m", "6m", "12m"):
        alpha = p.get("alpha_" + key)
        perf_rows.append(
            "<tr>"
            f"<td>{period_labels[key]}</td>"
            f"<td>{fmt(p.get('stock_'+key), 'roe')}</td>"
            f"<td>{fmt(p.get('index_'+key), 'roe')}</td>"
            f"<td>{'N/A' if alpha is None else f'{alpha:+.2f} puan'}</td>"
            "</tr>"
        )

    comments = "".join(
        f"<li>{esc(item)}</li>"
        for item in context["comments"]
    )

    peers = " · ".join(context["peer_symbols"]) or "Yeterli emsal yok"

    absolute_text = (
        "N/A"
        if s["total"] is None
        else f"{s['total']:.0f}/100"
    )

    relative_text = (
        "N/A"
        if b["total"] is None
        else f"{b['total']:.0f}/100"
    )

    price_text = (
        "N/A"
        if m.get("price") is None
        else f"{m['price']:.2f}"
    )

    alpha12 = p.get("alpha_12m")
    alpha12_text = (
        "N/A"
        if alpha12 is None
        else f"{alpha12:+.2f}"
    )

    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(context['symbol'])} — BIST Fundamental Intelligence</title>
<style>
body{{font-family:Arial,sans-serif;background:#0d1117;color:#e6edf3;margin:0}}
.wrap{{max-width:1180px;margin:auto;padding:28px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:18px 0}}
.card,table{{background:#161b22;border:1px solid #30363d;border-radius:10px}}
.card{{padding:16px}}
.big{{font-size:30px;font-weight:700}}
.muted{{color:#8b949e}}
.good{{color:#3fb950}}
.neutral{{color:#d29922}}
.bad{{color:#f85149}}
.na{{color:#8b949e}}
table{{width:100%;border-collapse:collapse;margin:12px 0 24px;overflow:hidden}}
th,td{{border:1px solid #30363d;padding:9px;text-align:right}}
th:first-child,td:first-child{{text-align:left}}
th{{background:#21262d}}
li{{margin:8px 0}}
.note{{border-left:4px solid #d29922;padding:12px;background:#161b22}}
</style>
</head>
<body>
<div class="wrap">

<h1>{esc(context['symbol'])} — Fundamental Intelligence Report</h1>
<div class="muted">
{esc(m.get('name',''))} · Profil: {esc(meta.get('profile','Genel'))}
· {esc(context['benchmark_scope'])}
</div>

<div class="grid">
<div class="card">
<div class="muted">Bireysel Temel Skor</div>
<div class="big {score_color(s['total'])}">{absolute_text}</div>
<div>{esc(s['status'])}</div>
</div>

<div class="card">
<div class="muted">Emsal Relatif Skor</div>
<div class="big {score_color(b['total'])}">{relative_text}</div>
<div>n={len(context['peer_data'])}</div>
</div>

<div class="card">
<div class="muted">Fiyat</div>
<div class="big">{esc(price_text)}</div>
<div>{esc(m.get('currency','TRY'))}</div>
</div>

<div class="card">
<div class="muted">12A XU100 Alfa</div>
<div class="big">{esc(alpha12_text)}</div>
<div>puan</div>
</div>
</div>

<h2>Finansal Faktörler</h2>
<table>
<tr>
<th>Metrik</th>
<th>Şirket</th>
<th>Mutlak Puan</th>
<th>Emsal Medyanı</th>
<th>Relatif Puan</th>
</tr>
{''.join(rows)}
</table>

<h2>BIST100 Relatif Performans</h2>
<table>
<tr>
<th>Dönem</th>
<th>{esc(context['symbol'])}</th>
<th>XU100</th>
<th>Alfa</th>
</tr>
{''.join(perf_rows)}
</table>

<h2>Otomatik Yorum</h2>
<ul>{comments}</ul>

<h2>Emsal Evreni</h2>
<div class="card">{esc(peers)}</div>

<p class="note">
MVP v0.1. Yahoo Finance verileri BIST için eksik/gecikmeli olabilir.
Eksik değerler uydurulmaz. Bu rapor araştırma amaçlıdır; yatırım tavsiyesi değildir.
</p>

</div>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BIST Fundamental Intelligence"
    )
    parser.add_argument("symbol", help="Örn: ASELS")
    args = parser.parse_args()

    symbol = args.symbol.strip().upper().replace(".IS", "")
    if not symbol:
        raise SystemExit("Hisse kodu boş olamaz.")

    print(f"[1/6] {symbol} ana verileri alınıyor...")
    universe = load_universe()
    meta = metadata_for(universe, symbol)
    metrics = get_info(symbol)
    scores = score_company(
        metrics,
        meta.get("profile", "Genel"),
    )

    print("[2/6] Emsal evreni belirleniyor...")
    peer_symbols, scope = choose_peers(
        universe,
        symbol,
        meta,
    )

    peer_data = []
    for peer in peer_symbols:
        try:
            peer_data.append(get_info(peer))
        except Exception as exc:
            print(f"  Uyarı: {peer} alınamadı: {exc}")

    print("[3/6] Sektör/endüstri medyanları hesaplanıyor...")
    benchmark = build_benchmark(metrics, peer_data)

    print("[4/6] BIST100 relatif performansı hesaplanıyor...")
    perf = relative_performance(symbol)

    print("[5/6] Otomatik yorum hazırlanıyor...")
    comments = build_comments(
        metrics,
        scores,
        benchmark,
        perf,
    )

    context = {
        "symbol": symbol,
        "metadata": meta,
        "metrics": metrics,
        "scores": scores,
        "peer_symbols": peer_symbols,
        "peer_data": peer_data,
        "benchmark_scope": scope,
        "benchmark": benchmark,
        "performance": perf,
        "comments": comments,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    REPORT_DIR.mkdir(exist_ok=True)

    html_path = REPORT_DIR / f"{symbol}_report.html"
    json_path = REPORT_DIR / f"{symbol}_report.json"

    html_path.write_text(
        render_html(context),
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(
            context,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print("[6/6] Rapor hazır.")
    print(f"HTML: {html_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
