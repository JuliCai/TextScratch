"""Input value building and expression parsing.

This module contains functions for building input values and parsing
inline expressions. These are kept together due to their circular
dependency (build_input_value calls parse_inline_expression and vice versa).
"""

import re
import string
from typing import Any, Dict, List, Optional

from .constants import BINARY_OPERATOR_TOKENS
from .diagnostics import DiagnosticContext
from .field_utils import (
    build_key_option_input,
    build_menu_shadow_input,
    default_empty_input,
    resolve_field_value,
    resolve_list_id,
    resolve_variable_id,
)
from .opcodes import CONTROL_BLOCKS, MATH_OPERATORS, OPCODE_FIELDS, OPCODE_MAP
from .opcode_utils import match_opcode_line
from .parsed_node import ParsedNode
from .string_utils import (
    coerce_number,
    split_top_level,
    split_top_level_whitespace,
    strip_wrappers,
    strip_wrapping_parens,
)
from .utils import gen_id


def parse_balanced_math_expression(
    value: str,
    procedure_defs: Dict[str, Dict[str, Any]],
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    broadcast_ids: Dict[str, str],
    procedure_args: Optional[Dict[str, str]],
) -> Optional[ParsedNode]:
    """Parse a balanced math expression like (a + b)."""
    text = value.strip()
    inner = strip_wrapping_parens(text)

    for token, opcode, left_name, right_name in BINARY_OPERATOR_TOKENS:
        # Do NOT include "<": ">" as balanced pairs here because:
        # 1. <> wraps boolean expressions like <not ...> or <x and y>
        # 2. < and > are also comparison operators: <(x) < (y)>
        # The comparison operator < inside expressions would be mistakenly treated
        # as a bracket opener, causing depth tracking to fail.
        # Only () {} [] are true balanced brackets in math contexts.
        split = split_top_level(inner, token, extra_pairs={"[": "]"})
        if split is None:
            continue
        left, right = split
        node = ParsedNode(opcode)
        node.inputs[left_name] = build_input_value(
            left,
            left_name,
            broadcast_ids,
            True,
            procedure_defs,
            local_vars,
            global_vars,
            local_lists,
            global_lists,
            procedure_args,
        )
        node.inputs[right_name] = build_input_value(
            right,
            right_name,
            broadcast_ids,
            True,
            procedure_defs,
            local_vars,
            global_vars,
            local_lists,
            global_lists,
            procedure_args,
        )
        return node

    return None


def parse_boolean_expression(
    value: str,
    procedure_defs: Dict[str, Dict[str, Any]],
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    broadcast_ids: Dict[str, str],
    procedure_args: Optional[Dict[str, str]],
) -> Optional[ParsedNode]:
    """Parse a boolean expression like <a and b> or <not c>."""
    raw = value.strip()

    # Only attempt boolean parsing when the text clearly contains a boolean form.
    if "<" not in raw and not raw.startswith("not "):
        return None

    text = raw

    if text.startswith("<") and text.endswith(">"):
        text = text[1:-1].strip()

    if text.startswith("not "):
        node = ParsedNode("operator_not")
        node.inputs["OPERAND"] = build_input_value(
            text[len("not ") :].strip(),
            "OPERAND",
            broadcast_ids,
            True,
            procedure_defs,
            local_vars,
            global_vars,
            local_lists,
            global_lists,
            procedure_args,
        )
        return node

    # For and/or splitting, we MUST include "<": ">" as balanced pairs because
    # boolean subexpressions like <(x) = (y)> need to be treated as atomic units.
    # Without this, "<<(in1) = [1]> and <(in2) = [1]>>" would split incorrectly.
    bracket_pairs = {"[": "]", "<": ">"}
    for token, opcode, left_name, right_name in (
        (" and ", "operator_and", "OPERAND1", "OPERAND2"),
        (" or ", "operator_or", "OPERAND1", "OPERAND2"),
    ):
        split = split_top_level(text, token, extra_pairs=bracket_pairs)
        if split:
            left, right = split
            node = ParsedNode(opcode)
            node.inputs[left_name] = build_input_value(
                left,
                left_name,
                broadcast_ids,
                True,
                procedure_defs,
                local_vars,
                global_vars,
                local_lists,
                global_lists,
                procedure_args,
            )
            node.inputs[right_name] = build_input_value(
                right,
                right_name,
                broadcast_ids,
                True,
                procedure_defs,
                local_vars,
                global_vars,
                local_lists,
                global_lists,
                procedure_args,
            )
            return node

    return None


