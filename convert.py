import argparse
import hashlib
import json
import os
import re
import shutil
import string
import zipfile
from itertools import count
from typing import Any, Dict, List, Optional, Tuple

try:  # Optional dependency for accurate image sizing
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Image = None


# Mapping of opcodes to ScratchBlocks format strings
# Keys are opcodes, values are format strings using input names
OPCODE_MAP: Dict[str, str] = {
    # Events
    "event_whenflagclicked": "when green flag clicked",
    "event_whenkeypressed": "when [{KEY_OPTION} v] key pressed",
    "event_whenthisspriteclicked": "when this sprite clicked",
    "event_whenbackdropswitchesto": "when backdrop switches to [{BACKDROP} v]",
    "event_whengreaterthan": "when [{WHENGREATERTHANMENU} v] > {VALUE}",
    "event_whenbroadcastreceived": "when I receive [{BROADCAST_OPTION} v]",
    "event_broadcast": "broadcast {BROADCAST_INPUT}",
    "event_broadcastandwait": "broadcast {BROADCAST_INPUT} and wait",

    # Motion
    "motion_movesteps": "move {STEPS} steps",
    "motion_turnright": "turn right {DEGREES} degrees",
    "motion_turnleft": "turn left {DEGREES} degrees",
    "motion_goto": "go to {TO}",
    "motion_gotoxy": "go to x: {X} y: {Y}",
    "motion_glideto": "glide {SECS} secs to {TO}",
    "motion_glidesecstoxy": "glide {SECS} secs to x: {X} y: {Y}",
    "motion_pointindirection": "point in direction {DIRECTION}",
    "motion_pointtowards": "point towards {TOWARDS}",
    "motion_changexby": "change x by {DX}",
    "motion_setx": "set x to {X}",
    "motion_changeyby": "change y by {DY}",
    "motion_sety": "set y to {Y}",
    "motion_ifonedgebounce": "if on edge, bounce",
    "motion_setrotationstyle": "set rotation style [{STYLE} v]",

    # Looks
    "looks_sayforsecs": "say {MESSAGE} for {SECS} seconds",
    "looks_say": "say {MESSAGE}",
    "looks_thinkforsecs": "think {MESSAGE} for {SECS} seconds",
    "looks_think": "think {MESSAGE}",
    "looks_switchcostumeto": "switch costume to {COSTUME}",
    "looks_nextcostume": "next costume",
    "looks_switchbackdropto": "switch backdrop to {BACKDROP}",
    "looks_nextbackdrop": "next backdrop",
    "looks_changesizeby": "change size by {CHANGE}",
    "looks_setsizeto": "set size to {SIZE} %",
    "looks_changeeffectby": "change [{EFFECT} v] effect by {CHANGE}",
    "looks_seteffectto": "set [{EFFECT} v] effect to {VALUE}",
    "looks_cleargraphiceffects": "clear graphic effects",
    "looks_show": "show",
    "looks_hide": "hide",
    "looks_gotofrontback": "go to [{FRONT_BACK} v] layer",
    "looks_goforwardbackwardlayers": "go [{FORWARD_BACKWARD} v] {NUM} layers",

    # Sound
    "sound_playuntildone": "play sound {SOUND_MENU} until done",
    "sound_play": "start sound {SOUND_MENU}",
    "sound_stopallsounds": "stop all sounds",
    "sound_changeeffectby": "change [{EFFECT} v] effect by {VALUE}",
    "sound_seteffectto": "set [{EFFECT} v] effect to {VALUE}",
    "sound_changevolumeby": "change volume by {VOLUME}",
    "sound_setvolumeto": "set volume to {VOLUME} %",

    # Pen
    "pen_clear": "erase all",
    "pen_stamp": "stamp",
    "pen_penup": "pen up",
    "pen_pendown": "pen down",
    "pen_setpenparamto": "set pen ({COLOR_PARAM} v) to {VALUE}",
    "pen_changepenparamby": "change pen ({COLOR_PARAM} v) by {VALUE}",
    "pen_setpencolortocolor": "set pen color to {COLOR}",
    "pen_changepensizeby": "change pen size by {SIZE}",
    "pen_setpensizeto": "set pen size to {SIZE}",

    # Pen (CamelCase variants found in some files)
    "pen_setPenColorToColor": "set pen color to {COLOR}",
    "pen_setPenSizeTo": "set pen size to {SIZE}",
    "pen_penUp": "pen up",
    "pen_penDown": "pen down",
    "pen_setPenColorParamTo": "set pen ({COLOR_PARAM} v) to {VALUE}",
    "pen_menu_colorParam": "{colorParam}",

    # Sound Menus
    "sound_sounds_menu": "{SOUND_MENU}",

    # Motion Reporters
    "motion_xposition": "(x position)",
    "motion_yposition": "(y position)",
    "motion_direction": "(direction)",

    # Control
    "control_wait": "wait {DURATION} seconds",
    "control_repeat": "repeat {TIMES}",
    "control_forever": "forever",
    "control_if": "if {CONDITION} then",
    "control_if_else": "if {CONDITION} then",
    "control_wait_until": "wait until {CONDITION}",
    "control_repeat_until": "repeat until {CONDITION}",
    "control_stop": "stop [{STOP_OPTION} v]",
    "control_start_as_clone": "when I start as a clone",
    "control_create_clone_of": "create clone of {CLONE_OPTION}",
    "control_delete_this_clone": "delete this clone",

    # Sensing
    "sensing_touchingobject": "<touching {TOUCHINGOBJECTMENU} ?>",
    "sensing_touchingcolor": "<touching color {COLOR} ?>",
    "sensing_coloristouchingcolor": "<color {COLOR} is touching {COLOR2} ?>",
    "sensing_distanceto": "(distance to {DISTANCETOMENU})",
    "sensing_askandwait": "ask {QUESTION} and wait",
    "sensing_answer": "(answer)",
    "sensing_keypressed": "<key [{KEY_OPTION} v] pressed?>",
    "sensing_mousedown": "<mouse down?>",
    "sensing_mousex": "(mouse x)",
    "sensing_mousey": "(mouse y)",
    "sensing_setdragmode": "set drag mode [{DRAG_MODE} v]",
    "sensing_loudness": "(loudness)",
    "sensing_timer": "(timer)",
    "sensing_resettimer": "reset timer",
    "sensing_of": "([{PROPERTY} v] of {OBJECT})",
    "sensing_current": "(current [{CURRENTMENU} v])",
    "sensing_dayssince2000": "(days since 2000)",
    "sensing_username": "(username)",

    # Operators
    "operator_add": "({NUM1} + {NUM2})",
    "operator_subtract": "({NUM1} - {NUM2})",
    "operator_multiply": "({NUM1} * {NUM2})",
    "operator_divide": "({NUM1} / {NUM2})",
    "operator_random": "(pick random {FROM} to {TO})",
    "operator_gt": "<{OPERAND1} > {OPERAND2}>",
    "operator_lt": "<{OPERAND1} < {OPERAND2}>",
    "operator_equals": "<{OPERAND1} = {OPERAND2}>",
    "operator_and": "<{OPERAND1} and {OPERAND2}>",
    "operator_or": "<{OPERAND1} or {OPERAND2}>",
    "operator_not": "<not {OPERAND}>",
    "operator_join": "(join {STRING1} {STRING2})",
    "operator_letter_of": "(letter {LETTER} of {STRING})",
    "operator_length": "(length of {STRING})",
    "operator_contains": "<{STRING1} contains {STRING2} ?>",
    "operator_mod": "({NUM1} mod {NUM2})",
    "operator_round": "(round {NUM})",
    "operator_mathop": "([{OPERATOR} v] of {NUM})",

    # Variables
    "data_variable": "({VARIABLE})",
    "data_setvariableto": "set [{VARIABLE} v] to {VALUE}",
    "data_changevariableby": "change [{VARIABLE} v] by {VALUE}",
    "data_showvariable": "show variable [{VARIABLE} v]",
    "data_hidevariable": "hide variable [{VARIABLE} v]",
    "data_listcontents": "({LIST})",
    "data_addtolist": "add {ITEM} to [{LIST} v]",
    "data_deleteoflist": "delete {INDEX} of [{LIST} v]",
    "data_deletealloflist": "delete all of [{LIST} v]",
    "data_insertatlist": "insert {ITEM} at {INDEX} of [{LIST} v]",
    "data_replaceitemoflist": "replace item {INDEX} of [{LIST} v] with {ITEM}",
    "data_itemoflist": "(item {INDEX} of [{LIST} v])",
    "data_itemnumoflist": "(item # of {ITEM} in [{LIST} v])",
    "data_lengthoflist": "(length of [{LIST} v])",
    "data_listcontainsitem": "<[{LIST} v] contains {ITEM} ?>",
    "data_showlist": "show list [{LIST} v]",
    "data_hidelist": "hide list [{LIST} v]",

    # Custom Blocks (Procedures)
    "argument_reporter_string_number": "({VALUE})",
    "argument_reporter_boolean": "<{VALUE}>",
}

