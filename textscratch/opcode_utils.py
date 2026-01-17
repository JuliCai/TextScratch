"""Opcode-related utilities for block parsing."""

import string
from typing import Any, Dict, Optional, Tuple

from .constants import MENU_SHADOW_FOR_INPUT, MENU_SHADOW_OPCODES
from .opcodes import OPCODE_MAP, OPCODE_NORMALIZATION, OPCODE_PATTERNS
from .utils import gen_id


def _opcode_literal_length(opcode: str) -> int:
    """Calculate the total length of literal text in an opcode's format string."""
    fmt = OPCODE_MAP.get(opcode, "")
    return sum(len(lit) for lit, _, _, _ in string.Formatter().parse(fmt) if lit)


def is_menu_shadow(opcode: str) -> bool:
    """Check if an opcode represents a menu shadow block."""
    return (
        opcode in MENU_SHADOW_OPCODES
        or opcode.endswith("menu")
        or opcode.startswith("pen_menu")
    )


def is_reporter_shape(opcode: str) -> bool:
    """Check if an opcode has a reporter shape (round or boolean)."""
    fmt = OPCODE_MAP.get(opcode, "").lstrip()
    return (
        fmt.startswith("(")
        or fmt.startswith("<")
        or fmt.startswith("[")
        or fmt.startswith("{")
    )


def is_boolean_reporter(opcode: str) -> bool:
    """Check if an opcode is a boolean reporter."""
    fmt = OPCODE_MAP.get(opcode, "").lstrip()
    return fmt.startswith("<") or opcode == "argument_reporter_boolean"


def match_opcode_line(
    line: str, allow_menu_only: bool = True
) -> Tuple[Optional[str], Dict[str, str]]:
    """Match a line against opcode patterns and return the opcode and captured groups."""
    for pattern, opcode, placeholders in OPCODE_PATTERNS:
        if not allow_menu_only and _opcode_literal_length(opcode) == 0:
            continue
        match = pattern.match(line)
        if match:
            groups = {name: match.group(name) for name in placeholders}
            normalized = OPCODE_NORMALIZATION.get(opcode, opcode)
            return normalized, groups
    return None, {}


def create_menu_shadow_block(
    input_name: str,
    parent_id: str,
    blocks: Dict[str, Dict[str, Any]],
) -> Optional[str]:
    """Create a shadow menu block for inputs that need one (like COSTUME).

    Returns the block ID of the created shadow, or None if no shadow is needed.
    """
    if input_name not in MENU_SHADOW_FOR_INPUT:
        return None

    opcode, field_name = MENU_SHADOW_FOR_INPUT[input_name]
    shadow_id = gen_id("shadow")

    # Use a default value - first costume/backdrop/sound will be selected at runtime
    # The actual value doesn't matter much since a reporter is overriding it
    default_value = ""

    blocks[shadow_id] = {
        "opcode": opcode,
        "next": None,
        "parent": parent_id,
        "inputs": {},
        "fields": {field_name: [default_value, None]},
        "shadow": True,
        "topLevel": False,
    }

    return shadow_id
