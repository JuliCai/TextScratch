import json
import string
from typing import Any, Dict, List

from .opcodes import CONTROL_BLOCKS, OPCODE_MAP


def parse_input(input_data: Any, blocks: Dict[str, Dict[str, Any]]) -> str:
    if not input_data or len(input_data) < 2:
        return ""

    val = input_data[1]

    if isinstance(val, str):
        return generate_block_code(val, blocks).strip()

    if isinstance(val, list):
        primitive_type = val[0]
        primitive_value = val[1] if len(val) > 1 else ""

        if primitive_type in [4, 5, 6, 7, 8]:
            return f"[{primitive_value}]"
        if primitive_type == 9:
            return f"({primitive_value})"
        if primitive_type == 10:
            return f"[{primitive_value}]"
        if primitive_type == 11:
            return primitive_value
        if primitive_type == 12:
            return f"({primitive_value})"
        if primitive_type == 13:
            return f"({primitive_value})"
        return str(primitive_value)

    return ""


def parse_field(field_data: Any) -> str:
    if not field_data:
        return ""
    return field_data[0]


def generate_block_code(block_id: str, blocks: Dict[str, Dict[str, Any]], indent_level: int = 0) -> str:
    if not block_id or block_id not in blocks:
        return ""

    block = blocks[block_id]
    opcode = block.get("opcode", "")
    inputs = block.get("inputs", {})
    fields = block.get("fields", {})

    indent = "    " * indent_level
    format_str = OPCODE_MAP.get(opcode, f"UNKNOWN_BLOCK_{opcode}")

    args: Dict[str, str] = {}

    for input_name, input_val in inputs.items():
        args[input_name] = parse_input(input_val, blocks)

    for field_name, field_val in fields.items():
        args[field_name] = parse_field(field_val)

    if opcode == "procedures_definition":
        custom_block_id = inputs.get("custom_block", [None, None])[1]
        if custom_block_id and custom_block_id in blocks:
            proto = blocks[custom_block_id]
            mutation = proto.get("mutation", {})
            proccode = mutation.get("proccode", "")
            warp_flag = str(mutation.get("warp", "false")).lower() == "true"
            try:
                argument_names = json.loads(mutation.get("argumentnames", "[]"))
            except json.JSONDecodeError:
                argument_names = []

            parts = proccode.replace("%b", "%s").split("%s")
            def_str = "define "
            for idx, part in enumerate(parts):
                def_str += part
                if idx < len(argument_names):
                    def_str += f"({argument_names[idx]})"
            if warp_flag:
                def_str += " #norefresh"
            return f"{indent}{def_str}\n"
        return f"{indent}define unknown\n"

    if opcode == "procedures_call":
        mutation = block.get("mutation", {})
        proccode = mutation.get("proccode", "")
        try:
            argument_ids = json.loads(mutation.get("argumentids", "[]"))
        except json.JSONDecodeError:
            argument_ids = []

        parts = proccode.replace("%b", "%s").split("%s")
        result_str = ""
        for idx, part in enumerate(parts):
            result_str += part
            if idx < len(argument_ids):
                arg_id = argument_ids[idx]
                if arg_id in inputs:
                    result_str += parse_input(inputs[arg_id], blocks)
                else:
                    result_str += "[]"
        return f"{indent}{result_str}\n"

    try:
        required_keys = [fname for _, fname, _, _ in string.Formatter().parse(format_str) if fname]
        for key in required_keys:
            if key not in args:
                args[key] = "<>" if ("OPERAND" in key or "CONDITION" in key) else ""
        code = format_str.format(**args)
    except KeyError as exc:
        code = f"{format_str} (Missing arg: {exc})"
    except Exception as exc:
        code = f"Error parsing {opcode}: {exc}"

    result = f"{indent}{code}\n"

    c_blocks = {"control_forever", "control_repeat", "control_repeat_until", "control_if", "control_if_else"}

    if opcode in c_blocks:
        substack_input = inputs.get("substack") or inputs.get("SUBSTACK")
        if substack_input:
            substack_id = substack_input[1]
            while substack_id:
                result += generate_block_code(substack_id, blocks, indent_level + 1)
                substack_id = blocks.get(substack_id, {}).get("next")

        if opcode == "control_if_else":
            result += f"{indent}else\n"
            substack2_input = inputs.get("substack2") or inputs.get("SUBSTACK2")
            if substack2_input:
                substack2_id = substack2_input[1]
                while substack2_id:
                    result += generate_block_code(substack2_id, blocks, indent_level + 1)
                    substack2_id = blocks.get(substack2_id, {}).get("next")

        result += f"{indent}end\n"

    return result


def generate_target_code(target: Dict[str, Any]) -> str:
    blocks = target.get("blocks", {})
    top_level = [bid for bid, blk in blocks.items() if blk.get("topLevel")]
    top_level.sort(key=lambda bid: (blocks[bid].get("y", 0), blocks[bid].get("x", 0)))

    lines: List[str] = []
    for start_id in top_level:
        current = start_id
        while current:
            lines.append(generate_block_code(current, blocks))
            current = blocks[current].get("next")
        lines.append("\n")

    return "".join(lines).rstrip() + "\n" if lines else ""
