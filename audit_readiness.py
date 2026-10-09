"""Conservative classification from an audit row, not an individual report verdict."""


def readiness_from_audit(row):
    codes = {x.get("code") for x in row.get("issues", [])}
    profile = row.get("profile")
    if row.get("status") in {"ERROR", "CRITICAL"}:
        return "REVIEW", "Motor-level failure"
    if "HISTORY_UNAVAILABLE" in codes or "SHORT_HISTORY" in codes:
        return "PARTIAL", "Missing or insufficient financial history"
    if profile in {"GYO", "Holding", "Yatırım Ortaklığı"}:
        return "VALUATION_PARTIAL", "Audit has no verified property/portfolio NAV evidence"
    if row.get("status") == "WARNING":
        return "REVIEW", "Provider/data warning requires reconciliation"
    return "READY", "Audit checks passed; external statement reconciliation not established"
