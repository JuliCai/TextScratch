import json
import os
import re
import string
from typing import Any, Dict, List, Optional, Tuple

from .opcodes import (
    CONTROL_BLOCKS,
    MATH_OPERATORS,
    OPCODE_FIELDS,
    OPCODE_MAP,
    OPCODE_PATTERNS,
)
from .utils import gen_id


class ParsedNode:
    def __init__(
        self,
        opcode: str,
        inputs: Optional[Dict[str, Any]] = None,
        fields: Optional[Dict[str, Any]] = None,
        mutation: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.opcode = opcode
        self.inputs = inputs or {}
        self.fields = fields or {}
        self.mutation = mutation or {}
        self.children: List[ParsedNode] = []
        self.children2: List[ParsedNode] = []
        self.procedure_info: Optional[Dict[str, Any]] = None


def split_scripts(content: str) -> List[List[Tuple[int, str]]]:
    scripts: List[List[Tuple[int, str]]] = []
    current: List[Tuple[int, str]] = []
    for raw_line in content.splitlines():
        if not raw_line.strip():
            if current:
                scripts.append(current)
                current = []
            continue
        indent_spaces = len(raw_line) - len(raw_line.lstrip(" "))
        indent_level = indent_spaces // 4
        current.append((indent_level, raw_line.strip()))
    if current:
        scripts.append(current)
    return scripts


def strip_wrappers(val: str) -> str:
    text = val.strip()
    if (text.startswith("[") and text.endswith("]")) or (text.startswith("(") and text.endswith(")")):
        return text[1:-1].strip()
    return text


def coerce_number(val: str) -> Optional[float]:
    try:
        return float(val)
    except ValueError:
        return None


def parse_inline_expression(
    value: str,
    procedure_defs: Dict[str, Dict[str, Any]],
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    broadcast_ids: Dict[str, str],
) -> Optional["ParsedNode"]:
    # Fast-path: mathop often appears without surrounding parentheses
    math_match = re.match(r"^\[([^\]]+)\] of \((.+)\)$", value)
    if math_match:
        op_token = math_match.group(1).strip()
        if op_token.endswith(" v"):
            op_token = op_token[:-2].strip()
        if op_token in MATH_OPERATORS:
            opcode = "operator_mathop"
            groups = {"OPERATOR": op_token, "NUM": math_match.group(2).strip()}
    else:
        opcode, groups = match_opcode_line(value)
    if not opcode and not (value.startswith("(") and value.endswith(")")):
        # Try matching math/reporters that often omit outer parentheses in inline text
        opcode, groups = match_opcode_line(f"({value})")

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
    if opcode in CONTROL_BLOCKS or opcode.startswith("event_") or opcode == "procedures_definition":
        return None

    # Skip menu-only patterns (no literals) that would greedily swallow any text, e.g. pen menus
    fmt = OPCODE_MAP.get(opcode, "")
    literal_len = sum(len(lit) for lit, _, _, _ in string.Formatter().parse(fmt) if lit)
    if literal_len == 0 or opcode.endswith("_menu") or opcode.startswith("pen_menu"):
        return None

    inputs: Dict[str, Any] = {}
    fields: Dict[str, Any] = {}

    for name, captured in groups.items():
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
) -> Any:
    raw = value.strip()
    inner = strip_wrappers(raw)
    num_val = coerce_number(inner)

    # Treat empty reporter/boolean placeholders (e.g., "<>", "()", "[]") as intentionally missing
    # inputs so we omit them from the block JSON instead of emitting an unusable literal string.
    if raw in {"<>", "[]", "()"} or (inner == "" and raw in {"", "()"}):
        return None

    if "BROADCAST" in input_name:
        bid = broadcast_ids.setdefault(inner, gen_id("broadcast"))
        return [1, [11, inner, bid]]

    if num_val is not None:
        return [1, [4, num_val]]

    if allow_inline:
        inline_node = parse_inline_expression(
            raw,
            procedure_defs,
            local_vars,
            global_vars,
            local_lists,
            global_lists,
            broadcast_ids,
        ) or parse_inline_expression(
            inner,
            procedure_defs,
            local_vars,
            global_vars,
            local_lists,
            global_lists,
            broadcast_ids,
        )
        if inline_node:
            return inline_node

    if inner in local_vars or inner in global_vars:
        vid = resolve_variable_id(inner, local_vars, global_vars)
        return [3, [12, inner, vid], [10, ""]]

    if inner in local_lists or inner in global_lists:
        lid = resolve_list_id(inner, local_lists, global_lists)
        return [3, [13, inner, lid], [10, ""]]

    return [1, [10, inner]]


