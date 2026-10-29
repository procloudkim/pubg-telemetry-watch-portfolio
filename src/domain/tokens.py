"""Validate local run and match identifiers before path construction."""

import re

TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


def validate_token(value, label):
    if not TOKEN.fullmatch(value):
        raise SystemExit(f"{label}은 영문·숫자·점·밑줄·하이픈 1~64자")
    return value
