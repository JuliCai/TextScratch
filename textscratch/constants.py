"""Constants used throughout the text-to-blocks conversion."""

from typing import Any, Dict, List, Tuple

# Binary operators with their opcodes and input names
BINARY_OPERATOR_TOKENS: List[Tuple[str, str, str, str]] = [
    (" + ", "operator_add", "NUM1", "NUM2"),
    (" - ", "operator_subtract", "NUM1", "NUM2"),
    (" * ", "operator_multiply", "NUM1", "NUM2"),
    (" / ", "operator_divide", "NUM1", "NUM2"),
]

# Opcodes that represent menu shadow blocks
MENU_SHADOW_OPCODES = {
    "looks_costume",
    "looks_backdrops",
    "sound_sounds_menu",
    "pen_menu_colorParam",
    "sensing_keyoptions",
    "sensing_distancetomenu",
    "sensing_of_object_menu",
    "motion_goto_menu",
    "motion_glideto_menu",
    "motion_pointtowards_menu",
    "control_create_clone_of_menu",
    "sensing_touchingobjectmenu",
}

# Map input names to their shadow menu opcodes and field names
MENU_SHADOW_FOR_INPUT: Dict[str, Tuple[str, str]] = {
    "COSTUME": ("looks_costume", "COSTUME"),
    "BACKDROP": ("looks_backdrops", "BACKDROP"),
    "SOUND_MENU": ("sound_sounds_menu", "SOUND_MENU"),
    "OBJECT": ("sensing_of_object_menu", "OBJECT"),
}
