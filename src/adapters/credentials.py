"""Credential lookup stays at the HTTP boundary and never enters diagnostics."""

import os
from .files import ROOT

API = "https://api.pubg.com"


def api_key() -> str:
    env = ROOT / ".env"
    key = ""
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("PUBG_API_KEY="):
                key = line.split("=", 1)[1].strip()
                break
    key = key or os.environ.get("PUBG_API_KEY", "").strip()
    if not key:
        raise SystemExit("PUBG_API_KEY 없음 — .env에 'PUBG_API_KEY=...' 한 줄 필요")
    return key
