"""Block emission - converting ParsedNodes to Scratch block JSON."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from .constants import MENU_SHADOW_OPCODES, NUMERIC_INPUTS
from .field_utils import default_empty_input
from .opcodes import CONTROL_BLOCKS
from .opcode_utils import create_menu_shadow_block, is_boolean_reporter
from .parsed_node import ParsedNode
from .utils import gen_id


def is_menu_shadow(opcode: str) -> bool:
    """Check if an opcode represents a menu shadow block."""
    return (
        opcode in MENU_SHADOW_OPCODES
        or opcode.endswith("menu")
        or opcode.startswith("pen_menu")
    )


def emit_blocks(
    nodes: List[ParsedNode],
    blocks: Dict[str, Dict[str, Any]],
    parent_id: Optional[str],
    top_level: bool,
    x: int,
    y: int,
) -> Tuple[Optional[str], Optional[str]]:
    """Emit ParsedNodes as Scratch block JSON dictionaries.
    
    Returns a tuple of (first_block_id, last_block_id).
    """
    first_id: Optional[str] = None
    prev_id: Optional[str] = None

    for node in nodes:
        block_id = gen_id("block")
        block_entry: Dict[str, Any] = {
            "opcode": node.opcode,
            "next": None,
            "parent": prev_id if prev_id else parent_id,
            "inputs": {},
            "fields": dict(node.fields),
            "shadow": False,
            "topLevel": False,
        }

        if node.mutation:
            block_entry["mutation"] = node.mutation

        boolean_inputs = {"CONDITION"} if node.opcode in CONTROL_BLOCKS | {"control_wait_until"} else set()
        if node.opcode in {"operator_and", "operator_or"}:
            boolean_inputs = {"OPERAND1", "OPERAND2"}
        elif node.opcode == "operator_not":
            boolean_inputs = {"OPERAND"}
        elif node.opcode == "procedures_call":
            boolean_inputs = {arg for arg, kind in zip(
                json.loads(node.mutation.get("argumentids", "[]")),
                re.findall(r"%[sb]", node.mutation["proccode"])) if kind == "%b"}

        for input_name, raw_val in (node.inputs or {}).items():
            if raw_val is None:
                continue
            shadow_kind = NUMERIC_INPUTS.get(node.opcode, {}).get(input_name, 10)
            shadow = [9, "#000000"] if input_name in {"COLOR", "COLOR2"} else [shadow_kind, ""]
            if isinstance(raw_val, ParsedNode):
                nested_first, _ = emit_blocks([raw_val], blocks, block_id, False, x, y)
                if is_menu_shadow(raw_val.opcode):
                    blocks[nested_first]["shadow"] = True
                    block_entry["inputs"][input_name] = [1, nested_first]
                    continue
                active = nested_first
            elif raw_val[0] == 1:
                primitive = list(raw_val[1])
                if primitive[0] in {4, 5, 6, 7, 8, 10}:
                    primitive[0] = shadow_kind
                block_entry["inputs"][input_name] = [1, primitive]
                continue
            else:
                active = raw_val[1]
            if input_name in boolean_inputs:
                block_entry["inputs"][input_name] = [2, active]
            else:
                menu_shadow = create_menu_shadow_block(input_name, block_id, blocks, node.opcode)
                if input_name == "BROADCAST_INPUT":
                    # A broadcast reporter still needs a broadcast-menu fallback.
                    shadow = [11, "message1", gen_id("broadcast")]
                block_entry["inputs"][input_name] = [3, active, menu_shadow or shadow]

        if prev_id:
            blocks[prev_id]["next"] = block_id

        if node.procedure_info:
            proto_id = node.procedure_info["prototype_id"]
            mutation = {
                "tagName": "mutation",
                "children": [],
                "proccode": node.procedure_info["proccode"],
                "argumentids": json.dumps(node.procedure_info["arg_ids"]),
                "argumentnames": json.dumps(node.procedure_info["arg_names"]),
                "argumentdefaults": json.dumps(
                    [False if t == "%b" else "" for t in node.procedure_info.get("arg_types", ["%s"] * len(node.procedure_info["arg_names"]))]
                ),
                "warp": "true" if node.procedure_info.get("warp") else "false",
            }

            proto_inputs: Dict[str, Any] = {}
            for index, (name, arg_id) in enumerate(zip(
                node.procedure_info["arg_names"], node.procedure_info["arg_ids"]
            )):
                arg_reporter_id = gen_id("arg")
                proto_inputs[arg_id] = [1, arg_reporter_id]
                blocks[arg_reporter_id] = {
                    "opcode": "argument_reporter_boolean" if node.procedure_info.get("arg_types", ["%s"] * len(node.procedure_info["arg_names"]))[index] == "%b" else "argument_reporter_string_number",
                    "next": None,
                    "parent": proto_id,
                    "inputs": {},
                    "fields": {"VALUE": [name, None]},
                    "shadow": True,
                    "topLevel": False,
                }

            blocks[proto_id] = {
                "opcode": "procedures_prototype",
                "next": None,
                "parent": block_id,
                "inputs": proto_inputs,
                "fields": {},
                "shadow": True,
                "topLevel": False,
                "mutation": mutation,
            }

            block_entry["inputs"]["custom_block"] = [1, proto_id]

        if block_entry.get("topLevel") is None:
            block_entry["topLevel"] = False

        blocks[block_id] = block_entry

        if top_level and prev_id is None and parent_id is None:
            block_entry["topLevel"] = True
            block_entry["x"] = x
            block_entry["y"] = y

        if node.opcode in CONTROL_BLOCKS:
            if node.children:
                child_first, child_last = emit_blocks(
                    node.children, blocks, block_id, False, x, y
                )
                if child_first:
                    block_entry.setdefault("inputs", {})["SUBSTACK"] = [2, child_first]
                if child_last:
                    blocks[child_last]["next"] = None
            if node.opcode == "control_if_else" and node.children2:
                child_first2, child_last2 = emit_blocks(
                    node.children2, blocks, block_id, False, x, y
                )
                if child_first2:
                    block_entry.setdefault("inputs", {})["SUBSTACK2"] = [2, child_first2]
                if child_last2:
                    blocks[child_last2]["next"] = None

        if first_id is None:
            first_id = block_id
        prev_id = block_id

    return first_id, prev_id
