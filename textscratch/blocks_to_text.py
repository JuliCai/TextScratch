import json
import re
import string
from typing import Any, Dict, List

from .opcodes import CONTROL_BLOCKS, OPCODE_MAP
from .string_utils import escape_text, coerce_number
from .opcode_utils import match_opcode_line


def humanize_touching_menu(value: str) -> str:
    lowered = value.strip().lower().replace("_", " ").strip()
    if lowered == "mouse":
        return "mouse-pointer"
    if lowered == "edge":
        return "edge"
    return value


def humanize_distance_menu(value: str) -> str:
    lowered = value.strip().lower().replace("_", " ").strip()
    if lowered == "mouse":
        return "mouse-pointer"
    if lowered == "myself":
        return "myself"
    return value


def humanize_goto_menu(value: str) -> str:
    lowered = value.strip().lower().replace("_", " ").strip()
    if lowered == "random":
        return "random position"
    if lowered == "mouse":
        return "mouse-pointer"
    return value


def humanize_pointtowards_menu(value: str) -> str:
    lowered = value.strip().lower().replace("_", " ").strip()
    if lowered == "mouse":
        return "mouse-pointer"
    if lowered == "random":
        return "random direction"
    return value


def humanize_of_object_menu(value: str) -> str:
    lowered = value.strip().lower().replace("_", " ").strip()
    if lowered == "stage":
        return "_stage_"
    return value


def humanize_clone_menu(value: str) -> str:
    lowered = value.strip().lower().replace("_", " ").strip()
    if lowered == "myself":
        return "_myself_"
    return value


def parse_input(input_data: Any, blocks: Dict[str, Dict[str, Any]], target=None) -> str:
    if not input_data or len(input_data) < 2:
        return ""

    val = input_data[1]

    if isinstance(val, str):
        return generate_block_code(val, blocks, target=target).strip()

    if isinstance(val, list):
        primitive_type = val[0]
        primitive_value = val[1] if len(val) > 1 else ""

        if primitive_type in [4, 5, 6, 7, 8]:
            return f"[{escape_text(primitive_value)}]"
        if primitive_type == 9:
            return f"({escape_text(primitive_value)})"
        if primitive_type == 10:
            return f"[{escape_text(primitive_value)}]"
        if primitive_type == 11:
            return f"[{escape_text(primitive_value)} v]"
        if primitive_type in {12, 13}:
            name = escape_text(primitive_value)
            kind = "variables" if primitive_type == 12 else "list"
            local = (target or {}).get("variables" if primitive_type == 12 else "lists", {})
            global_scope = (target and not target.get("isStage") and val[2] not in local
                            and any(v[0] == primitive_value for v in local.values()))
            opcode, _ = match_opcode_line(f"({name})", allow_menu_only=False)
            ambiguous = (primitive_type == 13 or coerce_number(primitive_value) is not None
                         or opcode not in {None, "data_variable"} or " :: " in name)
            qualifier = f" :: {kind}" + (" global" if global_scope else "") if ambiguous or global_scope else ""
            return f"({name}{qualifier})"
        return str(primitive_value)

    return ""


def parse_field(field_data: Any) -> str:
    if not field_data:
        return ""
    return escape_text(field_data[0])


