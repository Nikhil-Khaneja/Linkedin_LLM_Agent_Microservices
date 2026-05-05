"""Normalize list-of-string fields from LLM/DB. Never use list(str) — that iterates characters."""

from __future__ import annotations

import json
from typing import Any


def coerce_str_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        out: list[str] = []
        for x in val:
            if x is None:
                continue
            s = str(x).strip()
            if s:
                out.append(s)
        return out
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return []
        if s.startswith('['):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return coerce_str_list(parsed)
            except json.JSONDecodeError:
                pass
        return [p.strip() for p in s.replace(';', ',').split(',') if p.strip()]
    s = str(val).strip()
    return [s] if s else []
