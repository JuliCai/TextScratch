"""Convert scratchblocks text format to Scratch 3.0 block JSON.

This module provides the main entry point `code_to_blocks` for converting
scratchblocks text files into Scratch block dictionaries.

The implementation is split across several submodules:
- constants: Shared constants
- parsed_node: The ParsedNode class
- string_utils: String manipulation utilities
- field_utils: Field resolution and menu handling
- opcode_utils: Opcode-related utilities
- input_builder: Input value building and expression parsing
- procedure_utils: Procedure (custom block) utilities
- block_parser: Block parsing from text
- block_emitter: Converting ParsedNodes to JSON
- diagnostics: Error and warning reporting
"""

import os
import re
from typing import Any, Dict, List, Optional

from .block_emitter import emit_blocks
from .block_parser import parse_block_list, parse_line_to_node
from .diagnostics import DiagnosticContext
from .procedure_utils import build_procedure_call_pattern, is_space_separated_proccode
from .string_utils import split_scripts
from .utils import gen_id

# Re-export commonly used items for backwards compatibility
from .constants import BINARY_OPERATOR_TOKENS, MENU_SHADOW_FOR_INPUT, MENU_SHADOW_OPCODES
from .parsed_node import ParsedNode
from .string_utils import (
    coerce_number,
    remove_literal_top_level,
    split_top_level,
    split_top_level_whitespace,
    strip_inline_literals,
    strip_wrappers,
    strip_wrapping_parens,
)
from .field_utils import (
    build_key_option_input,
    build_menu_shadow_input,
    default_empty_input,
    normalize_distance_menu_to_sb3,
    normalize_menu_field_value,
    normalize_touching_menu_to_sb3,
    resolve_field_value,
    resolve_list_id,
    resolve_variable_id,
)
from .opcode_utils import (
    create_menu_shadow_block,
    is_boolean_reporter,
    is_menu_shadow,
    is_reporter_shape,
    match_opcode_line,
)
from .input_builder import (
    build_input_value,
    parse_balanced_math_expression,
    parse_boolean_expression,
    parse_inline_expression,
)
from .procedure_utils import match_space_separated_call


def code_to_blocks(
    code_path: str,
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    broadcast_ids: Dict[str, str],
    diag_ctx: Optional[DiagnosticContext] = None,
) -> Dict[str, Any]:
    """Convert a scratchblocks text file to Scratch block JSON.
    
    Args:
        code_path: Path to the scratchblocks text file.
        local_vars: Dictionary mapping local variable names to IDs.
        global_vars: Dictionary mapping global variable names to IDs.
        local_lists: Dictionary mapping local list names to IDs.
        global_lists: Dictionary mapping global list names to IDs.
        broadcast_ids: Dictionary mapping broadcast names to IDs.
        diag_ctx: Optional diagnostic context for error/warning collection.
    
    Returns:
        A dictionary of block IDs to block definitions.
    """
    if not code_path or not code_path.strip() or not os.path.exists(code_path):
        return {}
    with open(code_path, "r", encoding="utf-8") as handle:
        content = handle.read()

    scripts = split_scripts(content)
    blocks: Dict[str, Dict[str, Any]] = {}
    procedure_defs: Dict[str, Dict[str, Any]] = {}
    y_pos = 0

    # Pre-register Scratch Addons logging procedures (log, warn, error).
    # These have zero-width space chars and no local definition.
    for sa_name in ("log", "warn", "error"):
        # The proccode uses zero-width spaces: \u200b\u200b<name>\u200b\u200b %s
        proccode = f"\u200b\u200b{sa_name}\u200b\u200b %s"
        arg_id = gen_id("arg")
        procedure_defs[proccode] = {
            "proccode": proccode,
            "arg_ids": [arg_id],
            "arg_names": ["message"],
            "warp": False,
            "lead": f"\u200b\u200b{sa_name}\u200b\u200b",
            "first_token": f"\u200b\u200b{sa_name}\u200b\u200b",
            "call_pattern": build_procedure_call_pattern(proccode),
        }

    # Pre-scan to collect procedure signatures so calls earlier in the file can be parsed.
    for script in scripts:
        for _, text, _ in script:
            if text.startswith("define "):
                parse_line_to_node(
                    text,
                    procedure_defs,
                    local_vars,
                    global_vars,
                    local_lists,
                    global_lists,
                    broadcast_ids,
                    None,
                    None,
                    None,  # diag_ctx
                    None,  # line_number
                )

    procedure_index: Dict[str, List[Dict[str, Any]]] = {}
    fallback_procedures: List[Dict[str, Any]] = []
    for info in procedure_defs.values():
        lead = info.get("lead", "")
        token = info.get("first_token", "")

        # Proccodes that start with a placeholder (empty lead/token) are very loose
        # and can accidentally match unrelated lines. Keep them out of the primary
        # lookup and try them only as a later fallback.
        if lead or token:
            procedure_index.setdefault(f"lead:{lead}", []).append(info)
            procedure_index.setdefault(f"token:{token}", []).append(info)
        else:
            fallback_procedures.append(info)

    if fallback_procedures:
        procedure_index["__fallback__"] = fallback_procedures

    for script in scripts:
        nodes, _, _ = parse_block_list(
            script,
            0,
            0,
            procedure_defs,
            procedure_index,
            local_vars,
            global_vars,
            local_lists,
            global_lists,
            broadcast_ids,
            None,
            diag_ctx,
        )
        emit_blocks(nodes, blocks, None, True, 0, y_pos)
        y_pos += 120

    return blocks
