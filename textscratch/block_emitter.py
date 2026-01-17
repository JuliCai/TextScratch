"""Block emission - converting ParsedNodes to Scratch block JSON."""

import json
from typing import Any, Dict, List, Optional, Tuple

from .constants import MENU_SHADOW_OPCODES
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

        # Resolve inputs, emitting inline reporter blocks when necessary
        for input_name, raw_val in (node.inputs or {}).items():
            if raw_val is None:
                continue
            if isinstance(raw_val, ParsedNode):
                if (
                    raw_val.opcode in {"data_variable", "data_listcontents"}
                    and not raw_val.children
                    and not raw_val.children2
                ):
                    fields = raw_val.fields
                    if raw_val.opcode == "data_variable":
                        name, vid = fields.get("VARIABLE", ["", None])
                        block_entry["inputs"][input_name] = [3, [12, name, vid], [10, ""]]
                    else:
                        name, lid = fields.get("LIST", ["", None])
                        block_entry["inputs"][input_name] = [3, [13, name, lid], [10, ""]]
                else:
                    nested_first, _ = emit_blocks(
                        [raw_val], blocks, block_id, False, x, y
                    )
                    if nested_first:
                        if is_menu_shadow(raw_val.opcode):
                            blocks[nested_first]["shadow"] = True
                            block_entry["inputs"][input_name] = [1, nested_first]
                        else:
                            if is_boolean_reporter(raw_val.opcode):
                                block_entry["inputs"][input_name] = [2, nested_first]
                            else:
                                # Check if this input needs a menu shadow block
                                shadow_id = create_menu_shadow_block(
                                    input_name, block_id, blocks
                                )
                                if shadow_id:
                                    block_entry["inputs"][input_name] = [
                                        3,
                                        nested_first,
                                        shadow_id,
                                    ]
                                else:
                                    empty_shadow = default_empty_input(input_name)
                                    block_entry["inputs"][input_name] = [
                                        3,
                                        nested_first,
                                        empty_shadow[1],
                                    ]
                    else:
                        block_entry["inputs"][input_name] = default_empty_input(
                            input_name
                        )
            else:
                block_entry["inputs"][input_name] = raw_val

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
                    ["" for _ in node.procedure_info["arg_names"]]
                ),
                "warp": "true" if node.procedure_info.get("warp") else "false",
            }

            proto_inputs: Dict[str, Any] = {}
            for name, arg_id in zip(
                node.procedure_info["arg_names"], node.procedure_info["arg_ids"]
            ):
                arg_reporter_id = gen_id("arg")
                proto_inputs[arg_id] = [1, arg_reporter_id]
                blocks[arg_reporter_id] = {
                    "opcode": "argument_reporter_string_number",
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