def generate_block_code(block_id: str, blocks: Dict[str, Dict[str, Any]], indent_level: int = 0, target=None) -> str:
    if not block_id or block_id not in blocks:
        return ""

    block = blocks[block_id]
    if isinstance(block, list):
        return "    " * indent_level + parse_input([2, block], blocks, target) + "\n"
    opcode = block.get("opcode", "")
    inputs = block.get("inputs", {})
    fields = block.get("fields", {})

    indent = "    " * indent_level
    if opcode in {"data_variable", "data_listcontents"}:
        field = "VARIABLE" if opcode == "data_variable" else "LIST"
        return indent + parse_input([2, [12 if field == "VARIABLE" else 13] + fields[field]], blocks, target) + "\n"
    format_str = OPCODE_MAP.get(opcode, f"UNKNOWN_BLOCK_{opcode}")

    args: Dict[str, str] = {}

    for input_name, input_val in inputs.items():
        if input_name.upper() not in {"SUBSTACK", "SUBSTACK2", "CUSTOM_BLOCK"}:
            args[input_name] = parse_input(input_val, blocks, target)

    for field_name, field_val in fields.items():
        args[field_name] = parse_field(field_val)
        if field_name in {"VARIABLE", "LIST"} and target and not target.get("isStage"):
            local = target.get("variables" if field_name == "VARIABLE" else "lists", {})
            if len(field_val) > 1 and field_val[1] not in local and any(v[0] == field_val[0] for v in local.values()):
                args[field_name] += " :: global"

    if opcode == "sensing_touchingobjectmenu" and "TOUCHINGOBJECTMENU" in args:
        args["TOUCHINGOBJECTMENU"] = humanize_touching_menu(args["TOUCHINGOBJECTMENU"])

    if opcode == "sensing_distancetomenu" and "DISTANCETOMENU" in args:
        args["DISTANCETOMENU"] = humanize_distance_menu(args["DISTANCETOMENU"])

    if opcode in ("motion_goto_menu", "motion_glideto_menu") and "TO" in args:
        args["TO"] = humanize_goto_menu(args["TO"])

    if opcode == "motion_pointtowards_menu" and "TOWARDS" in args:
        args["TOWARDS"] = humanize_pointtowards_menu(args["TOWARDS"])

    if opcode == "sensing_of_object_menu" and "OBJECT" in args:
        args["OBJECT"] = humanize_of_object_menu(args["OBJECT"])

    if opcode == "control_create_clone_of_menu" and "CLONE_OPTION" in args:
        args["CLONE_OPTION"] = humanize_clone_menu(args["CLONE_OPTION"])

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

            parts = re.split(r"%[sb]", proccode)
            types = re.findall(r"%[sb]", proccode)
            def_str = "define "
            for idx, part in enumerate(parts):
                def_str += escape_text(part)
                if idx < len(argument_names):
                    name = escape_text(argument_names[idx])
                    def_str += f"<{name}>" if types[idx] == "%b" else f"({name})"
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
        types = re.findall(r"%[sb]", proccode)
        result_str = ""
        for idx, part in enumerate(parts):
            result_str += escape_text(part)
            if idx < len(argument_ids):
                arg_id = argument_ids[idx]
                if arg_id in inputs:
                    result_str += parse_input(inputs[arg_id], blocks, target)
                else:
                    result_str += "<>" if types[idx] == "%b" else "[]"
        return f"{indent}{result_str}\n"

    try:
        required_keys = [fname for _, fname, _, _ in string.Formatter().parse(format_str) if fname]
        for key in required_keys:
            if key not in args or args[key] == "":
                args[key] = "<>" if ("OPERAND" in key or "CONDITION" in key) else ""
        code = format_str.format(**args)
    except KeyError as exc:
        code = f"{format_str} (Missing arg: {exc})"
    except Exception as exc:
        code = f"Error parsing {opcode}: {exc}"

    result = f"{indent}{code}\n"

    c_blocks = CONTROL_BLOCKS

    if opcode in c_blocks:
        substack_input = inputs.get("substack") or inputs.get("SUBSTACK")
        if substack_input:
            substack_id = substack_input[1]
            while substack_id:
                result += generate_block_code(substack_id, blocks, indent_level + 1, target)
                substack_id = blocks.get(substack_id, {}).get("next")

        if opcode == "control_if_else":
            result += f"{indent}else\n"
            substack2_input = inputs.get("substack2") or inputs.get("SUBSTACK2")
            if substack2_input:
                substack2_id = substack2_input[1]
                while substack2_id:
                    result += generate_block_code(substack2_id, blocks, indent_level + 1, target)
                    substack2_id = blocks.get(substack2_id, {}).get("next")

        result += f"{indent}end\n"

    return result


def generate_target_code(target: Dict[str, Any]) -> str:
    blocks = target.get("blocks", {})
    top_level = [bid for bid, blk in blocks.items() if
                 (isinstance(blk, dict) and blk.get("topLevel")) or
                 (isinstance(blk, list) and len(blk) >= 5)]
    def position(bid):
        block = blocks[bid]
        return (block[4], block[3]) if isinstance(block, list) else (block.get("y", 0), block.get("x", 0))
    top_level.sort(key=position)

    lines: List[str] = []
    
    # Generate code for topLevel blocks only.
    # Zombie blocks (blocks with parent set but not actually referenced) are skipped
    # as they don't appear in the Scratch editor and are orphaned/corrupted data.
    for start_id in top_level:
        current = start_id
        while current:
            lines.append(generate_block_code(current, blocks, target=target))
            block = blocks[current]
            current = block.get("next") if isinstance(block, dict) else None
        lines.append("\n")

    return "".join(lines).rstrip() + "\n" if lines else ""
