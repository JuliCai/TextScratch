import json
import os
import re
from uuid import uuid4
from typing import Any


def safe_name(name: str, fallback: str = "item") -> str:
    sanitized = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in (name or ""))
    sanitized = sanitized.strip()
    sanitized = (sanitized or fallback)[:120]
    if re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", sanitized, re.IGNORECASE):
        sanitized = "_" + sanitized
    return sanitized


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json_file(path: str, data: Any) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=4)


def load_json_file(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def gen_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid4().hex}"
