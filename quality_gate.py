from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="BIST Fundamental Intelligence release quality gate")
    ap.add_argument("--summary", default="audit_summary/full_bist_audit_summary.json")
    ap.add_argument("--min-universe", type=int, default=600)
    ap.add_argument("--min-xu100", type=int, default=100)
    args = ap.parse_args()

    path = Path(args.summary)
    if not path.exists():
        raise SystemExit(f"QUALITY GATE FAIL: audit summary bulunamadı: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    statuses = data.get("status_counts", {})
    errors = int(statuses.get("ERROR", 0) or 0)
    critical = int(statuses.get("CRITICAL", 0) or 0)
    universe = int(data.get("symbols_checked", 0) or 0)
    reported = int(data.get("universe_count_reported", 0) or 0)
    xu100 = int(data.get("xu100_count_reported", 0) or 0)

    failures = []
    if errors:
        failures.append(f"ERROR={errors}")
    if critical:
        failures.append(f"CRITICAL={critical}")
    if universe < args.min_universe:
        failures.append(f"symbols_checked={universe} < {args.min_universe}")
    if reported < args.min_universe:
        failures.append(f"universe_count={reported} < {args.min_universe}")
    if xu100 < args.min_xu100:
        failures.append(f"XU100={xu100} < {args.min_xu100}")

    if failures:
        raise SystemExit("QUALITY GATE FAIL: " + " | ".join(failures))

    warnings = int(statuses.get("WARNING", 0) or 0)
    infos = int(statuses.get("INFO", 0) or 0)
    ok = int(statuses.get("OK", 0) or 0)

    print(
        "QUALITY GATE PASS | "
        f"universe={universe} | XU100={xu100} | "
        f"ERROR={errors} | CRITICAL={critical} | "
        f"WARNING={warnings} | INFO={infos} | OK={ok}"
    )


if __name__ == "__main__":
    main()
