"""Stable identity byte contracts; no I/O."""

import hashlib


def player_key(scope: str, name: str, account_id=None) -> str:
    """기존 v3 parsed key의 byte 계약을 공유한다."""
    return hashlib.sha256(f"{scope}|{account_id or ''}|{name}".encode()).hexdigest()[:24]