def resolve_variable_id(name: str, local_vars: Dict[str, str], global_vars: Dict[str, str]) -> str:
    if name in local_vars:
        return local_vars[name]
    if name in global_vars:
        return global_vars[name]
    vid = gen_id("var")
    local_vars[name] = vid
    return vid


def resolve_list_id(name: str, local_lists: Dict[str, str], global_lists: Dict[str, str]) -> str:
    if name in local_lists:
        return local_lists[name]
    if name in global_lists:
        return global_lists[name]
    lid = gen_id("list")
    local_lists[name] = lid
    return lid


def resolve_field_value(
    field_name: str,
    raw_value: str,
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    broadcast_ids: Dict[str, str],
) -> List[Any]:
    value = strip_wrappers(raw_value)
    if field_name == "VARIABLE":
        vid = resolve_variable_id(value, local_vars, global_vars)
        return [value, vid]
    if field_name == "LIST":
        lid = resolve_list_id(value, local_lists, global_lists)
        return [value, lid]
    if field_name == "BROADCAST_OPTION":
        bid = broadcast_ids.setdefault(value, gen_id("broadcast"))
        return [value, bid]
    return [value, None]


def match_opcode_line(line: str) -> Tuple[Optional[str], Dict[str, str]]:
    for pattern, opcode, placeholders in OPCODE_PATTERNS:
        match = pattern.match(line)
        if match:
            groups = {name: match.group(name) for name in placeholders}
            return opcode, groups
    return None, {}


def build_procedure_call_pattern(proccode: str) -> re.Pattern[str]:
    pattern = re.escape(proccode)
    pattern = pattern.replace("%s", r"(.+?)").replace("%b", r"(.+?)")
    return re.compile("^" + pattern + "$")


def parse_line_to_node(
    line: str,
    procedure_defs: Dict[str, Dict[str, Any]],
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    broadcast_ids: Dict[str, str],
) -> Optional[ParsedNode]:
    if line.startswith("define "):
        content = line[len("define "):]
        warp_flag = content.endswith(" #norefresh")
        if warp_flag:
            content = content[: -len(" #norefresh")]

        arg_names = re.findall(r"\((.*?)\)", content)
        base = re.sub(r"\(.*?\)", "%s", content).strip()
        arg_ids = [gen_id("arg") for _ in arg_names]

        info = {
            "proccode": base,
            "arg_names": arg_names,
            "arg_ids": arg_ids,
            "warp": warp_flag,
        }
        info["call_pattern"] = build_procedure_call_pattern(base)
        info["prototype_id"] = gen_id("proc_proto")
        procedure_defs[base] = info

        node = ParsedNode("procedures_definition")
        node.procedure_info = info
        return node

    for info in procedure_defs.values():
        match = info["call_pattern"].match(line)
        if match:
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
            for idx, val in enumerate(match.groups()):
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
                    )
            return node

    opcode, groups = match_opcode_line(line)
    if not opcode:
        return None

    inputs: Dict[str, Any] = {}
    fields: Dict[str, Any] = {}

    for name, value in groups.items():
        if name in OPCODE_FIELDS.get(opcode, set()):
            fields[name] = resolve_field_value(
                name,
                value,
                local_vars,
                global_vars,
                local_lists,
                global_lists,
                broadcast_ids,
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
            )

    return ParsedNode(opcode, inputs=inputs, fields=fields)


