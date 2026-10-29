"""Data quality results; PASS describes structural consistency only."""


def _check(check_id, dimension, ok, observed, expected, detail, severity="ERROR"):
    return {
        "id": check_id,
        "dimension": dimension,
        "status": "PASS" if ok else "FAIL",
        "severity": severity,
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }


def _quality(checks):
    failed = [item for item in checks if item["severity"] == "ERROR" and item["status"] == "FAIL"]
    return {"status": "FAIL" if failed else "PASS", "error_count": len(failed), "checks": checks}