def parse_inline_expression(
    value: str,
    procedure_defs: Dict[str, Dict[str, Any]],
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    broadcast_ids: Dict[str, str],
    procedure_args: Optional[Dict[str, str]],
) -> Optional[ParsedNode]:
    """Parse an inline expression (reporter or operator)."""
    text = value.strip()

    # Only parse expressions that look like reporters/booleans (wrapped in brackets).
    # This prevents greedy math parsing from misinterpreting command lines like
    # "set [y v] to (...)" as operator_add when the value contains embedded operators.
    if not (
        text.startswith("(")
        or text.startswith("<")
        or text.startswith("[")
        or text.startswith("{")
    ):
        return None

    # Treat hex color literals as plain literals, not variable reporters
    # (e.g., "#6e487f" should stay a color input, not become a variable reporter block).
    hex_candidate = strip_wrapping_parens(text)
    if re.match(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", hex_candidate):
        return None

    structured = parse_balanced_math_expression(
        value,
        procedure_defs,
        local_vars,
        global_vars,
        local_lists,
        global_lists,
        broadcast_ids,
        procedure_args,
    )
    if structured:
        return structured

    boolean_node = parse_boolean_expression(
        value,
        procedure_defs,
        local_vars,
        global_vars,
        local_lists,
        global_lists,
        broadcast_ids,
        procedure_args,
    )
    if boolean_node:
        return boolean_node

    text = value.strip()
    if text.startswith("(join ") and text.endswith(")"):
        join_body = text[1:-1].strip()
        remainder = join_body[len("join") :].strip()
        parts = split_top_level_whitespace(remainder, 2)
        if len(parts) == 2:
            node = ParsedNode("operator_join")
            node.inputs["STRING1"] = build_input_value(
                parts[0],
                "STRING1",
                broadcast_ids,
                True,
                procedure_defs,
                local_vars,
                global_vars,
                local_lists,
                global_lists,
                procedure_args,
            )
            node.inputs["STRING2"] = build_input_value(
                parts[1],
                "STRING2",
                broadcast_ids,
                True,
                procedure_defs,
                local_vars,
                global_vars,
                local_lists,
                global_lists,
                procedure_args,
            )
            return node

    def maybe_strip_parens(text: str) -> str:
        return strip_wrapping_parens(text)

    math_match: Optional[re.Match[str]] = None
    for candidate in (value, maybe_strip_parens(value)):
        math_match = re.match(r"^\[([^\]]+)\] of \((.+)\)$", candidate)
        if math_match:
            break

    if math_match:
        op_token = math_match.group(1).strip()
        if op_token.endswith(" v"):
            op_token = op_token[:-2].strip()
        if op_token in MATH_OPERATORS:
            opcode = "operator_mathop"
            groups = {"OPERATOR": op_token, "NUM": math_match.group(2).strip()}
        else:
            opcode, groups = match_opcode_line(value, allow_menu_only=False)
    else:
        opcode, groups = match_opcode_line(value, allow_menu_only=False)
    # Avoid wrapping free-form text in parentheses; only already-structured text should match.

    # Disambiguate sensing_of vs mathop when the property token is a math operator
    if opcode == "sensing_of":
        prop = groups.get("PROPERTY", "").strip()
        if prop.endswith(" v"):
            prop = prop[:-2].strip()
        obj = groups.get("OBJECT", "")
        if prop in MATH_OPERATORS:
            opcode = "operator_mathop"
            groups = {"OPERATOR": prop, "NUM": obj}
    if not opcode:
        return None

    # Avoid turning control/event/procedure-definition into inline nodes; inline should be reporter/command blocks
    if (
        opcode in CONTROL_BLOCKS
        or opcode.startswith("event_")
        or opcode == "procedures_definition"
    ):
        return None

    # Skip menu-only patterns (no literals) that would greedily swallow any text, e.g. pen menus
    fmt = OPCODE_MAP.get(opcode, "")
    literal_len = sum(len(lit) for lit, _, _, _ in string.Formatter().parse(fmt) if lit)
    if literal_len == 0 or opcode.endswith("_menu") or opcode.startswith("pen_menu"):
        return None

    inputs: Dict[str, Any] = {}
    fields: Dict[str, Any] = {}

    for name, captured in groups.items():
        if opcode == "sensing_keypressed" and name == "KEY_OPTION":
            inputs[name] = build_key_option_input(captured)
            continue
        if opcode in {"event_whenkeypressed", "sensing_keyoptions"} and name == "KEY_OPTION":
            fields[name] = resolve_field_value(
                name,
                captured,
                local_vars,
                global_vars,
                local_lists,
                global_lists,
                broadcast_ids,
            )
            continue

        if name in OPCODE_FIELDS.get(opcode, set()):
            fields[name] = resolve_field_value(
                name,
                captured,
                local_vars,
                global_vars,
                local_lists,
                global_lists,
                broadcast_ids,
            )
        else:
            inputs[name] = build_input_value(
                captured,
                name,
                broadcast_ids,
                True,
                procedure_defs,
                local_vars,
                global_vars,
                local_lists,
                global_lists,
                procedure_args,
            )

    return ParsedNode(opcode, inputs=inputs, fields=fields)


def build_input_value(
    value: str,
    input_name: str,
    broadcast_ids: Dict[str, str],
    allow_inline: bool,
    procedure_defs: Dict[str, Dict[str, Any]],
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    procedure_args: Optional[Dict[str, str]] = None,
    diag_ctx: Optional[DiagnosticContext] = None,
    line_number: Optional[int] = None,
) -> Any:
    """Build an input value, handling literals, variables, lists, and inline expressions."""
    raw = value.strip("\n\r")
    raw_stripped = raw.strip()
    wrapped_inner: Optional[str] = None
    hex_candidate: str
    hex_candidate = ""
    if (
        (raw_stripped.startswith("[") and raw_stripped.endswith("]"))
        or (raw_stripped.startswith("(") and raw_stripped.endswith(")"))
        or (raw_stripped.startswith("{") and raw_stripped.endswith("}"))
    ):
        wrapped_inner = raw_stripped[1:-1]
    inner = strip_wrappers(raw, strip_inner=False)
    inner_stripped = inner.strip()
    hex_candidate = strip_wrapping_parens(inner_stripped)
    is_color_input = input_name in {"COLOR", "COLOR2"}
    color_shadow_value = [
        9,
        hex_candidate
        if re.match(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", hex_candidate)
        else "#000000",
    ]
    num_val = coerce_number(inner_stripped)

    # Treat empty reporter/boolean placeholders (e.g., "<>", "()", "[]") as intentionally missing
    # inputs so we omit them from the block JSON instead of emitting an unusable literal string.
    if raw_stripped == "<>":
        return None
    if raw_stripped in {"[]", "()", "{}"} or (
        inner_stripped == "" and (wrapped_inner is None or wrapped_inner == "")
    ):
        return default_empty_input(input_name)

    if "BROADCAST" in input_name:
        bid = broadcast_ids.setdefault(inner, gen_id("broadcast"))
        return [1, [11, inner, bid]]

    if input_name == "COLOR_PARAM":
        return build_menu_shadow_input("pen_menu_colorParam", "colorParam", raw)

    if is_color_input:
        if re.match(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", hex_candidate):
            return [1, [9, hex_candidate]]

    # Helper to check if value looks like a menu (ends with " v]" or "v]")
    def is_menu_value(val: str) -> bool:
        stripped = val.strip()
        return stripped.startswith("[") and stripped.endswith("v]")

    if input_name == "DISTANCETOMENU":
        return build_menu_shadow_input("sensing_distancetomenu", "DISTANCETOMENU", raw)

    if input_name == "CLONE_OPTION":
        return build_menu_shadow_input(
            "control_create_clone_of_menu", "CLONE_OPTION", raw
        )

    if input_name == "TOUCHINGOBJECTMENU":
        return build_menu_shadow_input(
            "sensing_touchingobjectmenu", "TOUCHINGOBJECTMENU", raw
        )

    # Only create menu shadows for COSTUME/BACKDROP/SOUND_MENU if the value looks like a menu
    # (e.g., "[costume1 v]"). If it's a reporter expression, let it fall through to normal processing.
    if input_name == "COSTUME" and is_menu_value(raw):
        return build_menu_shadow_input("looks_costume", "COSTUME", raw)

    if input_name == "BACKDROP" and is_menu_value(raw):
        return build_menu_shadow_input("looks_backdrops", "BACKDROP", raw)

    if input_name == "SOUND_MENU" and is_menu_value(raw):
        return build_menu_shadow_input("sound_sounds_menu", "SOUND_MENU", raw)

    if input_name == "OBJECT":
        return build_menu_shadow_input("sensing_of_object_menu", "OBJECT", raw)

    if num_val is not None:
        return [1, [4, num_val]]

    # If this value is curly-wrapped, treat it as a custom-block argument reference.
    # This handles both in-scope args (with known IDs) and orphaned scripts (unknown IDs).
    is_curly_wrapped = raw_stripped.startswith("{") and raw_stripped.endswith("}")
    if is_curly_wrapped:
        arg_inner = raw_stripped[1:-1].strip()
        reporter_opcode = "argument_reporter_string_number"
        if arg_inner.startswith("<") and arg_inner.endswith(">"):
            arg_inner = arg_inner[1:-1].strip()
            reporter_opcode = "argument_reporter_boolean"
        # Use known arg_id if available, otherwise generate a new one
        if procedure_args and arg_inner in procedure_args:
            arg_id = procedure_args[arg_inner]
        else:
            arg_id = gen_id("arg")
        reporter = ParsedNode(reporter_opcode)
        reporter.fields = {"VALUE": [arg_inner, None]}
        reporter.mutation = {}
        return reporter

    if allow_inline:
        inline_node = parse_inline_expression(
            raw,
            procedure_defs,
            local_vars,
            global_vars,
            local_lists,
            global_lists,
            broadcast_ids,
            procedure_args,
        ) or parse_inline_expression(
            inner,
            procedure_defs,
            local_vars,
            global_vars,
            local_lists,
            global_lists,
            broadcast_ids,
            procedure_args,
        )
        if inline_node:
            return inline_node

    if inner in local_vars or inner in global_vars:
        vid = resolve_variable_id(inner, local_vars, global_vars)
        shadow = color_shadow_value if is_color_input else [10, ""]
        return [3, [12, inner, vid], shadow]

    if inner in local_lists or inner in global_lists:
        lid = resolve_list_id(inner, local_lists, global_lists)
        shadow = color_shadow_value if is_color_input else [10, ""]
        return [3, [13, inner, lid], shadow]

    # Warn about potential undefined variable references
    # A paren-wrapped identifier that's not a number and not a known variable/list
    # may indicate a typo or undefined variable
    if (
        diag_ctx is not None
        and raw_stripped.startswith("(")
        and raw_stripped.endswith(")")
        and inner_stripped
        and not inner_stripped.isdigit()
        and re.match(r"^[a-zA-Z_][a-zA-Z0-9_ ]*$", inner_stripped)
    ):
        diag_ctx.warning(f"Unknown reporter or undefined variable '{inner_stripped}'", line_number)

    literal_value = inner
    if wrapped_inner is not None:
        literal_value = wrapped_inner
    if is_color_input:
        return [1, color_shadow_value]
    return [1, [10, literal_value]]