# Placeholders that should be treated as fields (instead of inputs) when rebuilding blocks
OPCODE_FIELDS: Dict[str, set] = {
    "event_whenkeypressed": {"KEY_OPTION"},
    "event_whenbackdropswitchesto": {"BACKDROP"},
    "event_whengreaterthan": {"WHENGREATERTHANMENU"},
    "event_whenbroadcastreceived": {"BROADCAST_OPTION"},
    "control_stop": {"STOP_OPTION"},
    "looks_switchcostumeto": {"COSTUME"},
    "looks_switchbackdropto": {"BACKDROP"},
    "looks_seteffectto": {"EFFECT"},
    "looks_changeeffectby": {"EFFECT"},
    "looks_gotofrontback": {"FRONT_BACK"},
    "looks_goforwardbackwardlayers": {"FORWARD_BACKWARD"},
    "motion_setrotationstyle": {"STYLE"},
    "sound_changeeffectby": {"EFFECT"},
    "sound_seteffectto": {"EFFECT"},
    "sound_play": {"SOUND_MENU"},
    "sound_playuntildone": {"SOUND_MENU"},
    "pen_setpenparamto": {"COLOR_PARAM"},
    "pen_changepenparamby": {"COLOR_PARAM"},
    "pen_setPenColorParamTo": {"COLOR_PARAM"},
    "data_setvariableto": {"VARIABLE"},
    "data_changevariableby": {"VARIABLE"},
    "data_showvariable": {"VARIABLE"},
    "data_hidevariable": {"VARIABLE"},
    "data_addtolist": {"LIST"},
    "data_deleteoflist": {"LIST"},
    "data_deletealloflist": {"LIST"},
    "data_insertatlist": {"LIST"},
    "data_replaceitemoflist": {"LIST"},
    "data_itemoflist": {"LIST"},
    "data_itemnumoflist": {"LIST"},
    "data_lengthoflist": {"LIST"},
    "data_listcontainsitem": {"LIST"},
    "data_showlist": {"LIST"},
    "data_hidelist": {"LIST"},
    "data_variable": {"VARIABLE"},
    "data_listcontents": {"LIST"},
    "operator_mathop": {"OPERATOR"},
}

