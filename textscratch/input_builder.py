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
    unescape_text,
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
    # Repeatedly strip wrapping parens until stable, handling nested parens like
    # (([0.5] * ((ray dy) + [1]))) -> [0.5] * ((ray dy) + [1])
    inner = strip_wrapping_parens(text)
    while inner != text:
        text = inner
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

    opcode, groups = match_opcode_line(value, allow_menu_only=False)
    if opcode in {"data_variable", "data_listcontents"}:
        return None
    if not opcode or opcode in CONTROL_BLOCKS or opcode.startswith("event_"):
        return None

    inputs: Dict[str, Any] = {}
    fields: Dict[str, Any] = {}

    for name, captured in groups.items():
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
    raw = value.strip()
    raw_stripped = raw
    inner = strip_wrappers(raw, strip_inner=False)
    inner_stripped = inner.strip()
    is_color_input = input_name in {"COLOR", "COLOR2"}
    color_shadow_value = [9, "#000000"]
    is_square = raw.startswith("[") and raw.endswith("]")
    is_menu = is_square and inner.endswith(" v")
    is_reporter = raw.startswith(("(", "<", "{"))

    if raw == "<>":
        return None
    qualifier = re.fullmatch(r"\((.*) :: (variables|list)( global)?\)", raw)
    if qualifier:
        name, kind, scope = qualifier.groups()
        name = unescape_text(name)
        if kind == "variables":
            vid = resolve_variable_id(name, {} if scope else local_vars, global_vars)
            return [3, [12, name, vid], [10, ""]]
        lid = resolve_list_id(name, {} if scope else local_lists, global_lists)
        return [3, [13, name, lid], [10, ""]]
    if is_color_input and re.fullmatch(r"#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}", inner):
        color = inner if len(inner) == 7 else "#" + "".join(c * 2 for c in inner[1:])
        return [1, [9, color]]

    # Menus accept expressions too. Only literal menu selections become shadows.
    from .constants import MENU_SHADOW_FOR_INPUT
    if input_name == "BROADCAST_INPUT" and not is_reporter:
        name = unescape_text(inner[:-2] if is_menu else inner)
        bid = broadcast_ids.setdefault(name, gen_id("broadcast"))
        return [1, [11, name, bid]]
    if input_name in MENU_SHADOW_FOR_INPUT and not is_reporter:
        opcode, field = MENU_SHADOW_FOR_INPUT[input_name]
        return build_menu_shadow_input(opcode, field, raw)
    if input_name == "COLOR_PARAM" and raw.endswith(" v)"):
        return build_menu_shadow_input("pen_menu_colorParam", "colorParam", raw)

    # Square brackets always contain literal text, even if it is a variable name,
    # an expression, leading zeroes, whitespace, Infinity, or a very large integer.
    if is_square:
        return [1, [10, unescape_text(inner)]]
    if raw in {"", "()", "{}"}:
        return default_empty_input(input_name)
    if raw.startswith("(") and raw.endswith(")") and coerce_number(inner) is not None:
        return [1, [4, inner]]

    # If this value is curly-wrapped, treat it as a custom-block argument reference.
    # This handles both in-scope args (with known IDs) and orphaned scripts (unknown IDs).
    is_curly_wrapped = raw_stripped.startswith("{") and raw_stripped.endswith("}")
    if is_curly_wrapped:
        arg_inner = raw_stripped[1:-1]
        reporter_opcode = "argument_reporter_string_number"
        if arg_inner.startswith("<") and arg_inner.endswith(">"):
            arg_inner = arg_inner[1:-1]
            reporter_opcode = "argument_reporter_boolean"
        arg_inner = unescape_text(arg_inner)
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
        )
        if inline_node:
            return inline_node

    inner = unescape_text(inner)
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
    if is_color_input:
        return [1, color_shadow_value]
    return [1, [10, literal_value]]
