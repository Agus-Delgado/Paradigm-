"""Utilidades de session state y claves de dataset."""

from __future__ import annotations

import hashlib


def make_dataset_key(source: str, label: str, shape: tuple[int, int]) -> str:
    raw = f"{source}|{label}|{shape[0]}|{shape[1]}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]
