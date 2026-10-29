"""Normalize reserved/completed calls without mistaking intent for completion."""

import re
from datetime import datetime


def _ledger_requests(records):
    """legacy 완료 행과 v2 예약/완료를 잠재 요청 한 건씩으로 정규화한다."""
    rows, requests_by_id, seen = [], {}, {}
    for record in records:
        if (
            not isinstance(record.get("session_id"), str)
            or not record["session_id"]
            or not isinstance(record.get("requested_at"), str)
            or not isinstance(record.get("cache_hit", False), bool)
        ):
            raise ValueError("호출 원장 필수 필드 오류")
        if datetime.fromisoformat(record["requested_at"]).tzinfo is None:
            raise ValueError("호출 원장 UTC offset 누락")
        if "schema_version" not in record:
            rows.append(record)
            continue
        if record["schema_version"] != 2 or record.get("phase") not in {"reserved", "completed"}:
            raise ValueError("호출 원장 version/phase 오류")
        request_id = record.get("request_id")
        if not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{32}", request_id):
            raise ValueError("호출 원장 request_id 오류")
        for field in ("session_id", "requested_at", "endpoint", "run_ledger"):
            if not isinstance(record.get(field), str) or not record[field]:
                raise ValueError("호출 원장 필수 필드 오류")
        if record.get("cache_hit") is not False:
            raise ValueError("예약 원장 cache_hit 오류")
        timestamp = datetime.fromisoformat(record["requested_at"])
        if timestamp.tzinfo is None:
            raise ValueError("호출 원장 UTC offset 누락")
        identity = (request_id, record["phase"])
        if identity in seen:
            if seen[identity] != record:
                raise ValueError("호출 원장 중복 내용 불일치")
            continue
        seen[identity] = record
        if record["phase"] == "reserved":
            requests_by_id[request_id] = dict(record)
            rows.append(requests_by_id[request_id])
        else:
            previous = requests_by_id.get(request_id)
            if previous is None or any(
                previous[key] != record[key]
                for key in ("session_id", "requested_at", "endpoint", "run_ledger")
            ):
                raise ValueError("완료 원장의 예약 연결 오류")
            if datetime.fromisoformat(record["finished_at"]).tzinfo is None:
                raise ValueError("완료 시각 UTC offset 누락")
            previous.update(record)
    return rows
