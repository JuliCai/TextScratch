"""Opcode-related utilities for block parsing."""

import string
from typing import Any, Dict, Optional, Tuple

from .constants import MENU_SHADOW_FOR_INPUT, MENU_SHADOW_OPCODES
from .opcodes import OPCODE_MAP, OPCODE_NORMALIZATION, OPCODE_PATTERNS, MATH_OPERATORS
from .utils import gen_id
from .string_utils import match_parts


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
        fmt = OPCODE_MAP[opcode]
        literals = []
        for literal, field, _, _ in string.Formatter().parse(fmt):
            if not literals:
                literals.append(literal)
            else:
                literals[-1] += literal
            if field:
                literals.append("")
        captures = match_parts(line, literals) if placeholders else ([] if line == fmt else None)
        if captures is not None:
            groups = dict(zip(placeholders, captures))
            if opcode == "sensing_of" and groups.get("PROPERTY") in MATH_OPERATORS:
                if not groups["OBJECT"].endswith(" v]"):
                    return "operator_mathop", {"OPERATOR": groups["PROPERTY"], "NUM": groups["OBJECT"]}
            normalized = OPCODE_NORMALIZATION.get(opcode, opcode)
            return normalized, groups
    return None, {}


def create_menu_shadow_block(
    input_name: str,
    parent_id: str,
    blocks: Dict[str, Dict[str, Any]],
    owner_opcode: str = "",
) -> Optional[str]:
    """Create a shadow menu block for inputs that need one (like COSTUME).

    Returns the block ID of the created shadow, or None if no shadow is needed.
    """
    menu = MENU_SHADOW_FOR_INPUT.get(input_name)
    if input_name == "TO" and owner_opcode in {"motion_goto", "motion_glideto"}:
        menu = (owner_opcode + "_menu", "TO")
    elif input_name == "TOWARDS" and owner_opcode == "motion_pointtowards":
        menu = ("motion_pointtowards_menu", "TOWARDS")
    if menu is None:
        return None

    opcode, field_name = menu
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
