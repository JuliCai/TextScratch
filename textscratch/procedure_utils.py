"""Procedure (custom block) related utilities."""

import re
from typing import Any, Dict, List, Optional

from .string_utils import split_top_level_whitespace, strip_inline_literals


def build_procedure_call_pattern(proccode: str) -> re.Pattern[str]:
    """Build a regex pattern for matching procedure calls."""
    parts = re.split(r"(%s|%b)", proccode)
    regex_parts: List[str] = []
    for idx, part in enumerate(parts):
        if part in {"%s", "%b"}:
            # Constrain each capture to stop before the next literal to avoid catastrophic backtracking
            next_literal = ""
            for future in parts[idx + 1 :]:
                if future in {"%s", "%b"} or not future:
                    continue
                next_literal = re.escape(future)
                break
            if next_literal:
                regex_parts.append(r"(.+?)(?=%s)" % next_literal)
            else:
                regex_parts.append(r"(.+?)")
        elif part:
            regex_parts.append(re.escape(part))
    return re.compile("^" + "".join(regex_parts) + "$", re.DOTALL)


def is_space_separated_proccode(proccode: str) -> bool:
    """Check if a proccode has space-separated arguments."""
    parts = re.split(r"(%s|%b)", proccode)
    placeholder_indices = [
        idx for idx, part in enumerate(parts) if part in {"%s", "%b"}
    ]
    if len(placeholder_indices) < 2:
        return False

    for idx, pos in enumerate(placeholder_indices[:-1]):
        segment = "".join(parts[pos + 1 : placeholder_indices[idx + 1]]).strip()
        if not segment:
            continue
        # Treat simple word-like separators (e.g., "OBB2") as whitespace so we can still
        # parse long argument lists that include inline literal tokens.
        cleaned = segment.replace("_", " ").replace(":", " ").replace("-", " ")
        if all(token.isalnum() for token in cleaned.split() if token):
            continue
        return False
    return True


def match_space_separated_call(
    line: str, info: Dict[str, Any]
) -> Optional[List[str]]:
    """Match a line against a space-separated procedure call pattern."""
    lead = info.get("lead", "")
    arg_ids = info.get("arg_ids", [])
    inline_literals = info.get("inline_literals", [])

    if lead and not line.startswith(lead):
        return None

    remainder = line[len(lead) :].strip() if lead else line.strip()
    if inline_literals:
        remainder = strip_inline_literals(remainder, inline_literals)
    parts = split_top_level_whitespace(remainder, len(arg_ids))
    if len(parts) != len(arg_ids):
        return None
    return parts
