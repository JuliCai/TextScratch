"""Field resolution and menu handling utilities."""

from typing import Any, Dict, List, Optional

from .diagnostics import DiagnosticContext
from .parsed_node import ParsedNode
from .string_utils import strip_wrappers
from .utils import gen_id


def resolve_variable_id(
    name: str,
    local_vars: Dict[str, str],
    global_vars: Dict[str, str],
    diag_ctx: Optional[DiagnosticContext] = None,
    line_number: Optional[int] = None,
) -> str:
    """Get or create a variable ID for the given name.
    
    If the variable is not found, creates a new ID and optionally logs a warning.
    """
    if name in local_vars:
        return local_vars[name]
    if name in global_vars:
        return global_vars[name]
    # Variable not found - create it but warn
    if diag_ctx is not None:
        diag_ctx.warning(f"Undefined variable '{name}' (auto-created)", line_number)
    vid = gen_id("var")
    local_vars[name] = vid
    return vid


def resolve_list_id(
    name: str,
    local_lists: Dict[str, str],
    global_lists: Dict[str, str],
    diag_ctx: Optional[DiagnosticContext] = None,
    line_number: Optional[int] = None,
) -> str:
    """Get or create a list ID for the given name.
    
    If the list is not found, creates a new ID and optionally logs a warning.
    """
    if name in local_lists:
        return local_lists[name]
    if name in global_lists:
        return global_lists[name]
    # List not found - create it but warn
    if diag_ctx is not None:
        diag_ctx.warning(f"Undefined list '{name}' (auto-created)", line_number)
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
    diag_ctx: Optional[DiagnosticContext] = None,
    line_number: Optional[int] = None,
) -> List[Any]:
    """Resolve a field value, handling variables, lists, and broadcasts."""
    value = strip_wrappers(raw_value)
    if field_name == "VARIABLE":
        vid = resolve_variable_id(value, local_vars, global_vars, diag_ctx, line_number)
        return [value, vid]
    if field_name == "LIST":
        lid = resolve_list_id(value, local_lists, global_lists, diag_ctx, line_number)
        return [value, lid]
    if field_name == "BROADCAST_OPTION":
        bid = broadcast_ids.setdefault(value, gen_id("broadcast"))
        return [value, bid]
    return [value, None]


def build_key_option_input(raw_value: str) -> ParsedNode:
    """Build a key option menu input node."""
    menu = ParsedNode("sensing_keyoptions")
    menu.fields = {"KEY_OPTION": [strip_wrappers(raw_value), None]}
    menu.mutation = {}
    return menu


def build_menu_shadow_input(opcode: str, field_name: str, raw_value: str) -> ParsedNode:
    """Build a menu shadow input node."""
    cleaned = strip_wrappers(raw_value)
    if cleaned.endswith(" v"):
        cleaned = cleaned[: -len(" v")].strip()
    cleaned = normalize_menu_field_value(opcode, field_name, cleaned)
    menu = ParsedNode(opcode)
    menu.fields = {field_name: [cleaned, None]}
    menu.mutation = {}
    return menu


def normalize_touching_menu_to_sb3(value: str) -> str:
    """Normalize touching menu values to SB3 format."""
    normalized = value.strip()
    lowered = normalized.lower().replace("-", " ").replace("_", " ").strip()
    if lowered in {"mouse pointer", "mouse"}:
        return "_mouse_"
    if lowered == "edge":
        return "_edge_"
    return normalized


def normalize_distance_menu_to_sb3(value: str) -> str:
    """Normalize distance menu values to SB3 format."""
    normalized = value.strip()
    lowered = normalized.lower().replace("-", " ").replace("_", " ").strip()
    if lowered in {"mouse pointer", "mouse"}:
        return "_mouse_"
    if lowered == "myself":
        return "_myself_"
    return normalized


def normalize_goto_menu_to_sb3(value: str) -> str:
    """Normalize goto/glideto menu values to SB3 format."""
    normalized = value.strip()
    lowered = normalized.lower().replace("-", " ").replace("_", " ").strip()
    if lowered in {"random position", "random"}:
        return "_random_"
    if lowered in {"mouse pointer", "mouse"}:
        return "_mouse_"
    return normalized


def normalize_pointtowards_menu_to_sb3(value: str) -> str:
    """Normalize pointtowards menu values to SB3 format."""
    normalized = value.strip()
    lowered = normalized.lower().replace("-", " ").replace("_", " ").strip()
    if lowered in {"mouse pointer", "mouse"}:
        return "_mouse_"
    if lowered in {"random direction", "random"}:
        return "_random_"
    return normalized


def normalize_of_object_menu_to_sb3(value: str) -> str:
    """Normalize sensing_of object menu values to SB3 format."""
    normalized = value.strip()
    lowered = normalized.lower().replace("-", " ").replace("_", " ").strip()
    if lowered == "stage":
        return "_stage_"
    return normalized


def normalize_clone_menu_to_sb3(value: str) -> str:
    """Normalize clone menu values to SB3 format."""
    normalized = value.strip()
    lowered = normalized.lower().replace("-", " ").replace("_", " ").strip()
    if lowered == "myself":
        return "_myself_"
    return normalized


def normalize_menu_field_value(opcode: str, field_name: str, value: str) -> str:
    """Normalize menu field values based on opcode and field name."""
    if opcode == "sensing_touchingobjectmenu" and field_name == "TOUCHINGOBJECTMENU":
        return normalize_touching_menu_to_sb3(value)
    if opcode == "sensing_distancetomenu" and field_name == "DISTANCETOMENU":
        return normalize_distance_menu_to_sb3(value)
    if opcode in ("motion_goto_menu", "motion_glideto_menu") and field_name == "TO":
        return normalize_goto_menu_to_sb3(value)
    if opcode == "motion_pointtowards_menu" and field_name == "TOWARDS":
        return normalize_pointtowards_menu_to_sb3(value)
    if opcode == "sensing_of_object_menu" and field_name == "OBJECT":
        return normalize_of_object_menu_to_sb3(value)
    if opcode == "control_create_clone_of_menu" and field_name == "CLONE_OPTION":
        return normalize_clone_menu_to_sb3(value)
    return value


def default_empty_input(input_name: str) -> List[Any]:
    """Return the default empty input value based on input name."""
    upper = input_name.upper()
    if "COLOR" in upper:
        return [1, [9, "#000000"]]
    numeric_tokens = [
        "NUM",
        "OPERAND",
        "VALUE",
        "X",
        "Y",
        "DX",
        "DY",
        "INDEX",
        "LETTER",
        "FROM",
        "TO",
        "TIMES",
        "DURATION",
        "SECS",
        "ANGLE",
        "DEGREES",
        "STEP",
        "SIZE",
        "CHANGE",
    ]
    if any(token in upper for token in numeric_tokens):
        return [1, [4, ""]]
    return [1, [10, ""]]
