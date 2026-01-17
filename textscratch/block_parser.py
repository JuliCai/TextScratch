"""Block parsing from scratchblocks text."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from .constants import MENU_SHADOW_OPCODES
from .diagnostics import DiagnosticContext
from .field_utils import resolve_field_value
from .input_builder import build_input_value
from .opcodes import CONTROL_BLOCKS, OPCODE_FIELDS
from .opcode_utils import is_reporter_shape, match_opcode_line
from .parsed_node import ParsedNode
from .procedure_utils import (
    build_procedure_call_pattern,
    is_space_separated_proccode,
    match_space_separated_call,
)
from .string_utils import strip_wrappers
from .utils import gen_id


# Sound effect names - used to disambiguate sound vs looks effect blocks
SOUND_EFFECT_NAMES = {"PITCH", "PAN"}


def disambiguate_effect_opcode(opcode: str, groups: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
    """Disambiguate between looks and sound effect blocks based on effect name.
    
    Both looks_changeeffectby/looks_seteffectto and sound_changeeffectby/sound_seteffectto
    have the same text pattern. We determine which one to use based on the EFFECT field value.
    
    Returns the (possibly updated) opcode and groups dict.
    """
    if opcode not in ("looks_changeeffectby", "looks_seteffectto"):
        return opcode, groups
    
    effect_value = groups.get("EFFECT", "")
    # Strip wrappers and normalize
    effect_clean = strip_wrappers(effect_value).upper()
    
    if effect_clean in SOUND_EFFECT_NAMES:
        # Make a copy to avoid modifying the original
        new_groups = dict(groups)
        
        # Map to sound effect opcode and remap input names
        # looks uses CHANGE, sound uses VALUE
        if opcode == "looks_changeeffectby":
            if "CHANGE" in new_groups:
                new_groups["VALUE"] = new_groups.pop("CHANGE")
            return "sound_changeeffectby", new_groups
        elif opcode == "looks_seteffectto":
            # Both use VALUE, no remapping needed
            return "sound_seteffectto", new_groups
    
    return opcode, groups


def parse_line_to_node(
    line: str,
    procedure_defs: Dict[str, Dict[str, Any]],
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    broadcast_ids: Dict[str, str],
    procedure_index: Optional[Dict[str, List[Dict[str, Any]]]],
    procedure_args: Optional[Dict[str, str]],
    diag_ctx: Optional[DiagnosticContext] = None,
    line_number: Optional[int] = None,
) -> Optional[ParsedNode]:
    """Parse a single line of scratchblocks text into a ParsedNode."""
    # Import here to avoid circular dependency
    from .input_builder import build_key_option_input, parse_inline_expression
    from .field_utils import build_menu_shadow_input

    if line.startswith("define "):
        content = line[len("define ") :]
        warp_flag = content.endswith(" #norefresh")
        if warp_flag:
            content = content[: -len(" #norefresh")]

        arg_names: List[str] = []
        for match in re.finditer(r"\((.*?)\)|\{(.*?)\}", content):
            arg = match.group(1) if match.group(1) is not None else match.group(2)
            arg_names.append(arg)
        base = re.sub(r"\(.*?\)|\{.*?\}", "%s", content).strip()
        existing = procedure_defs.get(base)
        if existing:
            info = existing
            info["warp"] = info.get("warp") or warp_flag
            info.setdefault("call_pattern", build_procedure_call_pattern(base))
            info.setdefault("prototype_id", gen_id("proc_proto"))
            info.setdefault("lead", base.split("%", 1)[0].strip())
            info.setdefault("first_token", base.split()[0] if base.split() else "")
            info.setdefault("space_separated", is_space_separated_proccode(base))
            info.setdefault(
                "inline_literals",
                [
                    part.strip()
                    for part in re.split(r"(%s|%b)", base)
                    if part and part not in {"%s", "%b"} and part.strip()
                ],
            )
        else:
            arg_ids = [gen_id("arg") for _ in arg_names]
            info = {
                "proccode": base,
                "arg_names": arg_names,
                "arg_ids": arg_ids,
                "warp": warp_flag,
            }
            info["call_pattern"] = build_procedure_call_pattern(base)
            info["prototype_id"] = gen_id("proc_proto")
            info["lead"] = base.split("%", 1)[0].strip()
            info["first_token"] = base.split()[0] if base.split() else ""
            info["space_separated"] = is_space_separated_proccode(base)
            info["inline_literals"] = [
                part.strip()
                for part in re.split(r"(%s|%b)", base)
                if part and part not in {"%s", "%b"} and part.strip()
            ]
            procedure_defs[base] = info

        node = ParsedNode("procedures_definition")
        node.procedure_info = info
        return node

    line_first_token = line.split()[0] if line.split() else ""
    split_markers = ["(", "{"]
    split_pos = len(line)
    for marker in split_markers:
        pos = line.find(marker)
        if pos != -1 and pos < split_pos:
            split_pos = pos
    line_lead = line[:split_pos].strip()

    def try_procedure_candidates(candidate_list: List[Dict[str, Any]]) -> Optional[ParsedNode]:
        seen: set[int] = set()
        for info in candidate_list:
            marker = id(info)
            if marker in seen:
                continue
            seen.add(marker)

            args: Optional[Tuple[str, ...]] = None
            if info.get("space_separated"):
                space_args = match_space_separated_call(line, info)
                if space_args:
                    args = tuple(space_args)

            if args is None:
                match = info["call_pattern"].match(line)
                if match:
                    args = match.groups()

            if args is None:
                continue

            node = ParsedNode("procedures_call")
            node.mutation = {
                "tagName": "mutation",
                "children": [],
                "proccode": info["proccode"],
                "argumentids": json.dumps(info["arg_ids"]),
                "argumentnames": json.dumps(info["arg_names"]),
                "argumentdefaults": json.dumps(["" for _ in info["arg_names"]]),
                "warp": "true" if info.get("warp") else "false",
            }
            node.inputs = {}
            for idx, val in enumerate(args):
                if idx < len(info["arg_ids"]):
                    arg_id = info["arg_ids"][idx]
                    node.inputs[arg_id] = build_input_value(
                        val,
                        arg_id,
                        broadcast_ids,
                        True,
                        procedure_defs,
                        local_vars,
                        global_vars,
                        local_lists,
                        global_lists,
                        procedure_args,
                        diag_ctx,
                        line_number,
                    )
            return node
        return None

    candidates: List[Dict[str, Any]] = []
    fallback_candidates: List[Dict[str, Any]] = []
    if procedure_index is not None:
        for key in (
            f"lead:{line_lead}",
            f"token:{line_first_token}",
        ):
            candidates.extend(procedure_index.get(key, []))
        fallback_candidates.extend(procedure_index.get("__fallback__", []))
    else:
        candidates = list(procedure_defs.values())

    node = try_procedure_candidates(candidates)
    if node:
        return node

    inline_node = parse_inline_expression(
        line,
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

    opcode, groups = match_opcode_line(line, allow_menu_only=False)
    if opcode:
        # Disambiguate effect blocks (looks vs sound) based on effect name
        opcode, groups = disambiguate_effect_opcode(opcode, groups)
        
        if opcode in MENU_SHADOW_OPCODES:
            return None
        inputs: Dict[str, Any] = {}
        fields: Dict[str, Any] = {}

        for name, value in groups.items():
            if opcode == "sensing_keypressed" and name == "KEY_OPTION":
                inputs[name] = build_key_option_input(value)
                continue
            if opcode in {"event_whenkeypressed", "sensing_keyoptions"} and name == "KEY_OPTION":
                fields[name] = resolve_field_value(
                    name,
                    value,
                    local_vars,
                    global_vars,
                    local_lists,
                    global_lists,
                    broadcast_ids,
                )
                continue
            
            # Helper to check if value looks like a menu (ends with " v]" or "v]")
            def is_menu_value(val: str) -> bool:
                stripped = val.strip()
                return stripped.startswith("[") and stripped.endswith("v]")
            
            # Handle motion block menu inputs (TO for goto/glideto, TOWARDS for pointtowards)
            # Only create menu shadows if the value looks like a menu, not a reporter
            if opcode in ("motion_goto", "motion_glideto") and name == "TO" and is_menu_value(value):
                inputs[name] = build_menu_shadow_input("motion_goto_menu", "TO", value)
                continue
            if opcode == "motion_pointtowards" and name == "TOWARDS" and is_menu_value(value):
                inputs[name] = build_menu_shadow_input("motion_pointtowards_menu", "TOWARDS", value)
                continue

            if name in OPCODE_FIELDS.get(opcode, set()):
                fields[name] = resolve_field_value(
                    name,
                    value,
                    local_vars,
                    global_vars,
                    local_lists,
                    global_lists,
                    broadcast_ids,
                    diag_ctx,
                    line_number,
                )
            else:
                inputs[name] = build_input_value(
                    value,
                    name,
                    broadcast_ids,
                    True,
                    procedure_defs,
                    local_vars,
                    global_vars,
                    local_lists,
                    global_lists,
                    procedure_args,
                    diag_ctx,
                    line_number,
                )

        return ParsedNode(opcode, inputs=inputs, fields=fields)

    fallback_node = try_procedure_candidates(fallback_candidates)
    if fallback_node:
        return fallback_node

    # Report unknown block if diagnostics enabled
    if diag_ctx is not None and line.strip():
        # Extract a shortened version of the block for the error message
        first_token = line.split()[0] if line.split() else line
        # Limit message length
        block_preview = line[:50] + "..." if len(line) > 50 else line
        diag_ctx.error(f"Unknown block '{first_token}'", line_number, block_preview)

    return None


def parse_block_list(
    lines: List[Tuple[int, str, int]],
    idx: int,
    indent: int,
    procedure_defs: Dict[str, Dict[str, Any]],
    procedure_index: Optional[Dict[str, List[Dict[str, Any]]]],
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    broadcast_ids: Dict[str, str],
    procedure_args: Optional[Dict[str, str]],
    diag_ctx: Optional[DiagnosticContext] = None,
) -> Tuple[List[ParsedNode], int, bool]:
    """Parse a list of block lines into ParsedNodes, handling nesting.
    
    Args:
        lines: List of (indent_level, line_text, line_number) tuples.
        idx: Starting index in lines.
        indent: Current indentation level.
        procedure_defs: Dictionary of procedure definitions.
        procedure_index: Index for quick procedure lookup.
        local_vars: Local variable name to ID mapping.
        global_vars: Global variable name to ID mapping.
        local_lists: Local list name to ID mapping.
        global_lists: Global list name to ID mapping.
        broadcast_ids: Broadcast name to ID mapping.
        procedure_args: Current procedure argument name to ID mapping.
        diag_ctx: Optional diagnostic context for error/warning collection.
    
    Returns:
        Tuple of (parsed_nodes, new_index, hit_else_flag).
    """
    nodes: List[ParsedNode] = []
    hit_else = False
    active_proc_args = dict(procedure_args) if procedure_args else None

    while idx < len(lines):
        current_indent, text, line_num = lines[idx]
        if current_indent < indent:
            if text == "else" and current_indent == indent - 1:
                hit_else = True
                idx += 1
            break
        if text == "else":
            hit_else = True
            idx += 1
            break

        if text == "end":
            idx += 1
            # Skip explicit terminators; indentation already tells us when to stop.
            continue

        node = parse_line_to_node(
            text,
            procedure_defs,
            local_vars,
            global_vars,
            local_lists,
            global_lists,
            broadcast_ids,
            procedure_index,
            active_proc_args,
            diag_ctx,
            line_num,
        )

        idx += 1

        if node is None:
            continue

        # Skip reporter/boolean nodes only when nested; allow top-level loose reporters to persist.
        if is_reporter_shape(node.opcode) and indent > 0:
            continue

        if node.procedure_info:
            active_proc_args = {
                name: arg_id
                for name, arg_id in zip(
                    node.procedure_info.get("arg_names", []),
                    node.procedure_info.get("arg_ids", []),
                )
            }

        if node.opcode in CONTROL_BLOCKS:
            children, idx, saw_else = parse_block_list(
                lines,
                idx,
                indent + 1,
                procedure_defs,
                procedure_index,
                local_vars,
                global_vars,
                local_lists,
                global_lists,
                broadcast_ids,
                active_proc_args,
                diag_ctx,
            )
            node.children = children
            if saw_else:
                if node.opcode == "control_if":
                    node.opcode = "control_if_else"
                if node.opcode == "control_if_else":
                    children2, idx, _ = parse_block_list(
                        lines,
                        idx,
                        indent + 1,
                        procedure_defs,
                        procedure_index,
                        local_vars,
                        global_vars,
                        local_lists,
                        global_lists,
                        broadcast_ids,
                        active_proc_args,
                        diag_ctx,
                    )
                    node.children2 = children2

        nodes.append(node)

    return nodes, idx, hit_else