def parse_block_list(
    lines: List[Tuple[int, str]],
    idx: int,
    indent: int,
    procedure_defs: Dict[str, Dict[str, Any]],
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    broadcast_ids: Dict[str, str],
) -> Tuple[List[ParsedNode], int, bool]:
    nodes: List[ParsedNode] = []
    hit_else = False

    while idx < len(lines):
        current_indent, text = lines[idx]
        if current_indent < indent:
            break
        if text == "end":
            idx += 1
            if indent == 0:
                continue  # ignore stray top-level end lines
            break
        if text == "else":
            hit_else = True
            idx += 1
            break

        node = parse_line_to_node(
            text,
            procedure_defs,
            local_vars,
            global_vars,
            local_lists,
            global_lists,
            broadcast_ids,
        )

        idx += 1

        if node is None:
            continue

        if node.opcode in CONTROL_BLOCKS:
            children, idx, saw_else = parse_block_list(
                lines,
                idx,
                indent + 1,
                procedure_defs,
                local_vars,
                global_vars,
                local_lists,
                global_lists,
                broadcast_ids,
            )
            node.children = children
            if node.opcode == "control_if_else" and saw_else:
                children2, idx, _ = parse_block_list(
                    lines,
                    idx,
                    indent + 1,
                    procedure_defs,
                    local_vars,
                    global_vars,
                    local_lists,
                    global_lists,
                    broadcast_ids,
                )
                node.children2 = children2

        nodes.append(node)

    return nodes, idx, hit_else


def emit_blocks(
    nodes: List[ParsedNode],
    blocks: Dict[str, Dict[str, Any]],
    parent_id: Optional[str],
    top_level: bool,
    x: int,
    y: int,
) -> Tuple[Optional[str], Optional[str]]:
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

        # Resolve inputs, emitting inline reporter blocks when necessary
        for input_name, raw_val in (node.inputs or {}).items():
            if raw_val is None:
                continue
            if isinstance(raw_val, ParsedNode):
                if raw_val.opcode in {"data_variable", "data_listcontents"} and not raw_val.children and not raw_val.children2:
                    fields = raw_val.fields
                    if raw_val.opcode == "data_variable":
                        name, vid = fields.get("VARIABLE", ["", None])
                        block_entry["inputs"][input_name] = [3, [12, name, vid], [10, ""]]
                    else:
                        name, lid = fields.get("LIST", ["", None])
                        block_entry["inputs"][input_name] = [3, [13, name, lid], [10, ""]]
                else:
                    nested_first, _ = emit_blocks([raw_val], blocks, block_id, False, x, y)
                    if nested_first:
                        block_entry["inputs"][input_name] = [3, nested_first, [10, ""]]
                    else:
                        block_entry["inputs"][input_name] = [1, [10, ""]]
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
                "argumentdefaults": json.dumps(["" for _ in node.procedure_info["arg_names"]]),
                "warp": "true" if node.procedure_info.get("warp") else "false",
            }

            blocks[proto_id] = {
                "opcode": "procedures_prototype",
                "next": None,
                "parent": block_id,
                "inputs": {},
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
                child_first, child_last = emit_blocks(node.children, blocks, block_id, False, x, y)
                if child_first:
                    block_entry.setdefault("inputs", {})["SUBSTACK"] = [2, child_first]
                if child_last:
                    blocks[child_last]["next"] = None
            if node.opcode == "control_if_else" and node.children2:
                child_first2, child_last2 = emit_blocks(node.children2, blocks, block_id, False, x, y)
                if child_first2:
                    block_entry.setdefault("inputs", {})["SUBSTACK2"] = [2, child_first2]
                if child_last2:
                    blocks[child_last2]["next"] = None

        if first_id is None:
            first_id = block_id
        prev_id = block_id

    return first_id, prev_id


def code_to_blocks(
    code_path: str,
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    broadcast_ids: Dict[str, str],
) -> Dict[str, Any]:
    if not code_path or not code_path.strip() or not os.path.exists(code_path):
        return {}
    with open(code_path, "r", encoding="utf-8") as handle:
        content = handle.read()

    scripts = split_scripts(content)
    blocks: Dict[str, Dict[str, Any]] = {}
    procedure_defs: Dict[str, Dict[str, Any]] = {}
    y_pos = 0

    for script in scripts:
        nodes, _, _ = parse_block_list(
            script,
            0,
            0,
            procedure_defs,
            local_vars,
            global_vars,
            local_lists,
            global_lists,
            broadcast_ids,
        )
        emit_blocks(nodes, blocks, None, True, 0, y_pos)
        y_pos += 120

    return blocks