CONTROL_BLOCKS = {"control_forever", "control_repeat", "control_repeat_until", "control_if", "control_if_else"}

MATH_OPERATORS = {
    "abs",
    "floor",
    "ceiling",
    "sqrt",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "ln",
    "log",
    "e ^",
    "10 ^",
}

# Layout tuning constants for auto-arranging top-level stacks
BLOCK_BASE_WIDTH = 220
BLOCK_BASE_HEIGHT = 40
BLOCK_LABEL_CHAR_WIDTH = 6
STACK_GAP = 12
BRANCH_GAP = 12
CLAUSE_GAP = 16
INDENT_WIDTH = 28
ARRANGE_GAP_X = 80
ARRANGE_GAP_Y = 40
TARGET_RATIO = 0.5
RATIO_WEIGHT = 2.5
# Bracket (C-shaped) blocks have thinner end caps; scale their height to fit.
BRACKET_HEIGHT_SCALE = 1.66


def safe_name(name: str, fallback: str = "item") -> str:
    sanitized = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in (name or ""))
    sanitized = sanitized.strip()
    return sanitized or fallback


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json_file(path: str, data: Any) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=4)


def load_json_file(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


_id_counter = count(1)


def gen_id(prefix: str = "id") -> str:
    return f"{prefix}_{next(_id_counter)}"


def build_opcode_patterns() -> List[Tuple[re.Pattern[str], str, List[str]]]:
    patterns_with_score: List[Tuple[int, int, re.Pattern[str], str, List[str]]] = []
    formatter = string.Formatter()
    for opcode, fmt in OPCODE_MAP.items():
        regex_parts: List[str] = []
        placeholders: List[str] = []
        literal_len = 0
        for literal, field_name, _, _ in formatter.parse(fmt):
            regex_parts.append(re.escape(literal))
            literal_len += len(literal)
            if field_name:
                placeholders.append(field_name)
                regex_parts.append(r"(?P<%s>.+?)" % field_name)
        pattern = re.compile("^" + "".join(regex_parts) + "$")
        patterns_with_score.append((literal_len, len(placeholders), pattern, opcode, placeholders))

    # Sort patterns to prefer those with more literal text (more specific) first, then fewer placeholders
    patterns_with_score.sort(key=lambda item: (-item[0], item[1]))
    return [(pat, op, ph) for _, _, pat, op, ph in patterns_with_score]


OPCODE_PATTERNS = build_opcode_patterns()


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


def _extract_stack_id(input_entry: Any) -> Optional[str]:
    if not input_entry:
        return None
    if isinstance(input_entry, list) and len(input_entry) >= 2 and isinstance(input_entry[1], str):
        return input_entry[1]
    return None


def _estimate_label_width(block: Dict[str, Any]) -> int:
    opcode = block.get("opcode", "")
    fmt = OPCODE_MAP.get(opcode, opcode)
    label_text = re.sub(r"\{[^}]+\}", "", fmt)
    return max(BLOCK_BASE_WIDTH, BLOCK_LABEL_CHAR_WIDTH * len(label_text) + 80)


def _block_size(
    block_id: str,
    blocks: Dict[str, Dict[str, Any]],
    stack_cache: Dict[str, Tuple[int, int]],
    block_cache: Dict[str, Tuple[int, int]],
) -> Tuple[int, int]:
    if block_id in block_cache:
        return block_cache[block_id]

    block = blocks.get(block_id, {})
    width = _estimate_label_width(block)
    height = BLOCK_BASE_HEIGHT

    inputs = block.get("inputs", {}) or {}

    substack_id = _extract_stack_id(inputs.get("SUBSTACK") or inputs.get("substack"))
    if substack_id:
        child_w, child_h = _stack_size(substack_id, blocks, stack_cache, block_cache)
        width = max(width, child_w + INDENT_WIDTH)
        height += BRANCH_GAP + child_h

    substack2_id = _extract_stack_id(inputs.get("SUBSTACK2") or inputs.get("substack2"))
    if substack2_id:
        child_w2, child_h2 = _stack_size(substack2_id, blocks, stack_cache, block_cache)
        width = max(width, child_w2 + INDENT_WIDTH)
        height += CLAUSE_GAP + child_h2

    if block.get("opcode") in CONTROL_BLOCKS:
        height = int(height * BRACKET_HEIGHT_SCALE)

    block_cache[block_id] = (width, height)
    return width, height


def _stack_size(
    start_id: str,
    blocks: Dict[str, Dict[str, Any]],
    stack_cache: Dict[str, Tuple[int, int]],
    block_cache: Dict[str, Tuple[int, int]],
) -> Tuple[int, int]:
    if start_id in stack_cache:
        return stack_cache[start_id]

    total_height = 0
    max_width = 0
    current = start_id
    visited: set = set()

    while current and current not in visited:
        visited.add(current)
        block_width, block_height = _block_size(current, blocks, stack_cache, block_cache)
        total_height += block_height
        next_id = blocks.get(current, {}).get("next")
        if next_id:
            total_height += STACK_GAP
        max_width = max(max_width, block_width)
        current = next_id

    stack_cache[start_id] = (max_width, total_height)
    return max_width, total_height


def auto_arrange_top_blocks(blocks: Dict[str, Dict[str, Any]]) -> None:
    top_blocks = [bid for bid, blk in blocks.items() if blk.get("topLevel")]
    if not top_blocks:
        return

    block_cache: Dict[str, Tuple[int, int]] = {}
    stack_cache: Dict[str, Tuple[int, int]] = {}
    sizes: List[Tuple[str, int, int, int]] = []

    for order, bid in enumerate(top_blocks):
        width, height = _stack_size(bid, blocks, stack_cache, block_cache)
        sizes.append((bid, width, height, order))

    best_layout: Optional[Tuple[float, List[List[Tuple[str, int, int, int]]], List[int], List[int], int, int]] = None
    max_cols = max(1, min(len(sizes), 5))
    script_gap = ARRANGE_GAP_Y * 3
    script_gap_x = ARRANGE_GAP_X * 3

    for cols in range(1, max_cols + 1):
        columns: List[List[Tuple[str, int, int, int]]] = [[] for _ in range(cols)]
        col_heights = [0 for _ in range(cols)]

        for entry in sorted(sizes, key=lambda item: item[2], reverse=True):
            bid, width, height, order = entry
            target_col = min(range(cols), key=lambda idx: col_heights[idx])
            if columns[target_col]:
                col_heights[target_col] += script_gap
            col_heights[target_col] += height
            columns[target_col].append((bid, width, height, order))

        col_widths = [max((item[1] for item in col), default=0) for col in columns]
        total_width = sum(col_widths) + script_gap_x * (cols - 1)
        total_height = max(col_heights) if col_heights else 0
        ratio = total_width / total_height if total_height else 1.0
        area = total_width * total_height
        score = area * (1 + RATIO_WEIGHT * abs(ratio - TARGET_RATIO))

        if best_layout is None or score < best_layout[0]:
            best_layout = (score, columns, col_widths, col_heights, total_width, total_height)

    if not best_layout:
        return

    _, chosen_columns, col_widths, col_heights, total_width, total_height = best_layout

    # Normalize positions into a reasonable viewport
    # Avoid vertically squashing tall layouts; overlapping stacks were caused by
    # compressing everything into a 600px column height. Keep a constant scale
    # so gaps stay roughly in line with real block sizes.
    y_scale = 1.0
    x_offset = 40
    y_offset = 40

    x = x_offset
    for col_width, col_height, column in zip(col_widths, col_heights, chosen_columns):
        y = y_offset
        for bid, _, height, order in sorted(column, key=lambda item: item[3]):
            blk = blocks.get(bid, {})
            blk["x"] = x
            blk["y"] = int(y)
            y += (height + script_gap) * y_scale
        x += col_width + script_gap_x


def clear_block_positions(blocks: Dict[str, Dict[str, Any]]) -> None:
    """Remove x/y coordinates so the editor can place stacks itself."""
    for blk in blocks.values():
        blk.pop("x", None)
        blk.pop("y", None)


def code_to_blocks(
    code_path: str,
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    broadcast_ids: Dict[str, str],
) -> Dict[str, Any]:
    if not os.path.exists(code_path):
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


def build_variables_payload(entries: List[Dict[str, Any]]) -> Tuple[Dict[str, List[Any]], Dict[str, str]]:
    var_dict: Dict[str, List[Any]] = {}
    name_to_id: Dict[str, str] = {}
    for entry in entries:
        name = entry.get("name", "variable")
        value = entry.get("value", 0)
        vid = gen_id("var")
        name_to_id[name] = vid
        payload: List[Any] = [name, value]
        if entry.get("cloud"):
            payload.append(True)
        var_dict[vid] = payload
    return var_dict, name_to_id


def build_lists_payload(entries: List[Dict[str, Any]]) -> Tuple[Dict[str, List[Any]], Dict[str, str]]:
    list_dict: Dict[str, List[Any]] = {}
    name_to_id: Dict[str, str] = {}
    for entry in entries:
        name = entry.get("name", "list")
        value = entry.get("value", [])
        lid = gen_id("list")
        name_to_id[name] = lid
        list_dict[lid] = [name, value]
    return list_dict, name_to_id


def probe_image_size(path: str, ext: str) -> Optional[Tuple[float, float]]:
    ext = ext.lower()

    if ext in {"png", "jpg", "jpeg", "gif", "bmp", "webp"} and Image is not None:
        try:
            with Image.open(path) as img:
                w, h = img.size
                return float(w), float(h)
        except Exception:  # pragma: no cover - best effort
            return None

    if ext == "svg":
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                content = handle.read(2000)
            width_match = re.search(r"width=\"([0-9.]+)", content)
            height_match = re.search(r"height=\"([0-9.]+)", content)
            if width_match and height_match:
                return float(width_match.group(1)), float(height_match.group(1))
            viewbox_match = re.search(r"viewBox=\"[0-9.]+ [0-9.]+ ([0-9.]+) ([0-9.]+)\"", content)
            if viewbox_match:
                return float(viewbox_match.group(1)), float(viewbox_match.group(2))
        except Exception:  # pragma: no cover - best effort
            return None

    return None


def cleaned_asset_name(filename: str) -> str:
    base = os.path.splitext(os.path.basename(filename))[0]
    if "_" in base and base.split("_", 1)[0].isdigit():
        return base.split("_", 1)[1]
    return base


def prepare_costumes(asset_dir: str) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    costumes: List[Dict[str, Any]] = []
    files: List[Tuple[str, str]] = []

    if not os.path.exists(asset_dir):
        return costumes, files

    for fname in sorted(os.listdir(asset_dir)):
        path = os.path.join(asset_dir, fname)
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            data = handle.read()
        asset_id = hashlib.md5(data).hexdigest()
        ext = os.path.splitext(fname)[1].lower().lstrip(".")
        md5ext = f"{asset_id}.{ext}" if ext else asset_id

        size = probe_image_size(path, ext)
        center_x = size[0] / 2 if size else 0
        center_y = size[1] / 2 if size else 0

        bitmap_res = 1 if ext == "svg" else 2

        costumes.append(
            {
                "name": cleaned_asset_name(fname),
                "dataFormat": ext,
                "assetId": asset_id,
                "md5ext": md5ext,
                "bitmapResolution": bitmap_res,
                "rotationCenterX": center_x,
                "rotationCenterY": center_y,
            }
        )
        files.append((path, md5ext))
    return costumes, files


def prepare_sounds(asset_dir: str) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    sounds: List[Dict[str, Any]] = []
    files: List[Tuple[str, str]] = []

    if not os.path.exists(asset_dir):
        return sounds, files

    for fname in sorted(os.listdir(asset_dir)):
        path = os.path.join(asset_dir, fname)
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            data = handle.read()
        asset_id = hashlib.md5(data).hexdigest()
        ext = os.path.splitext(fname)[1].lower().lstrip(".")
        md5ext = f"{asset_id}.{ext}" if ext else asset_id
        sound_entry = {
            "name": cleaned_asset_name(fname),
            "assetId": asset_id,
            "dataFormat": ext,
            "rate": 0,
            "sampleCount": 0,
            "md5ext": md5ext,
        }
        sounds.append(sound_entry)
        files.append((path, md5ext))
    return sounds, files


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
    except KeyError as exc:  # pragma: no cover - defensive logging
        code = f"{format_str} (Missing arg: {exc})"
    except Exception as exc:  # pragma: no cover - defensive logging
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


def convert_variables_dict(variables: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for _, payload in variables.items():
        if isinstance(payload, list) and len(payload) >= 2:
            name, value = payload[0], payload[1]
            entry: Dict[str, Any] = {"name": name, "value": value}
            if len(payload) >= 3 and payload[2] is True:
                entry["cloud"] = True
            result.append(entry)
    return result


def convert_lists_dict(lists: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for _, payload in lists.items():
        if isinstance(payload, list) and len(payload) >= 2:
            name, value = payload[0], payload[1]
            result.append({"name": name, "value": value})
    return result


def write_variables_file(path: str, target: Dict[str, Any]) -> None:
    payload = {
        "variables": convert_variables_dict(target.get("variables", {})),
        "lists": convert_lists_dict(target.get("lists", {})),
    }
    write_json_file(path, payload)


def collect_broadcasts(targets: List[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    for target in targets:
        for _, name in target.get("broadcasts", {}).items():
            if name not in names:
                names.append(name)
    return names


def write_events_file(path: str, broadcasts: List[str]) -> None:
    write_json_file(path, {"broadcasts": broadcasts})


def build_miscdata(target: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "position": {
            "x": target.get("x", 0),
            "y": target.get("y", 0),
        },
        "size": target.get("size", 100),
        "direction": target.get("direction", 90),
        "visible": target.get("visible", True),
        "rotationStyle": target.get("rotationStyle", "all around"),
        "currentCostume": target.get("currentCostume", 0),
        "draggable": target.get("draggable", False),
        "volume": target.get("volume", 100),
        "layer": target.get("layerOrder", 0),
    }


def copy_costumes(target: Dict[str, Any], archive: zipfile.ZipFile, assets_dir: str) -> None:
    ensure_dir(assets_dir)
    for idx, costume in enumerate(target.get("costumes", [])):
        md5ext = costume.get("md5ext")
        if not md5ext:
            continue
        if md5ext not in archive.namelist():
            print(f"Warning: costume asset {md5ext} not found in archive")
            continue

        ext = os.path.splitext(md5ext)[1] or f".{costume.get('dataFormat', '')}"
        name = safe_name(costume.get("name", "costume"), "costume")
        dest_name = f"{idx:02d}_{name}{ext}"
        dest_path = os.path.join(assets_dir, dest_name)

        with archive.open(md5ext) as src, open(dest_path, "wb") as dst:
            shutil.copyfileobj(src, dst)


def copy_sounds(target: Dict[str, Any], archive: zipfile.ZipFile, sounds_dir: str) -> None:
    ensure_dir(sounds_dir)

    if not target.get("sounds"):
        return

    for idx, sound in enumerate(target.get("sounds", [])):
        md5ext = sound.get("md5ext")
        if not md5ext:
            continue
        if md5ext not in archive.namelist():
            print(f"Warning: sound asset {md5ext} not found in archive")
            continue

        ext = os.path.splitext(md5ext)[1] or f".{sound.get('dataFormat', '')}"
        name = safe_name(sound.get("name", "sound"), "sound")
        dest_name = f"sound_{idx:02d}_{name}{ext}"
        dest_path = os.path.join(sounds_dir, dest_name)

        with archive.open(md5ext) as src, open(dest_path, "wb") as dst:
            shutil.copyfileobj(src, dst)


def write_target(target: Dict[str, Any], archive: zipfile.ZipFile, output_root: str) -> None:
    is_stage = target.get("isStage", False)
    target_name = target.get("name", "Sprite")

    if is_stage:
        target_dir = os.path.join(output_root, "Stage")
    else:
        sprites_root = os.path.join(output_root, "Sprites")
        ensure_dir(sprites_root)
        target_dir = os.path.join(sprites_root, safe_name(target_name, "Sprite"))

    ensure_dir(target_dir)

    code_path = os.path.join(target_dir, "code.scratchblocks")
    code_text = generate_target_code(target)
    with open(code_path, "w", encoding="utf-8") as handle:
        handle.write(code_text)

    if not is_stage:
        write_variables_file(os.path.join(target_dir, "variables.json"), target)
        write_json_file(os.path.join(target_dir, "miscdata.json"), build_miscdata(target))

    assets_dir = os.path.join(target_dir, "Assets")
    sounds_dir = os.path.join(target_dir, "Sounds")
    copy_costumes(target, archive, assets_dir)
    copy_sounds(target, archive, sounds_dir)


def convert_project(sb3_path: str, output_dir: str, clean: bool = True) -> None:
    if not os.path.exists(sb3_path):
        print(f"Error: {sb3_path} not found")
        return

    with zipfile.ZipFile(sb3_path, "r") as archive:
        if "project.json" not in archive.namelist():
            print("Error: project.json not found in the archive.")
            return

        with archive.open("project.json") as handle:
            project = json.load(handle)

        if clean and os.path.exists(output_dir):
            shutil.rmtree(output_dir)

        ensure_dir(output_dir)
        ensure_dir(os.path.join(output_dir, "Sprites"))
        ensure_dir(os.path.join(output_dir, "Stage"))

        targets = project.get("targets", [])

        stage_target = next((t for t in targets if t.get("isStage")), None)
        if stage_target:
            write_variables_file(os.path.join(output_dir, "variables.json"), stage_target)
        else:
            write_json_file(os.path.join(output_dir, "variables.json"), {"variables": [], "lists": []})

        write_events_file(os.path.join(output_dir, "events.json"), collect_broadcasts(targets))

        for target in targets:
            write_target(target, archive, output_dir)

    print(f"Successfully converted {sb3_path} to {output_dir}")


def convert_folder_to_sb3(input_dir: str, output_path: str) -> None:
    if not os.path.isdir(input_dir):
        print(f"Error: {input_dir} not found or not a directory")
        return

    events_path = os.path.join(input_dir, "events.json")
    variables_path = os.path.join(input_dir, "variables.json")

    events_payload = load_json_file(events_path, {"broadcasts": []})
    broadcast_ids: Dict[str, str] = {name: gen_id("broadcast") for name in events_payload.get("broadcasts", [])}

    root_vars_payload = load_json_file(variables_path, {"variables": [], "lists": []})
    stage_vars, stage_var_ids = build_variables_payload(root_vars_payload.get("variables", []))
    stage_lists, stage_list_ids = build_lists_payload(root_vars_payload.get("lists", []))

    assets_to_pack: List[Tuple[str, str]] = []

    stage_dir = os.path.join(input_dir, "Stage")
    stage_blocks = code_to_blocks(
        os.path.join(stage_dir, "code.scratchblocks"),
        stage_var_ids,
        {},
        stage_list_ids,
        {},
        broadcast_ids,
    )
    auto_arrange_top_blocks(stage_blocks)
    stage_costumes, stage_assets = prepare_costumes(os.path.join(stage_dir, "Assets"))
    stage_sounds, stage_sound_assets = prepare_sounds(os.path.join(stage_dir, "Sounds"))
    assets_to_pack.extend(stage_assets)
    assets_to_pack.extend(stage_sound_assets)

    stage_target = {
        "isStage": True,
        "name": "Stage",
        "variables": stage_vars,
        "lists": stage_lists,
        "broadcasts": {bid: name for name, bid in broadcast_ids.items()},
        "blocks": stage_blocks,
        "comments": {},
        "currentCostume": 0,
        "costumes": stage_costumes,
        "sounds": stage_sounds,
        "volume": 100,
        "layerOrder": 0,
        "tempo": 60,
        "videoTransparency": 50,
        "videoState": "on",
        "textToSpeechLanguage": None,
    }

    targets: List[Dict[str, Any]] = [stage_target]

    sprites_root = os.path.join(input_dir, "Sprites")
    if os.path.exists(sprites_root):
        for idx, sprite_name in enumerate(sorted(os.listdir(sprites_root)), start=1):
            sprite_dir = os.path.join(sprites_root, sprite_name)
            if not os.path.isdir(sprite_dir):
                continue

            sprite_vars_payload = load_json_file(os.path.join(sprite_dir, "variables.json"), {"variables": [], "lists": []})
            sprite_vars, sprite_var_ids = build_variables_payload(sprite_vars_payload.get("variables", []))
            sprite_lists, sprite_list_ids = build_lists_payload(sprite_vars_payload.get("lists", []))

            misc = load_json_file(
                os.path.join(sprite_dir, "miscdata.json"),
                {
                    "position": {"x": 0, "y": 0},
                    "size": 100,
                    "direction": 90,
                    "visible": True,
                    "rotationStyle": "all around",
                    "currentCostume": 0,
                    "draggable": False,
                    "volume": 100,
                    "layer": idx,
                },
            )

            sprite_blocks = code_to_blocks(
                os.path.join(sprite_dir, "code.scratchblocks"),
                sprite_var_ids,
                stage_var_ids,
                sprite_list_ids,
                stage_list_ids,
                broadcast_ids,
            )
            auto_arrange_top_blocks(sprite_blocks)

            sprite_costumes, sprite_assets = prepare_costumes(os.path.join(sprite_dir, "Assets"))
            sprite_sounds, sprite_sound_assets = prepare_sounds(os.path.join(sprite_dir, "Sounds"))
            assets_to_pack.extend(sprite_assets)
            assets_to_pack.extend(sprite_sound_assets)

            current_costume = misc.get("currentCostume", 0)
            if current_costume >= len(sprite_costumes):
                current_costume = 0

            layer_order = misc.get("layer", idx)

            targets.append(
                {
                    "isStage": False,
                    "name": sprite_name,
                    "variables": sprite_vars,
                    "lists": sprite_lists,
                    "broadcasts": {},
                    "blocks": sprite_blocks,
                    "comments": {},
                    "currentCostume": current_costume,
                    "costumes": sprite_costumes,
                    "sounds": sprite_sounds,
                    "volume": misc.get("volume", 100),
                    "layerOrder": layer_order,
                    "visible": misc.get("visible", True),
                    "x": misc.get("position", {}).get("x", 0),
                    "y": misc.get("position", {}).get("y", 0),
                    "size": misc.get("size", 100),
                    "direction": misc.get("direction", 90),
                    "draggable": misc.get("draggable", False),
                    "rotationStyle": misc.get("rotationStyle", "all around"),
                }
            )

    project = {
        "targets": targets,
        "monitors": [],
        "extensions": [],
        "meta": {
            "semver": "3.0.0",
            "vm": "0.2.0",
            "agent": "",
            "platform": {"name":"TurboWarp","url":"https://turbowarp.org/"},
        },
    }

    ensure_dir(os.path.dirname(output_path) or ".")
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(project, indent=4))
        seen_assets = set()
        for src, dest in assets_to_pack:
            if dest in seen_assets:
                continue
            seen_assets.add(dest)
            archive.write(src, dest)

    print(f"Successfully converted {input_dir} to {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a Scratch .sb3 project into a folder of scratchblocks and assets.")
    parser.add_argument("input", help="Path to the .sb3 project file")
    parser.add_argument("--output-dir", default="Project", help="Output directory for the converted project")
    parser.add_argument("--no-clean", action="store_true", help="Do not remove the output directory before writing")
    parser.add_argument("--to-sb3", action="store_true", help="Convert from a project folder back to a .sb3 archive")
    parser.add_argument("--sb3-output", default="output.sb3", help="Output .sb3 path when using --to-sb3")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.to_sb3:
        convert_folder_to_sb3(args.input, args.sb3_output)
    else:
        convert_project(args.input, args.output_dir, clean=not args.no_clean)


if __name__ == "__main__":
    main()

